"""
Descriptor Samplers and Distractor Generators

Provides strategies for sampling descriptors from the graph and generating
plausible distractors for multiple-choice questions.

Classes:
    DescriptorSampler: Sample descriptors from graph with various strategies
    DistractorGenerator: Generate plausible wrong answers
"""

import random
from typing import List, Optional, Set, Dict
from collections import defaultdict

from ..graph import CoffeeDescriptionGraph


class DescriptorSampler:
    """
    Samples descriptors from the coffee flavor graph.

    Provides various sampling strategies (leaf, middle, any) with support
    for diversity constraints (avoiding overused descriptors).

    Example:
        >>> sampler = DescriptorSampler(graph)
        >>>
        >>> # Sample a leaf descriptor
        >>> leaf = sampler.sample_leaf()
        >>>
        >>> # Sample avoiding overused descriptors
        >>> usage = {"chocolate": 5, "fruity": 3}
        >>> descriptor = sampler.sample_leaf(
        ...     exclude_overused=True,
        ...     max_usage=3,
        ...     usage_tracker=usage
        ... )
    """

    def __init__(
        self,
        graph: CoffeeDescriptionGraph,
        random_seed: Optional[int] = None,
        global_exclude: Optional[Set[str]] = None
    ):
        """
        Initialize sampler.

        Args:
            graph: CoffeeDescriptionGraph instance
            random_seed: Random seed for reproducibility
            global_exclude: Set of descriptors to always exclude (e.g., to prevent data leakage)
        """
        self.graph = graph
        self.global_exclude = global_exclude or set()
        if random_seed is not None:
            random.seed(random_seed)

        # Cache descriptor lists
        self._leaf_cache = None
        self._middle_cache = None
        self._all_cache = None

    def sample_leaf(
        self,
        exclude: Optional[Set[str]] = None,
        exclude_overused: bool = False,
        max_usage: int = 3,
        usage_tracker: Optional[Dict[str, int]] = None
    ) -> Optional[str]:
        """
        Sample a leaf descriptor (no children).

        Args:
            exclude: Set of descriptors to exclude
            exclude_overused: Whether to exclude overused descriptors
            max_usage: Maximum times a descriptor can be used
            usage_tracker: Dict tracking descriptor usage counts

        Returns:
            Sampled descriptor or None if no valid options

        Example:
            >>> leaf = sampler.sample_leaf()
            >>> print(leaf)  # 'chocolate', 'strawberry', etc.
        """
        if self._leaf_cache is None:
            self._leaf_cache = self.graph.get_leaf_nodes()

        return self._sample_from_list(
            self._leaf_cache,
            exclude=exclude,
            exclude_overused=exclude_overused,
            max_usage=max_usage,
            usage_tracker=usage_tracker
        )

    def sample_middle(
        self,
        exclude: Optional[Set[str]] = None,
        exclude_overused: bool = False,
        max_usage: int = 3,
        usage_tracker: Optional[Dict[str, int]] = None
    ) -> Optional[str]:
        """
        Sample a middle descriptor (has both parent and children).

        Args:
            exclude: Set of descriptors to exclude
            exclude_overused: Whether to exclude overused descriptors
            max_usage: Maximum times a descriptor can be used
            usage_tracker: Dict tracking descriptor usage counts

        Returns:
            Sampled descriptor or None if no valid options
        """
        if self._middle_cache is None:
            self._middle_cache = self.graph.get_middle_nodes()

        return self._sample_from_list(
            self._middle_cache,
            exclude=exclude,
            exclude_overused=exclude_overused,
            max_usage=max_usage,
            usage_tracker=usage_tracker
        )

    def sample_any(
        self,
        exclude: Optional[Set[str]] = None,
        exclude_overused: bool = False,
        max_usage: int = 3,
        usage_tracker: Optional[Dict[str, int]] = None
    ) -> Optional[str]:
        """
        Sample any descriptor.

        Args:
            exclude: Set of descriptors to exclude
            exclude_overused: Whether to exclude overused descriptors
            max_usage: Maximum times a descriptor can be used
            usage_tracker: Dict tracking descriptor usage counts

        Returns:
            Sampled descriptor or None if no valid options
        """
        if self._all_cache is None:
            # descriptions is a list
            self._all_cache = list(self.graph.descriptions)

        return self._sample_from_list(
            self._all_cache,
            exclude=exclude,
            exclude_overused=exclude_overused,
            max_usage=max_usage,
            usage_tracker=usage_tracker
        )

    def _sample_from_list(
        self,
        candidates: List[str],
        exclude: Optional[Set[str]] = None,
        exclude_overused: bool = False,
        max_usage: int = 3,
        usage_tracker: Optional[Dict[str, int]] = None
    ) -> Optional[str]:
        """
        Sample from a list of candidates with filtering.

        Args:
            candidates: List of candidate descriptors
            exclude: Set of descriptors to exclude
            exclude_overused: Whether to exclude overused descriptors
            max_usage: Maximum times a descriptor can be used
            usage_tracker: Dict tracking descriptor usage counts

        Returns:
            Sampled descriptor or None if no valid options
        """
        # Apply filters
        valid_candidates = list(candidates)

        # Always apply global exclusion list (e.g., to prevent data leakage)
        if self.global_exclude:
            valid_candidates = [c for c in valid_candidates if c not in self.global_exclude]

        if exclude:
            valid_candidates = [c for c in valid_candidates if c not in exclude]

        if exclude_overused and usage_tracker:
            valid_candidates = [
                c for c in valid_candidates
                if usage_tracker.get(c, 0) < max_usage
            ]

        if not valid_candidates:
            return None

        return random.choice(valid_candidates)

    def sample_by_distance(
        self,
        target: str,
        count: int,
        require_different_distances: bool = True,
        min_difference: int = 1
    ) -> List[tuple]:
        """
        Sample descriptors at different distances from target.

        Args:
            target: Target descriptor
            count: Number of descriptors to sample
            require_different_distances: Whether to require different distances
            min_difference: Minimum distance difference between samples

        Returns:
            List of (descriptor, distance) tuples
        """
        # Get all descriptors with distances
        all_descriptors = list(self.graph.descriptions)
        descriptors_with_distances = []

        for desc in all_descriptors:
            if desc == target:
                continue

            # Skip globally excluded descriptors
            if desc in self.global_exclude:
                continue

            distance = self.graph.get_path_distance(target, desc)
            if distance is not None:
                descriptors_with_distances.append((desc, distance))

        if not descriptors_with_distances:
            return []

        # Sort by distance
        descriptors_with_distances.sort(key=lambda x: x[1])

        if not require_different_distances:
            # Just sample randomly
            sampled = random.sample(descriptors_with_distances, min(count, len(descriptors_with_distances)))
            return sampled

        # Sample ensuring different distance levels
        result = []
        used_distances = set()

        for desc, dist in descriptors_with_distances:
            # Check if this distance is far enough from already used distances
            if not used_distances or all(abs(dist - ud) >= min_difference for ud in used_distances):
                result.append((desc, dist))
                used_distances.add(dist)

                if len(result) >= count:
                    break

        return result

    def sample_different_branch(
        self,
        exclude: Optional[Set[str]] = None,
        exclude_overused: bool = False,
        max_usage: int = 3,
        usage_tracker: Optional[Dict[str, int]] = None
    ) -> Optional[str]:
        """
        Sample descriptor from a different branch (different parent).

        Args:
            exclude: Set of descriptors to exclude
            exclude_overused: Whether to exclude overused descriptors
            max_usage: Maximum times a descriptor can be used
            usage_tracker: Dict tracking descriptor usage counts

        Returns:
            Sampled descriptor or None if no valid options
        """
        # Just sample any descriptor, excluding the provided set
        return self.sample_any(
            exclude=exclude,
            exclude_overused=exclude_overused,
            max_usage=max_usage,
            usage_tracker=usage_tracker
        )


class DistractorGenerator:
    """
    Generates plausible distractors (wrong answers) for questions.

    Provides various strategies for generating distractors based on
    the question type and correct answer.

    Example:
        >>> gen = DistractorGenerator(graph)
        >>>
        >>> # Generate other root categories as distractors
        >>> distractors = gen.sample_other_roots(
        ...     correct_root="fruity",
        ...     count=3,
        ...     all_roots=["fruity", "floral", "nutty/cocoa", "spices", "roasted"]
        ... )
        >>> print(distractors)  # ['floral', 'nutty/cocoa', 'spices']
    """

    def __init__(self, graph: CoffeeDescriptionGraph, random_seed: Optional[int] = None):
        """
        Initialize distractor generator.

        Args:
            graph: CoffeeDescriptionGraph instance
            random_seed: Random seed for reproducibility
        """
        self.graph = graph
        if random_seed is not None:
            random.seed(random_seed)

    def sample_other_roots(
        self,
        correct_root: str,
        count: int,
        all_roots: Optional[List[str]] = None
    ) -> List[str]:
        """
        Sample other root categories (excluding correct one).

        Args:
            correct_root: The correct root category
            count: Number of distractors to sample
            all_roots: List of all root categories (optional, will fetch if not provided)

        Returns:
            List of distractor root categories

        Example:
            >>> distractors = gen.sample_other_roots("fruity", 3)
            >>> print(len(distractors))  # 3
            >>> print("fruity" in distractors)  # False
        """
        if all_roots is None:
            all_roots = self.graph.get_root_categories()

        other_roots = [r for r in all_roots if r != correct_root]

        if len(other_roots) < count:
            # Not enough roots, return all available
            return other_roots

        return random.sample(other_roots, count)

    def sample_plausible_non_ancestor(self, descriptor: str) -> Optional[str]:
        """
        Sample a plausible non-ancestor of a descriptor.

        Strategy: Sample from a different branch but similar depth
        to make it plausible.

        Args:
            descriptor: The descriptor

        Returns:
            A plausible non-ancestor or None

        Example:
            >>> non_ancestor = gen.sample_plausible_non_ancestor("chocolate")
            >>> print(non_ancestor)  # e.g., "floral" (different branch)
        """
        # Get descriptor's ancestors
        ancestors = set(self.graph.get_ancestors(descriptor))

        # Get descriptor's root
        root = self.graph.get_root_category(descriptor)

        # Get all other roots
        all_roots = self.graph.get_root_categories()
        other_roots = [r for r in all_roots if r != root]

        if not other_roots:
            return None

        # Sample from another root's subtree
        other_root = random.choice(other_roots)

        # Get middle nodes from that subtree (more plausible than root itself)
        middle_nodes = self.graph.get_middle_nodes()
        candidates = [
            node for node in middle_nodes
            if self.graph.get_root_category(node) == other_root
        ]

        if not candidates:
            # Fall back to the other root itself
            return other_root

        return random.choice(candidates)

    def sample_siblings(
        self,
        descriptor: str,
        count: int
    ) -> List[str]:
        """
        Sample sibling descriptors (same parent).

        Args:
            descriptor: The descriptor
            count: Number of siblings to sample

        Returns:
            List of sibling descriptors

        Example:
            >>> siblings = gen.sample_siblings("chocolate", 2)
            >>> # Returns other children of chocolate's parent
        """
        parent = self.graph.get_parent(descriptor)

        if parent is None:
            return []

        siblings = self.graph.get_children(parent)
        siblings = [s for s in siblings if s != descriptor]

        if len(siblings) <= count:
            return siblings

        return random.sample(siblings, count)

    def sample_cousins(
        self,
        descriptor: str,
        count: int
    ) -> List[str]:
        """
        Sample cousin descriptors (same grandparent, different parent).

        Args:
            descriptor: The descriptor
            count: Number of cousins to sample

        Returns:
            List of cousin descriptors

        Example:
            >>> cousins = gen.sample_cousins("chocolate", 2)
            >>> # Returns children of parent's siblings
        """
        parent = self.graph.get_parent(descriptor)

        if parent is None:
            return []

        grandparent = self.graph.get_parent(parent)

        if grandparent is None:
            return []

        # Get parent's siblings
        uncles = self.graph.get_children(grandparent)
        uncles = [u for u in uncles if u != parent]

        # Get cousins (children of uncles)
        cousins = []
        for uncle in uncles:
            cousins.extend(self.graph.get_children(uncle))

        if not cousins:
            return []

        if len(cousins) <= count:
            return cousins

        return random.sample(cousins, count)

    def sample_by_distance(
        self,
        target: str,
        candidates: List[str],
        count: int,
        distance_range: tuple = (2, 5)
    ) -> List[str]:
        """
        Sample descriptors by path distance from target.

        Args:
            target: Target descriptor
            candidates: List of candidate descriptors
            count: Number to sample
            distance_range: (min_distance, max_distance) range

        Returns:
            List of sampled descriptors

        Example:
            >>> distractors = gen.sample_by_distance(
            ...     "chocolate",
            ...     all_descriptors,
            ...     count=3,
            ...     distance_range=(2, 5)
            ... )
        """
        min_dist, max_dist = distance_range

        # Filter by distance
        valid_candidates = []
        for candidate in candidates:
            if candidate == target:
                continue

            distance = self.graph.get_path_distance(target, candidate)

            if distance is not None and min_dist <= distance <= max_dist:
                valid_candidates.append(candidate)

        if not valid_candidates:
            return []

        if len(valid_candidates) <= count:
            return valid_candidates

        return random.sample(valid_candidates, count)

    def sample_non_siblings(
        self,
        descriptor: str,
        parent: str,
        count: int
    ) -> List[str]:
        """
        Sample non-sibling descriptors (for A3 distractors).

        Args:
            descriptor: The descriptor
            parent: Parent of descriptor
            count: Number of distractors

        Returns:
            List of non-sibling descriptors (cousins, uncles, unrelated)
        """
        distractors = []

        # Get actual siblings
        siblings = set(self.graph.get_children(parent))
        siblings.discard(descriptor)

        # Try cousins first
        grandparent = self.graph.get_parent(parent)
        if grandparent:
            uncles = [u for u in self.graph.get_children(grandparent) if u != parent]
            for uncle in uncles:
                cousins = self.graph.get_children(uncle)
                distractors.extend(cousins)

        # Add uncles if we need more
        if grandparent and len(distractors) < count:
            uncles = [u for u in self.graph.get_children(grandparent) if u != parent]
            distractors.extend(uncles)

        # Add unrelated if we still need more
        if len(distractors) < count:
            all_descriptors = list(self.graph.descriptions)
            unrelated = [d for d in all_descriptors if d not in siblings and d != descriptor and d != parent]
            distractors.extend(unrelated)

        # Remove duplicates and sample
        distractors = list(set(distractors))

        if len(distractors) <= count:
            return distractors

        return random.sample(distractors, count)

    def generate_wrong_paths(
        self,
        descriptor: str,
        correct_path_list: List[str],
        count: int
    ) -> List[str]:
        """
        Generate wrong path strings (for A4 distractors).

        Strategies:
            - Wrong root (different root category)
            - Wrong middle (correct root and leaf, wrong intermediate)
            - Wrong order (correct nodes, shuffled)

        Args:
            descriptor: The target descriptor
            correct_path_list: Correct path as list [root, ..., descriptor]
            count: Number of distractors

        Returns:
            List of wrong path strings
        """
        distractors = []

        # Strategy 1: Wrong root
        if len(distractors) < count:
            wrong_roots = [r for r in self.graph.get_root_categories() if r != correct_path_list[0]]
            if wrong_roots:
                wrong_root = random.choice(wrong_roots)
                wrong_path = " → ".join([wrong_root] + correct_path_list[1:])
                distractors.append(wrong_path)

        # Strategy 2: Wrong middle (if path is long enough)
        if len(distractors) < count and len(correct_path_list) >= 3:
            # Replace middle node
            middle_idx = len(correct_path_list) // 2
            all_middle = self.graph.get_middle_nodes()
            wrong_middle = [m for m in all_middle if m not in correct_path_list]
            if wrong_middle:
                wrong_node = random.choice(wrong_middle)
                wrong_path_list = correct_path_list.copy()
                wrong_path_list[middle_idx] = wrong_node
                wrong_path = " → ".join(wrong_path_list)
                distractors.append(wrong_path)

        # Strategy 3: Wrong order
        if len(distractors) < count and len(correct_path_list) >= 3:
            shuffled = correct_path_list.copy()
            random.shuffle(shuffled)
            # Make sure it's actually different
            if shuffled != correct_path_list:
                wrong_path = " → ".join(shuffled)
                distractors.append(wrong_path)

        # If we still need more, generate random paths
        while len(distractors) < count:
            random_nodes = random.sample(list(self.graph.descriptions), min(len(correct_path_list), 4))
            random_path = " → ".join(random_nodes)
            if random_path not in distractors and random_path != " → ".join(correct_path_list):
                distractors.append(random_path)

        return distractors[:count]

    def generate_lca_distractors(
        self,
        descriptor1: str,
        descriptor2: str,
        correct_lca: str,
        count: int
    ) -> List[str]:
        """
        Generate LCA distractors (for A5).

        Strategies:
            - Too high (e.g., root when middle is correct)
            - Too low (descendant, not ancestor of both)
            - Ancestor of only one

        Args:
            descriptor1: First descriptor
            descriptor2: Second descriptor
            correct_lca: Correct LCA
            count: Number of distractors

        Returns:
            List of distractor nodes
        """
        distractors = []

        # Get ancestors of both
        ancestors1 = set(self.graph.get_ancestors(descriptor1))
        ancestors2 = set(self.graph.get_ancestors(descriptor2))
        common_ancestors = ancestors1 & ancestors2

        # Strategy 1: Too high (higher ancestor)
        higher_ancestors = [a for a in common_ancestors if a != correct_lca]
        if higher_ancestors and len(distractors) < count:
            distractors.append(random.choice(higher_ancestors))

        # Strategy 2: Ancestor of only one
        only_one = (ancestors1 - ancestors2) | (ancestors2 - ancestors1)
        only_one = [a for a in only_one if a != descriptor1 and a != descriptor2]
        if only_one and len(distractors) < count:
            distractors.append(random.choice(only_one))

        # Strategy 3: Random unrelated node
        all_nodes = list(self.graph.descriptions)
        unrelated = [n for n in all_nodes if n not in common_ancestors and n != descriptor1 and n != descriptor2]
        while len(distractors) < count and unrelated:
            node = random.choice(unrelated)
            if node not in distractors:
                distractors.append(node)
                unrelated.remove(node)

        return distractors[:count]

    def generate_wrong_rankings(
        self,
        candidates: List[str],
        count: int
    ) -> List[str]:
        """
        Generate wrong ranking strings (for E1).

        Args:
            candidates: List of candidates in correct order
            count: Number of wrong rankings

        Returns:
            List of wrong ranking strings
        """
        import itertools

        distractors = []
        correct_ranking = " > ".join(candidates)

        # Generate some permutations
        all_perms = list(itertools.permutations(candidates))

        # Filter out correct one
        wrong_perms = [p for p in all_perms if list(p) != candidates]

        # Sample from wrong permutations
        sampled_perms = random.sample(wrong_perms, min(count, len(wrong_perms)))

        for perm in sampled_perms:
            ranking_str = " > ".join(perm)
            distractors.append(ranking_str)

        return distractors[:count]
