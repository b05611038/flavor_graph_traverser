"""
Question Auditor - State Manager

Manages question audit state: pending, confirmed, flagged.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class QuestionAuditState:
    """State of a question in the audit process."""
    question_id: str
    status: str  # "pending", "confirmed", "flagged"
    timestamp: str
    notes: Optional[str] = None
    flag_reason: Optional[str] = None


class QuestionAuditor:
    """
    Manages question audit workflow.

    Tracks which questions are confirmed, flagged, or pending.
    Checks for duplicates against confirmed questions.
    """

    def __init__(self, state_file: str = "data/audit_state.json"):
        """
        Initialize auditor.

        Args:
            state_file: Path to JSON file storing audit state
        """
        self.state_file = Path(state_file)
        self.states: Dict[str, QuestionAuditState] = {}
        self.load_state()

    def load_state(self):
        """Load audit state from file."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                for qid, state_dict in data.items():
                    self.states[qid] = QuestionAuditState(**state_dict)

    def save_state(self):
        """Save audit state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            data = {qid: asdict(state) for qid, state in self.states.items()}
            json.dump(data, f, indent=2)

    def get_status(self, question_id: str) -> str:
        """Get status of a question."""
        if question_id in self.states:
            return self.states[question_id].status
        return "pending"

    def confirm_question(self, question_id: str, notes: Optional[str] = None):
        """Mark question as confirmed."""
        self.states[question_id] = QuestionAuditState(
            question_id=question_id,
            status="confirmed",
            timestamp=datetime.now().isoformat(),
            notes=notes
        )
        self.save_state()

    def flag_question(self, question_id: str, reason: str, notes: Optional[str] = None):
        """Mark question as flagged for review."""
        self.states[question_id] = QuestionAuditState(
            question_id=question_id,
            status="flagged",
            timestamp=datetime.now().isoformat(),
            flag_reason=reason,
            notes=notes
        )
        self.save_state()

    def unflag_question(self, question_id: str):
        """Remove flag from question (back to pending)."""
        if question_id in self.states:
            del self.states[question_id]
            self.save_state()

    def get_confirmed_questions(self) -> List[str]:
        """Get list of confirmed question IDs."""
        return [qid for qid, state in self.states.items() if state.status == "confirmed"]

    def get_flagged_questions(self) -> List[str]:
        """Get list of flagged question IDs."""
        return [qid for qid, state in self.states.items() if state.status == "flagged"]

    def get_pending_questions(self, all_question_ids: List[str]) -> List[str]:
        """Get list of pending question IDs."""
        return [qid for qid in all_question_ids if self.get_status(qid) == "pending"]

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
        question_options = frozenset(question.get("options", {}).values())

        for confirmed in confirmed_questions:
            confirmed_text = confirmed.get("text", "").lower().strip()
            confirmed_options = frozenset(confirmed.get("options", {}).values())

            # Check if text and options match
            if question_text == confirmed_text and question_options == confirmed_options:
                return confirmed.get("id")

        return None

    def get_stats(self) -> Dict[str, int]:
        """Get audit statistics."""
        stats = {
            "confirmed": len([s for s in self.states.values() if s.status == "confirmed"]),
            "flagged": len([s for s in self.states.values() if s.status == "flagged"]),
            "total_reviewed": len(self.states)
        }
        return stats


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
    options = question.get("options", {})
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
    if answer_format == "multi_label":
        llm_view = f"""{text}

{options_text}

When providing your final answer, select all applicable options.
Use this exact format: "Therefore, I select (X, Y, Z)" where X, Y, Z are the correct letters.
If none apply, respond: "Therefore, I select (NONE)"
"""
    else:
        llm_view = f"""{text}

{options_text}

When providing your final answer, use this exact format:
"Therefore, I select (X)" where X is A, B, C, or D.
"""

    # Annotated view with template/objects highlighted
    annotated_parts = []

    if template:
        annotated_parts.append(f"📋 TEMPLATE:\n  {template}")

    if objects:
        annotated_parts.append(f"\n🎯 OBJECTS (from graph):")
        for key, value in objects.items():
            # Skip list values for cleaner display
            if not isinstance(value, list):
                annotated_parts.append(f"  {key} = '{value}'")
            else:
                annotated_parts.append(f"  {key} = {value}")

    annotated_parts.append(f"\n❓ FINAL QUESTION:\n  {text}")
    annotated_parts.append(f"\n📝 OPTIONS:\n{options_text}")

    # Format answer display based on type
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
