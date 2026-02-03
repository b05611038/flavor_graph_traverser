"""
Tests for QuestionEvaluator

Tests the turn-based evaluation loop and metrics collection.
"""

import pytest
from unittest.mock import Mock, MagicMock
from FlavorGraphTraverser.evaluation import (
    QuestionEvaluator,
    EvaluationResult,
    EvaluationMetrics,
    BaseClient,
    Message,
    LLMResponse,
    UsageStats,
    GraphToolExecutor,
)


@pytest.fixture
def mock_client():
    """Create a mock LLM client."""
    client = Mock(spec=BaseClient)
    client.model = "test-model"
    return client


@pytest.fixture
def mock_executor():
    """Create a mock GraphToolExecutor."""
    executor = Mock(spec=GraphToolExecutor)
    return executor


@pytest.fixture
def sample_question():
    """Sample question for testing."""
    return {
        "id": "TEST_001",
        "text": "Which root category does 'chocolate' belong to?",
        "options": {
            "A": "fruity",
            "B": "floral",
            "C": "nutty/cocoa",
            "D": "spices"
        },
        "correct_answer": "C"
    }


@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "conditions": {
            "C0": {
                "name": "Zero-shot",
                "tools_enabled": False,
                "max_reasoning_calls": 0,
                "system_prompt": "You are an expert."
            },
            "C2": {
                "name": "Tools only",
                "tools_enabled": True,
                "max_reasoning_calls": 3,
                "system_prompt": "You are an expert with tools."
            }
        },
        "common": {
            "temperature": 0,
            "max_output_tokens": 1024,
            "answer_format": "Therefore, I select (X)"
        }
    }


class TestQuestionEvaluatorInit:
    """Test evaluator initialization."""

    def test_init_with_config(self, mock_client, mock_executor, mock_config):
        """Test initialization with provided config."""
        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C0", config=mock_config
        )

        assert evaluator.client == mock_client
        assert evaluator.executor == mock_executor
        assert evaluator.condition == "C0"
        assert evaluator.tools is None  # C0 has no tools

    def test_init_tools_enabled(self, mock_client, mock_executor, mock_config):
        """Test initialization with tools enabled."""
        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C2", config=mock_config
        )

        assert evaluator.tools is not None  # C2 has tools
        assert len(evaluator.tools) == 3  # validate, get_parent, get_children


class TestDirectEvaluation:
    """Test direct evaluation (C0, C1)."""

    def test_c0_correct_answer(self, mock_client, mock_executor, sample_question, mock_config):
        """Test C0 with correct answer."""
        # Mock response with correct answer
        mock_client.query.return_value = LLMResponse(
            content="Therefore, I select (C)",
            usage=UsageStats(input_tokens=50, output_tokens=10, total_tokens=60)
        )

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C0", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.model_answer == "C"
        assert result.is_correct is True
        assert result.status == "success"
        assert result.metrics.total_turns == 1
        assert result.metrics.total_tokens == 60
        assert result.metrics.reasoning_calls == 0
        assert result.metrics.validation_calls == 0

    def test_c0_wrong_answer(self, mock_client, mock_executor, sample_question, mock_config):
        """Test C0 with wrong answer."""
        mock_client.query.return_value = LLMResponse(
            content="Therefore, I select (A)",
            usage=UsageStats(input_tokens=50, output_tokens=10, total_tokens=60)
        )

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C0", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.model_answer == "A"
        assert result.is_correct is False
        assert result.status == "success"

    def test_c0_parse_error(self, mock_client, mock_executor, sample_question, mock_config):
        """Test C0 with unparseable answer."""
        mock_client.query.return_value = LLMResponse(
            content="I don't know the answer.",
            usage=UsageStats(input_tokens=50, output_tokens=10, total_tokens=60)
        )

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C0", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.model_answer is None
        assert result.is_correct is False
        assert result.status == "parse_error"

    def test_c0_api_error(self, mock_client, mock_executor, sample_question, mock_config):
        """Test C0 with API error."""
        mock_client.query.side_effect = Exception("API timeout")

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C0", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.model_answer is None
        assert result.is_correct is False
        assert result.status == "api_error"
        assert len(result.errors) > 0


class TestToolEvaluation:
    """Test tool-augmented evaluation (C2, C3)."""

    def test_c2_answer_immediately(self, mock_client, mock_executor, sample_question, mock_config):
        """Test C2 when model answers immediately without tools."""
        mock_client.query.return_value = LLMResponse(
            content="Therefore, I select (C)",
            usage=UsageStats(input_tokens=50, output_tokens=10, total_tokens=60)
        )

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C2", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.model_answer == "C"
        assert result.is_correct is True
        assert result.status == "success"
        assert result.metrics.reasoning_calls == 0
        assert result.metrics.validation_calls == 0
        assert result.metrics.answered_early is True  # Answered before max calls

    def test_c2_uses_validation(self, mock_client, mock_executor, sample_question, mock_config):
        """Test C2 with validation tool call."""
        # First response: validate tool call
        # Second response: answer
        mock_client.query.side_effect = [
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "function": {"name": "validate_descriptors", "arguments": '{"descriptors": ["chocolate"]}'}
                }],
                usage=UsageStats(input_tokens=50, output_tokens=20, total_tokens=70)
            ),
            LLMResponse(
                content="Therefore, I select (C)",
                usage=UsageStats(input_tokens=60, output_tokens=10, total_tokens=70)
            )
        ]

        mock_executor.execute.return_value = {"valid": {"chocolate": True}, "invalid": []}

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C2", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.model_answer == "C"
        assert result.is_correct is True
        assert result.metrics.validation_calls == 1
        assert result.metrics.reasoning_calls == 0  # validate doesn't count
        assert result.metrics.total_turns == 2

    def test_c2_uses_reasoning_tools(self, mock_client, mock_executor, sample_question, mock_config):
        """Test C2 with reasoning tool calls."""
        mock_client.query.side_effect = [
            # Turn 1: get_parent
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "function": {"name": "get_parent", "arguments": '{"descriptor": "chocolate"}'}
                }],
                usage=UsageStats(input_tokens=50, output_tokens=20, total_tokens=70)
            ),
            # Turn 2: get_parent again
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_2",
                    "function": {"name": "get_parent", "arguments": '{"descriptor": "cocoa"}'}
                }],
                usage=UsageStats(input_tokens=60, output_tokens=20, total_tokens=80)
            ),
            # Turn 3: answer
            LLMResponse(
                content="Therefore, I select (C)",
                usage=UsageStats(input_tokens=70, output_tokens=10, total_tokens=80)
            )
        ]

        mock_executor.execute.side_effect = [
            {"parent": "cocoa"},
            {"parent": "nutty/cocoa"}
        ]

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C2", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.model_answer == "C"
        assert result.is_correct is True
        assert result.metrics.reasoning_calls == 2
        assert result.metrics.validation_calls == 0
        assert result.metrics.total_turns == 3
        assert result.metrics.answered_early is True  # Answered at call 2, max is 3

    def test_c2_max_reasoning_calls(self, mock_client, mock_executor, sample_question, mock_config):
        """Test C2 hitting max reasoning calls limit."""
        # 3 reasoning calls, then forced answer
        mock_client.query.side_effect = [
            # Turn 1
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "function": {"name": "get_parent", "arguments": '{"descriptor": "chocolate"}'}
                }],
                usage=UsageStats(input_tokens=50, output_tokens=20, total_tokens=70)
            ),
            # Turn 2
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_2",
                    "function": {"name": "get_children", "arguments": '{"descriptor": "cocoa"}'}
                }],
                usage=UsageStats(input_tokens=60, output_tokens=20, total_tokens=80)
            ),
            # Turn 3
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_3",
                    "function": {"name": "get_parent", "arguments": '{"descriptor": "cocoa"}'}
                }],
                usage=UsageStats(input_tokens=70, output_tokens=20, total_tokens=90)
            ),
            # Forced answer turn
            LLMResponse(
                content="Therefore, I select (C)",
                usage=UsageStats(input_tokens=80, output_tokens=10, total_tokens=90)
            )
        ]

        mock_executor.execute.side_effect = [
            {"parent": "cocoa"},
            {"children": ["chocolate", "dark chocolate"]},
            {"parent": "nutty/cocoa"}
        ]

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C2", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.model_answer == "C"
        assert result.is_correct is True
        assert result.metrics.reasoning_calls == 3
        assert result.metrics.total_turns == 4  # 3 tool turns + 1 forced answer
        assert result.metrics.answered_early is False  # Forced after max calls

    def test_c2_tool_error(self, mock_client, mock_executor, sample_question, mock_config):
        """Test C2 with tool execution error."""
        mock_client.query.side_effect = [
            # Tool call
            LLMResponse(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "function": {"name": "get_parent", "arguments": '{"descriptor": "invalid"}'}
                }],
                usage=UsageStats(input_tokens=50, output_tokens=20, total_tokens=70)
            ),
            # Answer after error
            LLMResponse(
                content="Therefore, I select (A)",
                usage=UsageStats(input_tokens=60, output_tokens=10, total_tokens=70)
            )
        ]

        mock_executor.execute.side_effect = Exception("Descriptor not found")

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C2", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.model_answer == "A"
        assert result.is_correct is False
        assert result.status == "tool_error"
        assert len(result.errors) > 0
        assert result.errors[0]["type"] == "tool_error"

    def test_c2_no_answer_no_tools(self, mock_client, mock_executor, sample_question, mock_config):
        """Test C2 when model gives neither answer nor tool calls."""
        mock_client.query.return_value = LLMResponse(
            content="I cannot answer this question.",
            usage=UsageStats(input_tokens=50, output_tokens=10, total_tokens=60)
        )

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C2", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.model_answer is None
        assert result.is_correct is False
        assert result.status == "parse_error"


class TestMetricsCollection:
    """Test metrics collection."""

    def test_token_counting(self, mock_client, mock_executor, sample_question, mock_config):
        """Test token counting across multiple turns."""
        mock_client.query.side_effect = [
            LLMResponse(
                content="",
                tool_calls=[{"id": "1", "function": {"name": "get_parent", "arguments": '{}'}}],
                usage=UsageStats(input_tokens=50, output_tokens=20, total_tokens=70)
            ),
            LLMResponse(
                content="Therefore, I select (C)",
                usage=UsageStats(input_tokens=60, output_tokens=10, total_tokens=70)
            )
        ]

        mock_executor.execute.return_value = {"parent": "cocoa"}

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C2", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.metrics.input_tokens == 110  # 50 + 60
        assert result.metrics.output_tokens == 30  # 20 + 10
        assert result.metrics.total_tokens == 140  # 70 + 70

    def test_latency_measurement(self, mock_client, mock_executor, sample_question, mock_config):
        """Test latency measurement."""
        import time

        def slow_query(*args, **kwargs):
            time.sleep(0.01)  # 10ms delay
            return LLMResponse(
                content="Therefore, I select (C)",
                usage=UsageStats(input_tokens=50, output_tokens=10, total_tokens=60)
            )

        mock_client.query.side_effect = slow_query

        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C0", config=mock_config
        )
        result = evaluator.evaluate(sample_question)

        assert result.metrics.latency_ms >= 10  # At least 10ms
        assert result.metrics.latency_ms < 10000  # Should be under 10 seconds


class TestQuestionFormatting:
    """Test question formatting."""

    def test_format_question(self, mock_client, mock_executor, sample_question, mock_config):
        """Test question formatting creates correct messages."""
        evaluator = QuestionEvaluator(
            mock_client, mock_executor, "C0", config=mock_config
        )

        messages = evaluator._format_question(sample_question)

        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert "chocolate" in messages[1].content
        assert "(A)" in messages[1].content
        assert "(B)" in messages[1].content
        assert "(C)" in messages[1].content
        assert "(D)" in messages[1].content
