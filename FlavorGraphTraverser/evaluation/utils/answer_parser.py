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
