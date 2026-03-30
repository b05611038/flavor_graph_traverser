"""
Question Auditor - State Manager

Manages question audit state: pending, confirmed, flagged.

NOTE: This is now a backwards-compatible wrapper around AuditStateManager.
New code should use AuditStateManager directly.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime

from prompts import load_prompt

# Import new state manager
from FlavorGraphTraverser.evaluation.audit_state_manager import (
    AuditStateManager,
    QuestionAuditState,
    CANONICAL_STATE_FILE
)


class QuestionAuditor:
    """
    Manages question audit workflow.

    This is a backwards-compatible wrapper around AuditStateManager.
    Tracks which questions are confirmed, flagged, or pending.
    Checks for duplicates against confirmed questions.
    """

    def __init__(self, state_file: Optional[str] = None, read_only: bool = False):
        """
        Initialize auditor.

        Args:
            state_file: Path to JSON file storing audit state (defaults to canonical)
            read_only: If True, prevents writes (useful for review interface)
        """
        # Use new state manager
        if state_file:
            self._manager = AuditStateManager(Path(state_file), read_only=read_only)
        else:
            self._manager = AuditStateManager(read_only=read_only)

        # Expose state_file and states for backwards compatibility
        self.state_file = self._manager.state_file
        self.states = self._manager.states
        self.read_only = read_only

    def load_state(self):
        """Load audit state from file."""
        self._manager.load_state()
        self.states = self._manager.states

    def reload_state(self):
        """Reload state from file (useful for read-only mode)."""
        self._manager.reload_state()
        self.states = self._manager.states

    def save_state(self):
        """Save audit state to file."""
        self._manager.save_state()
        self.states = self._manager.states

    def get_status(self, question_id: str) -> str:
        """Get status of a question."""
        return self._manager.get_status(question_id)

    def confirm_question(self, question_id: str, notes: Optional[str] = None):
        """Mark question as confirmed."""
        self._manager.confirm_question(question_id, notes)
        self.states = self._manager.states

    def flag_question(self, question_id: str, reason: str, notes: Optional[str] = None):
        """Mark question as flagged for review."""
        self._manager.flag_question(question_id, reason, notes)
        self.states = self._manager.states

    def unflag_question(self, question_id: str):
        """Remove flag from question (back to pending)."""
        self._manager.unflag_question(question_id)
        self.states = self._manager.states

    def get_confirmed_questions(self) -> List[str]:
        """Get list of confirmed question IDs."""
        return self._manager.get_confirmed_questions()

    def get_flagged_questions(self) -> List[str]:
        """Get list of flagged question IDs."""
        return self._manager.get_flagged_questions()

    def get_pending_questions(self, all_question_ids: List[str]) -> List[str]:
        """Get list of pending question IDs."""
        return self._manager.get_pending_questions(all_question_ids)

    def check_duplicate(self, question: Dict, confirmed_questions: List[Dict]) -> Optional[str]:
        """
        Check if question is duplicate of any confirmed question.

        Args:
            question: Question dict to check
            confirmed_questions: List of confirmed question dicts

        Returns:
            ID of duplicate question if found, None otherwise
        """
        question_text = question.get("text", "").lower().strip()
        question_options = frozenset((question.get("options") or {}).values())

        for confirmed in confirmed_questions:
            confirmed_text = confirmed.get("text", "").lower().strip()
            confirmed_options = frozenset((confirmed.get("options") or {}).values())

            # Check if text and options match
            if question_text == confirmed_text and question_options == confirmed_options:
                return confirmed.get("id")

        return None

    def get_stats(self) -> Dict[str, int]:
        """Get audit statistics."""
        return self._manager.get_stats()


def format_question_for_display(question: Dict) -> Dict[str, str]:
    """
    Format question for auditor display with annotations.

    Returns:
        Dict with formatted fields for web display
    """
    # Get metadata
    qid = question.get("id", "UNKNOWN")
    category = question.get("category", "UNKNOWN")
    task_type = question.get("task_type", "UNKNOWN")

    # Format question text with annotations
    text = question.get("text", "")

    # Extract template info if available
    template = question.get("_template", "")
    objects = question.get("_objects", {})

    # Format options
    options = question.get("options") or {}
    options_text = "\n".join([f"  ({key}) {value}" for key, value in sorted(options.items())])

    # Get correct answer (handle both single-label and multi-label)
    correct_answer = question.get("correct_answer", "UNKNOWN")
    answer_format = question.get("answer_format", "single")

    # Format correct answer text
    if isinstance(correct_answer, list):
        # Multi-label format
        if len(correct_answer) == 0:
            correct_text = "NONE (no correct answers)"
        else:
            correct_texts = [f"({letter}) {options.get(letter, 'UNKNOWN')}" for letter in correct_answer]
            correct_text = ", ".join(correct_texts)
    else:
        # Single-label format
        correct_text = options.get(correct_answer, "UNKNOWN")

    # Format what LLM sees (different for multi-label)
    if answer_format == "open":
        llm_view = text
    elif answer_format == "multi_label":
        option_keys = sorted(options.keys())
        options_list = ", ".join(option_keys)
        answer_instruction = load_prompt("answer_format_multi", options_list=options_list)
        llm_view = f"{text}\n\n{options_text}\n\n{answer_instruction}\n"
    else:
        # Generate dynamic answer format based on number of options
        option_keys = sorted(options.keys())
        if len(option_keys) == 0:
            answer_instruction = load_prompt("answer_format_open")
        elif len(option_keys) == 2:
            options_list = f"{option_keys[0]} or {option_keys[1]}"
            answer_instruction = load_prompt("answer_format_single", options_list=options_list)
        else:
            options_list = ", ".join(option_keys[:-1]) + f", or {option_keys[-1]}"
            answer_instruction = load_prompt("answer_format_single", options_list=options_list)

        llm_view = f"{text}\n\n{options_text}\n\n{answer_instruction}\n"

    # Annotated view with template/objects highlighted
    annotated_parts = []

    # F-category: open-ended with judging notes
    evaluation = question.get("evaluation", {})
    if category == "F" or (evaluation and evaluation.get("method") == "llm_judge"):
        group = question.get("group", "")
        group_index = question.get("group_index", "")
        judging_notes = evaluation.get("judging_notes", {})

        if group:
            annotated_parts.append(f"📦 GROUP: {group}  (Q{group_index})")

        # ── LLM-visible section ──
        annotated_parts.append(f"\n👁️  VISIBLE TO LLM\n{'─' * 40}")
        annotated_parts.append(f"{text}")
        annotated_parts.append(f"{'─' * 40}")

        # ── Judge-only section ──
        annotated_parts.append(f"\n🔒 JUDGE / AUDITOR ONLY\n{'─' * 40}")

        # Show coffees from _objects if present
        coffees = objects.get("coffees", {})
        if coffees:
            annotated_parts.append(f"☕ COFFEES:")
            for letter, descriptors in sorted(coffees.items()):
                annotated_parts.append(f"  {letter}: {', '.join(descriptors)}")

        best = objects.get("best_answers", [])
        wrong = objects.get("clearly_wrong", [])
        plausible = objects.get("plausible_wrong", [])
        if best:
            annotated_parts.append(f"\n✅ BEST ANSWERS: {best}")
        if plausible:
            annotated_parts.append(f"⚠️  PLAUSIBLE BUT WRONG: {plausible}")
        if wrong:
            annotated_parts.append(f"❌ CLEARLY WRONG: {wrong}")

        if judging_notes:
            annotated_parts.append(f"\n🧑‍⚖️ JUDGING NOTES:")
            what = judging_notes.get("what_to_evaluate", "")
            if what:
                annotated_parts.append(f"  What to evaluate: {what}")
            rubric = judging_notes.get("scoring_rubric", {})
            if rubric:
                annotated_parts.append(f"\n  Scoring rubric (0-5):")
                for score in sorted(rubric.keys(), reverse=True):
                    annotated_parts.append(f"    [{score}] {rubric[score]}")
            judge_inst = judging_notes.get("judge_instructions", "")
            if judge_inst:
                annotated_parts.append(f"\n  Judge instructions: {judge_inst}")

        judge_model = evaluation.get('judge_model')
        judge_str = f" | Judge: {judge_model}" if judge_model else ""
        annotated_parts.append(f"\n📊 Evaluation: {evaluation.get('method','?')}{judge_str} | Scoring: {evaluation.get('scoring','?')}")

    else:
        if template:
            annotated_parts.append(f"📋 TEMPLATE:\n  {template}")

        if objects:
            annotated_parts.append(f"\n🎯 OBJECTS (from graph):")
            for key, value in objects.items():
                if not isinstance(value, list):
                    annotated_parts.append(f"  {key} = '{value}'")
                else:
                    annotated_parts.append(f"  {key} = {value}")

        annotated_parts.append(f"\n❓ FINAL QUESTION:\n  {text}")
        annotated_parts.append(f"\n📝 OPTIONS:\n{options_text}")

        if isinstance(correct_answer, list):
            annotated_parts.append(f"\n✅ CORRECT ANSWERS: {correct_answer} → {correct_text}")
            annotated_parts.append(f"   Format: Multi-label (select all that apply)")
        else:
            annotated_parts.append(f"\n✅ CORRECT ANSWER: ({correct_answer}) {correct_text}")

    annotated_text = "\n".join(annotated_parts)

    return {
        "id": qid,
        "category": category,
        "task_type": task_type,
        "llm_view": llm_view,
        "annotated_view": annotated_text,
        "correct_answer": correct_answer,
        "correct_text": correct_text
    }
