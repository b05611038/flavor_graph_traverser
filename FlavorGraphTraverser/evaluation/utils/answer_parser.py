"""
Answer Parser

Extracts answers (A/B/C/D) from LLM responses using regex patterns.
Follows priority order from Implementation Guide.
"""

import re
from typing import Optional
from dataclasses import dataclass


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


def parse_answer(response_text: str) -> AnswerParseResult:
    """
    Extract answer from LLM response using priority patterns.
    
    Priority order (from Implementation Guide):
    1. r"I select \(([A-D])\)"           # Primary
    2. r"answer is \(([A-D])\)"          # Fallback 1
    3. Last standalone (X) in response   # Fallback 2
    4. Last standalone letter A/B/C/D    # Fallback 3
    5. None found → parse_error          # Mark as incorrect
    
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
