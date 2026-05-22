"""
Question Generator

Generates benchmark questions from coffee flavor graph using templates.

Architecture:
    QuestionGenerator (orchestrator)
    ├── DescriptorSampler (sample nodes from graph)
    ├── DistractorGenerator (generate wrong answers)
    └── QuestionValidator (validate question quality)

Example:
    >>> from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
    >>> from FlavorGraphTraverser.generation import QuestionGenerator
    >>>
    >>> data = load_graph_data("data/graphs/coffee_flavor_wheel.json")
    >>> graph = CoffeeDescriptionGraph(data['descriptions'], data['connections'], root=data['root'])
    >>>
    >>> generator = QuestionGenerator(graph)
    >>> questions = generator.generate_all()  # Generate ~275 questions
    >>> generator.save_questions(questions, "data/questions/generated.json")
"""

import json
import random
import yaml
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict

from ..graph import CoffeeDescriptionGraph
from .samplers import DescriptorSampler, DistractorGenerator
from .validators import QuestionValidator


@dataclass
class QuestionTemplate:
    """
    Template for generating questions.

    Attributes:
        task_type: Type of task (e.g., "A1_root_classification")
        template: Question text template with placeholders
        count: Number of questions to generate
        sampling: Sampling strategy configuration
        validation: Validation rules
        options: Option generation configuration
    """
    task_type: str
    template: str
    count: int
    sampling: Dict[str, Any]
    validation: List[str]
    options: Optional[Dict[str, Any]] = None
    description: str = ""


class QuestionGenerator:
    """
    Generates benchmark questions from coffee flavor graph.

    Uses template-based generation with sampling strategies to create
    diverse, high-quality questions across multiple task types.

    Attributes:
        graph: CoffeeDescriptionGraph instance
        templates: Loaded question templates
        sampler: DescriptorSampler for sampling nodes
        distractor_gen: DistractorGenerator for wrong answers
        validator: QuestionValidator for quality checks
        random_seed: Random seed for reproducibility

    Example:
        >>> generator = QuestionGenerator(graph)
        >>>
        >>> # Generate all questions
        >>> questions = generator.generate_all()
        >>> print(f"Generated {len(questions)} questions")
        >>>
        >>> # Generate specific category
        >>> a1_questions = generator.generate_category("A1_root_classification")
        >>>
        >>> # Save to file
        >>> generator.save_questions(questions, "output.json")
    """

    def __init__(
        self,
        graph: CoffeeDescriptionGraph,
        templates_path: Optional[str] = None,
        random_seed: Optional[int] = None,
        exclude_descriptors: Optional[set] = None,
        tool_graph_nodes: Optional[set] = None,
        existing_questions: Optional[List[Dict]] = None,
    ):
        """
        Initialize question generator.

        Args:
            graph: CoffeeDescriptionGraph instance
            templates_path: Path to templates YAML (default: configs/question_templates.yaml)
            random_seed: Random seed for reproducibility (default: from config or 42)
            exclude_descriptors: Set of descriptors to exclude from sampling (e.g., to prevent data leakage)
            tool_graph_nodes: Set of ALL node names in the tool graph. Used by the validator to reject
                              questions where any component (descriptor, sibling, distractor) appears
                              in the tool graph.
            existing_questions: All previously generated questions (confirmed, flagged, AND pending).
                                Used to prevent regenerating duplicate targets/pairs across runs.
        """
        self.graph = graph
        self.exclude_descriptors = exclude_descriptors or set()
        self.tool_graph_nodes = tool_graph_nodes or set()

        # Build used-descriptor sets from existing questions to prevent repetition.
        # E1/E2/F targets: block from confirmed + flagged + pending to avoid repeats.
        # E3 parents: block from confirmed + flagged so the generator never reuses a parent
        #             the user has already seen (whether accepted or rejected).
        #             Pending E3 parents remain available for regeneration.
        self._used_targets: set = set()           # targets already used in E1/E2/F
        self._used_e3_parents: set = set()        # similar_parent used in confirmed/flagged E3
        self._used_e1_candidate_sets: set = set() # frozensets of E1 candidate triplets
        self._used_e2_candidate_pairs: set = set() # frozensets of E2 (closer, farther) pairs
        for q in (existing_questions or []):
            obj = q.get('_objects', {})
            tt = q.get('task_type', '')
            audit_status = q.get('_audit_status', 'pending')  # injected by caller
            if tt in ('E1_similarity_ranking', 'E2_pairwise_comparison', 'F_flavor_description'):
                t = obj.get('target', '')
                if t:
                    self._used_targets.add(t)
            if tt == 'E1_similarity_ranking':
                cands = obj.get('candidates', [])
                if cands:
                    self._used_e1_candidate_sets.add(frozenset(cands))
            elif tt == 'E2_pairwise_comparison':
                pair = frozenset([obj.get('closer', ''), obj.get('farther', '')])
                if all(pair):
                    self._used_e2_candidate_pairs.add(pair)
            elif tt == 'E3_odd_one_out' and audit_status == 'confirmed':
                p = obj.get('similar_parent', '')
                if p:
                    self._used_e3_parents.add(p)

        # Load templates
        if templates_path is None:
            project_root = Path(__file__).parent.parent.parent
            templates_path = project_root / "configs" / "question_templates.yaml"

        with open(templates_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Set random seed
        self.random_seed = random_seed or self.config.get("settings", {}).get("random_seed", 42)
        random.seed(self.random_seed)

        # Initialize components with exclusion list
        self.sampler = DescriptorSampler(
            graph,
            random_seed=self.random_seed,
            global_exclude=self.exclude_descriptors
        )
        self.distractor_gen = DistractorGenerator(graph, random_seed=self.random_seed)
        self.validator = QuestionValidator(graph, tool_graph_nodes=self.tool_graph_nodes)

        # Track descriptor usage for diversity (per task type)
        self.descriptor_usage_by_type = defaultdict(lambda: defaultdict(int))
        # Also keep global usage for cross-type diversity
        self.descriptor_usage = defaultdict(int)
        self.max_reuse = self.config.get("settings", {}).get("diversity", {}).get("max_descriptor_reuse", 3)

    @staticmethod
    def _generate_uuid_id(task_type: str) -> str:
        """
        Generate unique ID using UUID4.

        Args:
            task_type: Task type prefix (e.g., "A2_ancestor_verification")

        Returns:
            ID like "A2_ancestor_verification_a1b2c3d4"

        Example:
            >>> QuestionGenerator._generate_uuid_id("A2_ancestor_verification")
            "A2_ancestor_verification_f47ac10b"
        """
        # Generate UUID4 and take first 8 characters
        uuid_str = str(uuid.uuid4()).replace('-', '')[:8]
        return f"{task_type}_{uuid_str}"

    def generate_all(self) -> List[Dict[str, Any]]:
        """
        Generate all questions across all categories.

        Returns:
            List of question dicts

        Example:
            >>> questions = generator.generate_all()
            >>> print(f"Total: {len(questions)}")
            >>> print(f"Categories: {set(q['category'] for q in questions)}")
        """
        all_questions = []

        # Category A: Taxonomic
        for task_type, template_config in self.config.get("taxonomic", {}).items():
            questions = self.generate_category(task_type, template_config)
            all_questions.extend(questions)

        # Category E: Similarity
        for task_type, template_config in self.config.get("similarity", {}).items():
            questions = self.generate_category(task_type, template_config)
            all_questions.extend(questions)

        # Category F: Open-ended
        for task_type, template_config in self.config.get("open_ended", {}).items():
            questions = self.generate_category(task_type, template_config)
            all_questions.extend(questions)

        return all_questions

    def generate_category(
        self,
        task_type: str,
        template_config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate questions for a specific category.

        Args:
            task_type: Task type (e.g., "A1_root_classification")
            template_config: Template configuration (default: load from config)

        Returns:
            List of question dicts

        Example:
            >>> questions = generator.generate_category("A1_root_classification")
            >>> print(f"Generated {len(questions)} A1 questions")
        """
        # Get template config
        if template_config is None:
            template_config = self._find_template_config(task_type)

        if template_config is None:
            raise ValueError(f"Template not found for task type: {task_type}")

        # Determine which generation method to use
        category_prefix = task_type.split("_")[0]

        if category_prefix == "A1":
            return self._generate_a1(task_type, template_config)
        elif category_prefix == "A2":
            return self._generate_a2(task_type, template_config)
        elif category_prefix == "A3":
            return self._generate_a3(task_type, template_config)
        elif category_prefix == "A4":
            return self._generate_a4(task_type, template_config)
        elif category_prefix == "A5":
            return self._generate_a5(task_type, template_config)
        elif category_prefix == "E1":
            return self._generate_e1(task_type, template_config)
        elif category_prefix == "E2":
            return self._generate_e2(task_type, template_config)
        elif category_prefix == "E3":
            return self._generate_e3(task_type, template_config)
        elif category_prefix == "F":
            return self._generate_f(task_type, template_config)
        else:
            raise ValueError(f"Unknown task type prefix: {category_prefix}")

    def _find_template_config(self, task_type: str) -> Optional[Dict[str, Any]]:
        """Find template config for task type."""
        for category in ["taxonomic", "similarity", "open_ended"]:
            if task_type in self.config.get(category, {}):
                return self.config[category][task_type]
        return None

    def _get_all_root_categories(self, descriptor: str) -> list:
        """
        Get ALL root categories that a descriptor belongs to (DAG-aware).

        In a DAG, a node can have multiple parents leading to different roots.

        Args:
            descriptor: The descriptor to check

        Returns:
            List of all valid root categories
        """
        # Get all direct parents using graph's built-in method
        all_parents = self.graph.parents_of_description(descriptor)

        # Get root category for each parent
        root_categories = set()
        for parent in all_parents:
            try:
                root = self.graph.get_root_category(parent)
                if root:
                    root_categories.add(root)
            except Exception:
                pass

        return sorted(list(root_categories))

    def _generate_a1(self, task_type: str, config: Dict) -> List[Dict]:
        """
        Generate A1 (root classification) questions with multi-label format.

        Template: "Which of the following are root categories that '{descriptor}' belongs to? (Select all that apply)"

        Strategy:
            1. Sample leaf descriptor
            2. Get ALL its root categories (DAG-aware) - these are valid
            3. Sample 3-4 invalid roots as distractors
            4. Present 5-6 options total (mix valid + invalid)
            5. Correct answer = ALL valid roots in the options
            6. Format supports 0, 1, or multiple correct answers
        """
        questions = []
        count = config["count"]
        template = "Which of the following are root categories that '{descriptor}' belongs to? (Select all that apply)"

        # Get all roots for sampling, exclude non-flavor roots
        all_roots = self.graph.get_root_categories()

        # Filter out non-flavor root categories
        # Note: 'defected' is kept but will display as 'other' in options
        non_flavor_roots = {'taste', 'baked', 'ROOT:SYSTEM'}
        all_roots = [r for r in all_roots if r not in non_flavor_roots]

        # Track descriptors used in this task type to prevent duplicates
        type_usage = self.descriptor_usage_by_type[task_type]

        for i in range(count):
            # Sample leaf descriptor (exclude already used in this task type ONLY)
            # Note: Descriptors can be reused across different task types
            used_in_type = {d for d, c in type_usage.items() if c > 0}
            descriptor = self.sampler.sample_leaf(
                exclude=used_in_type,
                exclude_overused=False,  # Allow reuse across task types
                max_usage=None,  # No global limit
                usage_tracker=None  # Don't track global usage
            )

            if descriptor is None:
                continue  # Skip if no valid descriptor

            # Get ALL valid root categories (DAG-aware)
            valid_roots = self._get_all_root_categories(descriptor)

            if not valid_roots:
                continue  # Skip if no valid roots found

            # Get invalid roots
            invalid_roots = [r for r in all_roots if r not in valid_roots]

            # Decide how many options to present (5 or 6)
            num_options = random.choice([5, 6])

            # Decide mix: include some valid, some invalid
            # Ensure at least 1 valid and at least 2 invalid for complexity
            num_valid_in_options = min(len(valid_roots), num_options - 2)  # Leave room for distractors
            num_invalid_in_options = num_options - num_valid_in_options

            if len(invalid_roots) < num_invalid_in_options:
                continue  # Skip if not enough invalid roots

            # Sample which valid roots to include
            if num_valid_in_options < len(valid_roots):
                valid_in_options = random.sample(valid_roots, num_valid_in_options)
            else:
                valid_in_options = valid_roots.copy()

            # Sample invalid roots
            invalid_in_options = random.sample(invalid_roots, num_invalid_in_options)

            # Combine all options and shuffle
            all_options = valid_in_options + invalid_in_options
            random.shuffle(all_options)

            # Create options dict with letters A-F
            letters = ['A', 'B', 'C', 'D', 'E', 'F'][:num_options]
            options = {letter: option for letter, option in zip(letters, all_options)}

            # Map 'defected' to 'other' for display (graph uses 'defected' internally)
            display_options = {
                letter: ('other' if value == 'defected' else value)
                for letter, value in options.items()
            }

            # Find which letters are correct (valid roots) - use original options for comparison
            correct_letters = [letter for letter, root in options.items() if root in valid_in_options]

            # Format answer as list (can be empty, single, or multiple)
            correct_answer = sorted(correct_letters)  # Sort for consistency

            # Format question text with conditional footnote for 'other'
            question_text = template.format(descriptor=descriptor)
            if 'other' in display_options.values():
                question_text += "\n\n*'other' includes non-standard or less common flavor categories"

            # Create question with UUID-based ID
            content_id = self._generate_uuid_id(task_type)

            question = {
                "id": content_id,
                "category": "A",
                "task_type": task_type,
                "text": question_text,
                "options": display_options,  # Use display options with 'other' instead of 'defected'
                "correct_answer": correct_answer,  # List of correct letters
                "answer_format": "multi_label",  # Indicates multiple selections allowed
                "_template": template,
                "_objects": {
                    "descriptor": descriptor,
                    "all_valid_roots": valid_roots,  # ALL valid roots in entire graph
                    "valid_roots_in_options": valid_in_options,  # Valid roots shown in this question
                    "invalid_roots_in_options": invalid_in_options,  # Invalid roots shown
                },
                "_evaluation_note": "Multi-label: Model must select ALL and ONLY the valid roots in options. Can be 0, 1, or multiple correct answers."
            }

            # Validate (includes leakage check)
            if self.validator.validate(question):
                questions.append(question)
                self.descriptor_usage[descriptor] += 1
                type_usage[descriptor] += 1

        return questions

    def _generate_a2(self, task_type: str, config: Dict) -> List[Dict]:
        """
        Generate A2 (ancestor verification) questions.

        Template: "Is '{ancestor}' an ancestor of '{descriptor}'?"

        Strategy:
            1. Sample descriptor
            2. 50% true: sample actual ancestor
            3. 50% false: sample plausible non-ancestor
            4. Create Yes/No options
        """
        questions = []
        count = config["count"]
        # Handle both "template" and "templates"
        if "templates" in config:
            templates = config["templates"]
        elif "template" in config:
            templates = [config["template"]]
        else:
            raise ValueError("Config must have 'template' or 'templates' field")

        true_count = count // 2
        false_count = count - true_count

        # Track descriptors used in this task type
        type_usage = self.descriptor_usage_by_type[task_type]

        # Generate TRUE questions
        for i in range(true_count):
            used_in_type = {d for d, c in type_usage.items() if c > 0}
            descriptor = self.sampler.sample_any(
                exclude=used_in_type,
                exclude_overused=True,
                max_usage=self.max_reuse,
                usage_tracker=self.descriptor_usage
            )

            if descriptor is None:
                continue

            # Sample actual ancestor
            ancestors = self.graph.get_ancestors(descriptor)
            if not ancestors:
                continue

            ancestor = random.choice(ancestors)
            template = random.choice(templates)

            # Generate UUID-based ID
            content_id = self._generate_uuid_id(task_type)

            question = {
                "id": content_id,
                "category": "A",
                "task_type": task_type,
                "text": template.format(descriptor=descriptor, ancestor=ancestor),
                "options": {"A": "Yes", "B": "No"},
                "correct_answer": "A",
                "_template": template,
                "_objects": {
                    "descriptor": descriptor,
                    "ancestor": ancestor,
                    "is_ancestor": True
                }
            }

            if self.validator.validate(question):
                questions.append(question)
                self.descriptor_usage[descriptor] += 1
                type_usage[descriptor] += 1

        # Generate FALSE questions
        for i in range(false_count):
            used_in_type = {d for d, c in type_usage.items() if c > 0}
            descriptor = self.sampler.sample_any(
                exclude=used_in_type,
                exclude_overused=True,
                max_usage=self.max_reuse,
                usage_tracker=self.descriptor_usage
            )

            if descriptor is None:
                continue

            # Sample plausible non-ancestor
            non_ancestor = self.distractor_gen.sample_plausible_non_ancestor(descriptor)

            if non_ancestor is None:
                continue

            template = random.choice(templates)

            # Generate UUID-based ID
            content_id = self._generate_uuid_id(task_type)

            question = {
                "id": content_id,
                "category": "A",
                "task_type": task_type,
                "text": template.format(descriptor=descriptor, ancestor=non_ancestor),
                "options": {"A": "Yes", "B": "No"},
                "correct_answer": "B",
                "_template": template,
                "_objects": {
                    "descriptor": descriptor,
                    "ancestor": non_ancestor,
                    "is_ancestor": False
                }
            }

            if self.validator.validate(question):
                questions.append(question)
                self.descriptor_usage[descriptor] += 1
                type_usage[descriptor] += 1

        return questions

    def _generate_a3(self, task_type: str, config: Dict) -> List[Dict]:
        """
        Generate A3 (sibling identification) questions.

        Template: "Which of the following shares the same parent as '{descriptor}'?"

        Strategy:
            1. Sample middle descriptor (has siblings)
            2. Get its siblings (same parent)
            3. Sample one sibling as correct answer
            4. Generate distractors: cousins, uncles, unrelated
        """
        questions = []
        count = config["count"]
        template = config["template"]

        # Try more attempts to reach target count
        max_attempts = count * 10
        attempts = 0

        # Track descriptors used in this task type
        type_usage = self.descriptor_usage_by_type[task_type]

        while len(questions) < count and attempts < max_attempts:
            attempts += 1

            # Sample middle descriptor (exclude already used in this task type)
            used_in_type = {d for d, c in type_usage.items() if c > 0}
            descriptor = self.sampler.sample_middle(
                exclude=used_in_type,
                exclude_overused=True,
                max_usage=self.max_reuse,
                usage_tracker=self.descriptor_usage
            )

            if descriptor is None:
                continue

            # Get siblings
            parent = self.graph.get_parent(descriptor)
            if parent is None:
                continue

            siblings = [s for s in self.graph.get_children(parent) if s != descriptor]
            if not siblings:
                continue  # No siblings

            # Pick one sibling as correct answer
            correct_sibling = random.choice(siblings)

            # Generate distractors
            distractors = self.distractor_gen.sample_non_siblings(
                descriptor=descriptor,
                parent=parent,
                count=3
            )

            if len(distractors) < 3:
                continue  # Not enough distractors

            # Create options
            options, correct_letter = self._create_multiple_choice_options(
                correct_answer=correct_sibling,
                distractors=distractors
            )

            # Generate UUID-based ID
            content_id = self._generate_uuid_id(task_type)

            question = {
                "id": content_id,
                "category": "A",
                "task_type": task_type,
                "text": template.format(descriptor=descriptor),
                "options": options,
                "correct_answer": correct_letter,
                "_template": template,
                "_objects": {
                    "descriptor": descriptor,
                    "parent": parent,
                    "correct_sibling": correct_sibling,
                    **{f"distractor{j+1}": d for j, d in enumerate(distractors)}
                }
            }

            # Validate (includes leakage check for descriptor, sibling, and distractors)
            if self.validator.validate(question):
                questions.append(question)
                self.descriptor_usage[descriptor] += 1
                type_usage[descriptor] += 1

        return questions

    def _generate_a4(self, task_type: str, config: Dict) -> List[Dict]:
        """
        Generate A4 (path reconstruction) questions.

        Template: "What is the path from the root to '{descriptor}'?"

        Strategy:
            1. Sample leaf descriptor (at least depth 3)
            2. Get correct path: root → ... → descriptor
            3. Generate distractors: wrong root, wrong middle, wrong order
        """
        questions = []
        count = config["count"]
        template = config["template"]

        # Track descriptors used in this task type
        type_usage = self.descriptor_usage_by_type[task_type]

        for i in range(count):
            # Sample leaf descriptor (exclude already used in this task type ONLY)
            # Note: Descriptors can be reused across different task types
            used_in_type = {d for d, c in type_usage.items() if c > 0}
            descriptor = self.sampler.sample_leaf(
                exclude=used_in_type,
                exclude_overused=False,  # Allow reuse across task types
                max_usage=None,  # No global limit
                usage_tracker=None  # Don't track global usage
            )

            if descriptor is None:
                continue

            # Get path from root
            ancestors = self.graph.get_ancestors(descriptor)
            if len(ancestors) < 2:  # Need at least depth 3 (root + 1 middle + descriptor)
                continue

            # Build correct path (root → ... → descriptor)
            correct_path = " → ".join(list(reversed(ancestors)) + [descriptor])

            # Generate distractor paths
            distractors = self.distractor_gen.generate_wrong_paths(
                descriptor=descriptor,
                correct_path_list=list(reversed(ancestors)) + [descriptor],
                count=3
            )

            if len(distractors) < 3:
                continue

            # Create options
            options, correct_letter = self._create_multiple_choice_options(
                correct_answer=correct_path,
                distractors=distractors
            )

            # Generate UUID-based ID
            content_id = self._generate_uuid_id(task_type)

            question = {
                "id": content_id,
                "category": "A",
                "task_type": task_type,
                "text": template.format(descriptor=descriptor),
                "options": options,
                "correct_answer": correct_letter,
                "_template": template,
                "_objects": {
                    "descriptor": descriptor,
                    "correct_path": correct_path,
                    **{f"distractor{j+1}": d for j, d in enumerate(distractors)}
                }
            }

            if self.validator.validate(question):
                questions.append(question)
                self.descriptor_usage[descriptor] += 1
                type_usage[descriptor] += 1

        return questions

    def _generate_a5(self, task_type: str, config: Dict) -> List[Dict]:
        """
        Generate A5 (LCA finding) questions.

        Template: "What is the lowest common ancestor of '{descriptor1}' and '{descriptor2}'?"

        Strategy:
            1. Sample two descriptors
            2. Find their lowest common ancestor (LCA)
            3. Generate distractors: too high (e.g., root), too low, ancestor of only one
        """
        questions = []
        count = config["count"]
        template = config["template"]

        # Track descriptors used in this task type
        type_usage = self.descriptor_usage_by_type[task_type]

        for i in range(count):
            # Sample first descriptor (exclude already used in this task type)
            used_in_type = {d for d, c in type_usage.items() if c > 0}
            descriptor1 = self.sampler.sample_any(
                exclude=used_in_type,
                exclude_overused=True,
                max_usage=self.max_reuse,
                usage_tracker=self.descriptor_usage
            )

            if descriptor1 is None:
                continue

            # Sample second descriptor (different from first and not used in type)
            descriptor2 = self.sampler.sample_any(
                exclude=used_in_type | {descriptor1},
                exclude_overused=True,
                max_usage=self.max_reuse,
                usage_tracker=self.descriptor_usage
            )

            if descriptor2 is None:
                continue

            # Find LCA
            lca = self.graph.find_lca(descriptor1, descriptor2)
            if lca is None:
                continue

            # Generate distractors
            distractors = self.distractor_gen.generate_lca_distractors(
                descriptor1=descriptor1,
                descriptor2=descriptor2,
                correct_lca=lca,
                count=3
            )

            if len(distractors) < 3:
                continue

            # Create options
            options, correct_letter = self._create_multiple_choice_options(
                correct_answer=lca,
                distractors=distractors
            )

            # Generate UUID-based ID
            content_id = self._generate_uuid_id(task_type)

            question = {
                "id": content_id,
                "category": "A",
                "task_type": task_type,
                "text": template.format(descriptor1=descriptor1, descriptor2=descriptor2),
                "options": options,
                "correct_answer": correct_letter,
                "_template": template,
                "_objects": {
                    "descriptor1": descriptor1,
                    "descriptor2": descriptor2,
                    "lca": lca,
                    **{f"distractor{j+1}": d for j, d in enumerate(distractors)}
                }
            }

            if self.validator.validate(question):
                questions.append(question)
                self.descriptor_usage[descriptor1] += 1
                self.descriptor_usage[descriptor2] += 1
                type_usage[descriptor1] += 1
                type_usage[descriptor2] += 1

        return questions

    def _generate_e1(self, task_type: str, config: Dict) -> List[Dict]:
        """
        Generate E1 (similarity ranking) questions.

        Template: "Rank these flavors from most similar to '{target}' to least similar: [{candidates}]"

        Strategy:
            1. Sample target descriptor
            2. Sample 3 candidates at different distances
            3. Correct answer is ranking by distance (shorter = more similar)
            4. Generate distractor rankings
        """
        questions = []
        count = config["count"]
        template = config["template"]
        candidate_count = config.get("candidate_count", 3)

        # Track descriptors used in this task type
        type_usage = self.descriptor_usage_by_type[task_type]

        for i in range(count):
            # Sample target — exclude targets already used in any existing question
            used_in_type = {d for d, c in type_usage.items() if c > 0}
            target = self.sampler.sample_any(
                exclude=used_in_type | self._used_targets,
                exclude_overused=True,
                max_usage=self.max_reuse,
                usage_tracker=self.descriptor_usage
            )

            if target is None:
                continue

            # Sample candidates at different distances
            candidates_with_distances = self.sampler.sample_by_distance(
                target=target,
                count=candidate_count,
                require_different_distances=True
            )

            if len(candidates_with_distances) < candidate_count:
                continue

            # Sort by distance (ascending = most similar first)
            candidates_sorted = [c for c, d in sorted(candidates_with_distances, key=lambda x: x[1])]

            # Skip if this exact candidate set was already used in a previous question
            if frozenset(candidates_sorted) in self._used_e1_candidate_sets:
                continue

            # Map 'defected' -> 'other' for display
            candidates_sorted = [('other' if c == 'defected' else c) for c in candidates_sorted]
            target_display = 'other' if target == 'defected' else target

            # Build correct ranking string
            correct_ranking = " > ".join(candidates_sorted)

            # Build candidate list string for question
            candidates_str = ", ".join(candidates_sorted)

            # Generate distractor rankings
            distractors = self.distractor_gen.generate_wrong_rankings(
                candidates=candidates_sorted,
                count=3
            )

            if len(distractors) < 3:
                continue

            # Create options
            options, correct_letter = self._create_multiple_choice_options(
                correct_answer=correct_ranking,
                distractors=distractors
            )

            # Add footnote if 'other' appears anywhere
            question_text = template.format(target=target_display, candidates=candidates_str)
            has_other = 'other' in candidates_sorted or target_display == 'other'
            if has_other:
                question_text += "\n\n*'other' includes non-standard or less common flavor categories"

            # Generate UUID-based ID (E1)
            content_id = self._generate_uuid_id(task_type)

            question = {
                "id": content_id,
                "category": "E",
                "task_type": task_type,
                "text": question_text,
                "options": options,
                "correct_answer": correct_letter,
                "_template": template,
                "_objects": {
                    "target": target,
                    "candidates": candidates_sorted,
                    "correct_ranking": correct_ranking,
                    **{f"distractor{j+1}": d for j, d in enumerate(distractors)}
                }
            }

            if self.validator.validate(question):
                questions.append(question)
                self.descriptor_usage[target] += 1
                type_usage[target] += 1
                self._used_targets.add(target)
                self._used_e1_candidate_sets.add(frozenset(candidates_sorted))

        return questions

    def _generate_e2(self, task_type: str, config: Dict) -> List[Dict]:
        """
        Generate E2 (3-way similarity choice) questions.

        Template: "Which is most similar to '{target}': '{option1}', '{option2}', or '{option3}'?"

        Strategy:
            1. Sample target descriptor
            2. Sample 3 candidates at strictly increasing distances (d1 < d2 < d3)
            3. Closest one (d1) is the correct answer
            4. Shuffle options before presenting

        Difficulty: random baseline is 33% (vs 50% for old binary format).
        All candidates are in the same root-category branch as the target.
        """
        questions = []
        count = config["count"]

        template = config.get(
            "template",
            "Which of the following flavors is most similar to '{target}'?"
        )

        min_distance_diff = config.get("min_distance_diff", 1)
        min_closer_distance = config.get("min_closer_distance", 2)

        # Track descriptors used in this task type
        type_usage = self.descriptor_usage_by_type[task_type]

        for i in range(count):
            # Sample target — exclude targets already used in any existing question
            used_in_type = {d for d, c in type_usage.items() if c > 0}
            target = self.sampler.sample_any(
                exclude=used_in_type | self._used_targets,
                exclude_overused=True,
                max_usage=self.max_reuse,
                usage_tracker=self.descriptor_usage
            )

            if target is None:
                continue

            # Sample 3 candidates at different distances (same branch as target)
            options_with_distances = self.sampler.sample_by_distance(
                target=target,
                count=3,
                require_different_distances=True,
                min_difference=min_distance_diff
            )

            if len(options_with_distances) < 3:
                continue

            # Sort by distance: closest first
            options_sorted = sorted(options_with_distances, key=lambda x: x[1])
            closer = options_sorted[0][0]   # correct answer
            middle = options_sorted[1][0]   # distractor
            farther = options_sorted[2][0]  # distractor

            # Skip if correct answer is too close (trivial name/semantic match)
            if options_sorted[0][1] < min_closer_distance:
                continue

            # Skip if this candidate set was already used
            candidate_set = frozenset([closer, middle, farther])
            if candidate_set in self._used_e2_candidate_pairs:
                continue

            # Map 'defected' -> 'other' for display
            target_display = 'other' if target == 'defected' else target
            closer_d  = 'other' if closer  == 'defected' else closer
            middle_d  = 'other' if middle  == 'defected' else middle
            farther_d = 'other' if farther == 'defected' else farther

            # Shuffle the 3 options and find correct letter
            all_opts = [closer_d, middle_d, farther_d]
            random.shuffle(all_opts)
            letters = ['A', 'B', 'C']
            options = {letter: opt for letter, opt in zip(letters, all_opts)}
            correct_answer = [k for k, v in options.items() if v == closer_d][0]

            # Build question text (options are shown separately as A/B/C)
            question_text = template.format(target=target_display)
            if 'other' in (target_display, closer_d, middle_d, farther_d):
                question_text += "\n\n*'other' includes non-standard or less common flavor categories"

            content_id = self._generate_uuid_id(task_type)

            question = {
                "id": content_id,
                "category": "E",
                "task_type": task_type,
                "text": question_text,
                "options": options,
                "correct_answer": correct_answer,
                "_template": template,
                "_objects": {
                    "target": target,
                    "closer": closer,
                    "middle": middle,
                    "farther": farther,
                    "option1": all_opts[0],
                    "option2": all_opts[1],
                    "option3": all_opts[2],
                }
            }

            if self.validator.validate(question):
                questions.append(question)
                self.descriptor_usage[target] += 1
                type_usage[target] += 1
                self._used_targets.add(target)
                self._used_e2_candidate_pairs.add(candidate_set)

        return questions

    def _generate_e3(self, task_type: str, config: Dict) -> List[Dict]:
        """
        Generate E3 (odd one out) questions.

        Template: "Which of these is the odd one out: [{candidates}]"

        Strategy:
            1. Sample a parent node with >= 3 valid children
            2. Sample 3 children as similar group
            3. Sample odd one from a DIFFERENT root category
            4. Shuffle and present

        Quality constraints:
            - Odd one must be from a different root category than siblings (strict separation)
            - No shared words among siblings (prevents trivial name-pattern detection)
            - No shared words between odd one and any sibling (prevents giveaway)
            - Minimum node name length >= 3 chars (filters noise like 'me', 'old')
            - Minimum node depth >= 2 from root (filters generic category names)
        """
        questions = []
        count = config["count"]
        template = config["template"]
        max_attempts = count * 30
        attempts = 0

        type_usage = self.descriptor_usage_by_type[task_type]

        # Build root-category lookup
        root_categories = set(self.graph.get_children('ROOT:SYSTEM'))

        def get_root(node):
            if node in root_categories:
                return node
            visited = {node}
            queue = [node]
            while queue:
                n = queue.pop(0)
                p = self.graph.get_parent(n)
                if p is None or p == 'ROOT:SYSTEM':
                    return n
                if p in root_categories:
                    return p
                if p not in visited:
                    visited.add(p)
                    queue.append(p)
            return node

        def get_depth(node):
            depth = 0
            n = node
            while True:
                p = self.graph.get_parent(n)
                if p is None or p == 'ROOT:SYSTEM':
                    return depth
                depth += 1
                n = p

        def words(name):
            return set(name.lower().split())

        def normalize(name):
            """Remove spaces/hyphens for near-duplicate detection."""
            return name.lower().replace(' ', '').replace('-', '')

        def has_near_duplicate(group):
            """True if any two nodes are essentially the same after normalization.
            e.g. 'redcurrant' vs 'red currant jam' share 'redcurrant' as prefix."""
            norms = [normalize(n) for n in group]
            for i in range(len(norms)):
                for j in range(i + 1, len(norms)):
                    a, b = norms[i], norms[j]
                    # One is a prefix of the other (e.g. 'redcurrant' in 'redcurrantjam')
                    if a.startswith(b) or b.startswith(a):
                        return True
            return False

        def has_common_root_word(group):
            """True if a significant word (len>=4) appears as substring in ALL siblings.
            Catches cases like 'herb tea', 'vanilla herb', 'herbal tea' where 'herb'
            appears in all three (exact or as prefix of 'herbal')."""
            all_lower = [n.lower() for n in group]
            # Collect all words of length >= 4 from all siblings
            candidate_words = set()
            for n in all_lower:
                for w in n.split():
                    if len(w) >= 3:
                        candidate_words.add(w)
            for w in candidate_words:
                if all(w in n for n in all_lower):
                    return True
            return False

        def is_valid_node(node):
            """Filter out short or too-shallow nodes."""
            return len(node) >= 3 and get_depth(node) >= 2

        while len(questions) < count and attempts < max_attempts:
            attempts += 1

            # Sample a parent with at least 3 valid children
            parent = self.sampler.sample_middle()
            if parent is None or parent in self._used_e3_parents:
                continue

            children = [c for c in self.graph.get_children(parent)
                        if c not in self.exclude_descriptors and is_valid_node(c)]
            if len(children) < 3:
                continue

            # Sample 3 siblings; reject if trivially grouped by word patterns
            similar_group = random.sample(children, 3)
            if has_near_duplicate(similar_group):
                continue
            if has_common_root_word(similar_group):
                continue

            sibling_root = get_root(parent)

            # Sample odd one from a DIFFERENT root category
            exclude_for_odd = set(children)
            odd_one = None
            for _ in range(30):
                candidate = self.sampler.sample_any(
                    exclude=exclude_for_odd,
                    exclude_overused=True,
                    max_usage=self.max_reuse,
                    usage_tracker=self.descriptor_usage
                )
                if candidate is None:
                    break
                if get_root(candidate) == sibling_root:
                    continue
                if not is_valid_node(candidate):
                    continue
                # Odd one must not share words with any sibling, and not be near-duplicate
                if any(words(candidate) & words(s) for s in similar_group):
                    continue
                if has_near_duplicate([candidate] + similar_group):
                    continue
                odd_one = candidate
                break

            if odd_one is None:
                continue

            # Map 'defected' -> 'other' for display
            similar_group_display = ['other' if c == 'defected' else c for c in similar_group]
            odd_one_display = 'other' if odd_one == 'defected' else odd_one

            all_candidates_display = similar_group_display + [odd_one_display]
            random.shuffle(all_candidates_display)

            letters = ['A', 'B', 'C', 'D']
            options = {letter: cand for letter, cand in zip(letters, all_candidates_display)}
            correct_letter = [k for k, v in options.items() if v == odd_one_display][0]

            question_text = template
            if 'other' in all_candidates_display:
                question_text += "\n\n*'other' includes non-standard or less common flavor categories"

            content_id = self._generate_uuid_id(task_type)
            question = {
                "id": content_id,
                "category": "E",
                "task_type": task_type,
                "text": question_text,
                "options": options,
                "correct_answer": correct_letter,
                "_template": template,
                "_objects": {
                    "similar_group": similar_group,
                    "similar_parent": parent,
                    "odd_one": odd_one,
                    "all_candidates": similar_group + [odd_one],
                    "sibling_root": sibling_root,
                    "odd_root": get_root(odd_one),
                }
            }

            if self.validator.validate(question):
                questions.append(question)
                self.descriptor_usage[odd_one] += 1
                type_usage[odd_one] += 1
                self._used_e3_parents.add(parent)

        return questions

    def _generate_f(self, task_type: str, config: Dict) -> List[Dict]:
        """
        Generate F (open-ended reasoning) questions.

        Templates:
            - "Describe the flavor profile of '{descriptor}' in the context of coffee tasting."
            - "Explain the relationship between '{descriptor1}' and '{descriptor2}'..."

        Strategy:
            1. Sample descriptor(s) based on question type
            2. Generate reference answer from graph structure
            3. No multiple choice - evaluated by LLM judge
        """
        questions = []
        count = config["count"]
        templates = config["templates"]

        # Distribution: 6 single_descriptor, 4 descriptor_pair, 2 category_overview
        single_desc_count = 6
        pair_count = 4
        category_count = 2

        # Track descriptors used in this task type
        type_usage = self.descriptor_usage_by_type[task_type]

        # Generate single descriptor questions
        for i in range(single_desc_count):
            used_in_type = {d for d, c in type_usage.items() if c > 0}
            descriptor = self.sampler.sample_any(
                exclude=used_in_type,
                exclude_overused=True,
                max_usage=self.max_reuse,
                usage_tracker=self.descriptor_usage
            )

            if descriptor is None:
                continue

            # Generate reference answer
            ancestors = self.graph.get_ancestors(descriptor)
            children = self.graph.get_children(descriptor)

            reference_answer = self._build_reference_answer_single(
                descriptor, ancestors, children
            )

            # Generate UUID-based ID (F - single descriptor)
            content_id = self._generate_uuid_id(task_type)

            question = {
                "id": content_id,
                "category": "F",
                "task_type": task_type,
                "text": templates[0].format(descriptor=descriptor),  # Single descriptor template
                "options": {},  # No options for open-ended
                "correct_answer": None,  # No single correct answer
                "reference_answer": reference_answer,
                "evaluation_method": "llm_judge",
                "_template": templates[0],
                "_objects": {
                    "descriptor": descriptor,
                    "question_subtype": "single_descriptor"
                }
            }

            questions.append(question)
            self.descriptor_usage[descriptor] += 1
            type_usage[descriptor] += 1

        # Generate descriptor pair questions
        for i in range(pair_count):
            used_in_type = {d for d, c in type_usage.items() if c > 0}
            descriptor1 = self.sampler.sample_any(
                exclude=used_in_type,
                exclude_overused=True,
                max_usage=self.max_reuse,
                usage_tracker=self.descriptor_usage
            )

            if descriptor1 is None:
                continue

            descriptor2 = self.sampler.sample_any(
                exclude=used_in_type | {descriptor1},
                exclude_overused=True,
                max_usage=self.max_reuse,
                usage_tracker=self.descriptor_usage
            )

            if descriptor2 is None:
                continue

            # Generate reference answer
            lca = self.graph.find_lca(descriptor1, descriptor2)
            distance = self.graph.get_path_distance(descriptor1, descriptor2)

            reference_answer = self._build_reference_answer_pair(
                descriptor1, descriptor2, lca, distance
            )

            # Generate UUID-based ID (F - descriptor pair)
            content_id = self._generate_uuid_id(task_type)

            question = {
                "id": content_id,
                "category": "F",
                "task_type": task_type,
                "text": templates[2].format(descriptor1=descriptor1, descriptor2=descriptor2),
                "options": {},
                "correct_answer": None,
                "reference_answer": reference_answer,
                "evaluation_method": "llm_judge",
                "_template": templates[2],
                "_objects": {
                    "descriptor1": descriptor1,
                    "descriptor2": descriptor2,
                    "question_subtype": "descriptor_pair"
                }
            }

            questions.append(question)
            self.descriptor_usage[descriptor1] += 1
            self.descriptor_usage[descriptor2] += 1
            type_usage[descriptor1] += 1
            type_usage[descriptor2] += 1

        # Generate category overview questions
        for i in range(category_count):
            # Sample a root category (exclude those in tool graph to prevent leakage)
            root_categories = self.graph.get_root_categories()
            if self.tool_graph_nodes:
                root_categories = [r for r in root_categories if r not in self.tool_graph_nodes]
            if not root_categories:
                continue

            category = random.choice(root_categories)
            children = self.graph.get_children(category)

            reference_answer = self._build_reference_answer_category(category, children)

            # Generate UUID-based ID (F - category overview)
            content_id = self._generate_uuid_id(task_type)

            # Use descriptor template but with category
            question = {
                "id": content_id,
                "category": "F",
                "task_type": task_type,
                "text": templates[0].format(descriptor=category),  # Reuse single descriptor template
                "options": {},
                "correct_answer": None,
                "reference_answer": reference_answer,
                "evaluation_method": "llm_judge",
                "_template": templates[0],
                "_objects": {
                    "descriptor": category,
                    "question_subtype": "category_overview"
                }
            }

            questions.append(question)

        return questions[:count]  # Return up to count

    def _build_reference_answer_single(self, descriptor: str, ancestors: List[str], children: List[str]) -> str:
        """Build reference answer for single descriptor question."""
        parts = [f"'{descriptor}' is a coffee flavor descriptor."]

        if ancestors:
            path = " → ".join(list(reversed(ancestors)) + [descriptor])
            parts.append(f"Hierarchically, it is classified as: {path}")

        if children:
            children_str = ", ".join(children)
            parts.append(f"It includes specific flavors such as: {children_str}")

        return " ".join(parts)

    def _build_reference_answer_pair(
        self, descriptor1: str, descriptor2: str, lca: Optional[str], distance: Optional[int]
    ) -> str:
        """Build reference answer for descriptor pair question."""
        parts = [f"Comparing '{descriptor1}' and '{descriptor2}':"]

        if lca:
            parts.append(f"They share a common ancestor: '{lca}'")

        if distance:
            parts.append(f"The graph distance between them is {distance} levels")
            if distance <= 2:
                parts.append("suggesting they are relatively similar flavors")
            elif distance <= 4:
                parts.append("suggesting they are moderately related")
            else:
                parts.append("suggesting they are quite distinct flavors")

        return " ".join(parts)

    def _build_reference_answer_category(self, category: str, children: List[str]) -> str:
        """Build reference answer for category overview question."""
        parts = [f"'{category}' is a root category in the coffee flavor wheel."]

        if children:
            children_str = ", ".join(children[:5])  # Limit to 5 for readability
            parts.append(f"It encompasses flavors including: {children_str}")
            if len(children) > 5:
                parts.append(f"and {len(children)-5} others")

        return " ".join(parts)

    def _create_multiple_choice_options(
        self,
        correct_answer: str,
        distractors: List[str]
    ) -> Tuple[Dict[str, str], str]:
        """
        Create A/B/C/D options with shuffling.

        Args:
            correct_answer: The correct answer
            distractors: List of wrong answers

        Returns:
            (options_dict, correct_letter)

        Example:
            >>> options, correct = self._create_multiple_choice_options(
            ...     "fruity",
            ...     ["floral", "nutty/cocoa", "spices"]
            ... )
            >>> print(options)  # {'A': 'nutty/cocoa', 'B': 'fruity', 'C': 'floral', 'D': 'spices'}
            >>> print(correct)  # 'B'
        """
        all_options = [correct_answer] + distractors
        random.shuffle(all_options)

        letters = ['A', 'B', 'C', 'D']
        options = {letter: option for letter, option in zip(letters, all_options)}

        # Find correct letter
        correct_letter = [k for k, v in options.items() if v == correct_answer][0]

        return options, correct_letter

    def save_questions(self, questions: List[Dict], output_path: str):
        """
        Save questions to JSON file.

        Args:
            questions: List of question dicts
            output_path: Path to output JSON file

        Example:
            >>> generator.save_questions(questions, "data/questions/generated.json")
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Add metadata
        output_data = {
            "metadata": {
                "total_count": len(questions),
                "by_category": self._count_by_category(questions),
                "by_task_type": self._count_by_task_type(questions),
                "random_seed": self.random_seed,
                "generated_at": self._get_timestamp()
            },
            "questions": questions
        }

        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

    def _count_by_category(self, questions: List[Dict]) -> Dict[str, int]:
        """Count questions by category."""
        counts = defaultdict(int)
        for q in questions:
            counts[q["category"]] += 1
        return dict(counts)

    def _count_by_task_type(self, questions: List[Dict]) -> Dict[str, int]:
        """Count questions by task type."""
        counts = defaultdict(int)
        for q in questions:
            counts[q["task_type"]] += 1
        return dict(counts)

    def _get_timestamp(self) -> str:
        """Get ISO timestamp."""
        return datetime.now().isoformat()

    @staticmethod
    def deduplicate_questions(questions: List[Dict], by_field: str = 'descriptor') -> Tuple[List[Dict], List[Dict]]:
        """
        Remove duplicate questions based on a field in _objects.

        Args:
            questions: List of question dicts
            by_field: Field in _objects to check for duplicates (default: 'descriptor')

        Returns:
            Tuple of (unique_questions, duplicates)

        Example:
            >>> unique, dupes = QuestionGenerator.deduplicate_questions(questions)
            >>> print(f"Kept {len(unique)}, removed {len(dupes)} duplicates")
        """
        seen = {}
        unique = []
        duplicates = []

        for q in questions:
            # Get the field value from _objects
            if '_objects' not in q or by_field not in q['_objects']:
                unique.append(q)
                continue

            value = q['_objects'][by_field]

            # Check if we've seen this value before
            if value in seen:
                # This is a duplicate
                duplicates.append(q)
            else:
                # First occurrence, keep it
                seen[value] = q
                unique.append(q)

        return unique, duplicates
