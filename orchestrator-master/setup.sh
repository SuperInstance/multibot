#!/bin/bash
set -e

# Multi-Agent Orchestrator Setup Script (Bash version)
# This is a bash wrapper around the Python setup script

echo "🚀 Multi-Agent Orchestrator Setup"
echo "=================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    echo "Please install Python 3.8 or higher and try again"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $PYTHON_VERSION found, but Python $REQUIRED_VERSION or higher is required"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION found"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if setup.py exists
SETUP_SCRIPT="$SCRIPT_DIR/setup.py"
if [ ! -f "$SETUP_SCRIPT" ]; then
    echo "❌ Setup script not found: $SETUP_SCRIPT"
    exit 1
fi

echo "📋 Running Python setup script..."
echo ""

# Run the Python setup script
python3 "$SETUP_SCRIPT" "$@"

# Capture the exit code
SETUP_EXIT_CODE=$?

if [ $SETUP_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "🎉 Setup completed successfully!"
    echo ""
    echo "To get started:"
    echo "  1. Make sure your API keys are set:"
    echo "     export ANTHROPIC_API_KEY=\"your-api-key-here\""
    echo ""
    echo "  2. Start the orchestrator:"
    echo "     cd orchestrator"
    echo "     ./scripts/start_master.sh"
    echo ""
    echo "  3. Open the web dashboard:"
    echo "     http://localhost:8080"
else
    echo ""
    echo "❌ Setup failed with exit code $SETUP_EXIT_CODE"
    echo "Please check the error messages above and try again"
fi

exit $SETUP_EXIT_CODE