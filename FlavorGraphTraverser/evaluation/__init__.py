"""
Evaluation Module

Benchmarking infrastructure for tool-augmented LLM inference.
"""

from .evaluator import QuestionEvaluator, EvaluationResult, EvaluationMetrics
from .client import create_client, BaseClient, Message, LLMResponse, UsageStats
from .tools import GraphToolExecutor, get_tool_definitions
from .utils import (
    parse_answer, AnswerParseResult,
    parse_judge_score, JudgeScoreResult,
    parse_multiselect_answer, MultiSelectParseResult,
    load_conditions_config,
    normalize_response,
)
from .batch_runner import BatchRunner, BatchConfig
from .judge import LLMJudge, JudgeResult

__all__ = [
    # Evaluator
    "QuestionEvaluator",
    "EvaluationResult",
    "EvaluationMetrics",

    # Batch Runner
    "BatchRunner",
    "BatchConfig",

    # Client
    "create_client",
    "BaseClient",
    "Message",
    "LLMResponse",
    "UsageStats",

    # Tools
    "GraphToolExecutor",
    "get_tool_definitions",

    # Utils
    "parse_answer",
    "AnswerParseResult",
    "parse_judge_score",
    "JudgeScoreResult",
    "parse_multiselect_answer",
    "MultiSelectParseResult",
    "load_conditions_config",
    "normalize_response",

    # Judge
    "LLMJudge",
    "JudgeResult",
]
