# Testing Guide

Comprehensive testing infrastructure for FlavorGraphTraverser.

## Test Suite Overview

**Total: 47 tests, all passing** ✅

- **Unit Tests**: 39 tests
- **Integration Tests**: 8 tests
- **Coverage**: Client layer, tool interface, graph operations

## Quick Start

```bash
# Run all tests
pytest

# Quick tests (no Ollama required)
./scripts/run_tests.sh quick

# Specific test categories
./scripts/run_tests.sh unit          # Unit tests only
./scripts/run_tests.sh integration   # Integration tests
./scripts/run_tests.sh tools         # Tool tests only
./scripts/run_tests.sh client        # Client tests only

# With coverage report
./scripts/run_tests.sh coverage
```

---

## Test Categories

### 1. Client Layer Tests (16 tests)

#### `tests/client/test_base.py` (9 tests)

Tests the abstract base client interface and data classes.

**Tests:**
- ✅ Message dataclass creation and fields
- ✅ Message with tool calls
- ✅ Message with tool results
- ✅ UsageStats dataclass
- ✅ LLMResponse dataclass
- ✅ LLMResponse with usage stats
- ✅ LLMResponse with tool calls
- ✅ BaseClient cannot be instantiated directly (abstract)
- ✅ BaseClient.format_messages() conversion

**Coverage:**
- `Message`, `UsageStats`, `LLMResponse` data classes
- `BaseClient` abstract interface
- Message formatting for API compatibility

#### `tests/client/test_ollama.py` (7 tests)

Tests OllamaClient with local server (localhost:11434).

**Tests:**
- ✅ Client creation with configuration
- ✅ Server availability check
- ✅ List available models
- ✅ Simple query and response
- ✅ Query with usage statistics
- ✅ Function calling support check (returns False for Ollama)
- ✅ Multi-turn conversation handling

**Requirements:**
- Ollama server running at localhost:11434
- TinyLlama model installed
- Tests auto-skip if server unavailable

**Coverage:**
- Connection to Ollama server
- API request/response handling
- Token usage tracking
- Multi-turn conversation state

---

### 2. Tool Interface Tests (23 tests)

#### `tests/tools/test_definitions.py` (7 tests)

Tests tool definition schemas for function calling.

**Tests:**
- ✅ get_tool_definitions() returns list of 3 tools
- ✅ All tools have required fields (type, function, parameters)
- ✅ Tool names match constants (TOOL_VALIDATE, TOOL_GET_PARENT, TOOL_GET_CHILDREN)
- ✅ validate_descriptors schema (array, max 10 items)
- ✅ get_parent schema (string parameter)
- ✅ get_children schema (string parameter)
- ✅ Descriptions mention key information (no call limit vs budget, shared budget)

**Coverage:**
- OpenAI function calling format compliance
- Tool parameter schemas
- Tool metadata (descriptions, limits)

#### `tests/tools/test_executor.py` (16 tests)

Tests GraphToolExecutor against coffee_flavor_wheel graph.

**Tests - Initialization:**
- ✅ Executor initialization with graph

**Tests - validate_descriptors:**
- ✅ All valid descriptors
- ✅ All invalid descriptors
- ✅ Mixed valid/invalid descriptors
- ✅ Max 10 descriptor limit enforcement

**Tests - get_parent:**
- ✅ Valid descriptor returns parents
- ✅ Invalid descriptor returns error
- ✅ Root node returns empty list

**Tests - get_children:**
- ✅ Valid descriptor returns children
- ✅ Invalid descriptor returns error
- ✅ Leaf node returns empty list

**Tests - execute():**
- ✅ Execute validate_descriptors via execute()
- ✅ Execute get_parent via execute()
- ✅ Execute get_children via execute()
- ✅ Unknown tool raises ValueError

**Tests - Helper methods:**
- ✅ is_valid_descriptor() boolean check

**Coverage:**
- Tool execution against real graph data
- Error handling for invalid descriptors
- Edge cases (root nodes, leaf nodes)
- Batch validation (up to 10 descriptors)

---

### 3. Integration Tests (8 tests)

#### `tests/integration/test_client_tools_integration.py` (8 tests)

Tests complete workflow combining clients and tools.

**Tests:**
- ✅ Query with tool definitions (compatibility test)
- ✅ Manual tool simulation (multi-turn workflow)
- ✅ Executor handles both valid and invalid descriptors
- ✅ Complete tool workflow (validate → get_parent → get_children)
- ✅ Batch validation with mixed valid/invalid
- ✅ Tool definitions follow OpenAI format
- ✅ Error propagation in tool results
- ✅ Tool result structure consistency

**Coverage:**
- End-to-end client + tools workflow
- Tool call simulation
- Error handling across layers
- OpenAI API format compliance

---

## Test Fixtures

Shared fixtures defined in `tests/conftest.py`:

### Session-Scoped Fixtures

```python
@pytest.fixture(scope="session")
def project_root():
    """Project root directory path."""

@pytest.fixture(scope="session")
def coffee_flavor_wheel_path(project_root):
    """Path to coffee_flavor_wheel.pkl."""

@pytest.fixture(scope="session")
def coffee_flavor_wheel_graph(coffee_flavor_wheel_path):
    """Loaded CoffeeDescriptionGraph from coffee_flavor_wheel."""

@pytest.fixture(scope="session")
def graph_executor(coffee_flavor_wheel_graph):
    """GraphToolExecutor instance."""

@pytest.fixture(scope="session")
def sample_descriptors(coffee_flavor_wheel_graph):
    """Sample valid and invalid descriptors."""
```

### Function-Scoped Fixtures

```python
@pytest.fixture
def ollama_config():
    """Ollama client configuration dict."""

@pytest.fixture
def openrouter_config():
    """OpenRouter client configuration (requires API key)."""
```

---

## Running Tests

### Command-Line Options

```bash
# Verbose output
pytest -v

# Show test execution times
pytest --durations=10

# Stop on first failure
pytest -x

# Run specific test file
pytest tests/tools/test_executor.py

# Run specific test class
pytest tests/tools/test_executor.py::TestGraphToolExecutor

# Run specific test method
pytest tests/tools/test_executor.py::TestGraphToolExecutor::test_validate_descriptors_all_valid

# Run tests matching pattern
pytest -k "validate"

# Generate coverage report
pytest --cov=FlavorGraphTraverser --cov-report=html
```

### Test Runner Script

The `scripts/run_tests.sh` script provides shortcuts:

```bash
# Run all tests
./scripts/run_tests.sh

# Unit tests only (tools + client)
./scripts/run_tests.sh unit

# Integration tests
./scripts/run_tests.sh integration

# Tool tests only
./scripts/run_tests.sh tools

# Client tests only
./scripts/run_tests.sh client

# Quick tests (no Ollama)
./scripts/run_tests.sh quick

# With coverage report
./scripts/run_tests.sh coverage

# Watch mode (requires pytest-watch)
./scripts/run_tests.sh watch
```

---

## Test Requirements

### Minimal Requirements (Quick Tests)

```bash
# Only Python dependencies needed
pip install pytest
pip install -r requirements.txt

# Run tests that don't require Ollama
./scripts/run_tests.sh quick
```

**Tests that run:**
- All tool definition tests (7)
- All tool executor tests (16)
- All base client tests (9)

**Total: 32 tests**

### Full Requirements (All Tests)

```bash
# Python dependencies
pip install pytest pytest-cov
pip install -r requirements.txt

# Ollama server required
# Running at localhost:11434
# With TinyLlama model installed
```

**Additional tests:**
- Ollama client tests (7)
- Full integration tests (8)

**Total: 47 tests**

---

## Coverage Report

Generate HTML coverage report:

```bash
pytest --cov=FlavorGraphTraverser --cov-report=html --cov-report=term
```

View report:

```bash
open htmlcov/index.html
```

**Current Coverage:**
- `FlavorGraphTraverser.evaluation.client`: High coverage
- `FlavorGraphTraverser.evaluation.tools`: High coverage
- `FlavorGraphTraverser.graph`: Covered via integration
- `FlavorGraphTraverser.loader`: Covered via fixtures

---

## Continuous Integration

### GitHub Actions

Example `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10', '3.11']

    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    - name: Run quick tests
      run: ./scripts/run_tests.sh quick
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## Writing New Tests

### Test Structure Template

```python
"""
Tests for NewModule

Description of what this test module covers.
"""

import pytest
from FlavorGraphTraverser.evaluation.newmodule import NewClass


class TestNewClass:
    """Test NewClass functionality."""

    def test_initialization(self):
        """Should initialize with correct parameters."""
        obj = NewClass(param="value")
        assert obj.param == "value"

    def test_method_success_case(self):
        """Should perform operation successfully."""
        obj = NewClass()
        result = obj.method()
        assert result == expected_value

    def test_method_error_case(self):
        """Should raise error for invalid input."""
        obj = NewClass()
        with pytest.raises(ValueError, match="error message"):
            obj.method(invalid_input)

    @pytest.mark.skipif(
        condition,
        reason="Requires external dependency"
    )
    def test_with_external_dependency(self):
        """Should work with external service."""
        # Test implementation
```

### Test Best Practices

1. **Descriptive names**: Use `test_method_should_do_something()` format
2. **One assertion focus**: Each test should verify one behavior
3. **Arrange-Act-Assert**: Structure tests clearly
4. **Use fixtures**: Share setup code via conftest.py
5. **Mock external dependencies**: Don't rely on external services
6. **Test edge cases**: Empty inputs, None, invalid types
7. **Document requirements**: Use skipif for optional dependencies

---

## Troubleshooting

### Common Issues

**1. Import Errors**

```bash
# Install package in editable mode
pip install -e .
```

**2. Ollama Tests Failing**

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Run without Ollama tests
./scripts/run_tests.sh quick
```

**3. Graph File Not Found**

```bash
# Generate graphs
python scripts/dump_graphs.py

# Or run with auto-skip
pytest  # Tests auto-skip if files missing
```

**4. pytest Command Not Found**

```bash
# Use python -m pytest instead
python -m pytest

# Or install pytest
pip install pytest
```

---

## Test Markers

Define custom markers in `pytest.ini`:

```ini
[pytest]
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    requires_ollama: marks tests that require Ollama server
    requires_api: marks tests that require API keys
```

Use markers:

```bash
# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run tests requiring ollama
pytest -m requires_ollama
```

---

## See Also

- [pytest documentation](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
