"""
Question Validators

Validates generated questions for quality and answerability.

Classes:
    QuestionValidator: Validates questions meet quality criteria
"""

import re
from typing import Dict, Any, List, Optional, Set

from ..graph import CoffeeDescriptionGraph

# Fields in _objects where values are specific descriptors that must NOT appear in the tool graph
PROTECTED_FIELDS = {
    'descriptor', 'descriptor1', 'descriptor2',
    'correct_sibling',
    'distractor1', 'distractor2', 'distractor3',
    'target', 'option1', 'option2', 'option3',
    'closer', 'middle', 'farther',
    'odd_one',
}

# List-valued fields in _objects where each element must NOT appear in the tool graph
PROTECTED_LIST_FIELDS = {
    'similar_group', 'candidates', 'all_candidates',
}

# Fields in _objects that are structural/categorical and CAN appear in the tool graph
STRUCTURAL_FIELDS = {
    'parent', 'ancestor', 'lca', 'root', 'root_category',
    'all_valid_roots', 'valid_roots_in_options', 'invalid_roots_in_options',
    'is_ancestor', 'correct_path', 'correct_ranking',
    'question_subtype', 'similar_parent',
}

_STOP_WORDS = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}


def _tokenize(s: str) -> Set[str]:
    """Return meaningful word tokens from a string, excluding stop words."""
    return set(re.findall(r'\b\w+\b', s.lower())) - _STOP_WORDS


class QuestionValidator:
    """
    Validates generated questions for quality.

    Checks that questions are:
    - Answerable (correct answer is valid)
    - Unambiguous (only one correct answer)
    - Non-trivial (distractors are plausible)
    - Well-formed (all required fields present)
    - Leak-free (no question components appear in tool graph)

    Example:
        >>> validator = QuestionValidator(graph, tool_graph_nodes={"chocolate", "vanilla"})
        >>>
        >>> question = {
        ...     "text": "Which root category does 'caramel' belong to?",
        ...     "options": {"A": "fruity", "B": "nutty/cocoa", "C": "floral", "D": "spices"},
        ...     "correct_answer": "B"
        ... }
        >>>
        >>> is_valid = validator.validate(question)
        >>> print(is_valid)  # True
    """

    def __init__(self, graph: CoffeeDescriptionGraph, tool_graph_nodes: Optional[Set[str]] = None):
        """
        Initialize validator.

        Args:
            graph: CoffeeDescriptionGraph instance
            tool_graph_nodes: Set of ALL node names in the tool graph (for leakage checking).
                              If provided, questions with protected components in this set are rejected.
        """
        self.graph = graph
        self.tool_graph_nodes = tool_graph_nodes or set()

    def validate(self, question: Dict[str, Any]) -> bool:
        """
        Validate a question.

        Args:
            question: Question dict

        Returns:
            True if valid, False otherwise

        Validation checks:
            1. Required fields present
            2. Options are valid
            3. Correct answer is in options
            4. All descriptors exist in graph
            5. Correct answer is actually correct
            6. No duplicate options

        Example:
            >>> is_valid = validator.validate(question)
        """
        if not self._check_required_fields(question):
            return False

        if not self._check_options_format(question):
            return False

        if not self._check_correct_answer(question):
            return False

        if not self._check_descriptors_in_graph(question):
            return False

        if not self._check_no_duplicate_options(question):
            return False

        if not self._check_no_leakage(question):
            return False

        # ROOT:SYSTEM is a structural node and must never appear in any question field
        if not self._check_no_root_system(question):
            return False

        # Reject questions solvable by text/name matching rather than graph reasoning
        if not self._check_no_text_overlap(question):
            return False

        # Task-specific validation
        task_type = question.get("task_type", "")
        if task_type.startswith("A1"):
            return self._validate_a1(question)
        elif task_type.startswith("A2"):
            return self._validate_a2(question)
        # A3–A5 and E1–E3 rely on the shared checks above.
        # Their graph relationships are verified during generation (not re-validated here)
        # because re-checking paths/siblings/LCAs would duplicate generation logic.

        return True

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _find_leaked_components(self, objects: Dict[str, Any]) -> List[tuple]:
        """
        Return (field, value) pairs whose values appear in the tool graph.

        Used by both _check_no_leakage() and get_leaked_fields() to avoid
        duplicating the field-iteration logic.
        """
        leaked = []

        for field in PROTECTED_FIELDS:
            value = objects.get(field)
            if isinstance(value, str) and value in self.tool_graph_nodes:
                leaked.append((field, value))

        for field in PROTECTED_LIST_FIELDS:
            value = objects.get(field)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item in self.tool_graph_nodes:
                        leaked.append((f"{field}[]", item))

        return leaked

    # ------------------------------------------------------------------
    # Generic checks
    # ------------------------------------------------------------------

    def _check_required_fields(self, question: Dict[str, Any]) -> bool:
        """Check all required fields are present."""
        required = ["id", "category", "task_type", "text", "options", "correct_answer"]
        return all(field in question for field in required)

    def _check_options_format(self, question: Dict[str, Any]) -> bool:
        """Check options are properly formatted."""
        options = question.get("options", {})
        if not isinstance(options, dict) or len(options) == 0:
            return False
        return all(isinstance(key, str) and len(key) == 1 and key.isupper() for key in options)

    def _check_correct_answer(self, question: Dict[str, Any]) -> bool:
        """Check correct answer is in options (supports both single and multi-label)."""
        correct_answer = question.get("correct_answer")
        options = question.get("options", {})
        if isinstance(correct_answer, list):
            return all(letter in options for letter in correct_answer)
        return correct_answer in options

    def _check_descriptors_in_graph(self, question: Dict[str, Any]) -> bool:
        """Check all descriptors mentioned exist in graph."""
        objects = question.get("_objects", {})
        descriptor_keys = {"descriptor", "descriptor1", "descriptor2", "ancestor", "parent", "root", "root_category"}
        for key, value in objects.items():
            if key in descriptor_keys and isinstance(value, str):
                if value not in self.graph.descriptions:
                    return False
        return True

    def _check_no_duplicate_options(self, question: Dict[str, Any]) -> bool:
        """Check no duplicate option values."""
        values = list(question.get("options", {}).values())
        return len(values) == len(set(values))

    def _check_no_leakage(self, question: Dict[str, Any]) -> bool:
        """
        Check that no protected question components appear in the tool graph.

        Protected components (descriptors, siblings, distractors) must not be
        in the tool graph, as that would allow a tool-augmented model to look
        them up directly and solve the question mechanically.

        Structural components (parent, ancestor, lca) are allowed in the tool
        graph since they represent categorical information.
        """
        if not self.tool_graph_nodes:
            return True
        objects = question.get("_objects", {})
        return len(self._find_leaked_components(objects)) == 0

    def _check_no_root_system(self, question: Dict[str, Any]) -> bool:
        """
        Check that ROOT:SYSTEM does not appear in any field.

        ROOT:SYSTEM is a structural node in the graph and should never be used
        as a component in questions (descriptor, parent, ancestor, path, etc.).
        """
        objects = question.get("_objects", {})
        for value in objects.values():
            if isinstance(value, str) and 'ROOT:SYSTEM' in value:
                return False
            if isinstance(value, list):
                if any(isinstance(item, str) and 'ROOT:SYSTEM' in item for item in value):
                    return False
        return True

    def _check_no_text_overlap(self, question: Dict[str, Any]) -> bool:
        """
        Prevent questions solvable by name/text matching rather than graph reasoning.

        Rules by task type:
        - E1: reject if the CORRECT (closest) candidate shares words with the target.
              Distractors sharing words are fine — they act as traps.
        - E2: reject if the CORRECT (closer) option shares words with the target.
        - A1–A5: reject if the descriptor shares words with any option or its parent.
              Skipped for A4 where the descriptor must appear in the path options.
        """
        task_type = question.get("task_type", "")
        objects = question.get("_objects", {})

        if task_type == "A4_path_reconstruction":
            # Descriptor is part of the path, so overlap is expected and correct
            return True

        if task_type == "E1_similarity_ranking":
            target = objects.get("target", "")
            candidates = objects.get("candidates", [])
            # candidates[0] is the closest (correct answer)
            if target and candidates:
                if _tokenize(target) & _tokenize(candidates[0]):
                    return False
            return True

        if task_type == "E2_pairwise_comparison":
            target = objects.get("target", "")
            closer = objects.get("closer", "")
            if target and closer and (_tokenize(target) & _tokenize(closer)):
                return False
            return True

        # Default: check descriptor against options and parent
        descriptor = objects.get("descriptor", "")
        if not descriptor:
            return True

        desc_words = _tokenize(descriptor)
        if not desc_words:
            return True

        for option_text in question.get("options", {}).values():
            if desc_words & _tokenize(option_text):
                return False

        parent = objects.get("parent", "")
        if parent and (desc_words & _tokenize(parent)):
            return False

        return True

    # ------------------------------------------------------------------
    # Task-specific validators
    # ------------------------------------------------------------------

    def _validate_a1(self, question: Dict[str, Any]) -> bool:
        """
        Validate A1 (root classification) question.

        Supports both single-label and multi-label formats.

        Checks:
            1. Descriptor is in graph
            2. For multi-label: Correct answers match valid roots in options
            3. All options are valid roots
        """
        objects = question.get("_objects", {})
        descriptor = objects.get("descriptor")

        if not descriptor or descriptor not in self.graph.descriptions:
            return False

        answer_format = question.get("answer_format", "single")
        correct_answer = question["correct_answer"]
        options = question["options"]

        if answer_format == "multi_label" and isinstance(correct_answer, list):
            valid_roots_in_options = set(objects.get("valid_roots_in_options", []))
            marked_correct = set(options[letter] for letter in correct_answer)
            if marked_correct != valid_roots_in_options:
                return False
        else:
            correct_option_value = options[correct_answer]
            actual_root = self.graph.get_root_category(descriptor)
            if correct_option_value != actual_root:
                return False

        all_roots = set(self.graph.get_root_categories())
        return all(v in all_roots for v in options.values())

    def _validate_a2(self, question: Dict[str, Any]) -> bool:
        """
        Validate A2 (ancestor verification) question.

        Checks:
            1. Both descriptor and ancestor are in graph
            2. Correct answer matches actual ancestor relationship
        """
        objects = question.get("_objects", {})
        descriptor = objects.get("descriptor")
        ancestor = objects.get("ancestor")
        is_ancestor = objects.get("is_ancestor")

        if not descriptor or not ancestor:
            return False

        if descriptor not in self.graph.descriptions or ancestor not in self.graph.descriptions:
            return False

        actual_ancestors = self.graph.get_ancestors(descriptor)
        actually_is_ancestor = ancestor in actual_ancestors

        if is_ancestor != actually_is_ancestor:
            return False

        correct_letter = question["correct_answer"]
        options = question["options"]
        expected = "Yes" if is_ancestor else "No"
        return options[correct_letter] == expected

    # ------------------------------------------------------------------
    # Diagnostic utilities
    # ------------------------------------------------------------------

    def get_leaked_fields(self, question: Dict[str, Any]) -> List[str]:
        """
        Get list of fields that leak into the tool graph.

        Returns:
            List of "field_name: value" strings for leaked components.
        """
        if not self.tool_graph_nodes:
            return []
        objects = question.get("_objects", {})
        return [f"{field}: {value}" for field, value in self._find_leaked_components(objects)]

    def get_validation_report(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed validation report.

        Args:
            question: Question dict

        Returns:
            Dict with validation results and reasons

        Example:
            >>> report = validator.get_validation_report(question)
            >>> print(report["is_valid"])
            >>> print(report["errors"])
        """
        report = {"is_valid": True, "errors": [], "warnings": []}

        checks = [
            (self._check_required_fields, "Missing required fields"),
            (self._check_options_format, "Invalid options format"),
            (self._check_correct_answer, "Correct answer not in options"),
            (self._check_descriptors_in_graph, "Descriptor not found in graph"),
            (self._check_no_duplicate_options, "Duplicate option values"),
        ]

        for check_fn, error_msg in checks:
            if not check_fn(question):
                report["is_valid"] = False
                report["errors"].append(error_msg)

        if not self._check_no_leakage(question):
            report["is_valid"] = False
            leaked = self.get_leaked_fields(question)
            report["errors"].append(f"Data leakage: {', '.join(leaked)}")

        return report
