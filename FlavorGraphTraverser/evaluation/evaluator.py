"""
Question Evaluator

Evaluates a single question under a specific condition.
Implements the turn-based evaluation loop from Implementation Guide.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from .client import BaseClient, Message, LLMResponse
from .tools import GraphToolExecutor, get_tool_definitions, TOOL_VALIDATE, TOOL_GET_PARENT, TOOL_GET_CHILDREN
from .utils import parse_answer, AnswerParseResult, load_conditions_config


@dataclass
class EvaluationMetrics:
    """Metrics collected during evaluation."""
    reasoning_calls: int = 0
    validation_calls: int = 0
    total_turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int = 0
    answered_early: bool = False  # Did model answer before max reasoning calls?
    

@dataclass
class EvaluationResult:
    """Result of evaluating a single question."""
    question_id: str
    model: str
    condition: str
    
    # Question data
    question_text: str
    options: Dict[str, str]
    correct_answer: str
    
    # Result
    model_answer: Optional[str]
    is_correct: bool
    status: str  # "success", "parse_error", "api_error", "refusal", "tool_error"
    
    # Metrics
    metrics: EvaluationMetrics
    
    # Debug info
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    parse_result: Optional[AnswerParseResult] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""


class QuestionEvaluator:
    """
    Evaluates a single question under a specific condition.
    
    Implements turn-based evaluation loop with tool call tracking.
    
    Example:
        >>> client = create_client("openrouter", "anthropic/claude-sonnet-4.5")
        >>> executor = GraphToolExecutor(graph)
        >>> evaluator = QuestionEvaluator(client, executor, "C2")
        >>> result = evaluator.evaluate(question)
    """
    
    def __init__(
        self,
        client: BaseClient,
        executor: GraphToolExecutor,
        condition: str,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize evaluator.
        
        Args:
            client: LLM client instance
            executor: GraphToolExecutor instance
            condition: Condition name ("C0", "C1", "C2", "C3")
            config: Optional config dict (loads from YAML if None)
        """
        self.client = client
        self.executor = executor
        self.condition = condition
        
        # Load config
        if config is None:
            config = load_conditions_config()
        
        self.config = config
        self.condition_config = config["conditions"][condition]
        self.common_config = config["common"]
        
        # Get tools if enabled
        self.tools = get_tool_definitions() if self.condition_config["tools_enabled"] else None
        
    def evaluate(self, question: Dict[str, Any]) -> EvaluationResult:
        """
        Evaluate a single question.
        
        Args:
            question: Question dict with keys: id, text, options, correct_answer
            
        Returns:
            EvaluationResult with answer, correctness, and metrics
        """
        start_time = time.time()
        metrics = EvaluationMetrics()
        errors = []
        
        try:
            # Format question
            messages = self._format_question(question)
            conversation_history = [self._message_to_dict(m) for m in messages]
            
            # Run evaluation based on condition
            if self.condition_config["tools_enabled"]:
                # Tool-augmented evaluation (C2, C3)
                model_answer, parse_result, metrics, errors = self._evaluate_with_tools(
                    messages, question, metrics
                )
            else:
                # Direct prompting (C0, C1)
                model_answer, parse_result, metrics, errors = self._evaluate_direct(
                    messages, metrics
                )
            
            # Determine status
            if errors:
                # Check error types
                status = "api_error" if any(e.get("type") == "api_error" for e in errors) else "tool_error"
            elif model_answer is None:
                status = "parse_error"
            else:
                status = "success"
            
            # Calculate correctness
            is_correct = (model_answer == question.get("correct_answer")) if model_answer else False
            
            # Calculate latency
            metrics.latency_ms = int((time.time() - start_time) * 1000)
            
            return EvaluationResult(
                question_id=question.get("id", "unknown"),
                model=self.client.model,
                condition=self.condition,
                question_text=question.get("text", ""),
                options=question.get("options", {}),
                correct_answer=question.get("correct_answer", ""),
                model_answer=model_answer,
                is_correct=is_correct,
                status=status,
                metrics=metrics,
                conversation_history=conversation_history,
                parse_result=parse_result,
                errors=errors,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
            
        except Exception as e:
            # Unexpected error
            return EvaluationResult(
                question_id=question.get("id", "unknown"),
                model=self.client.model,
                condition=self.condition,
                question_text=question.get("text", ""),
                options=question.get("options", {}),
                correct_answer=question.get("correct_answer", ""),
                model_answer=None,
                is_correct=False,
                status="api_error",
                metrics=metrics,
                errors=[{"type": "unexpected_error", "message": str(e)}],
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
    
    def _format_question(self, question: Dict[str, Any]) -> List[Message]:
        """Format question into initial messages."""
        # System message
        system_prompt = self.condition_config["system_prompt"]
        messages = [Message(role="system", content=system_prompt)]
        
        # User message with question
        question_text = question.get("text", "")
        options = question.get("options", {})
        
        # Format options
        options_text = "\n".join([f"({key}) {value}" for key, value in sorted(options.items())])

        # Add answer format instruction (dynamic based on number of options)
        option_keys = sorted(options.keys())
        if len(option_keys) == 0:
            # Open-ended question (e.g., F_flavor_description)
            answer_format = "Provide your answer in a clear, detailed response."
        elif len(option_keys) == 1:
            options_list = option_keys[0]
            answer_format = f'When providing your final answer, use this exact format:\n"Therefore, I select ({options_list})".'
        elif len(option_keys) == 2:
            options_list = f"{option_keys[0]} or {option_keys[1]}"
            answer_format = f'When providing your final answer, use this exact format:\n"Therefore, I select (X)" where X is {options_list}.'
        elif len(option_keys) == 3:
            options_list = f"{option_keys[0]}, {option_keys[1]}, or {option_keys[2]}"
            answer_format = f'When providing your final answer, use this exact format:\n"Therefore, I select (X)" where X is {options_list}.'
        else:
            # For 4+ options: A, B, C, or D
            options_list = ", ".join(option_keys[:-1]) + f", or {option_keys[-1]}"
            answer_format = f'When providing your final answer, use this exact format:\n"Therefore, I select (X)" where X is {options_list}.'

        user_message = f"{question_text}\n\n{options_text}\n\n{answer_format}"
        messages.append(Message(role="user", content=user_message))
        
        return messages
    
    def _evaluate_direct(
        self,
        messages: List[Message],
        metrics: EvaluationMetrics
    ) -> Tuple[Optional[str], AnswerParseResult, EvaluationMetrics, List[Dict]]:
        """Evaluate with direct prompting (C0, C1 - no tools)."""
        errors = []
        
        try:
            # Single turn
            response = self.client.query(
                messages,
                temperature=self.common_config["temperature"],
                max_tokens=self.common_config["max_output_tokens"]
            )
            
            metrics.total_turns = 1
            if response.usage:
                metrics.input_tokens = response.usage.input_tokens
                metrics.output_tokens = response.usage.output_tokens
                metrics.total_tokens = response.usage.total_tokens
            
            # Parse answer
            parse_result = parse_answer(response.content)
            
            return parse_result.answer, parse_result, metrics, errors
            
        except Exception as e:
            errors.append({"type": "api_error", "message": str(e)})
            return None, AnswerParseResult(None, None, None), metrics, errors
    
    def _evaluate_with_tools(
        self,
        messages: List[Message],
        question: Dict[str, Any],
        metrics: EvaluationMetrics
    ) -> Tuple[Optional[str], AnswerParseResult, EvaluationMetrics, List[Dict]]:
        """Evaluate with tool-augmented loop (C2, C3)."""
        errors = []
        max_reasoning_calls = self.condition_config["max_reasoning_calls"]
        
        reasoning_calls = 0
        
        while reasoning_calls < max_reasoning_calls:
            metrics.total_turns += 1
            
            try:
                # Query LLM
                response = self.client.query(
                    messages,
                    tools=self.tools,
                    temperature=self.common_config["temperature"],
                    max_tokens=self.common_config["max_output_tokens"]
                )
                
                # Track tokens
                if response.usage:
                    metrics.input_tokens += response.usage.input_tokens
                    metrics.output_tokens += response.usage.output_tokens
                    metrics.total_tokens += response.usage.total_tokens
                
                # Add assistant message to history
                messages.append(Message(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls
                ))
                
                # Check for answer in response
                parse_result = parse_answer(response.content or "")
                if parse_result.success:
                    # Model answered
                    metrics.answered_early = (reasoning_calls < max_reasoning_calls)
                    return parse_result.answer, parse_result, metrics, errors
                
                # Handle tool calls
                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        tool_name = tool_call.get("function", {}).get("name") or tool_call.get("name")
                        tool_args_str = tool_call.get("function", {}).get("arguments") or tool_call.get("arguments", "{}")
                        
                        # Parse arguments
                        import json
                        try:
                            tool_args = json.loads(tool_args_str) if isinstance(tool_args_str, str) else tool_args_str
                        except:
                            tool_args = tool_args_str
                        
                        # Track call type
                        if tool_name == TOOL_VALIDATE:
                            metrics.validation_calls += 1
                        elif tool_name in [TOOL_GET_PARENT, TOOL_GET_CHILDREN]:
                            reasoning_calls += 1
                            metrics.reasoning_calls = reasoning_calls
                        
                        # Execute tool
                        try:
                            tool_result = self.executor.execute(tool_name, tool_args)
                            
                            # Add tool result to messages
                            messages.append(Message(
                                role="tool",
                                content=json.dumps(tool_result),
                                tool_call_id=tool_call.get("id", f"call_{len(messages)}"),
                                name=tool_name
                            ))
                        except Exception as e:
                            errors.append({
                                "type": "tool_error",
                                "tool": tool_name,
                                "message": str(e)
                            })
                            # Add error as tool result
                            messages.append(Message(
                                role="tool",
                                content=json.dumps({"error": str(e)}),
                                tool_call_id=tool_call.get("id", f"call_{len(messages)}"),
                                name=tool_name
                            ))
                else:
                    # No tool calls and no answer - model gave up or refused
                    return None, AnswerParseResult(None, "No answer or tool call", None), metrics, errors
                
            except Exception as e:
                errors.append({"type": "api_error", "turn": metrics.total_turns, "message": str(e)})
                return None, AnswerParseResult(None, None, None), metrics, errors
        
        # Exceeded max reasoning calls - force answer
        metrics.total_turns += 1
        messages.append(Message(role="user", content="Provide your final answer now."))
        
        try:
            response = self.client.query(
                messages,
                temperature=self.common_config["temperature"],
                max_tokens=self.common_config["max_output_tokens"]
            )
            
            if response.usage:
                metrics.input_tokens += response.usage.input_tokens
                metrics.output_tokens += response.usage.output_tokens
                metrics.total_tokens += response.usage.total_tokens
            
            parse_result = parse_answer(response.content or "")
            return parse_result.answer, parse_result, metrics, errors
            
        except Exception as e:
            errors.append({"type": "api_error", "turn": metrics.total_turns, "message": str(e)})
            return None, AnswerParseResult(None, None, None), metrics, errors
    
    def _message_to_dict(self, message: Message) -> Dict[str, Any]:
        """Convert Message to dict for logging."""
        d = {
            "role": message.role,
            "content": message.content
        }
        if message.tool_calls:
            d["tool_calls"] = message.tool_calls
        if message.tool_call_id:
            d["tool_call_id"] = message.tool_call_id
        if message.name:
            d["name"] = message.name
        return d
