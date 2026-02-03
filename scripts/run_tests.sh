#!/bin/bash
# Test Runner Script
# Provides shortcuts for running different test suites

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}FlavorGraphTraverser Test Suite${NC}"
echo ""

# Default: Run all tests
if [ $# -eq 0 ]; then
    echo -e "${GREEN}Running all tests...${NC}"
    pytest
    exit 0
fi

# Parse command
case "$1" in
    unit)
        echo -e "${GREEN}Running unit tests only...${NC}"
        pytest tests/tools tests/client -v
        ;;
    integration)
        echo -e "${GREEN}Running integration tests...${NC}"
        pytest tests/integration -v
        ;;
    tools)
        echo -e "${GREEN}Running tool tests...${NC}"
        pytest tests/tools -v
        ;;
    client)
        echo -e "${GREEN}Running client tests...${NC}"
        pytest tests/client -v
        ;;
    quick)
        echo -e "${GREEN}Running quick tests (no Ollama required)...${NC}"
        pytest tests/tools tests/client/test_base.py -v
        ;;
    coverage)
        echo -e "${GREEN}Running tests with coverage report...${NC}"
        pytest --cov=FlavorGraphTraverser --cov-report=html --cov-report=term
        echo ""
        echo -e "${GREEN}Coverage report generated in htmlcov/index.html${NC}"
        ;;
    watch)
        echo -e "${GREEN}Running tests in watch mode...${NC}"
        pytest-watch
        ;;
    *)
        echo "Usage: $0 {unit|integration|tools|client|quick|coverage|watch}"
        echo ""
        echo "Options:"
        echo "  (none)        Run all tests"
        echo "  unit          Run unit tests only (tools + client)"
        echo "  integration   Run integration tests"
        echo "  tools         Run tool tests only"
        echo "  client        Run client tests only"
        echo "  quick         Run tests that don't require Ollama"
        echo "  coverage      Run tests with coverage report"
        echo "  watch         Run tests in watch mode (requires pytest-watch)"
        exit 1
        ;;
esac
