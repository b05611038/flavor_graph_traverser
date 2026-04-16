#!/usr/bin/env python3
"""
Review Flagged Questions - CLI Tool

Interactive CLI for reviewing questions flagged in the web auditor.
Work with Claude to fix problems, regenerate questions, or adjust rules.
"""

import sys
import os
import json
from pathlib import Path
from typing import List, Dict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from FlavorGraphTraverser.evaluation.question_auditor import QuestionAuditor


class FlaggedQuestionReviewer:
    """CLI tool for reviewing flagged questions."""

    def __init__(self, flagged_log: str, auditor: QuestionAuditor):
        """
        Initialize reviewer.

        Args:
            flagged_log: Path to flagged questions JSONL file
            auditor: QuestionAuditor instance
        """
        self.flagged_log = Path(flagged_log)
        self.auditor = auditor
        self.flagged_questions = []

    def load_flagged(self):
        """Load flagged questions from log."""
        if not self.flagged_log.exists():
            return []

        flagged = []
        with open(self.flagged_log, 'r') as f:
            for line in f:
                if line.strip():
                    flagged.append(json.loads(line))

        self.flagged_questions = flagged
        return flagged

    def display_question(self, entry: Dict):
        """Display a flagged question with details."""
        print(f"\n{'='*70}")
        print(f"📋 FLAGGED QUESTION REVIEW")
        print(f"{'='*70}\n")

        question = entry['question']
        qid = entry['question_id']
        reason = entry['reason']
        notes = entry.get('notes', '')
        timestamp = entry['timestamp']

        print(f"Question ID: {qid}")
        print(f"Category: {question.get('category', 'UNKNOWN')}")
        print(f"Task Type: {question.get('task_type', 'UNKNOWN')}")
        print(f"Flagged: {timestamp}")
        print(f"\n🚩 FLAG REASON: {reason}")
        if notes:
            print(f"📝 NOTES: {notes}")

        print(f"\n{'-'*70}")
        print("📄 WHAT LLM SEES:")
        print(f"{'-'*70}\n")

        # Show question text
        text = question.get('text', '')
        print(text)
        print()

        # Show options
        options = question.get('options', {})
        for key in sorted(options.keys()):
            print(f"  ({key}) {options[key]}")

        print("\nWhen providing your final answer, use this exact format:")
        print('"Therefore, I select (X)" where X is A, B, C, or D.')

        print(f"\n{'-'*70}")
        print("🔍 ANNOTATED VIEW:")
        print(f"{'-'*70}\n")

        # Show template if available
        if '_template' in question:
            print(f"📋 TEMPLATE:\n  {question['_template']}\n")

        # Show objects if available
        if '_objects' in question:
            print("🎯 OBJECTS (from graph):")
            for key, value in question['_objects'].items():
                print(f"  {key} = '{value}'")
            print()

        # Show correct answer
        correct = question.get('correct_answer', 'UNKNOWN')
        correct_text = options.get(correct, 'UNKNOWN')
        print(f"✅ CORRECT ANSWER: ({correct}) {correct_text}")

        print(f"\n{'='*70}\n")

    def review_interactive(self):
        """Interactive review session."""
        flagged = self.load_flagged()

        if not flagged:
            print("\n✅ No flagged questions to review!\n")
            return

        print(f"\n🔍 Found {len(flagged)} flagged question(s)\n")
        print("="*70)
        print("REVIEW SESSION - Work with Claude to fix problems")
        print("="*70)
        print("\nFor each question, you can:")
        print("  1. Discuss the problem with Claude in this CLI")
        print("  2. Regenerate the question")
        print("  3. Note issues for later")
        print("  4. Accept as-is (unflag)")
        print("  5. Keep flagged for now")
        print("\nLet's review each question...\n")

        for idx, entry in enumerate(flagged, 1):
            print(f"\n{'#'*70}")
            print(f"# QUESTION {idx} of {len(flagged)}")
            print(f"{'#'*70}")

            self.display_question(entry)

            # Show action menu
            self._show_action_menu(entry)

    def _show_action_menu(self, entry: Dict):
        """Show action menu for a flagged question."""
        qid = entry['question_id']

        print("\n" + "="*70)
        print("ACTIONS:")
        print("="*70)
        print("\n[1] Discuss with Claude (stay in CLI)")
        print("[2] Save notes about this question")
        print("[3] Unflag and accept as-is")
        print("[4] Keep flagged, review later")
        print("[5] Export question JSON for inspection")
        print("[Q] Quit review session")
        print()

        while True:
            choice = input("Your choice: ").strip().lower()

            if choice == '1':
                self._discuss_mode(entry)
                break
            elif choice == '2':
                self._save_notes(entry)
                break
            elif choice == '3':
                self.auditor.unflag_question(qid)
                print(f"\n✅ Question {qid} unflagged and accepted")
                break
            elif choice == '4':
                print(f"\n⏸️  Question {qid} kept flagged for later review")
                break
            elif choice == '5':
                self._export_json(entry)
            elif choice == 'q':
                print("\n👋 Exiting review session...")
                sys.exit(0)
            else:
                print("Invalid choice. Please enter 1-5 or Q.")

    def _discuss_mode(self, entry: Dict):
        """Enter discussion mode - show information for Claude to help."""
        print("\n" + "="*70)
        print("💬 DISCUSSION MODE")
        print("="*70)
        print("\nYou can now discuss this question with Claude.")
        print("Claude has full context of the question above.")
        print("\nExample things to discuss:")
        print("  - Is the question ambiguous?")
        print("  - Is the correct answer actually correct?")
        print("  - Should we adjust the template?")
        print("  - Should we regenerate with different objects?")
        print("\nYou can copy the question text above and paste it into")
        print("your conversation with Claude, or just ask questions here.")
        print("\n(Press Enter to return to action menu)")
        input()

    def _save_notes(self, entry: Dict):
        """Save notes about a flagged question."""
        print("\n" + "="*70)
        print("📝 SAVE NOTES")
        print("="*70)
        print("\nEnter your notes about this question:")
        print("(Press Ctrl+D or Ctrl+Z when done)\n")

        notes_lines = []
        try:
            while True:
                line = input()
                notes_lines.append(line)
        except EOFError:
            pass

        notes = '\n'.join(notes_lines)

        # Save to a notes file
        notes_file = Path("data/question_review_notes.jsonl")
        notes_file.parent.mkdir(parents=True, exist_ok=True)

        note_entry = {
            "question_id": entry['question_id'],
            "notes": notes,
            "original_flag": entry['reason']
        }

        with open(notes_file, 'a') as f:
            f.write(json.dumps(note_entry) + '\n')

        print(f"\n✅ Notes saved to {notes_file}")

    def _export_json(self, entry: Dict):
        """Export question as JSON for inspection."""
        qid = entry['question_id']
        export_file = Path(f"data/exports/{qid}.json")
        export_file.parent.mkdir(parents=True, exist_ok=True)

        with open(export_file, 'w') as f:
            json.dump(entry['question'], f, indent=2)

        print(f"\n✅ Question exported to: {export_file}")
        print("You can inspect or edit this file manually.")


def main():
    """Run the flagged question reviewer."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Review flagged questions in CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Review all flagged questions
  python scripts/review_flagged.py

  # Specify custom flagged log location
  python scripts/review_flagged.py --flagged-log data/my_flags.jsonl

This tool helps you review questions that were flagged in the web auditor.
You can discuss problems with Claude, save notes, or unflag questions.
        """
    )

    parser.add_argument(
        '--flagged-log',
        default='data/flagged_questions.jsonl',
        help="Path to flagged questions log (default: data/flagged_questions.jsonl)"
    )
    parser.add_argument(
        '--state-file',
        default='data/audit_state.json',
        help="Path to audit state file (default: data/audit_state.json)"
    )

    args = parser.parse_args()

    # Initialize
    auditor = QuestionAuditor(state_file=args.state_file)
    reviewer = FlaggedQuestionReviewer(args.flagged_log, auditor)

    # Run review session
    print("\n" + "="*70)
    print("🔍 FLAGGED QUESTION REVIEWER")
    print("="*70)
    print(f"\nLoading flagged questions from: {args.flagged_log}")

    flagged_count = len(reviewer.load_flagged())

    if flagged_count == 0:
        print("\n✅ No flagged questions found!")
        print("\nIf you've flagged questions in the web auditor,")
        print(f"they should appear in: {args.flagged_log}")
        return

    # Start interactive review
    reviewer.review_interactive()

    print("\n" + "="*70)
    print("✅ Review session complete!")
    print("="*70)
    print()


if __name__ == '__main__':
    main()
