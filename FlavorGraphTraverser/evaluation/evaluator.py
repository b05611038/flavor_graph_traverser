"""
Question Evaluator

Evaluates a single question under a specific condition.
Implements the turn-based evaluation loop from Implementation Guide.
"""

import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from .client import BaseClient, Message, LLMResponse
from .tools import GraphToolExecutor, get_tool_definitions, TOOL_VALIDATE, TOOL_GET_PARENT, TOOL_GET_CHILDREN
from .utils import (
    parse_answer, AnswerParseResult,
    parse_multiselect_answer, MultiSelectParseResult,
    load_conditions_config,
    build_icl_system_prompt, format_icl_tool_result, parse_icl_tool_call,
)
from .judge import LLMJudge, JudgeResult

# Score threshold for F-category: score >= this counts as "correct"
JUDGE_PASS_THRESHOLD = 3


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

    # Task type for per-task breakdown (e.g. "A1", "A4", "F")
    task_type: str = ""

    # F-category: raw model response text passed to judge
    # (model_answer is None for F; the full response is here)
    model_response_text: Optional[str] = None

    # F-category judge scoring (None for A/E questions)
    judge_score: Optional[int] = None
    judge_result: Optional[Dict[str, Any]] = None  # serializable JudgeResult


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
        config: Optional[Dict[str, Any]] = None,
        judge_client: Optional[BaseClient] = None,
        tool_mode: str = "native",
    ):
        """
        Initialize evaluator.

        Args:
            client: LLM client instance (the model being evaluated)
            executor: GraphToolExecutor instance
            condition: Condition name ("C0", "C1", "C2", "C3")
            config: Optional config dict (loads from YAML if None)
            judge_client: Optional LLM client for F-category judge evaluation.
                          If None, F-category questions are run but not judged
                          (status set to "no_judge").
            tool_mode: "native" (function calling API) or "icl" (text-based tool
                       simulation for models without function calling support).
                       ICL mode degrades gracefully: if the model ignores the tool
                       format, it just answers from its own knowledge.
        """
        self.client = client
        self.executor = executor
        self.condition = condition
        self.tool_mode = tool_mode
        self.judge = LLMJudge(judge_client) if judge_client is not None else None

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

        # Detect question type
        is_f_category = (
            question.get("category", "").upper() == "F"
            or question.get("evaluation", {}).get("method") == "llm_judge"
        )
        is_multiselect = isinstance(question.get("correct_answer"), list)
        task_type = self._get_task_type(question)

        try:
            # Format question (conversation_history built at end, after all turns complete)
            messages = self._format_question(question)

            model_response_text = None
            parse_result = AnswerParseResult(None, None, None)

            if is_f_category:
                # F-category: multi-turn with tools if C2/C3, else single-turn
                if self.condition_config["tools_enabled"]:
                    if self.tool_mode == "icl":
                        model_response_text, _, metrics, errors = self._evaluate_with_icl_tools(
                            messages, metrics
                        )
                    else:
                        model_response_text, _, metrics, errors = self._evaluate_with_tools(
                            messages, question, metrics
                        )
                    # Use the full last assistant response as the judge input
                    model_response_text = self._last_assistant_content(messages) or model_response_text or ""
                else:
                    model_response_text, metrics, errors = self._get_raw_response(messages, metrics)
                judge_score, judge_result_dict, status = self._run_judge(
                    question, model_response_text, errors
                )
                model_answer = None
                is_correct = (judge_score >= JUDGE_PASS_THRESHOLD) if judge_score is not None else False

            elif is_multiselect:
                # A1, A4: multi-select answer parsing
                if self.condition_config["tools_enabled"]:
                    if self.tool_mode == "icl":
                        raw_text, parse_result, metrics, errors = self._evaluate_with_icl_tools(
                            messages, metrics
                        )
                    else:
                        raw_text, parse_result, metrics, errors = self._evaluate_with_tools(
                            messages, question, metrics
                        )
                    # raw_text here is the last parsed single-letter (may be None);
                    # re-parse the full conversation for multiselect
                    last_assistant = self._last_assistant_content(messages)
                    ms_result = parse_multiselect_answer(last_assistant)
                else:
                    raw_text, parse_result, metrics, errors = self._evaluate_direct(
                        messages, metrics
                    )
                    ms_result = parse_multiselect_answer(parse_result.matched_text or "")
                    if not ms_result.success:
                        # parse_result.matched_text may be partial; try full response
                        last_assistant = self._last_assistant_content(messages)
                        ms_result = parse_multiselect_answer(last_assistant)

                model_answer = ms_result.answers  # list or None
                correct = question.get("correct_answer", [])
                if ms_result.success:
                    is_correct = set(model_answer) == set(correct)
                    status = "success"
                else:
                    is_correct = False
                    status = "parse_error"
                judge_score = None
                judge_result_dict = None

            else:
                # A2, A3, A5, E1, E2, E3: single-choice
                if self.condition_config["tools_enabled"]:
                    if self.tool_mode == "icl":
                        model_answer, parse_result, metrics, errors = self._evaluate_with_icl_tools(
                            messages, metrics
                        )
                    else:
                        model_answer, parse_result, metrics, errors = self._evaluate_with_tools(
                            messages, question, metrics
                        )
                else:
                    model_answer, parse_result, metrics, errors = self._evaluate_direct(
                        messages, metrics
                    )

                if errors:
                    status = "api_error" if any(e.get("type") == "api_error" for e in errors) else "tool_error"
                elif model_answer is None:
                    status = "parse_error"
                else:
                    status = "success"

                is_correct = (model_answer == question.get("correct_answer")) if model_answer else False
                judge_score = None
                judge_result_dict = None

            # Calculate latency
            metrics.latency_ms = int((time.time() - start_time) * 1000)

            # Build full conversation history now that all turns are complete
            conversation_history = [self._message_to_dict(m) for m in messages]

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
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                task_type=task_type,
                model_response_text=model_response_text,
                judge_score=judge_score,
                judge_result=judge_result_dict,
            )

        except Exception as e:
            conversation_history = [self._message_to_dict(m) for m in messages]
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
                conversation_history=conversation_history,
                errors=[{"type": "unexpected_error", "message": str(e)}],
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                task_type=task_type,
            )
    
    def _get_task_type(self, question: Dict[str, Any]) -> str:
        """Extract short task type label (A1, A2, ..., E3, F) from question."""
        if question.get("task_type"):
            # e.g. "A1_root_classification" -> "A1"
            return question["task_type"].split("_")[0].upper()
        qid = question.get("id", "")
        prefix = qid.split("_")[0].upper()
        # F questions may have ids like "F_G1_Q1"
        if prefix == "F":
            return "F"
        return prefix

    def _get_raw_response(
        self,
        messages: List[Message],
        metrics: EvaluationMetrics,
    ) -> tuple:
        """
        Get raw model response text without answer parsing (used for F-category).

        Returns:
            (response_text, metrics, errors)
        """
        errors = []
        try:
            response = self.client.query(
                messages,
                temperature=self.common_config["temperature"],
                max_tokens=self.common_config["max_output_tokens"],
            )
            metrics.total_turns = 1
            if response.usage:
                metrics.input_tokens = response.usage.input_tokens
                metrics.output_tokens = response.usage.output_tokens
                metrics.total_tokens = response.usage.total_tokens
            # Save to messages so conversation_history is complete
            messages.append(Message(
                role="assistant",
                content=response.content or "",
                thinking_content=response.thinking_content,
            ))
            return response.content or "", metrics, errors
        except Exception as e:
            errors.append({"type": "api_error", "message": str(e)})
            return "", metrics, errors

    def _last_assistant_content(self, messages: List[Message]) -> str:
        """Return content of the last assistant message (for multi-select re-parse)."""
        for msg in reversed(messages):
            if msg.role == "assistant":
                return msg.content or ""
        return ""

    def _run_judge(
        self,
        question: Dict[str, Any],
        model_response: Optional[str],
        errors: List[Dict],
    ) -> tuple:
        """
        Run LLM judge on an F-category response.

        Returns:
            (judge_score, judge_result_dict, status)
        """
        if self.judge is None:
            return None, None, "no_judge"

        if errors and any(e.get("type") == "api_error" for e in errors):
            return None, None, "api_error"

        judge_result = self.judge.evaluate(question, model_response or "")

        judge_result_dict = {
            "score": judge_result.score,
            "judge_response": judge_result.judge_response,
            "status": judge_result.status,
            "pattern_matched": judge_result.parse_result.pattern_matched,
        }
        if judge_result.error:
            judge_result_dict["error"] = judge_result.error

        if judge_result.status == "success":
            status = "success"
        elif judge_result.status == "api_error":
            status = "api_error"
        else:
            status = "judge_parse_error"

        return judge_result.score, judge_result_dict, status

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

        # Add answer format instruction (dynamic based on question type and options)
        option_keys = sorted(options.keys())
        is_multiselect = isinstance(question.get("correct_answer"), list)

        if len(option_keys) == 0:
            # Open-ended question (F_flavor_description)
            answer_format = "Provide your answer in a clear, detailed response."
        elif is_multiselect:
            # A1, A4: select all that apply; NONE if none apply
            options_list = ", ".join(option_keys)
            answer_format = (
                f'When providing your final answer, use this exact format:\n'
                f'"Therefore, I select (X, Y, ...)" listing all correct options from {options_list}, '
                f'or "Therefore, I select (NONE)" if none apply.'
            )
        elif len(option_keys) == 2:
            options_list = f"{option_keys[0]} or {option_keys[1]}"
            answer_format = f'When providing your final answer, use this exact format:\n"Therefore, I select (X)" where X is {options_list}.'
        else:
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

            # Append assistant response to history (captures thinking_content)
            messages.append(Message(
                role="assistant",
                content=response.content or "",
                thinking_content=response.thinking_content,
            ))

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
                
                # Add assistant message to history (include thinking if present)
                messages.append(Message(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                    thinking_content=response.thinking_content,
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
    
    def _evaluate_with_icl_tools(
        self,
        messages: List[Message],
        metrics: EvaluationMetrics,
    ) -> Tuple[Optional[str], AnswerParseResult, EvaluationMetrics, List[Dict]]:
        """
        Evaluate using text-based ICL tool simulation.

        Used for models without native function calling support.
        Tools are described in the system prompt; the model outputs:
            TOOL_CALL: {"name": "...", "args": {...}}
        Results are injected as plain user messages:
            TOOL_RESULT: <json>

        If the model does not output TOOL_CALL, parse_answer() runs on the
        response — the model effectively answers from its own knowledge.
        """
        import json as _json

        errors = []
        max_reasoning_calls = self.condition_config["max_reasoning_calls"]
        reasoning_calls = 0

        # Inject ICL tool instructions into the system message
        icl_messages = []
        for msg in messages:
            if msg.role == "system":
                icl_messages.append(Message(
                    role="system",
                    content=build_icl_system_prompt(msg.content),
                ))
            else:
                icl_messages.append(msg)

        while reasoning_calls < max_reasoning_calls:
            metrics.total_turns += 1
            try:
                response = self.client.query(
                    icl_messages,
                    temperature=self.common_config["temperature"],
                    max_tokens=self.common_config["max_output_tokens"],
                )

                if response.usage:
                    metrics.input_tokens += response.usage.input_tokens
                    metrics.output_tokens += response.usage.output_tokens
                    metrics.total_tokens += response.usage.total_tokens

                content = response.content or ""
                icl_messages.append(Message(
                    role="assistant",
                    content=content,
                    thinking_content=response.thinking_content,
                ))

                # Try to parse a tool call from the response text
                tool_name, tool_args = parse_icl_tool_call(content)

                if tool_name:
                    # Count call type
                    if tool_name == TOOL_VALIDATE:
                        metrics.validation_calls += 1
                    elif tool_name in [TOOL_GET_PARENT, TOOL_GET_CHILDREN]:
                        reasoning_calls += 1
                        metrics.reasoning_calls = reasoning_calls

                    # Execute tool
                    try:
                        tool_result = self.executor.execute(tool_name, tool_args)
                        result_text = format_icl_tool_result(tool_name, tool_result)
                    except Exception as e:
                        errors.append({"type": "tool_error", "tool": tool_name, "message": str(e)})
                        result_text = format_icl_tool_result(tool_name, {"error": str(e)})

                    icl_messages.append(Message(role="user", content=result_text))

                else:
                    # No tool call — check if the model answered
                    parse_result = parse_answer(content)
                    if parse_result.success:
                        metrics.answered_early = (reasoning_calls < max_reasoning_calls)
                        # Sync back to caller's messages list
                        messages[:] = icl_messages
                        return parse_result.answer, parse_result, metrics, errors
                    # No answer and no tool call — force answer on next turn
                    break

            except Exception as e:
                errors.append({"type": "api_error", "turn": metrics.total_turns, "message": str(e)})
                messages[:] = icl_messages
                return None, AnswerParseResult(None, None, None), metrics, errors

        # Force final answer
        metrics.total_turns += 1
        icl_messages.append(Message(role="user", content="Provide your final answer now."))
        try:
            response = self.client.query(
                icl_messages,
                temperature=self.common_config["temperature"],
                max_tokens=self.common_config["max_output_tokens"],
            )
            if response.usage:
                metrics.input_tokens += response.usage.input_tokens
                metrics.output_tokens += response.usage.output_tokens
                metrics.total_tokens += response.usage.total_tokens
            content = response.content or ""
            icl_messages.append(Message(
                role="assistant",
                content=content,
                thinking_content=response.thinking_content,
            ))
            parse_result = parse_answer(content)
            messages[:] = icl_messages
            return parse_result.answer, parse_result, metrics, errors
        except Exception as e:
            errors.append({"type": "api_error", "turn": metrics.total_turns, "message": str(e)})
            messages[:] = icl_messages
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
        if message.thinking_content:
            d["thinking_content"] = message.thinking_content
        return d
