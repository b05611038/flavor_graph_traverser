"""
Answer Parser — Multi-Layer Pipeline

Extracts answers (A/B/C/D) from LLM responses using a three-layer pipeline:
  Layer 1: Canonical patterns — exact instructed format
  Layer 2: Model-specific normalization → re-run Layer 1
  Layer 3: Constrained fallback — last sentences with signal words only

Also provides parse_judge_score() for extracting 0-5 scores from judge responses.
"""

import re
from typing import Callable, List, Optional, TypeVar, Union
from dataclasses import dataclass, field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AnswerParseResult:
    """Result of answer parsing."""
    answer: Optional[str]  # "A", "B", "C", "D", or None
    pattern_matched: Optional[str]  # Which pattern matched
    matched_text: Optional[str]  # The actual matched text

    @property
    def success(self) -> bool:
        """Whether parsing was successful."""
        return self.answer is not None


@dataclass
class JudgeScoreResult:
    """Result of judge score parsing."""
    score: Optional[int]  # 0-5, or None if not parsed
    pattern_matched: Optional[str]  # Which pattern matched
    matched_text: Optional[str]  # The actual matched text

    @property
    def success(self) -> bool:
        """Whether parsing was successful."""
        return self.score is not None


@dataclass
class MultiSelectParseResult:
    """Result of multi-select answer parsing (A1, A4, A5 questions)."""
    answers: Optional[List[str]]  # ["A", "C"] or [] for NONE, or None if parse failed
    pattern_matched: Optional[str]
    matched_text: Optional[str]

    @property
    def success(self) -> bool:
        """Whether parsing was successful (including valid empty selection)."""
        return self.answers is not None


# ---------------------------------------------------------------------------
# Layer 2 — Model-specific text normalizers
# ---------------------------------------------------------------------------

def _strip_bold_markdown(text: str) -> str:
    """Remove bold markdown wrapping around parenthesized answers.
    **(B)** → (B), **(A, C)** → (A, C)"""
    return re.sub(r"\*\*\(([^)]+)\)\*\*", r"(\1)", text)


def _close_truncated_parens(text: str) -> str:
    """Close truncated parentheses at end of string.
    'I select (D' at end → 'I select (D)'"""
    return re.sub(r"\(([A-F](?:\s*,\s*[A-F])*)\s*$", r"(\1)", text)
    # Also handle truncated NONE
    # (applied separately since the first sub may have already matched)


def _close_truncated_parens_full(text: str) -> str:
    """Close truncated parentheses including NONE and multi-select content.
    'I select (D' → 'I select (D)', 'I select (NONE' → 'I select (NONE)'"""
    return re.sub(r"\(([^)\n]{1,30})\s*$", r"(\1)", text)


# Registry: model-name substring → list of normalizer functions
_MODEL_NORMALIZERS = {
    "mistral": [_strip_bold_markdown],
    "gpt-oss": [_close_truncated_parens_full],
}


def _apply_model_normalizers(text: str, model_id: Optional[str]) -> str:
    """Apply all matching model-specific normalizers to text."""
    if not model_id:
        return text
    model_lower = model_id.lower()
    for key, normalizers in _MODEL_NORMALIZERS.items():
        if key in model_lower:
            for fn in normalizers:
                text = fn(text)
    return text


# ---------------------------------------------------------------------------
# Layer 3 — Constrained fallback helpers
# ---------------------------------------------------------------------------

_ANSWER_SIGNAL_WORDS = re.compile(
    r"\b(select|answer|choose|option|go\s+with|pick|therefore|conclude|chosen|choice)\b",
    re.IGNORECASE,
)


def _extract_tail_sentences(text: str, n: int = 3) -> str:
    """Extract the last N sentences from text."""
    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?\n])\s+", text.strip())
    return " ".join(sentences[-n:]) if sentences else text


# ---------------------------------------------------------------------------
# Layer 1 — Canonical patterns (single-choice)
# ---------------------------------------------------------------------------

_SINGLE_CANONICAL = [
    (r"I select \(([A-D])\)", "I select (X)"),
    (r"answer is \(([A-D])\)", "answer is (X)"),
    (r"I select ([A-D])\b", "I select X"),
    (r"answer is ([A-D])\b", "answer is X"),
]


def _canonical_single(text: str) -> AnswerParseResult:
    """Layer 1: Try canonical single-choice patterns."""
    for pattern, name in _SINGLE_CANONICAL:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return AnswerParseResult(
                answer=match.group(1).upper(),
                pattern_matched=name,
                matched_text=match.group(0),
            )
    return AnswerParseResult(None, None, None)


# ---------------------------------------------------------------------------
# Layer 1 — Canonical patterns (multi-select)
# ---------------------------------------------------------------------------

_MULTI_CANONICAL = [
    (r"I select \(([^)]+)\)", "I select (...)"),
    (r"I select ([A-F](?:\s*,\s*[A-F])*|NONE)\b", "I select ..."),
    (r"answer is \(([^)]+)\)", "answer is (...)"),
    (r"answer is ([A-F](?:\s*,\s*[A-F])*|NONE)\b", "answer is ..."),
]


def _extract_letters(inner: str, pattern_name: str, matched: str) -> Optional[MultiSelectParseResult]:
    """Parse inner content of a multi-select match into a list of letters."""
    inner = inner.strip()
    if inner.upper() == "NONE":
        return MultiSelectParseResult([], pattern_name + " (NONE)", matched)
    tokens = [t.strip().upper() for t in re.split(r"[,\s]+", inner) if t.strip()]
    has_none = any(t == "NONE" for t in tokens)
    letters = [t for t in tokens if re.match(r"^[A-F]$", t)]
    if has_none and not letters:
        return MultiSelectParseResult([], pattern_name + " (NONE)", matched)
    if letters:
        return MultiSelectParseResult(letters, pattern_name, matched)
    return None


def _canonical_multi(text: str) -> MultiSelectParseResult:
    """Layer 1: Try canonical multi-select patterns."""
    for pattern, name in _MULTI_CANONICAL:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result = _extract_letters(match.group(1), name, match.group(0))
            if result is not None:
                return result
    return MultiSelectParseResult(None, None, None)


# ---------------------------------------------------------------------------
# Layer 3 — Constrained fallback (single-choice)
# ---------------------------------------------------------------------------

def _fallback_single(text: str) -> AnswerParseResult:
    """Layer 3: Constrained fallback for single-choice.
    Only searches the last few sentences, and only if a signal word is present."""
    tail = _extract_tail_sentences(text, n=3)
    if not _ANSWER_SIGNAL_WORDS.search(tail):
        return AnswerParseResult(None, "No match", None)

    # Try (X) first, then standalone letter — last occurrence in tail
    for pattern, name in [
        (r"\(([A-D])\)", "Last (X) [low-confidence]"),
        (r"\b([A-D])\b", "Last letter [low-confidence]"),
    ]:
        matches = list(re.finditer(pattern, tail, re.IGNORECASE | re.DOTALL))
        if matches:
            last = matches[-1]
            return AnswerParseResult(
                answer=last.group(1).upper(),
                pattern_matched=name,
                matched_text=last.group(0),
            )
    return AnswerParseResult(None, "No match", None)


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

def parse_answer(
    response_text: str,
    thinking_content: Optional[str] = None,
    model_id: Optional[str] = None,
) -> AnswerParseResult:
    """
    Extract single-choice answer from LLM response using a three-layer pipeline.

    Layer 1: Canonical patterns on response_text
    Layer 2: Model-specific normalization → re-run Layer 1; then try thinking_content
    Layer 3: Constrained fallback on response_text (signal-word gated, tail only)

    Args:
        response_text: LLM response text (visible content)
        thinking_content: Extended thinking content (for reasoning models like kimi)
        model_id: Model identifier (e.g. "moonshotai/kimi-k2.5") for model-specific rules

    Returns:
        AnswerParseResult with extracted answer and metadata

    Example:
        >>> parse_answer("Therefore, I select (B).").answer
        'B'
        >>> parse_answer("I select **(B)**", model_id="mistral-medium-3.1").answer
        'B'
    """
    if not response_text and not thinking_content:
        return AnswerParseResult(None, None, None)

    text = response_text or ""

    # Layer 1: canonical patterns on raw response
    result = _canonical_single(text)
    if result.success:
        return result

    # Layer 2a: model-specific normalization → re-run canonical
    normalized = _apply_model_normalizers(text, model_id)
    if normalized != text:
        result = _canonical_single(normalized)
        if result.success:
            result.pattern_matched += " [normalized]"
            return result

    # Layer 2b: try thinking_content with canonical patterns
    if thinking_content:
        result = _canonical_single(thinking_content)
        if result.success:
            result.pattern_matched += " [thinking]"
            return result

    # Layer 3: constrained fallback on original text
    return _fallback_single(text)


def parse_multiselect_answer(
    response_text: str,
    thinking_content: Optional[str] = None,
    model_id: Optional[str] = None,
) -> MultiSelectParseResult:
    """
    Extract multi-select answer from LLM response (A1, A4, A5 questions)
    using a three-layer pipeline.

    Layer 1: Canonical patterns on response_text
    Layer 2: Model-specific normalization → re-run Layer 1; then try thinking_content
    Layer 3: No fallback for multi-select (too risky) → parse_error

    Args:
        response_text: LLM response text
        thinking_content: Extended thinking content (for reasoning models)
        model_id: Model identifier for model-specific rules

    Returns:
        MultiSelectParseResult with list of selected letters

    Example:
        >>> parse_multiselect_answer("Therefore, I select (A, C).").answers
        ['A', 'C']
    """
    if not response_text and not thinking_content:
        return MultiSelectParseResult(None, None, None)

    text = response_text or ""

    # Layer 1: canonical patterns on raw response
    result = _canonical_multi(text)
    if result.success:
        return result

    # Layer 2a: model-specific normalization → re-run canonical
    normalized = _apply_model_normalizers(text, model_id)
    if normalized != text:
        result = _canonical_multi(normalized)
        if result.success:
            result.pattern_matched += " [normalized]"
            return result

    # Layer 2b: try thinking_content with canonical patterns
    if thinking_content:
        result = _canonical_multi(thinking_content)
        if result.success:
            result.pattern_matched += " [thinking]"
            return result

    # No fallback for multi-select — return parse error
    return MultiSelectParseResult(None, "No match", None)


# ---------------------------------------------------------------------------
# Judge score parser (unchanged — judges follow format reliably)
# ---------------------------------------------------------------------------

def parse_judge_score(response_text: str) -> JudgeScoreResult:
    """
    Extract 0-5 score from judge LLM response.

    Priority order:
    1. "Score: N"                   # Primary (structured output requested)
    2. "Final score: N"             # Alternate header
    3. "I give/assign/rate ... N"   # Narrative
    4. "N/5"                        # Fraction format
    5. Last standalone 0-5 digit    # Fallback

    Args:
        response_text: Judge LLM response text

    Returns:
        JudgeScoreResult with extracted score and metadata

    Example:
        >>> result = parse_judge_score("The response shows good reasoning. Score: 4")
        >>> result.score
        4
    """
    if not response_text:
        return JudgeScoreResult(None, None, None)

    exact_patterns = [
        (r"(?:^|\n)\s*score[:\s]+([0-5])\b", "Score: N"),
        (r"final score[:\s]+([0-5])\b", "final score: N"),
        (r"\b([0-5])\s*/\s*5\b", "N/5"),
        (r"\b([0-5])\s+out\s+of\s+5\b", "N out of 5"),
        (r"I (?:give|assign|rate)[^\n]{0,40}\b([0-5])\b(?!\s*/)", "I give/assign N"),
    ]
    fallback_patterns = [
        (r"\b([0-5])\b", "last digit"),
    ]

    for pattern, pattern_name in exact_patterns:
        match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
        if match:
            score = int(match.group(1))
            return JudgeScoreResult(
                score=score,
                pattern_matched=pattern_name,
                matched_text=match.group(0).strip()
            )

    for pattern, pattern_name in fallback_patterns:
        matches = list(re.finditer(pattern, response_text, re.IGNORECASE | re.DOTALL))
        if matches:
            last_match = matches[-1]
            score = int(last_match.group(1))
            return JudgeScoreResult(
                score=score,
                pattern_matched=pattern_name,
                matched_text=last_match.group(0).strip()
            )

    return JudgeScoreResult(None, "No match", None)


# ---------------------------------------------------------------------------
# Score computation (unchanged)
# ---------------------------------------------------------------------------

def compute_question_score(
    model_answer,
    correct_answer,
    is_correct: bool,
    judge_score: int = None,
    status: str = "success",
) -> float:
    """
    Compute a 0–1 score for a single question.

    Scoring rules:
    - Single-choice (A2, A3, E1, E2, E3): 0 or 1 (binary)
    - Multi-select (A1, A4, A5): F1 between predicted and correct sets
    - F-category: judge_score / 5 (continuous 0–1)
    - parse_error / api_error: 0

    Args:
        model_answer: Model's answer (str, list, or None)
        correct_answer: Ground truth (str or list)
        is_correct: Binary correctness (used for single-choice)
        judge_score: Judge score 0–5 for F-category (None for A/E)
        status: Evaluation status

    Returns:
        Float score in [0, 1]

    Examples:
        >>> compute_question_score("B", "B", True)
        1.0
        >>> compute_question_score(["A", "C"], ["B", "C", "D"], False)
        0.4
        >>> compute_question_score(None, None, False, judge_score=4)
        0.8
    """
    # F-category: use judge score directly
    if judge_score is not None:
        return judge_score / 5.0

    # Error states get 0
    if status in ("parse_error", "api_error", "tool_error", "no_judge", "judge_parse_error"):
        return 0.0

    # Multi-select: F1 score
    if isinstance(correct_answer, list):
        if model_answer is None or not isinstance(model_answer, list):
            return 0.0
        pred = set(model_answer)
        gold = set(correct_answer)
        if not gold and not pred:
            return 1.0  # both empty = correct
        if not gold or not pred:
            return 0.0
        tp = len(pred & gold)
        precision = tp / len(pred) if pred else 0.0
        recall = tp / len(gold) if gold else 0.0
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    # Single-choice: binary
    return 1.0 if is_correct else 0.0
