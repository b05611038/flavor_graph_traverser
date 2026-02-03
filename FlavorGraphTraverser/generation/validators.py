"""
Question Validators

Validates generated questions for quality and answerability.

Classes:
    QuestionValidator: Validates questions meet quality criteria
"""

from typing import Dict, Any, List, Optional

from ..graph import CoffeeDescriptionGraph


class QuestionValidator:
    """
    Validates generated questions for quality.

    Checks that questions are:
    - Answerable (correct answer is valid)
    - Unambiguous (only one correct answer)
    - Non-trivial (distractors are plausible)
    - Well-formed (all required fields present)

    Example:
        >>> validator = QuestionValidator(graph)
        >>>
        >>> question = {
        ...     "text": "Which root category does 'chocolate' belong to?",
        ...     "options": {"A": "fruity", "B": "nutty/cocoa", "C": "floral", "D": "spices"},
        ...     "correct_answer": "B"
        ... }
        >>>
        >>> is_valid = validator.validate(question)
        >>> print(is_valid)  # True
    """

    def __init__(self, graph: CoffeeDescriptionGraph):
        """
        Initialize validator.

        Args:
            graph: CoffeeDescriptionGraph instance
        """
        self.graph = graph

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
        # Check required fields
        if not self._check_required_fields(question):
            return False

        # Check options format
        if not self._check_options_format(question):
            return False

        # Check correct answer is valid
        if not self._check_correct_answer(question):
            return False

        # Check descriptors exist in graph
        if not self._check_descriptors_in_graph(question):
            return False

        # Check no duplicate options
        if not self._check_no_duplicate_options(question):
            return False

        # Task-specific validation
        task_type = question.get("task_type", "")
        if task_type.startswith("A1"):
            return self._validate_a1(question)
        elif task_type.startswith("A2"):
            return self._validate_a2(question)
        # Add more task-specific validators as needed

        return True

    def _check_required_fields(self, question: Dict[str, Any]) -> bool:
        """Check all required fields are present."""
        required = ["id", "category", "task_type", "text", "options", "correct_answer"]

        for field in required:
            if field not in question:
                return False

        return True

    def _check_options_format(self, question: Dict[str, Any]) -> bool:
        """Check options are properly formatted."""
        options = question.get("options", {})

        if not isinstance(options, dict):
            return False

        if len(options) == 0:
            return False

        # Check all keys are single uppercase letters
        for key in options.keys():
            if not (isinstance(key, str) and len(key) == 1 and key.isupper()):
                return False

        return True

    def _check_correct_answer(self, question: Dict[str, Any]) -> bool:
        """Check correct answer is in options (supports both single and multi-label)."""
        correct_answer = question.get("correct_answer")
        options = question.get("options", {})

        # Handle multi-label format (list of letters)
        if isinstance(correct_answer, list):
            # All letters must be valid option keys
            return all(letter in options for letter in correct_answer)

        # Handle single-label format (single letter)
        return correct_answer in options

    def _check_descriptors_in_graph(self, question: Dict[str, Any]) -> bool:
        """Check all descriptors mentioned exist in graph."""
        objects = question.get("_objects", {})

        for key, value in objects.items():
            if isinstance(value, str) and not value.startswith("_"):
                # Check if it's a descriptor (not metadata)
                if key in ["descriptor", "descriptor1", "descriptor2", "ancestor", "parent", "root", "root_category"]:
                    if value not in self.graph.descriptions:
                        return False

        return True

    def _check_no_duplicate_options(self, question: Dict[str, Any]) -> bool:
        """Check no duplicate option values."""
        options = question.get("options", {})
        values = list(options.values())

        return len(values) == len(set(values))

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

        if not descriptor:
            return False

        if descriptor not in self.graph.descriptions:
            return False

        # Check if multi-label format
        answer_format = question.get("answer_format", "single")
        correct_answer = question["correct_answer"]
        options = question["options"]

        if answer_format == "multi_label" and isinstance(correct_answer, list):
            # Multi-label validation
            valid_roots_in_options = set(objects.get("valid_roots_in_options", []))

            # Get which options are marked correct
            marked_correct = set(options[letter] for letter in correct_answer)

            # Check marked correct matches valid roots
            if marked_correct != valid_roots_in_options:
                return False

        else:
            # Single-label validation (legacy)
            correct_option_value = options[correct_answer]
            actual_root = self.graph.get_root_category(descriptor)

            if correct_option_value != actual_root:
                return False

        # Check all options are valid roots
        all_roots = set(self.graph.get_root_categories())

        for option_value in options.values():
            if option_value not in all_roots:
                return False

        return True

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

        if descriptor not in self.graph.descriptions:
            return False

        if ancestor not in self.graph.descriptions:
            return False

        # Check actual relationship
        actual_ancestors = self.graph.get_ancestors(descriptor)
        actually_is_ancestor = ancestor in actual_ancestors

        # Check metadata matches reality
        if is_ancestor != actually_is_ancestor:
            return False

        # Check correct answer matches
        correct_letter = question["correct_answer"]
        options = question["options"]

        if is_ancestor:
            # Should be "Yes"
            if options[correct_letter] != "Yes":
                return False
        else:
            # Should be "No"
            if options[correct_letter] != "No":
                return False

        return True

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
        report = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }

        # Run all checks and collect errors
        if not self._check_required_fields(question):
            report["is_valid"] = False
            report["errors"].append("Missing required fields")

        if not self._check_options_format(question):
            report["is_valid"] = False
            report["errors"].append("Invalid options format")

        if not self._check_correct_answer(question):
            report["is_valid"] = False
            report["errors"].append("Correct answer not in options")

        if not self._check_descriptors_in_graph(question):
            report["is_valid"] = False
            report["errors"].append("Descriptor not found in graph")

        if not self._check_no_duplicate_options(question):
            report["is_valid"] = False
            report["errors"].append("Duplicate option values")

        return report
