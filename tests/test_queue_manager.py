#!/usr/bin/env python3
"""
Tests for Queue Manager API

Run with: python -m pytest tests/test_queue_manager.py -v
Or directly: python tests/test_queue_manager.py
"""

import json
import tempfile
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from FlavorGraphTraverser.evaluation.queue_manager import QueueManager


def create_test_data():
    """Create test questions and audit state."""
    questions = {
        "metadata": {
            "total_questions": 10,
            "by_task_type": {
                "A1_root_classification": 4,
                "A2_ancestor_verification": 4,
                "A3_sibling_identification": 2
            }
        },
        "questions": [
            # A1 questions
            {"id": "A1_1", "task_type": "A1_root_classification", "_objects": {"descriptor": "a1_confirmed"}},
            {"id": "A1_2", "task_type": "A1_root_classification", "_objects": {"descriptor": "a1_flagged"}},
            {"id": "A1_3", "task_type": "A1_root_classification", "_objects": {"descriptor": "a1_pending"}},
            {"id": "A1_4", "task_type": "A1_root_classification", "_objects": {"descriptor": "a1_confirmed2"}},
            # A2 questions
            {"id": "A2_1", "task_type": "A2_ancestor_verification", "_objects": {"descriptor": "a2_confirmed"}},
            {"id": "A2_2", "task_type": "A2_ancestor_verification", "_objects": {"descriptor": "a2_flagged"}},
            {"id": "A2_3", "task_type": "A2_ancestor_verification", "_objects": {"descriptor": "a2_pending"}},
            {"id": "A2_4", "task_type": "A2_ancestor_verification", "_objects": {"descriptor": "a2_flagged2"}},
            # A3 questions
            {"id": "A3_1", "task_type": "A3_sibling_identification", "_objects": {"descriptor": "a3_confirmed"}},
            {"id": "A3_2", "task_type": "A3_sibling_identification", "_objects": {"descriptor": "a3_pending"}},
        ]
    }

    audit_state = {
        "A1_1": {"status": "confirmed"},
        "A1_2": {"status": "flagged"},
        # A1_3 is pending (not in audit state)
        "A1_4": {"status": "confirmed"},
        "A2_1": {"status": "confirmed"},
        "A2_2": {"status": "flagged"},
        # A2_3 is pending
        "A2_4": {"status": "flagged"},
        "A3_1": {"status": "confirmed"},
        # A3_2 is pending
    }

    return questions, audit_state


def test_initialization():
    """Test QueueManager initialization."""
    print("\n=== Test: Initialization ===")

    questions_data, audit_state_data = create_test_data()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as qf:
        json.dump(questions_data, qf)
        questions_file = qf.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as af:
        json.dump(audit_state_data, af)
        audit_file = af.name

    qm = QueueManager(questions_file, audit_file)

    assert len(qm.questions) == 10, f"Expected 10 questions, got {len(qm.questions)}"
    assert len(qm.audit_state) == 7, f"Expected 7 audit entries, got {len(qm.audit_state)}"

    print("✓ Initialization successful")
    print(f"  Loaded {len(qm.questions)} questions")
    print(f"  Loaded {len(qm.audit_state)} audit entries")

    # Cleanup
    Path(questions_file).unlink()
    Path(audit_file).unlink()


def test_get_status():
    """Test get_status method."""
    print("\n=== Test: Get Status ===")

    questions_data, audit_state_data = create_test_data()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as qf:
        json.dump(questions_data, qf)
        questions_file = qf.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as af:
        json.dump(audit_state_data, af)
        audit_file = af.name

    qm = QueueManager(questions_file, audit_file)

    # Test confirmed
    assert qm.get_status("A1_1") == "confirmed"
    # Test flagged
    assert qm.get_status("A1_2") == "flagged"
    # Test pending (not in audit state)
    assert qm.get_status("A1_3") == "pending"

    print("✓ Status detection works correctly")
    print("  Confirmed: A1_1")
    print("  Flagged: A1_2")
    print("  Pending: A1_3")

    # Cleanup
    Path(questions_file).unlink()
    Path(audit_file).unlink()


def test_get_stats():
    """Test get_stats method."""
    print("\n=== Test: Get Stats ===")

    questions_data, audit_state_data = create_test_data()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as qf:
        json.dump(questions_data, qf)
        questions_file = qf.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as af:
        json.dump(audit_state_data, af)
        audit_file = af.name

    qm = QueueManager(questions_file, audit_file)

    stats = qm.get_stats()

    # Check A1 stats
    a1_stats = stats['A1_root_classification']
    assert a1_stats['confirmed'] == 2, f"Expected 2 A1 confirmed, got {a1_stats['confirmed']}"
    assert a1_stats['flagged'] == 1, f"Expected 1 A1 flagged, got {a1_stats['flagged']}"
    assert a1_stats['pending'] == 1, f"Expected 1 A1 pending, got {a1_stats['pending']}"
    assert a1_stats['total'] == 4, f"Expected 4 A1 total, got {a1_stats['total']}"

    # Check A2 stats
    a2_stats = stats['A2_ancestor_verification']
    assert a2_stats['confirmed'] == 1
    assert a2_stats['flagged'] == 2
    assert a2_stats['pending'] == 1
    assert a2_stats['total'] == 4

    print("✓ Statistics calculated correctly")
    print(f"  A1: {a1_stats}")
    print(f"  A2: {a2_stats}")

    # Cleanup
    Path(questions_file).unlink()
    Path(audit_file).unlink()


def test_filter_questions():
    """Test filter_questions method."""
    print("\n=== Test: Filter Questions ===")

    questions_data, audit_state_data = create_test_data()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as qf:
        json.dump(questions_data, qf)
        questions_file = qf.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as af:
        json.dump(audit_state_data, af)
        audit_file = af.name

    qm = QueueManager(questions_file, audit_file)

    # Filter by task type
    a1_questions = qm.filter_questions(task_types=['A1_root_classification'])
    assert len(a1_questions) == 4, f"Expected 4 A1 questions, got {len(a1_questions)}"

    # Filter by status
    confirmed = qm.filter_questions(statuses=['confirmed'])
    assert len(confirmed) == 4, f"Expected 4 confirmed questions, got {len(confirmed)}"

    # Exclude status
    not_confirmed = qm.filter_questions(exclude_statuses=['confirmed'])
    assert len(not_confirmed) == 6, f"Expected 6 non-confirmed questions, got {len(not_confirmed)}"

    # Combined filter
    a2_not_confirmed = qm.filter_questions(
        task_types=['A2_ancestor_verification'],
        exclude_statuses=['confirmed']
    )
    assert len(a2_not_confirmed) == 3, f"Expected 3 A2 non-confirmed, got {len(a2_not_confirmed)}"

    print("✓ Filtering works correctly")
    print(f"  A1 questions: {len(a1_questions)}")
    print(f"  Confirmed: {len(confirmed)}")
    print(f"  Not confirmed: {len(not_confirmed)}")
    print(f"  A2 not confirmed: {len(a2_not_confirmed)}")

    # Cleanup
    Path(questions_file).unlink()
    Path(audit_file).unlink()


def test_move_to_front():
    """Test move_to_front method."""
    print("\n=== Test: Move to Front ===")

    questions_data, audit_state_data = create_test_data()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as qf:
        json.dump(questions_data, qf)
        questions_file = qf.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as af:
        json.dump(audit_state_data, af)
        audit_file = af.name

    qm = QueueManager(questions_file, audit_file)

    # Original order: A1_1, A1_2, A1_3, A1_4, A2_1, A2_2, A2_3, A2_4, A3_1, A3_2
    original_first = qm.questions[0]['id']
    assert original_first == "A1_1"

    # Move A2 to front
    qm.move_to_front(task_types=['A2_ancestor_verification'])

    # Check new order
    new_first = qm.questions[0]['id']
    assert new_first == "A2_1", f"Expected A2_1 first, got {new_first}"

    # Check that A2 questions are at front
    first_four = [q['id'] for q in qm.questions[:4]]
    assert all(qid.startswith('A2') for qid in first_four), f"Expected A2 questions at front, got {first_four}"

    print("✓ Move to front works correctly")
    print(f"  Original first: {original_first}")
    print(f"  New first: {new_first}")
    print(f"  First 4: {first_four}")

    # Cleanup
    Path(questions_file).unlink()
    Path(audit_file).unlink()


def test_move_to_back():
    """Test move_to_back method."""
    print("\n=== Test: Move to Back ===")

    questions_data, audit_state_data = create_test_data()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as qf:
        json.dump(questions_data, qf)
        questions_file = qf.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as af:
        json.dump(audit_state_data, af)
        audit_file = af.name

    qm = QueueManager(questions_file, audit_file)

    # Move A1 to back
    qm.move_to_back(task_types=['A1_root_classification'])

    # Check that A1 questions are at back
    last_four = [q['id'] for q in qm.questions[-4:]]
    assert all(qid.startswith('A1') for qid in last_four), f"Expected A1 questions at back, got {last_four}"

    # First question should not be A1
    first = qm.questions[0]['id']
    assert not first.startswith('A1'), f"Expected non-A1 first, got {first}"

    print("✓ Move to back works correctly")
    print(f"  First: {first}")
    print(f"  Last 4: {last_four}")

    # Cleanup
    Path(questions_file).unlink()
    Path(audit_file).unlink()


def test_reorder_by_priority():
    """Test reorder_by_priority method."""
    print("\n=== Test: Reorder by Priority ===")

    questions_data, audit_state_data = create_test_data()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as qf:
        json.dump(questions_data, qf)
        questions_file = qf.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as af:
        json.dump(audit_state_data, af)
        audit_file = af.name

    qm = QueueManager(questions_file, audit_file)

    # Priority: A2 non-confirmed > A3 non-confirmed > confirmed
    qm.reorder_by_priority([
        {'task_types': ['A2_ancestor_verification'], 'exclude_statuses': ['confirmed']},
        {'task_types': ['A3_sibling_identification'], 'exclude_statuses': ['confirmed']},
        {'statuses': ['confirmed']}
    ])

    # Check order
    ids = [q['id'] for q in qm.questions]

    # First 3 should be A2 non-confirmed (Priority 1)
    assert ids[0:3] == ['A2_2', 'A2_3', 'A2_4'], f"Expected A2 non-confirmed first, got {ids[0:3]}"

    # Next should be A3 non-confirmed (Priority 2)
    assert ids[3] == 'A3_2', f"Expected A3_2 next, got {ids[3]}"

    # Confirmed should come after A2/A3 non-confirmed (Priority 3)
    confirmed_ids = [qid for qid in ids if qm.get_status(qid) == 'confirmed']
    # Confirmed should start at position 4 or later
    assert all(ids.index(cid) >= 4 for cid in confirmed_ids), f"Expected confirmed after priority 1&2, got positions {[ids.index(cid) for cid in confirmed_ids]}"

    # Check that A2 and A3 non-confirmed come before all confirmed
    a2_a3_non_confirmed = ['A2_2', 'A2_3', 'A2_4', 'A3_2']
    for qid in a2_a3_non_confirmed:
        assert ids.index(qid) < min(ids.index(cid) for cid in confirmed_ids), f"Expected {qid} before confirmed"

    print("✓ Reorder by priority works correctly")
    print(f"  Order: {ids}")
    print(f"  Priority 1 (A2 non-confirmed): {ids[0:3]}")
    print(f"  Priority 2 (A3 non-confirmed): {ids[3]}")
    print(f"  Priority 3 (confirmed): positions {[ids.index(cid) for cid in confirmed_ids]}")

    # Cleanup
    Path(questions_file).unlink()
    Path(audit_file).unlink()


def test_save_and_reload():
    """Test saving and reloading questions."""
    print("\n=== Test: Save and Reload ===")

    questions_data, audit_state_data = create_test_data()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as qf:
        json.dump(questions_data, qf)
        questions_file = qf.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as af:
        json.dump(audit_state_data, af)
        audit_file = af.name

    # Create queue manager and reorder
    qm1 = QueueManager(questions_file, audit_file)
    qm1.move_to_front(task_types=['A2_ancestor_verification'])
    original_order = [q['id'] for q in qm1.questions]
    qm1.save()

    # Reload and check order is preserved
    qm2 = QueueManager(questions_file, audit_file)
    reloaded_order = [q['id'] for q in qm2.questions]

    assert original_order == reloaded_order, "Order not preserved after save/reload"

    print("✓ Save and reload works correctly")
    print(f"  Order preserved: {len(original_order)} questions")

    # Cleanup
    Path(questions_file).unlink()
    Path(audit_file).unlink()


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Queue Manager API Tests")
    print("=" * 70)

    tests = [
        test_initialization,
        test_get_status,
        test_get_stats,
        test_filter_questions,
        test_move_to_front,
        test_move_to_back,
        test_reorder_by_priority,
        test_save_and_reload,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ Test failed: {test.__name__}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ Test error: {test.__name__}")
            print(f"   Exception: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print("Test Results")
    print("=" * 70)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n✓ All tests passed!")
    else:
        print(f"\n❌ {failed} test(s) failed")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
