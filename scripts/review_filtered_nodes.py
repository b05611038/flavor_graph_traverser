#!/usr/bin/env python3
"""
Review Tool for Filtered Nodes
===============================

Helper script to review filtered nodes and build exception lists.
"""

import json
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from flavor_filter import FlavorFilter


def export_for_review(filter_obj: FlavorFilter, output_file: str = 'filtered_nodes_review.json'):
    """Export filtered nodes with metadata for manual review."""

    nodes_with_metadata = filter_obj.filter_nodes(stage='all', return_metadata=True)

    # Organize by root category for easier review
    by_category = {}
    for node_info in nodes_with_metadata:
        cat = node_info['root_category'] or 'unknown'
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(node_info)

    # Sort categories by node count
    sorted_categories = sorted(by_category.items(), key=lambda x: -len(x[1]))

    # Convert sets to lists for JSON serialization
    config_json = {}
    for k, v in filter_obj.config.items():
        if isinstance(v, set):
            config_json[k] = list(v)
        else:
            config_json[k] = v

    output = {
        'summary': {
            'total_valid_nodes': len(nodes_with_metadata),
            'num_categories': len(by_category),
            'config': config_json,
        },
        'categories': {
            cat: {
                'count': len(nodes),
                'nodes': [n['node'] for n in nodes],
                'sample': nodes[:10]  # First 10 with metadata
            }
            for cat, nodes in sorted_categories
        }
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✓ Exported {len(nodes_with_metadata)} nodes to {output_file}")
    print(f"\nReview the file and create exception lists:")
    print(f"  1. Find problematic nodes → add to blacklist")
    print(f"  2. Find good nodes that were filtered → add to whitelist")

    return output


def create_exception_lists_template():
    """Create template files for exception lists."""

    blacklist_template = """# Manual Blacklist
# Add problematic nodes here (one per line)
# Lines starting with # are ignored

# Example:
# some_bad_flavor
# another_problematic_node
"""

    whitelist_template = """# Manual Whitelist
# Add nodes that should be included (one per line)
# Lines starting with # are ignored

# Example:
# some_good_flavor
# important_node
"""

    with open('blacklist.txt', 'w') as f:
        f.write(blacklist_template)

    with open('whitelist.txt', 'w') as f:
        f.write(whitelist_template)

    print("✓ Created template files:")
    print("  - blacklist.txt (add problematic nodes)")
    print("  - whitelist.txt (add nodes to force include)")


def load_exception_lists():
    """Load exception lists from text files."""

    def read_list(filename):
        try:
            with open(filename, 'r') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                return set(lines)
        except FileNotFoundError:
            return set()

    blacklist = read_list('blacklist.txt')
    whitelist = read_list('whitelist.txt')

    print(f"Loaded exception lists:")
    print(f"  Blacklist: {len(blacklist)} nodes")
    print(f"  Whitelist: {len(whitelist)} nodes")

    return blacklist, whitelist


def interactive_review():
    """Interactive review of filtered nodes."""

    # Load graph
    print("Loading SYSTEM graph...")
    data = load_graph_data('system_graph.pkl')
    graph = CoffeeDescriptionGraph(data['descriptions'], data['connections'], root=data['root'])

    # Create filter with default config
    print("\nInitializing filter with default config...")
    filter_obj = FlavorFilter(graph)

    # Show statistics
    stats = filter_obj.get_statistics()
    print("\n" + "="*70)
    print(f"Filtering Results: {stats['final_valid']} / {stats['total_nodes']} nodes ({stats['filter_rate']})")
    print("="*70)

    # Load exception lists
    blacklist, whitelist = load_exception_lists()
    if blacklist:
        filter_obj.add_to_blacklist(list(blacklist))
    if whitelist:
        filter_obj.add_to_whitelist(list(whitelist))

    # Export for review
    print("\nExporting nodes for review...")
    export_for_review(filter_obj, 'filtered_nodes_review.json')

    # Show breakdown by category
    print("\n" + "="*70)
    print("Nodes by Root Category (Top 20)")
    print("="*70)

    by_cat = filter_obj.get_filtered_by_root_category()
    for i, (cat, nodes) in enumerate(sorted(by_cat.items(), key=lambda x: -len(x[1]))[:20], 1):
        print(f"{i:2d}. {cat}: {len(nodes)} nodes")
        print(f"    Sample: {', '.join(nodes[:3])}")

    # Suggest next steps
    print("\n" + "="*70)
    print("Next Steps")
    print("="*70)
    print("""
1. Review 'filtered_nodes_review.json' file
   - Check if nodes look like actual flavors
   - Identify problematic categories

2. Adjust configuration if needed:
   # Edit this script or create new config
   config = {
       'min_depth': 2,  # Try 3 for deeper nodes
       'min_siblings': 1,  # Require siblings for A3 questions
       # ... etc
   }

3. Add exceptions:
   - Edit 'blacklist.txt' - add problematic nodes
   - Edit 'whitelist.txt' - add good nodes that were filtered

4. Re-run this script to see updated results

5. Generate questions:
   python generate_questions_with_filter.py
    """)


def show_category_samples():
    """Show sample nodes from each category for quality check."""

    # Load graph
    data = load_graph_data('system_graph.pkl')
    graph = CoffeeDescriptionGraph(data['descriptions'], data['connections'], root=data['root'])

    filter_obj = FlavorFilter(graph)
    by_cat = filter_obj.get_filtered_by_root_category()

    print("="*70)
    print("Category Quality Check - Random Samples")
    print("="*70)

    import random
    for cat, nodes in sorted(by_cat.items(), key=lambda x: -len(x[1]))[:15]:
        print(f"\n{cat} ({len(nodes)} nodes):")

        # Show 5 random samples
        samples = random.sample(nodes, min(5, len(nodes)))
        for node in samples:
            # Get path to show hierarchy
            paths = graph.pathways_between_descriptions(graph.root, node, reverse_direction=True, formated_string=False)
            if paths:
                path_str = ' → '.join(paths[0][-3:])  # Last 3 levels
                print(f"  • {node}")
                print(f"    Path: ...{path_str}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--samples':
        show_category_samples()
    elif len(sys.argv) > 1 and sys.argv[1] == '--create-templates':
        create_exception_lists_template()
    else:
        interactive_review()
