#!/bin/bash
set -e  # Exit on any error

echo "=== Starting Woodwork Coding Agent Environment Setup ==="

# Debug: Check current user and sudo access
echo "Current user: $(whoami)"
echo "User ID: $(id)"
echo "Checking sudoers configuration..."
sudo -n true 2>/dev/null && echo "✅ Sudo works without password" || echo "❌ Sudo requires password"

# Verify Python is pre-installed
echo "Verifying Python installation..."
python3 --version
pip3 --version
echo "✅ Python is installed"

# Configure Git with agent credentials
echo "Configuring Git..."
git config --global --add safe.directory /workspace
git config --global user.name "$AGENT_GIT_NAME"
git config --global user.email "$AGENT_GIT_EMAIL"
git config --global credential.helper store
git config --global init.defaultBranch main
git config --global pull.rebase false

# Set up GitHub authentication
echo "Setting up GitHub authentication..."
echo "https://$AGENT_GIT_USERNAME:$GITHUB_PAT@github.com" > ~/.git-credentials
chmod 600 ~/.git-credentials

# Create Python virtual environment
echo "Creating Python virtual environment..."
if python3 -m venv /workspace/venv; then
    echo "✅ venv command succeeded"
    if [ -d "/workspace/venv" ]; then
        echo "✅ /workspace/venv directory exists"
        ls -la /workspace/venv
    else
        echo "❌ /workspace/venv directory does NOT exist after creation!"
        ls -la /workspace/
        exit 1
    fi
else
    echo "❌ python3 -m venv command failed!"
    exit 1
fi

source /workspace/venv/bin/activate

# Verify activation
if [ -n "$VIRTUAL_ENV" ]; then
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
else
    echo "❌ Failed to activate virtual environment"
    exit 1
fi

# Install uv for fast package management
echo "Installing uv package manager..."
pip install --upgrade pip uv

# Install woodwork-engine with all dependencies using uv (much faster than pip)
echo "Installing woodwork-engine[all] with all dependencies..."
echo "This includes test, dev, and optional dependencies (chromadb, langchain, etc.)"
cd /workspace
uv pip install -e ".[all]"

echo "✅ All dependencies installed successfully"

# Make venv activation persistent
echo "Making virtual environment persistent..."
echo 'source /workspace/venv/bin/activate' >> ~/.bashrc

# Verify GitHub authentication
echo "Verifying GitHub authentication..."
if git ls-remote https://github.com/willwoodward/woodwork-engine.git HEAD > /dev/null 2>&1; then
    echo "✅ GitHub authentication verified successfully"
else
    echo "❌ GitHub authentication failed - please check your PAT and credentials"
    exit 1
fi

echo "🎉 Development environment ready for woodwork-engine with authenticated Git access!"
echo "=== Setup Complete ==="