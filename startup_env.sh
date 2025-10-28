#!/bin/bash
echo "=== Running Startup Scripts ===" 

# Activate Python virtual environment if it exists
if [ -d "/workspace/venv" ]; then
    echo "Activating Python virtual environment..."
    source /workspace/venv/bin/activate
    echo "✅ Python virtual environment activated"
fi

# Display current working environment status
echo "📍 Current directory: $(pwd)"
echo "🐍 Python version: $(python3 --version 2>/dev/null || echo 'Python not available')"
echo "📦 Git status: $(git status --porcelain | wc -l) modified files"
echo "🔧 Development environment ready!"

echo "=== Startup Complete ==="