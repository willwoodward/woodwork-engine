#!/bin/bash
set -e  # Exit on any error

echo "=== Starting Woodwork Coding Agent Environment Setup ==="

# Update system packages
echo "Updating system packages..."
apt-get update && apt-get install -y python3 python3-pip python3-venv

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
python3 -m venv /workspace/venv
source /workspace/venv/bin/activate

# Install Python development tools
echo "Installing Python development tools..."
pip install --upgrade pip
pip install pytest black flake8 ruff pre-commit

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