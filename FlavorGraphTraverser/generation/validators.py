"""
Question Validators

Validates generated questions for quality and answerability.

Classes:
    QuestionValidator: Validates questions meet quality criteria
"""

from typing import Dict, Any, List, Optional, Set

from ..graph import CoffeeDescriptionGraph

# Fields in _objects where values are specific descriptors that must NOT appear in the tool graph
PROTECTED_FIELDS = {
    'descriptor', 'descriptor1', 'descriptor2',
    'correct_sibling',
    'distractor1', 'distractor2', 'distractor3',
    'target', 'option1', 'option2',
    'closer', 'farther',
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

        # Check no data leakage (components in tool graph)
        if not self._check_no_leakage(question):
            return False

        # Check no ROOT:SYSTEM in any field (structural node, never valid in questions)
        if not self._check_no_root_system(question):
            return False

        # Check no text overlap (pattern matching prevention)
        if not self._check_no_text_overlap(question):
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
            return True  # No tool graph provided, skip check

        objects = question.get("_objects", {})

        # Check protected string fields
        for field in PROTECTED_FIELDS:
            value = objects.get(field)
            if isinstance(value, str) and value in self.tool_graph_nodes:
                return False

        # Check protected list fields
        for field in PROTECTED_LIST_FIELDS:
            value = objects.get(field)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item in self.tool_graph_nodes:
                        return False

        return True

    def _check_no_root_system(self, question: Dict[str, Any]) -> bool:
        """
        Check that ROOT:SYSTEM does not appear in any field.

        ROOT:SYSTEM is a structural node in the graph and should never be used
        as a component in questions (descriptor, parent, ancestor, path, etc.).
        This is a critical validation rule that applies to ALL fields.
        """
        objects = question.get("_objects", {})

        # Check all string fields
        for field, value in objects.items():
            if isinstance(value, str):
                if 'ROOT:SYSTEM' in value:
                    return False
            elif isinstance(value, list):
                # Check all list items
                for item in value:
                    if isinstance(item, str) and 'ROOT:SYSTEM' in item:
                        return False

        return True

    def _check_no_text_overlap(self, question: Dict[str, Any]) -> bool:
        """
        Check that the descriptor doesn't have significant word overlap with options.

        This prevents trivial pattern matching questions like:
        - "citrus" with option "orange fruit" (both contain "citrus")
        - "peanut butter" as descriptor with parent "peanut"
        - "chocolate" with option containing "chocolate"

        NOTE: Skipped for A4 (path reconstruction) questions where the descriptor
        MUST appear in the path options.

        Returns:
            True if no problematic overlap, False otherwise
        """
        import re

        # Skip check for A4 questions (descriptor must appear in path)
        task_type = question.get("task_type", "")
        if task_type == "A4_path_reconstruction":
            return True

        objects = question.get("_objects", {})
        descriptor = objects.get("descriptor", "")

        if not descriptor:
            return True

        # Normalize descriptor to words
        desc_words = set(re.findall(r'\b\w+\b', descriptor.lower()))

        # Remove common stop words that don't indicate pattern matching
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
        desc_words = desc_words - stop_words

        if not desc_words:
            return True

        # Check descriptor vs options (from question options dict)
        options = question.get("options", {})
        for option_text in options.values():
            option_words = set(re.findall(r'\b\w+\b', option_text.lower()))
            option_words = option_words - stop_words

            # If there's any meaningful word overlap, it's pattern matching
            overlap = desc_words & option_words
            if overlap:
                return False

        # Check descriptor vs parent (catches nutty/cocoa issues)
        parent = objects.get("parent", "")
        if parent:
            parent_words = set(re.findall(r'\b\w+\b', parent.lower()))
            parent_words = parent_words - stop_words
            overlap = desc_words & parent_words
            if overlap:
                return False

        return True

    def get_leaked_fields(self, question: Dict[str, Any]) -> List[str]:
        """
        Get list of fields that leak into the tool graph.

        Returns:
            List of "field_name: value" strings for leaked components.
        """
        if not self.tool_graph_nodes:
            return []

        leaked = []
        objects = question.get("_objects", {})

        for field in PROTECTED_FIELDS:
            value = objects.get(field)
            if isinstance(value, str) and value in self.tool_graph_nodes:
                leaked.append(f"{field}: {value}")

        for field in PROTECTED_LIST_FIELDS:
            value = objects.get(field)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item in self.tool_graph_nodes:
                        leaked.append(f"{field}[]: {item}")

        return leaked

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

        if not self._check_no_leakage(question):
            report["is_valid"] = False
            leaked = self.get_leaked_fields(question)
            report["errors"].append(f"Data leakage: {', '.join(leaked)}")

        return report
