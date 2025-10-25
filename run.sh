#!/bin/bash

# Healthcare Staffing Intelligence Chatbot
# Startup script

echo "🚀 Healthcare Staffing Intelligence Chatbot"
echo "=========================================="
echo ""

# Determine virtual environment directory (.venv preferred, fallback to venv)
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    VENV_DIR="venv"
fi

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please run: python3 -m venv .venv"
    exit 1
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found!"
    echo "   Please create .env file with required variables"
    echo "   See README.md for details"
    exit 1
fi

# Check if dependencies are installed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
fi

echo ""
echo "✅ Environment ready!"
echo ""

# Run the application
echo "🎯 Starting server..."
echo ""
export WATCHFILES_FORCE_POLLING=1
export UVICORN_RELOAD=false
export HOST=127.0.0.1
python3 main.py
