#!/usr/bin/env python3
"""
Complete Question Generator for QUESTIONS.md
=============================================

Generate all question types using FlavorGraphTraverser API.
"""

import json
import random
from typing import List, Dict, Optional
from collections import defaultdict
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph


class QuestionGenerator:
    """Generate benchmark questions from flavor hierarchy graph."""

    def __init__(self, graph: CoffeeDescriptionGraph, seed: int = 42):
        self.graph = graph
        self.seed = seed
        random.seed(seed)
        self._build_caches()

    def _build_caches(self):
        """Build helper data structures."""
        print("Building caches...")

        # Root categories (direct children of root)
        self.root_categories = self.graph.children_of_description(self.graph.root)

        # Leaf nodes
        self.leaf_nodes = [
            d for d in self.graph.descriptions
            if len(self.graph.children_of_description(d)) == 0 and d != self.graph.root
        ]

        # Cache parent-child relationships
        self.children_map = {d: self.graph.children_of_description(d) for d in self.graph.descriptions}
        self.parents_map = {d: self.graph.parents_of_description(d) for d in self.graph.descriptions}

        print(f"  Root categories: {len(self.root_categories)}")
        print(f"  Leaf nodes: {len(self.leaf_nodes)}")

    def _find_root_category(self, description: str) -> Optional[str]:
        """Find which root category this description belongs to."""
        if description in self.root_categories:
            return description

        # Walk up to root
        current = description
        visited = set()
        while current and current != self.graph.root:
            if current in visited:
                break
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
        """Get path from description to root."""
        paths = self.graph.pathways_between_descriptions(
            self.graph.root, description,
            reverse_direction=True, formated_string=False
        )
        return paths[0] if paths else []

    # ========================================================================
    # A1: Root Classification (50 questions)
    # ========================================================================

    def generate_a1(self, n: int = 50) -> List[Dict]:
        """Generate A1: Root Classification questions."""
        questions = []

        for _ in range(n * 3):  # Try more times
            if len(questions) >= n:
                break

            target = random.choice(self.leaf_nodes)
            correct_root = self._find_root_category(target)

            if not correct_root or len(self.root_categories) < 4:
                continue

            # Generate options
            distractors = [c for c in self.root_categories if c != correct_root]
            options = [correct_root] + random.sample(distractors, 3)
            random.shuffle(options)

            answer = chr(65 + options.index(correct_root))  # A, B, C, D

            questions.append({
                'id': f'A1_{len(questions)+1:03d}',
                'category': 'A1',
                'question': f"Which root category does '{target}' belong to?",
                'options': {chr(65+i): opt for i, opt in enumerate(options)},
                'answer': answer,
                'metadata': {'target': target, 'correct_root': correct_root}
            })

        return questions[:n]

    # ========================================================================
    # A2: Ancestor Verification (50 questions)
    # ========================================================================

    def generate_a2(self, n: int = 50) -> List[Dict]:
        """Generate A2: Ancestor Verification questions."""
        questions = []

        for i in range(n * 2):
            if len(questions) >= n:
                break

            is_positive = i % 2 == 0
            descendant = random.choice(self.leaf_nodes)
            path = self._get_path_to_root(descendant)

            if len(path) < 3:
                continue

            if is_positive:
                # True ancestor
                ancestor = random.choice(path[1:-1])  # Not root, not self
                answer = 'A'
            else:
                # False ancestor - pick from different branch
                desc_root = self._find_root_category(descendant)
                other_roots = [r for r in self.root_categories if r != desc_root]
                if not other_roots:
                    continue
                ancestor = random.choice(other_roots)
                answer = 'B'

            questions.append({
                'id': f'A2_{len(questions)+1:03d}',
                'category': 'A2',
                'question': f"Is '{descendant}' a descendant of '{ancestor}'?",
                'options': {'A': 'Yes', 'B': 'No'},
                'answer': answer,
                'metadata': {'descendant': descendant, 'ancestor': ancestor, 'is_ancestor': answer == 'A'}
            })

        return questions[:n]

    # ========================================================================
    # A3: Sibling Identification (30 questions)
    # ========================================================================

    def generate_a3(self, n: int = 30) -> List[Dict]:
        """Generate A3: Sibling Identification questions."""
        questions = []

        for _ in range(n * 3):
            if len(questions) >= n:
                break

            target = random.choice(self.leaf_nodes)
            parents = self.parents_map.get(target, [])

            if not parents:
                continue

            parent = parents[0]
            siblings = [s for s in self.children_map[parent] if s != target]

            if len(siblings) < 1:
                continue

            correct = random.choice(siblings)

            # Generate distractors from other categories
            target_root = self._find_root_category(target)
            distractors = []
            for cat in [c for c in self.root_categories if c != target_root]:
                if cat in self.children_map and self.children_map[cat]:
                    distractors.append(random.choice(self.children_map[cat]))

            if len(distractors) < 3:
                continue

            options = [correct] + distractors[:3]
            random.shuffle(options)
            answer = chr(65 + options.index(correct))

            questions.append({
                'id': f'A3_{len(questions)+1:03d}',
                'category': 'A3',
                'question': f"Which shares the same parent as '{target}'?",
                'options': {chr(65+i): opt for i, opt in enumerate(options)},
                'answer': answer,
                'metadata': {'target': target, 'parent': parent, 'correct_sibling': correct}
            })

        return questions[:n]

    # ========================================================================
    # A4: Path Reconstruction (30 questions)
    # ========================================================================

    def generate_a4(self, n: int = 30) -> List[Dict]:
        """Generate A4: Path Reconstruction questions."""
        questions = []

        for _ in range(n * 3):
            if len(questions) >= n:
                break

            target = random.choice(self.leaf_nodes)
            correct_path = self._get_path_to_root(target)

            if len(correct_path) < 3:
                continue

            # Correct path (exclude root)
            path_str = ' → '.join(reversed(correct_path[:-1]))

            # Generate distractor paths
            distractors = []

            # Distractor 1: Skip intermediate node
            if len(correct_path) > 3:
                skip_path = [correct_path[0]] + [correct_path[-2]]
                distractors.append(' → '.join(reversed(skip_path)))

            # Distractor 2: Wrong intermediate from same category
            if len(correct_path) >= 3:
                target_root = self._find_root_category(target)
                if target_root and target_root in self.children_map:
                    other_intermediates = [c for c in self.children_map[target_root] if c != correct_path[-2]]
                    if other_intermediates:
                        wrong_path = [correct_path[0], random.choice(other_intermediates), target_root]
                        distractors.append(' → '.join(reversed(wrong_path)))

            # Distractor 3: Wrong category
            other_roots = [r for r in self.root_categories if r != self._find_root_category(target)]
            if other_roots:
                wrong_root = random.choice(other_roots)
                wrong_path = [correct_path[0], wrong_root]
                distractors.append(' → '.join(reversed(wrong_path)))

            if len(distractors) < 3:
                continue

            options = [path_str] + distractors[:3]
            random.shuffle(options)
            answer = chr(65 + options.index(path_str))

            questions.append({
                'id': f'A4_{len(questions)+1:03d}',
                'category': 'A4',
                'question': f"What is the path from '{target}' to its root category?",
                'options': {chr(65+i): opt for i, opt in enumerate(options)},
                'answer': answer,
                'metadata': {'target': target, 'correct_path': correct_path}
            })

        return questions[:n]

    # ========================================================================
    # A5: Lowest Common Ancestor (20 questions)
    # ========================================================================

    def generate_a5(self, n: int = 20) -> List[Dict]:
        """Generate A5: Lowest Common Ancestor questions."""
        questions = []

        for _ in range(n * 5):
            if len(questions) >= n:
                break

            # Pick two leaf nodes from same root category
            target_root = random.choice(self.root_categories)
            candidates = [d for d in self.leaf_nodes if self._find_root_category(d) == target_root]

            if len(candidates) < 2:
                continue

            node1, node2 = random.sample(candidates, 2)
            path1 = self._get_path_to_root(node1)
            path2 = self._get_path_to_root(node2)

            if len(path1) < 3 or len(path2) < 3:
                continue

            # Find LCA
            lca = None
            for i in range(min(len(path1), len(path2)) - 1, -1, -1):
                if path1[i] == path2[i]:
                    continue
                if i + 1 < len(path1) and i + 1 < len(path2) and path1[i+1] == path2[i+1]:
                    lca = path1[i+1]
                    break

            if not lca or lca == self.graph.root:
                continue

            # Generate options
            options = [lca]

            # Add ancestors of LCA as distractors
            lca_path = self._get_path_to_root(lca)
            if len(lca_path) > 1:
                options.extend([p for p in lca_path[1:-1] if p != lca][:2])

            # Add root as distractor
            options.append(self.graph.root)

            if len(options) < 4:
                continue

            options = options[:4]
            random.shuffle(options)
            answer = chr(65 + options.index(lca))

            questions.append({
                'id': f'A5_{len(questions)+1:03d}',
                'category': 'A5',
                'question': f"What is the most specific category containing both '{node1}' and '{node2}'?",
                'options': {chr(65+i): opt for i, opt in enumerate(options)},
                'answer': answer,
                'metadata': {'node1': node1, 'node2': node2, 'lca': lca}
            })

        return questions[:n]

    # ========================================================================
    # E1: Similarity Ranking (30 questions)
    # ========================================================================

    def generate_e1(self, n: int = 30) -> List[Dict]:
        """Generate E1: Similarity Ranking questions."""
        questions = []

        for _ in range(n * 3):
            if len(questions) >= n:
                break

            target = random.choice(self.leaf_nodes)
            target_root = self._find_root_category(target)

            if not target_root:
                continue

            # Pick 3 candidates with different distances
            candidates = []

            # Close: same category
            same_cat = [d for d in self.leaf_nodes if self._find_root_category(d) == target_root and d != target]
            if same_cat:
                candidates.append(random.choice(same_cat))

            # Medium: different category
            other_cats = [r for r in self.root_categories if r != target_root]
            if len(other_cats) >= 2:
                for cat in random.sample(other_cats, 2):
                    cat_nodes = [d for d in self.leaf_nodes if self._find_root_category(d) == cat]
                    if cat_nodes:
                        candidates.append(random.choice(cat_nodes))

            if len(candidates) < 3:
                continue

            # Compute distances
            distances = [(c, self.graph.distance_between_descriptions(target, c)) for c in candidates]
            distances.sort(key=lambda x: x[1])

            # Correct ranking
            correct = ' > '.join([d[0] for d in distances])

            # Generate distractor rankings
            import itertools
            all_perms = list(itertools.permutations([d[0] for d in distances]))
            distractors = [' > '.join(p) for p in all_perms if p != tuple(d[0] for d in distances)]

            if len(distractors) < 3:
                continue

            options = [correct] + random.sample(distractors, 3)
            random.shuffle(options)
            answer = chr(65 + options.index(correct))

            questions.append({
                'id': f'E1_{len(questions)+1:03d}',
                'category': 'E1',
                'question': f"Rank by similarity to '{target}': {', '.join([d[0] for d in distances])}",
                'options': {chr(65+i): opt for i, opt in enumerate(options)},
                'answer': answer,
                'metadata': {'target': target, 'distances': {d[0]: d[1] for d in distances}}
            })

        return questions[:n]

    # ========================================================================
    # E2: Pairwise Comparison (30 questions)
    # ========================================================================

    def generate_e2(self, n: int = 30) -> List[Dict]:
        """Generate E2: Pairwise Comparison questions."""
        questions = []

        for _ in range(n * 2):
            if len(questions) >= n:
                break

            target = random.choice(self.leaf_nodes)
            target_root = self._find_root_category(target)

            # Pick one close, one far
            close_candidates = [d for d in self.leaf_nodes if self._find_root_category(d) == target_root and d != target]
            far_candidates = [d for d in self.leaf_nodes if self._find_root_category(d) != target_root]

            if not close_candidates or not far_candidates:
                continue

            close = random.choice(close_candidates)
            far = random.choice(far_candidates)

            # Verify distances
            dist_close = self.graph.distance_between_descriptions(target, close)
            dist_far = self.graph.distance_between_descriptions(target, far)

            if dist_close >= dist_far:
                continue

            # Randomize order
            if random.random() < 0.5:
                options = {'A': close, 'B': far}
                answer = 'A'
            else:
                options = {'A': far, 'B': close}
                answer = 'B'

            questions.append({
                'id': f'E2_{len(questions)+1:03d}',
                'category': 'E2',
                'question': f"Which is more similar to '{target}': {options['A']} or {options['B']}?",
                'options': options,
                'answer': answer,
                'metadata': {'target': target, 'closer': close, 'farther': far}
            })

        return questions[:n]

    # ========================================================================
    # E3: Odd One Out (20 questions)
    # ========================================================================

    def generate_e3(self, n: int = 20) -> List[Dict]:
        """Generate E3: Odd One Out questions."""
        questions = []

        for _ in range(n * 3):
            if len(questions) >= n:
                break

            # Pick a category
            category = random.choice(self.root_categories)
            in_category = [d for d in self.leaf_nodes if self._find_root_category(d) == category]
            out_category = [d for d in self.leaf_nodes if self._find_root_category(d) != category]

            if len(in_category) < 3 or len(out_category) < 1:
                continue

            # 3 from category, 1 outlier
            in_group = random.sample(in_category, 3)
            outlier = random.choice(out_category)

            options = in_group + [outlier]
            random.shuffle(options)
            answer = chr(65 + options.index(outlier))

            questions.append({
                'id': f'E3_{len(questions)+1:03d}',
                'category': 'E3',
                'question': f"Which does NOT belong: {', '.join(options)}?",
                'options': {chr(65+i): opt for i, opt in enumerate(options)},
                'answer': answer,
                'metadata': {'in_group': in_group, 'outlier': outlier, 'category': category}
            })

        return questions[:n]

    # ========================================================================
    # F: Open Reasoning (15 questions)
    # ========================================================================

    def generate_f(self, n: int = 15) -> List[Dict]:
        """Generate F: Open Reasoning questions."""
        questions = []
        templates = [
            "A customer enjoys '{flavor}' flavors but wants to explore something new. Using the flavor hierarchy, suggest alternatives and explain your reasoning.",
            "Explain the relationship between '{flavor1}' and '{flavor2}' using the flavor hierarchy.",
            "A barista wants to create a flavor profile around '{flavor}'. What complementary flavors would you suggest and why?",
            "Compare and contrast '{flavor1}' and '{flavor2}' in terms of their position in the flavor hierarchy.",
        ]

        for i in range(n):
            template = random.choice(templates)

            if '{flavor1}' in template:
                flavor1 = random.choice(self.leaf_nodes)
                flavor2 = random.choice([d for d in self.leaf_nodes if d != flavor1])
                question = template.format(flavor1=flavor1, flavor2=flavor2)
            else:
                flavor = random.choice(self.leaf_nodes)
                question = template.format(flavor=flavor)

            questions.append({
                'id': f'F_{i+1:03d}',
                'category': 'F',
                'question': question,
                'answer_format': 'open_ended',
                'rubric': {
                    'relevance': 'Are suggestions related in the hierarchy?',
                    'reasoning': 'Is the justification logical?',
                    'specificity': 'Are concrete descriptors mentioned?',
                    'coherence': 'Do recommendations form a unified profile?'
                }
            })

        return questions

    # ========================================================================
    # Generate All
    # ========================================================================

    def generate_all(self) -> Dict:
        """Generate all question categories."""
        print("\n" + "="*70)
        print("Generating All Questions")
        print("="*70)

        result = {}

        print("\nA1: Root Classification (50)...")
        result['A1'] = self.generate_a1(50)
        print(f"  ✓ Generated {len(result['A1'])}")

        print("A2: Ancestor Verification (50)...")
        result['A2'] = self.generate_a2(50)
        print(f"  ✓ Generated {len(result['A2'])}")

        print("A3: Sibling Identification (30)...")
        result['A3'] = self.generate_a3(30)
        print(f"  ✓ Generated {len(result['A3'])}")

        print("A4: Path Reconstruction (30)...")
        result['A4'] = self.generate_a4(30)
        print(f"  ✓ Generated {len(result['A4'])}")

        print("A5: Lowest Common Ancestor (20)...")
        result['A5'] = self.generate_a5(20)
        print(f"  ✓ Generated {len(result['A5'])}")

        print("E1: Similarity Ranking (30)...")
        result['E1'] = self.generate_e1(30)
        print(f"  ✓ Generated {len(result['E1'])}")

        print("E2: Pairwise Comparison (30)...")
        result['E2'] = self.generate_e2(30)
        print(f"  ✓ Generated {len(result['E2'])}")

        print("E3: Odd One Out (20)...")
        result['E3'] = self.generate_e3(20)
        print(f"  ✓ Generated {len(result['E3'])}")

        print("F: Open Reasoning (15)...")
        result['F'] = self.generate_f(15)
        print(f"  ✓ Generated {len(result['F'])}")

        return result


def main():
    """Generate complete question dataset."""
    # Load graph
    print("Loading graph...")
    data = load_graph_data('system_graph.pkl')
    graph = CoffeeDescriptionGraph(
        data['descriptions'],
        data['connections'],
        root=data['root'],
        graph_name=data['graph_name']
    )
    print(f"  ✓ Loaded {len(graph.descriptions)} descriptions")

    # Generate questions
    generator = QuestionGenerator(graph, seed=42)
    questions = generator.generate_all()

    # Calculate total
    total = sum(len(qs) for qs in questions.values())

    # Save
    output = {
        'metadata': {
            'graph_name': 'SYSTEM',
            'num_descriptions': len(graph.descriptions),
            'seed': 42,
            'total_questions': total
        },
        'questions': questions
    }

    with open('questions_complete.json', 'w') as f:
        json.dump(output, f, indent=2)

    print("\n" + "="*70)
    print("✓ Complete Question Set Generated!")
    print("="*70)
    print(f"\nTotal questions: {total}")
    print("\nBreakdown:")
    for cat, qs in questions.items():
        print(f"  {cat}: {len(qs)} questions")
    print(f"\nSaved to: questions_complete.json")


if __name__ == '__main__':
    main()
