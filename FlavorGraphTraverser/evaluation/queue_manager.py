#!/usr/bin/env python3
"""
Question Queue Manager

Reliable API for managing the question review queue.
The auditor shows questions in order from the questions file,
filtering to show only pending/flagged questions.

This module provides operations to reorder questions by priority.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Set, Optional, Callable
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from FlavorGraphTraverser.backup import backup_before_write
from collections import defaultdict


class QueueManager:
    """Manages the question review queue."""

    def __init__(self, questions_file: str, audit_state_file: str):
        """
        Initialize queue manager.

        Args:
            questions_file: Path to questions JSON file
            audit_state_file: Path to audit state JSON file
        """
        self.questions_file = Path(questions_file)
        self.audit_state_file = Path(audit_state_file)
        self.questions = []
        self.audit_state = {}
        self._load()

    def _load(self):
        """Load questions and audit state from files."""
        # Load questions
        with open(self.questions_file) as f:
            data = json.load(f)
            if isinstance(data, dict) and "questions" in data:
                self.questions = data["questions"]
                self.metadata = data.get("metadata", {})
            else:
                self.questions = data
                self.metadata = {}

        # Load audit state
        with open(self.audit_state_file) as f:
            self.audit_state = json.load(f)

    def save(self):
        """Save questions back to file."""
        data = {
            "metadata": self.metadata,
            "questions": self.questions
        }
        data["metadata"]["last_modified"] = datetime.now().isoformat()

        backup_before_write(self.questions_file)
        with open(self.questions_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"✓ Saved {len(self.questions)} questions to {self.questions_file}")

    def get_status(self, question_id: str) -> str:
        """
        Get audit status of a question.

        Args:
            question_id: Question ID

        Returns:
            'confirmed', 'flagged', or 'pending'
        """
        if question_id in self.audit_state:
            return self.audit_state[question_id].get('status', 'pending')
        return 'pending'

    def get_stats(self) -> Dict:
        """
        Get queue statistics.

        Returns:
            Dict with counts by task type and status
        """
        stats = defaultdict(lambda: {'confirmed': 0, 'flagged': 0, 'pending': 0, 'total': 0})

        for q in self.questions:
            task_type = q['task_type']
            status = self.get_status(q['id'])
            stats[task_type][status] += 1
            stats[task_type]['total'] += 1

        return dict(stats)

    def filter_questions(
        self,
        task_types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        exclude_statuses: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Filter questions by task type and/or status.

        Args:
            task_types: List of task types to include (None = all)
            statuses: List of statuses to include (None = all)
            exclude_statuses: List of statuses to exclude

        Returns:
            Filtered list of questions
        """
        filtered = []

        for q in self.questions:
            # Check task type
            if task_types and q['task_type'] not in task_types:
                continue

            # Check status
            status = self.get_status(q['id'])

            if statuses and status not in statuses:
                continue

            if exclude_statuses and status in exclude_statuses:
                continue

            filtered.append(q)

        return filtered

    def move_to_front(
        self,
        task_types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        exclude_statuses: Optional[List[str]] = None
    ):
        """
        Move matching questions to front of queue.

        Args:
            task_types: Task types to move (None = all)
            statuses: Statuses to move (None = all)
            exclude_statuses: Statuses to exclude

        Example:
            # Move all pending/flagged A2 questions to front
            qm.move_to_front(task_types=['A2_ancestor_verification'],
                           exclude_statuses=['confirmed'])
        """
        matching = self.filter_questions(task_types, statuses, exclude_statuses)
        others = [q for q in self.questions if q not in matching]

        self.questions = matching + others

        print(f"✓ Moved {len(matching)} questions to front")
        print(f"  Remaining: {len(others)} questions")

    def move_to_back(
        self,
        task_types: Optional[List[str]] = None,
        statuses: Optional[List[str]] = None,
        exclude_statuses: Optional[List[str]] = None
    ):
        """
        Move matching questions to back of queue.

        Args:
            task_types: Task types to move (None = all)
            statuses: Statuses to move (None = all)
            exclude_statuses: Statuses to exclude

        Example:
            # Move all confirmed A1 questions to back
            qm.move_to_back(task_types=['A1_root_classification'],
                          statuses=['confirmed'])
        """
        matching = self.filter_questions(task_types, statuses, exclude_statuses)
        others = [q for q in self.questions if q not in matching]

        self.questions = others + matching

        print(f"✓ Moved {len(matching)} questions to back")
        print(f"  Remaining at front: {len(others)} questions")

    def reorder_by_priority(self, priority_rules: List[Dict]):
        """
        Reorder questions by priority rules.

        Args:
            priority_rules: List of rules, each with 'task_types', 'statuses', 'exclude_statuses'
                           Rules are applied in order (first rule = highest priority)

        Example:
            # Prioritize pending/flagged A2, then A3, then everything else
            qm.reorder_by_priority([
                {'task_types': ['A2_ancestor_verification'], 'exclude_statuses': ['confirmed']},
                {'task_types': ['A3_sibling_identification'], 'exclude_statuses': ['confirmed']},
                {'statuses': ['confirmed']}  # Confirmed questions at back
            ])
        """
        buckets = []
        remaining = list(self.questions)

        for rule in priority_rules:
            task_types = rule.get('task_types')
            statuses = rule.get('statuses')
            exclude_statuses = rule.get('exclude_statuses')

            # Filter from remaining questions
            matching = []
            new_remaining = []

            for q in remaining:
                # Check task type
                if task_types and q['task_type'] not in task_types:
                    new_remaining.append(q)
                    continue

                # Check status
                status = self.get_status(q['id'])

                if statuses and status not in statuses:
                    new_remaining.append(q)
                    continue

                if exclude_statuses and status in exclude_statuses:
                    new_remaining.append(q)
                    continue

                matching.append(q)

            buckets.append(matching)
            remaining = new_remaining

        # Add any remaining questions at the end
        if remaining:
            buckets.append(remaining)

        # Flatten buckets
        self.questions = []
        for i, bucket in enumerate(buckets):
            print(f"  Priority {i+1}: {len(bucket)} questions")
            self.questions.extend(bucket)

        print(f"✓ Reordered {len(self.questions)} questions by {len(priority_rules)} priority rules")

    def print_queue_head(self, n: int = 20):
        """
        Print first N questions in queue with their status.

        Args:
            n: Number of questions to show
        """
        print(f"\nFirst {n} questions in queue:")
        print("=" * 70)

        for i, q in enumerate(self.questions[:n]):
            task_type = q['task_type']
            status = self.get_status(q['id'])
            descriptor = q.get('_objects', {}).get('descriptor', 'N/A')

            # Abbreviate task type
            task_abbr = task_type.split('_')[0]  # A1, A2, etc.

            print(f"{i+1:3d}. {task_abbr:3s} | {status:9s} | {descriptor}")

    def print_pending_queue(self, n: int = 20):
        """
        Print first N pending/flagged questions (what auditor will show).

        Args:
            n: Number of questions to show
        """
        pending_flagged = self.filter_questions(exclude_statuses=['confirmed'])

        print(f"\nNext {n} questions for auditor (pending/flagged):")
        print("=" * 70)

        for i, q in enumerate(pending_flagged[:n]):
            task_type = q['task_type']
            status = self.get_status(q['id'])
            descriptor = q.get('_objects', {}).get('descriptor', 'N/A')

            # Abbreviate task type
            task_abbr = task_type.split('_')[0]

            print(f"{i+1:3d}. {task_abbr:3s} | {status:9s} | {descriptor}")

        print()
        print(f"Total pending/flagged: {len(pending_flagged)}")

    def custom_sort(self, key_func: Callable):
        """
        Sort questions using a custom key function.

        Args:
            key_func: Function that takes a question dict and returns a sort key

        Example:
            # Sort by descriptor alphabetically within each task type
            qm.custom_sort(lambda q: (q['task_type'], q['_objects']['descriptor']))
        """
        self.questions.sort(key=key_func)
        print(f"✓ Sorted {len(self.questions)} questions by custom function")
