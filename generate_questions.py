#!/usr/bin/env python3
"""
Question Generator for Coffee Flavor Hierarchy
===============================================

Generate benchmark questions based on QUESTIONS.md templates using
the SYSTEM graph from coffee_database.

This script creates questions for:
- Category A: Taxonomic Reasoning (180 questions)
  - A1: Root Classification
  - A2: Ancestor Verification
  - A3: Sibling Identification
  - A4: Path Reconstruction
  - A5: Lowest Common Ancestor
- Category E: Similarity Reasoning (80 questions)
  - E1: Similarity Ranking
  - E2: Pairwise Comparison
  - E3: Odd One Out
- Category F: Open Reasoning (15 questions, LLM-judged)

Usage:
    python generate_questions.py --output questions_dataset.json
"""

import argparse
import json
import random
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

from FlavorGraphTraverser import load_system_graph


class QuestionGenerator:
    """Generate benchmark questions from the SYSTEM graph."""

    def __init__(self, graph, seed: int = 42):
        """
        Initialize question generator.

        Args:
            graph: CoffeeDescriptionGraph instance
            seed: Random seed for reproducibility
        """
        self.graph = graph
        self.seed = seed
        random.seed(seed)

        # Cache frequently used data
        self._build_caches()

    def _build_caches(self):
        """Build caches for efficient question generation."""
        print("Building caches...")

        # Get root categories (direct children of ROOT:SYSTEM)
        self.root_categories = self.graph.children_of_description(self.graph.root)
        print(f"  Root categories: {len(self.root_categories)}")

        # Find all leaf nodes
        self.leaf_nodes = [
            desc for desc in self.graph.descriptions
            if len(self.graph.children_of_description(desc)) == 0
            and desc != self.graph.root
        ]
        print(f"  Leaf nodes: {len(self.leaf_nodes)}")

        # Build parent-child relationships
        self.children_map = {}
        self.parents_map = {}
        for desc in self.graph.descriptions:
            self.children_map[desc] = self.graph.children_of_description(desc)
            self.parents_map[desc] = self.graph.parents_of_description(desc)

        # Group nodes by their root category
        self.category_groups = defaultdict(list)
        for desc in self.graph.descriptions:
            if desc == self.graph.root:
                continue
            root_cat = self._find_root_category(desc)
            if root_cat:
                self.category_groups[root_cat].append(desc)

        print(f"  Category groups: {len(self.category_groups)}")

    def _find_root_category(self, description: str) -> Optional[str]:
        """Find the root category for a given description."""
        if description in self.root_categories:
            return description

        # Walk up to root
        current = description
        visited = set()
        while current and current != self.graph.root:
            if current in visited:
                break  # Avoid cycles
            visited.add(current)

            parents = self.parents_map.get(current, [])
            if not parents:
                break

            parent = parents[0]
            if parent in self.root_categories:
                return parent

            current = parent

        return None

    def _get_path_to_root(self, description: str) -> List[str]:
        """Get the path from description to root."""
        path = [description]
        current = description
        visited = set()

        while current != self.graph.root:
            if current in visited:
                break
            visited.add(current)

            parents = self.parents_map.get(current, [])
            if not parents:
                break

            current = parents[0]
            path.append(current)

        return path

    # ========================================================================
    # A1: Root Classification
    # ========================================================================

    def generate_a1_root_classification(self, num_questions: int = 50) -> List[Dict]:
        """Generate A1: Root Classification questions."""
        questions = []
        attempts = 0
        max_attempts = num_questions * 10

        while len(questions) < num_questions and attempts < max_attempts:
            attempts += 1

            # Sample a leaf node
            target = random.choice(self.leaf_nodes)
            correct_root = self._find_root_category(target)

            if not correct_root:
                continue

            # Generate distractors (other root categories)
            distractors = [
                cat for cat in self.root_categories
                if cat != correct_root
            ]

            if len(distractors) < 3:
                continue

            options = [correct_root] + random.sample(distractors, 3)
            random.shuffle(options)
            correct_idx = options.index(correct_root)
            answer_letter = chr(65 + correct_idx)  # A, B, C, D

            question = {
                'id': f'A1_{len(questions)+1:03d}',
                'category': 'A1',
                'type': 'root_classification',
                'question': f"Which root category does '{target}' belong to?",
                'options': {
                    'A': options[0],
                    'B': options[1],
                    'C': options[2],
                    'D': options[3]
                },
                'answer': answer_letter,
                'explanation': {
                    'target': target,
                    'correct_root': correct_root,
                    'path': self._get_path_to_root(target)
                }
            }

            questions.append(question)

        return questions[:num_questions]

    # ========================================================================
    # A2: Ancestor Verification
    # ========================================================================

    def generate_a2_ancestor_verification(self, num_questions: int = 50) -> List[Dict]:
        """Generate A2: Ancestor Verification questions."""
        questions = []
        attempts = 0
        max_attempts = num_questions * 10

        while len(questions) < num_questions and attempts < max_attempts:
            attempts += 1

            # Half positive, half negative examples
            is_positive = len(questions) % 2 == 0

            if is_positive:
                # Generate positive example (true ancestor)
                descendant = random.choice(self.leaf_nodes)
                path = self._get_path_to_root(descendant)

                if len(path) < 3:
                    continue

                # Pick an ancestor (not root or immediate parent)
                ancestor = random.choice(path[2:-1] if len(path) > 3 else path[1:-1])

                answer = 'A'  # Yes
            else:
                # Generate negative example (not ancestor)
                descendant = random.choice(self.leaf_nodes)
                descendant_path = self._get_path_to_root(descendant)
                descendant_root = self._find_root_category(descendant)

                # Pick from different root category
                other_roots = [r for r in self.root_categories if r != descendant_root]
                if not other_roots:
                    continue

                other_root = random.choice(other_roots)
                other_nodes = self.category_groups[other_root]

                if not other_nodes:
                    continue

                ancestor = random.choice(other_nodes)
                answer = 'B'  # No

            question = {
                'id': f'A2_{len(questions)+1:03d}',
                'category': 'A2',
                'type': 'ancestor_verification',
                'question': f"Is '{descendant}' a descendant of '{ancestor}'?",
                'options': {
                    'A': 'Yes',
                    'B': 'No'
                },
                'answer': answer,
                'explanation': {
                    'descendant': descendant,
                    'ancestor': ancestor,
                    'is_ancestor': answer == 'A',
                    'path': self._get_path_to_root(descendant)
                }
            }

            questions.append(question)

        return questions[:num_questions]

    # ========================================================================
    # A3: Sibling Identification
    # ========================================================================

    def generate_a3_sibling_identification(self, num_questions: int = 30) -> List[Dict]:
        """Generate A3: Sibling Identification questions."""
        questions = []
        attempts = 0
        max_attempts = num_questions * 10

        while len(questions) < num_questions and attempts < max_attempts:
            attempts += 1

            # Find a node with siblings
            target = random.choice(self.leaf_nodes)
            parents = self.parents_map.get(target, [])

            if not parents:
                continue

            parent = parents[0]
            siblings = [
                s for s in self.children_map.get(parent, [])
                if s != target
            ]

            if len(siblings) < 1:
                continue

            correct_sibling = random.choice(siblings)

            # Generate distractors from other categories
            target_root = self._find_root_category(target)
            other_roots = [r for r in self.root_categories if r != target_root]

            distractors = []
            for _ in range(3):
                if not other_roots:
                    break
                other_root = random.choice(other_roots)
                other_nodes = self.category_groups[other_root]
                if other_nodes:
                    distractors.append(random.choice(other_nodes))

            if len(distractors) < 3:
                continue

            options = [correct_sibling] + distractors[:3]
            random.shuffle(options)
            correct_idx = options.index(correct_sibling)
            answer_letter = chr(65 + correct_idx)

            question = {
                'id': f'A3_{len(questions)+1:03d}',
                'category': 'A3',
                'type': 'sibling_identification',
                'question': f"Which shares the same parent as '{target}'?",
                'options': {
                    'A': options[0],
                    'B': options[1],
                    'C': options[2],
                    'D': options[3]
                },
                'answer': answer_letter,
                'explanation': {
                    'target': target,
                    'parent': parent,
                    'siblings': siblings,
                    'correct_sibling': correct_sibling
                }
            }

            questions.append(question)

        return questions[:num_questions]

    # ========================================================================
    # Generate All Questions
    # ========================================================================

    def generate_all_questions(self) -> Dict:
        """Generate all question categories."""
        print("\n" + "="*70)
        print("Generating Questions")
        print("="*70)

        all_questions = {}

        print("\nA1: Root Classification...")
        all_questions['A1'] = self.generate_a1_root_classification(50)
        print(f"  Generated: {len(all_questions['A1'])} questions")

        print("\nA2: Ancestor Verification...")
        all_questions['A2'] = self.generate_a2_ancestor_verification(50)
        print(f"  Generated: {len(all_questions['A2'])} questions")

        print("\nA3: Sibling Identification...")
        all_questions['A3'] = self.generate_a3_sibling_identification(30)
        print(f"  Generated: {len(all_questions['A3'])} questions")

        # TODO: Implement A4, A5, E1, E2, E3, F

        return all_questions


def main():
    """Main generation workflow."""
    parser = argparse.ArgumentParser(
        description='Generate benchmark questions from SYSTEM graph'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='questions_dataset.json',
        help='Output JSON file path'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility'
    )

    args = parser.parse_args()

    # Load graph
    print("Loading SYSTEM graph...")
    graph = load_system_graph()
    print(f"  ✓ Loaded: {len(graph.descriptions)} descriptions")

    # Generate questions
    generator = QuestionGenerator(graph, seed=args.seed)
    questions = generator.generate_all_questions()

    # Save to file
    output = {
        'metadata': {
            'graph_name': 'SYSTEM',
            'num_descriptions': len(graph.descriptions),
            'root': graph.root,
            'seed': args.seed,
            'total_questions': sum(len(qs) for qs in questions.values())
        },
        'questions': questions
    }

    output_path = Path(args.output)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\n" + "="*70)
    print("✓ Questions Generated!")
    print("="*70)
    print(f"\nOutput: {output_path}")
    print(f"Total questions: {output['metadata']['total_questions']}")
    print("\nQuestion breakdown:")
    for category, qs in questions.items():
        print(f"  {category}: {len(qs)} questions")

    print("\n" + "="*70)


if __name__ == '__main__':
    main()
