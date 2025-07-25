#!/bin/bash
# Setup script for CodeDox

echo "🚀 Setting up CodeDox..."

# Check for required tools
echo "📋 Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
else
    echo "✅ Python $(python3 --version)"
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 14 or higher."
    exit 1
else
    echo "✅ Node.js $(node --version)"
fi

# Check PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "⚠️  PostgreSQL client not found. Make sure PostgreSQL is installed and running."
else
    echo "✅ PostgreSQL client found"
fi

# Check uv
if ! command -v uv &> /dev/null; then
    echo "⚠️  uv not found. Installing uv is recommended for faster package installation."
    echo "   Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    USE_PIP=true
else
    echo "✅ uv found"
    USE_PIP=false
fi

# Create virtual environment
echo ""
echo "🔧 Setting up Python environment..."
if [ "$USE_PIP" = true ]; then
    python3 -m venv .venv
else
    uv venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
if [ "$USE_PIP" = true ]; then
    pip install --upgrade pip
    pip install -r requirements.txt
else
    uv pip install -r requirements.txt
fi

# Install Playwright browsers
echo ""
echo "🌐 Installing Playwright browsers..."
crawl4ai-setup

# Install VS Code language detection
echo ""
echo "🔍 Installing VS Code language detection..."
cd src/language_detector
npm install
cd ../..

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "📄 Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your configuration"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Create PostgreSQL database: createdb codedox"
echo "2. Initialize database: python cli.py init"
echo "3. Configure your .env file"
echo "4. Start the application: python cli.py all"
echo ""
echo "For more information, see the README.md"