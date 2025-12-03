#!/bin/bash
# Convenience script to activate the virtual environment
# Usage: source activate.sh

if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "✓ Virtual environment activated (.venv)"
    echo "  Python: $(which python)"
    echo "  Version: $(python --version)"
else
    echo "✗ Virtual environment not found (.venv)"
    echo "  Run: python3 -m venv .venv"
    exit 1
fi
