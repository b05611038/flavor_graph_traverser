#!/usr/bin/env python3
"""
Inspect duplicate descriptors, texts, and options in questions.

Helps identify questions that reuse the same descriptors or have similar content.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import argparse
from collections import defaultdict
from typing import Dict, List


def check_duplicate_descriptors(questions: List[Dict], task_type_filter: str = None) -> Dict:
    """Check for duplicate descriptors."""
    descriptors = defaultdict(list)

    for q in questions:
        if task_type_filter and q['task_type'] != task_type_filter:
            continue

        desc = q.get('_objects', {}).get('descriptor')
        if desc:
            descriptors[desc].append({
                'id': q['id'],
                'type': q['task_type'],
                'status': q.get('_audit_status', 'unknown')
            })

    # Find duplicates
    duplicates = {k: v for k, v in descriptors.items() if len(v) > 1}
    return duplicates


def check_duplicate_texts(questions: List[Dict], task_type_filter: str = None) -> Dict:
    """Check for duplicate question texts."""
    texts = defaultdict(list)

    for q in questions:
        if task_type_filter and q['task_type'] != task_type_filter:
            continue

        text = q.get('text', '').strip().lower()
        if text:
            texts[text].append({
                'id': q['id'],
                'type': q['task_type']
            })

    duplicates = {k: v for k, v in texts.items() if len(v) > 1}
    return duplicates


def check_similar_options(questions: List[Dict], task_type_filter: str = None) -> Dict:
    """Check for questions with identical option sets."""
    option_sets = defaultdict(list)

    for q in questions:
        if task_type_filter and q['task_type'] != task_type_filter:
            continue

        options = q.get('options', {})
        # Create frozenset of option values for comparison
        option_frozenset = frozenset(options.values())

        if option_frozenset:
            option_sets[option_frozenset].append({
                'id': q['id'],
                'type': q['task_type'],
                'text': q.get('text', '')[:80]
            })

    duplicates = {k: v for k, v in option_sets.items() if len(v) > 1}
    return duplicates


def search_descriptor(questions: List[Dict], search_term: str) -> List[Dict]:
    """Search for questions containing a specific descriptor."""
    results = []

    search_lower = search_term.lower()

    for q in questions:
        # Check descriptor
        desc = q.get('_objects', {}).get('descriptor', '')
        if search_lower in desc.lower():
            results.append({
                'id': q['id'],
                'type': q['task_type'],
                'descriptor': desc,
                'text': q.get('text', '')[:100]
            })
            continue

        # Check question text
        if search_lower in q.get('text', '').lower():
            results.append({
                'id': q['id'],
                'type': q['task_type'],
                'descriptor': desc,
                'text': q.get('text', '')[:100],
                'location': 'question text'
            })
            continue

        # Check options
        for opt_val in q.get('options', {}).values():
            if search_lower in opt_val.lower():
                results.append({
                    'id': q['id'],
                    'type': q['task_type'],
                    'descriptor': desc,
                    'text': q.get('text', '')[:100],
                    'location': 'option',
                    'option_text': opt_val
                })
                break

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Inspect duplicate descriptors and content in questions'
    )
    parser.add_argument(
        'questions_file',
        help='Path to questions JSON file'
    )
    parser.add_argument(
        '--type',
        choices=['descriptors', 'texts', 'options', 'all'],
        default='all',
        help='Type of duplicates to check (default: all)'
    )
    parser.add_argument(
        '--task-type',
        help='Filter by task type (e.g., A1_root_classification)'
    )
    parser.add_argument(
        '--search',
        help='Search for questions containing this term (e.g., "carrot")'
    )
    parser.add_argument(
        '--min-count',
        type=int,
        default=2,
        help='Minimum repetition count to report (default: 2)'
    )

    args = parser.parse_args()

    # Load questions
    with open(args.questions_file, 'r') as f:
        data = json.load(f)
        if isinstance(data, dict) and 'questions' in data:
            questions = data['questions']
        else:
            questions = data

    print("=" * 70)
    print("Duplicate Inspector")
    print("=" * 70)
    print(f"Questions file: {args.questions_file}")
    print(f"Total questions: {len(questions)}")
    if args.task_type:
        filtered = [q for q in questions if q['task_type'] == args.task_type]
        print(f"Filtered to {args.task_type}: {len(filtered)} questions")
    print()

    # Handle search
    if args.search:
        print(f"Searching for '{args.search}'...")
        print("=" * 70)
        results = search_descriptor(questions, args.search)

        if results:
            print(f"Found {len(results)} questions containing '{args.search}':\n")
            for r in results:
                print(f"{r['id']} ({r['type']})")
                if r.get('descriptor'):
                    print(f"  Descriptor: {r['descriptor']}")
                print(f"  Text: {r['text']}...")
                if 'location' in r:
                    print(f"  Found in: {r['location']}")
                    if 'option_text' in r:
                        print(f"  Option: {r['option_text']}")
                print()
        else:
            print(f"No questions found containing '{args.search}'")
        return

    # Check duplicates
    if args.type in ['descriptors', 'all']:
        print("\n1. Duplicate Descriptors")
        print("=" * 70)
        duplicates = check_duplicate_descriptors(questions, args.task_type)

        # Filter by min count
        duplicates = {k: v for k, v in duplicates.items() if len(v) >= args.min_count}

        if duplicates:
            print(f"Found {len(duplicates)} descriptors used multiple times:\n")
            for desc, qlist in sorted(duplicates.items(), key=lambda x: -len(x[1])):
                print(f"'{desc}': used {len(qlist)} times")

                # Group by task type
                by_type = defaultdict(list)
                for q in qlist:
                    by_type[q['type']].append(q['id'])

                for task_type, qids in sorted(by_type.items()):
                    print(f"  {task_type}:")
                    for qid in qids:
                        print(f"    - {qid}")
                print()
        else:
            print("No duplicate descriptors found.\n")

    if args.type in ['texts', 'all']:
        print("\n2. Duplicate Question Texts")
        print("=" * 70)
        duplicates = check_duplicate_texts(questions, args.task_type)

        duplicates = {k: v for k, v in duplicates.items() if len(v) >= args.min_count}

        if duplicates:
            print(f"Found {len(duplicates)} duplicate question texts:\n")
            for text, qlist in sorted(duplicates.items(), key=lambda x: -len(x[1]))[:10]:
                print(f"Text: {text[:80]}...")
                print(f"Used {len(qlist)} times:")
                for q in qlist:
                    print(f"  - {q['id']} ({q['type']})")
                print()
        else:
            print("No duplicate question texts found.\n")

    if args.type in ['options', 'all']:
        print("\n3. Duplicate Option Sets")
        print("=" * 70)
        duplicates = check_similar_options(questions, args.task_type)

        duplicates = {k: v for k, v in duplicates.items() if len(v) >= args.min_count}

        if duplicates:
            print(f"Found {len(duplicates)} duplicate option sets:\n")
            for i, (option_set, qlist) in enumerate(sorted(duplicates.items(), key=lambda x: -len(x[1]))[:10], 1):
                print(f"Option Set #{i} (used {len(qlist)} times):")
                print(f"  Options: {', '.join(sorted(option_set)[:5])}...")
                print(f"  Questions:")
                for q in qlist:
                    print(f"    - {q['id']} ({q['type']}): {q['text']}...")
                print()
        else:
            print("No duplicate option sets found.\n")


if __name__ == '__main__':
    main()
