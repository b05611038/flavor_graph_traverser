"""
Hierarchical Filtering Pipeline for Question Generation
========================================================

Multi-stage filtering with adjustable parameters and exception lists.
"""

from typing import List, Dict, Set, Optional, Union
from FlavorGraphTraverser import CoffeeDescriptionGraph


class FlavorFilter:
    """
    Hierarchical filtering pipeline for selecting valid question targets.

    Pipeline stages:
    1. Structural filters (hard constraints)
    2. Category filters (exclude problematic categories)
    3. Quality filters (ensure good question generation)
    4. Exception handling (manual overrides)
    """

    def __init__(
        self,
        graph: CoffeeDescriptionGraph,
        config: Optional[Dict] = None
    ):
        self.graph = graph
        self.config = config or self._default_config()

        # Pre-compute graph properties
        self._cache = self._build_cache()

    def _default_config(self) -> Dict:
        """Default filtering configuration."""
        return {
            # Stage 1: Structural
            'require_leaf_node': True,
            'min_depth': 2,  # At least: root -> category -> target
            'max_depth': None,

            # Stage 2: Category filtering
            'excluded_root_categories': [
                'taste',  # Abstract concept, not flavor
                'defected',  # Quality issues, not flavors
                'other',  # Catch-all category
            ],
            'excluded_keywords': [
                'ROOT:',
                'overall',  # "overall sweet" is meta-category
                'general',
                'basic',
            ],

            # Stage 3: Quality
            'min_siblings': 0,  # For A3 questions
            'require_valid_path': True,

            # Stage 4: Exceptions
            'manual_blacklist': set(),  # Add problematic nodes here
            'manual_whitelist': set(),  # Force include specific nodes
        }

    def _build_cache(self) -> Dict:
        """Pre-compute graph properties for faster filtering."""
        cache = {
            'leaf_nodes': set(),
            'node_depths': {},
            'root_categories': set(self.graph.children_of_description(self.graph.root)),
            'node_to_root_category': {},
            'node_siblings': {},
        }

        # Compute for all nodes
        for node in self.graph.descriptions:
            # Leaf check
            children = self.graph.children_of_description(node)
            if len(children) == 0:
                cache['leaf_nodes'].add(node)

            # Depth
            paths = self.graph.pathways_between_descriptions(
                self.graph.root, node,
                reverse_direction=True,
                formated_string=False
            )
            if paths:
                cache['node_depths'][node] = len(paths[0]) - 1
                # Root category (first after root)
                if len(paths[0]) > 1:
                    cache['node_to_root_category'][node] = paths[0][-2]

            # Siblings
            parents = self.graph.parents_of_description(node)
            if parents:
                siblings = [
                    s for s in self.graph.children_of_description(parents[0])
                    if s != node
                ]
                cache['node_siblings'][node] = siblings

        return cache

    def filter_nodes(
        self,
        stage: str = 'all',
        return_metadata: bool = False
    ) -> Union[List[str], List[Dict]]:
        """
        Apply filtering pipeline.

        Args:
            stage: Which stages to apply ('structural', 'category', 'quality', 'all')
            return_metadata: If True, return dicts with filtering info

        Returns:
            List of valid node names, or list of dicts with metadata
        """
        candidates = set(self.graph.descriptions)
        metadata = {node: {'stages_passed': []} for node in candidates}

        # Stage 1: Structural filters
        if stage in ['structural', 'all']:
            candidates = self._apply_structural_filters(candidates, metadata)

        # Stage 2: Category filters
        if stage in ['category', 'all']:
            candidates = self._apply_category_filters(candidates, metadata)

        # Stage 3: Quality filters
        if stage in ['quality', 'all']:
            candidates = self._apply_quality_filters(candidates, metadata)

        # Stage 4: Exception handling
        if stage == 'all':
            candidates = self._apply_exceptions(candidates, metadata)

        # Return results
        if return_metadata:
            return [
                {
                    'node': node,
                    'depth': self._cache['node_depths'].get(node, 0),
                    'root_category': self._cache['node_to_root_category'].get(node, None),
                    'siblings': len(self._cache['node_siblings'].get(node, [])),
                    'stages_passed': metadata[node]['stages_passed'],
                }
                for node in sorted(candidates)
            ]
        else:
            return sorted(candidates)

    def _apply_structural_filters(
        self,
        candidates: Set[str],
        metadata: Dict
    ) -> Set[str]:
        """Stage 1: Hard structural constraints."""
        filtered = set()

        for node in candidates:
            passed = True
            reasons = []

            # Check leaf node requirement
            if self.config['require_leaf_node']:
                if node not in self._cache['leaf_nodes']:
                    passed = False
                    reasons.append('not_leaf')

            # Check depth constraints
            depth = self._cache['node_depths'].get(node, 0)

            if self.config['min_depth'] and depth < self.config['min_depth']:
                passed = False
                reasons.append(f'depth_too_shallow({depth})')

            if self.config['max_depth'] and depth > self.config['max_depth']:
                passed = False
                reasons.append(f'depth_too_deep({depth})')

            # Check valid path
            if self.config['require_valid_path']:
                if node not in self._cache['node_depths']:
                    passed = False
                    reasons.append('no_valid_path')

            if passed:
                filtered.add(node)
                metadata[node]['stages_passed'].append('structural')
            else:
                metadata[node]['filter_reasons'] = reasons

        return filtered

    def _apply_category_filters(
        self,
        candidates: Set[str],
        metadata: Dict
    ) -> Set[str]:
        """Stage 2: Category-based filtering."""
        filtered = set()

        for node in candidates:
            passed = True
            reasons = []

            # Check root category
            root_cat = self._cache['node_to_root_category'].get(node)
            if root_cat in self.config['excluded_root_categories']:
                passed = False
                reasons.append(f'excluded_root_category({root_cat})')

            # Check keywords
            for keyword in self.config['excluded_keywords']:
                if keyword.lower() in node.lower():
                    passed = False
                    reasons.append(f'excluded_keyword({keyword})')
                    break

            if passed:
                filtered.add(node)
                metadata[node]['stages_passed'].append('category')
            else:
                metadata[node]['filter_reasons'] = metadata.get(node, {}).get('filter_reasons', []) + reasons

        return filtered

    def _apply_quality_filters(
        self,
        candidates: Set[str],
        metadata: Dict
    ) -> Set[str]:
        """Stage 3: Quality constraints for question generation."""
        filtered = set()

        for node in candidates:
            passed = True
            reasons = []

            # Check sibling availability (for A3 questions)
            if self.config['min_siblings'] > 0:
                siblings = self._cache['node_siblings'].get(node, [])
                if len(siblings) < self.config['min_siblings']:
                    passed = False
                    reasons.append(f'insufficient_siblings({len(siblings)})')

            if passed:
                filtered.add(node)
                metadata[node]['stages_passed'].append('quality')
            else:
                metadata[node]['filter_reasons'] = metadata.get(node, {}).get('filter_reasons', []) + reasons

        return filtered

    def _apply_exceptions(
        self,
        candidates: Set[str],
        metadata: Dict
    ) -> Set[str]:
        """Stage 4: Manual exception handling."""
        # Remove blacklisted
        filtered = candidates - self.config['manual_blacklist']

        # Add whitelisted
        for node in self.config['manual_whitelist']:
            if node in self.graph.descriptions:
                filtered.add(node)
                if node not in metadata:
                    metadata[node] = {'stages_passed': []}
                metadata[node]['stages_passed'].append('manual_whitelist')

        return filtered

    def get_statistics(self) -> Dict:
        """Get filtering statistics."""
        all_nodes = set(self.graph.descriptions)

        structural = self._apply_structural_filters(
            all_nodes,
            {node: {'stages_passed': []} for node in all_nodes}
        )

        category = self._apply_category_filters(
            structural,
            {node: {'stages_passed': []} for node in structural}
        )

        quality = self._apply_quality_filters(
            category,
            {node: {'stages_passed': []} for node in category}
        )

        final = self._apply_exceptions(
            quality,
            {node: {'stages_passed': []} for node in quality}
        )

        return {
            'total_nodes': len(all_nodes),
            'after_structural': len(structural),
            'after_category': len(category),
            'after_quality': len(quality),
            'final_valid': len(final),
            'filter_rate': f"{100 * len(final) / len(all_nodes):.1f}%",
        }

    def update_config(self, **kwargs):
        """Update configuration parameters."""
        self.config.update(kwargs)

    def add_to_blacklist(self, nodes: List[str]):
        """Add nodes to manual blacklist."""
        self.config['manual_blacklist'].update(nodes)

    def add_to_whitelist(self, nodes: List[str]):
        """Add nodes to manual whitelist."""
        self.config['manual_whitelist'].update(nodes)

    def get_filtered_by_root_category(self) -> Dict[str, List[str]]:
        """Get filtered nodes grouped by root category."""
        valid_nodes = self.filter_nodes(stage='all')

        by_category = {}
        for node in valid_nodes:
            cat = self._cache['node_to_root_category'].get(node, 'unknown')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(node)

        return by_category


def preview_filtering(graph: CoffeeDescriptionGraph, config: Optional[Dict] = None):
    """
    Preview filtering results with statistics.

    Returns: FlavorFilter instance for further inspection
    """
    filter_obj = FlavorFilter(graph, config)

    print("="*70)
    print("Filtering Pipeline Preview")
    print("="*70)

    # Show configuration
    print("\n📋 Configuration:")
    print("-"*70)
    for key, value in filter_obj.config.items():
        if isinstance(value, set):
            print(f"  {key}: {list(value) if value else '[]'}")
        else:
            print(f"  {key}: {value}")

    # Show statistics
    print("\n📊 Filtering Statistics:")
    print("-"*70)
    stats = filter_obj.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Show by category
    print("\n📂 Valid Nodes by Root Category:")
    print("-"*70)
    by_cat = filter_obj.get_filtered_by_root_category()
    for cat, nodes in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(nodes)} nodes")
        print(f"    Sample: {nodes[:3]}")

    # Show some filtered out examples
    print("\n❌ Sample Filtered Out Nodes:")
    print("-"*70)
    all_nodes = set(graph.descriptions)
    valid_nodes = set(filter_obj.filter_nodes())
    filtered_out = all_nodes - valid_nodes

    metadata = filter_obj.filter_nodes(stage='all', return_metadata=True)
    metadata_map = {m['node']: m for m in metadata if m['node'] in valid_nodes}

    for node in list(filtered_out)[:5]:
        # Try to find why it was filtered
        test_meta = {'stages_passed': []}
        temp = {node}

        temp = filter_obj._apply_structural_filters(temp, {node: test_meta})
        if not temp:
            print(f"  • {node} (failed: structural)")
            continue

        temp = filter_obj._apply_category_filters(temp, {node: test_meta})
        if not temp:
            print(f"  • {node} (failed: category)")
            continue

        temp = filter_obj._apply_quality_filters(temp, {node: test_meta})
        if not temp:
            print(f"  • {node} (failed: quality)")
            continue

    print("\n" + "="*70)

    return filter_obj


if __name__ == '__main__':
    from FlavorGraphTraverser import load_graph_data

    # Load SYSTEM graph
    data = load_graph_data('system_graph.pkl')
    graph = CoffeeDescriptionGraph(
        data['descriptions'],
        data['connections'],
        root=data['root']
    )

    # Preview with default config
    filter_obj = preview_filtering(graph)

    print("\n💡 Adjustment Examples:")
    print("-"*70)
    print("""
    # Too few results? Relax constraints:
    filter_obj.update_config(min_depth=1)  # Allow shallower nodes
    filter_obj.update_config(require_leaf_node=False)  # Allow intermediate nodes

    # Too many results? Tighten constraints:
    filter_obj.update_config(min_depth=3)  # Require deeper nodes
    filter_obj.update_config(min_siblings=2)  # Require siblings for A3

    # Found problematic node? Add to blacklist:
    filter_obj.add_to_blacklist(['problematic_node_1', 'problematic_node_2'])

    # Want to force include? Add to whitelist:
    filter_obj.add_to_whitelist(['important_node'])

    # Re-generate:
    valid_nodes = filter_obj.filter_nodes(stage='all')
    """)
