"""
LLM Judge

Evaluates open-ended F-category responses using an LLM judge.
The judge receives the question, model response, and scoring rubric,
then returns a 0-5 score.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..client.base import BaseClient, Message
from ..utils.answer_parser import parse_judge_score, JudgeScoreResult
from prompts import load_prompt


JUDGE_SYSTEM_PROMPT = load_prompt("judge_system")


@dataclass
class JudgeResult:
    """Result of LLM judge evaluation."""
    score: Optional[int]       # 0-5, or None if parsing failed
    judge_response: str        # Raw judge response text
    parse_result: JudgeScoreResult
    status: str                # "success", "parse_error", "api_error"
    error: Optional[str] = None


class LLMJudge:
    """
    Evaluates F-category open-ended responses using an LLM judge.

    The judge receives:
    - The original question text
    - The model's response
    - The scoring rubric (0-5) from question metadata
    - Optional judge instructions

    Example:
        >>> judge_client = create_client("openrouter", "anthropic/claude-opus-4.6")
        >>> judge = LLMJudge(judge_client)
        >>> result = judge.evaluate(question, model_response)
        >>> result.score  # 0-5
    """

    def __init__(self, client: BaseClient, temperature: float = 0.0, max_tokens: int = 1024):
        """
        Initialize judge.

        Args:
            client: LLM client to use as judge
            temperature: Sampling temperature (default 0 for determinism)
            max_tokens: Max tokens for judge response
        """
        self.client = client
        self.temperature = temperature
        self.max_tokens = max_tokens

    def evaluate(self, question: Dict[str, Any], model_response: str) -> JudgeResult:
        """
        Evaluate a model response for an F-category question.

        Args:
            question: Question dict (must have "text" and "evaluation.judging_notes")
            model_response: The model's raw response text to evaluate

        Returns:
            JudgeResult with score and metadata
        """
        try:
            prompt = self._build_prompt(question, model_response)
            messages = [
                Message(role="system", content=JUDGE_SYSTEM_PROMPT),
                Message(role="user", content=prompt),
            ]

            response = self.client.query(
                messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            judge_text = response.content or ""
            parse_result = parse_judge_score(judge_text)

            if parse_result.success:
                return JudgeResult(
                    score=parse_result.score,
                    judge_response=judge_text,
                    parse_result=parse_result,
                    status="success",
                )
            else:
                return JudgeResult(
                    score=None,
                    judge_response=judge_text,
                    parse_result=parse_result,
                    status="parse_error",
                )

        except Exception as e:
            return JudgeResult(
                score=None,
                judge_response="",
                parse_result=JudgeScoreResult(None, None, None),
                status="api_error",
                error=str(e),
            )

    def _build_prompt(self, question: Dict[str, Any], model_response: str) -> str:
        """Build the judge evaluation prompt."""
        question_text = question.get("text", "")
        evaluation = question.get("evaluation", {})
        judging_notes = evaluation.get("judging_notes", {})

        what_to_evaluate = judging_notes.get("what_to_evaluate", "")
        scoring_rubric = judging_notes.get("scoring_rubric", {})
        judge_instructions = judging_notes.get("judge_instructions", "")

        parts = []

        parts.append("## Question\n" + question_text)
        parts.append("## Response to Evaluate\n" + (model_response or "(no response)"))

        if what_to_evaluate:
            parts.append("## What to Evaluate\n" + what_to_evaluate)

        if scoring_rubric:
            rubric_lines = ["## Scoring Rubric (0–5)"]
            for score_key in sorted(scoring_rubric.keys(), key=lambda x: int(x), reverse=True):
                rubric_lines.append(f"[{score_key}] {scoring_rubric[score_key]}")
            parts.append("\n".join(rubric_lines))

        if judge_instructions:
            parts.append("## Judge Instructions\n" + judge_instructions)

        parts.append(load_prompt("judge_closing"))

        return "\n\n".join(parts)
