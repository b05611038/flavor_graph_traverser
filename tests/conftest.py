"""
Pytest Configuration and Fixtures

Shared fixtures for all tests.
"""

import pytest
import os
from pathlib import Path
from FlavorGraphTraverser import load_graph_data, CoffeeDescriptionGraph
from FlavorGraphTraverser.evaluation.tools import GraphToolExecutor


@pytest.fixture(scope="session")
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def coffee_flavor_wheel_path(project_root):
    """Get path to coffee_flavor_wheel graph."""
    return project_root / "data" / "graphs" / "coffee_flavor_wheel.json"


@pytest.fixture(scope="session")
def coffee_flavor_wheel_graph(coffee_flavor_wheel_path):
    """Load coffee_flavor_wheel graph."""
    if not coffee_flavor_wheel_path.exists():
        pytest.skip(f"Graph file not found: {coffee_flavor_wheel_path}")

    data = load_graph_data(str(coffee_flavor_wheel_path))
    return CoffeeDescriptionGraph(
        data['descriptions'],
        data['connections'],
        root=data['root']
    )


@pytest.fixture(scope="session")
def graph_executor(coffee_flavor_wheel_graph):
    """Create GraphToolExecutor with coffee_flavor_wheel."""
    return GraphToolExecutor(coffee_flavor_wheel_graph)


@pytest.fixture(scope="session")
def sample_descriptors(coffee_flavor_wheel_graph):
    """Get sample descriptors from the graph."""
    all_desc = coffee_flavor_wheel_graph.descriptions
    return {
        'valid': all_desc[:5] if len(all_desc) >= 5 else all_desc,
        'invalid': ['unknown_flavor', 'nonexistent', 'fake_descriptor']
    }


@pytest.fixture
def ollama_config():
    """Ollama client configuration."""
    return {
        'client_type': 'ollama',
        'model': 'tinyllama',
        'base_url': os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    }


@pytest.fixture
def openrouter_config():
    """OpenRouter client configuration."""
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set")

    return {
        'client_type': 'openrouter',
        'model': 'anthropic/claude-haiku',  # Use cheapest model for tests
        'api_key': api_key
    }
