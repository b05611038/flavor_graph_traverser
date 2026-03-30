"""
Answer Parser

Extracts answers (A/B/C/D) from LLM responses using regex patterns.
Follows priority order from Implementation Guide.

Also provides parse_judge_score() for extracting 0-5 scores from judge responses.
"""

import re
from typing import List, Optional
from dataclasses import dataclass, field


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


def parse_answer(response_text: str) -> AnswerParseResult:
    """
    Extract answer from LLM response using priority patterns.
    
    Priority order (from Implementation Guide):
    1. r'I select \\(([A-D])\\)'           # Primary
    2. r'answer is \\(([A-D])\\)'          # Fallback 1
    3. Last standalone (X) in response   # Fallback 2
    4. Last standalone letter A/B/C/D    # Fallback 3
    5. None found -> parse_error          # Mark as incorrect
    
    Args:
        response_text: LLM response text
        
    Returns:
        AnswerParseResult with extracted answer and metadata
        
    Example:
        >>> result = parse_answer("I think... Therefore, I select (B).")
        >>> result.answer
        'B'
        >>> result.pattern_matched
        'I select (X)'
    """
    if not response_text:
        return AnswerParseResult(None, None, None)
    
    patterns = [
        (r"I select \(([A-D])\)", "I select (X)"),
        (r"answer is \(([A-D])\)", "answer is (X)"),
        (r"\(([A-D])\)", "Last (X)"),
        (r"\b([A-D])\b(?!.*\b[A-D]\b)", "Last letter"),
    ]
    
    for pattern, pattern_name in patterns:
        match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
        if match:
            answer = match.group(1).upper()
            matched_text = match.group(0)
            return AnswerParseResult(
                answer=answer,
                pattern_matched=pattern_name,
                matched_text=matched_text
            )
    
    # No pattern matched
    return AnswerParseResult(None, "No match", None)


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

    patterns = [
        (r"(?:^|\n)\s*score[:\s]+([0-5])\b", "Score: N"),
        (r"final score[:\s]+([0-5])\b", "final score: N"),
        (r"\b([0-5])\s*/\s*5\b", "N/5"),
        (r"\b([0-5])\s+out\s+of\s+5\b", "N out of 5"),
        (r"I (?:give|assign|rate)[^\n]{0,40}\b([0-5])\b(?!\s*/)", "I give/assign N"),
        (r"\b([0-5])\b(?!.*\b[0-5]\b)", "last digit"),
    ]

    for pattern, pattern_name in patterns:
        match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
        if match:
            score = int(match.group(1))
            return JudgeScoreResult(
                score=score,
                pattern_matched=pattern_name,
                matched_text=match.group(0).strip()
            )

    return JudgeScoreResult(None, "No match", None)


@dataclass
class MultiSelectParseResult:
    """Result of multi-select answer parsing (A1, A4 questions)."""
    answers: Optional[List[str]]  # ["A", "C"] or [] for NONE, or None if parse failed
    pattern_matched: Optional[str]
    matched_text: Optional[str]

    @property
    def success(self) -> bool:
        """Whether parsing was successful (including valid empty selection)."""
        return self.answers is not None


def parse_multiselect_answer(response_text: str) -> MultiSelectParseResult:
    """
    Extract multi-select answer from LLM response (A1, A4 questions).

    Priority order:
    1. "I select (A, C, E)"  -> ["A", "C", "E"]
    2. "I select (NONE)"     -> []
    3. "answer is (A, C)"    -> ["A", "C"]
    4. "answer is (NONE)"    -> []

    Args:
        response_text: LLM response text

    Returns:
        MultiSelectParseResult with list of selected letters (may be empty for NONE)

    Example:
        >>> result = parse_multiselect_answer("Therefore, I select (A, C).")
        >>> result.answers
        ['A', 'C']
        >>> parse_multiselect_answer("Therefore, I select (NONE).").answers
        []
    """
    if not response_text:
        return MultiSelectParseResult(None, None, None)

    def _extract_letters(inner: str, pattern_name: str, matched: str) -> Optional[MultiSelectParseResult]:
        inner = inner.strip()
        if inner.upper() == "NONE":
            return MultiSelectParseResult([], pattern_name + " (NONE)", matched)
        letters = [t.strip().upper() for t in re.split(r"[,\s]+", inner) if t.strip()]
        letters = [l for l in letters if re.match(r"^[A-F]$", l)]
        if letters:
            return MultiSelectParseResult(letters, pattern_name, matched)
        return None

    patterns = [
        (r"I select \(([^)]+)\)", "I select (...)"),
        (r"answer is \(([^)]+)\)", "answer is (...)"),
    ]

    for pattern, pattern_name in patterns:
        match = re.search(pattern, response_text, re.IGNORECASE)
        if match:
            result = _extract_letters(match.group(1), pattern_name, match.group(0))
            if result is not None:
                return result

    return MultiSelectParseResult(None, "No match", None)


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
    if status in ("parse_error", "api_error", "tool_error", "no_judge"):
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
