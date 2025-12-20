#!/bin/bash
# Test runner script for Resonance

set -e  # Exit on error

echo "===================================="
echo "Resonance Integration Test Suite"
echo "===================================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Install with:"
    echo "   pip install pytest pytest-mock"
    exit 1
fi

# Function to run tests with a specific marker
run_tests() {
    local marker=$1
    local description=$2

    echo "Running: $description"
    echo "------------------------------------"

    if pytest -m "$marker" "$@"; then
        echo "✅ $description passed"
    else
        echo "❌ $description failed"
        return 1
    fi

    echo ""
}

# Default: Run all tests except slow/network
if [ "$1" == "" ]; then
    echo "Running all fast tests (excluding slow/network tests)"
    echo ""
    pytest -m "not slow and not requires_network" tests/

# Run only unit tests
elif [ "$1" == "unit" ]; then
    run_tests "unit" "Unit tests"

# Run only integration tests
elif [ "$1" == "integration" ]; then
    run_tests "integration" "Integration tests"

# Run all tests including slow ones
elif [ "$1" == "all" ]; then
    echo "Running ALL tests (including slow tests)"
    echo ""
    pytest tests/

# Run tests with network access
elif [ "$1" == "network" ]; then
    echo "⚠️  WARNING: This will make real API calls to MusicBrainz/Discogs"
    echo "   Press Ctrl+C to cancel, or wait 5 seconds to continue..."
    sleep 5
    run_tests "requires_network" "Network tests"

# Run specific test file or pattern
else
    echo "Running: $1"
    pytest "$@"
fi

echo ""
echo "===================================="
echo "Test run complete"
echo "===================================="
