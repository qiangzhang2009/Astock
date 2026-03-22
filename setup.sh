#!/bin/bash
# Astock setup script — run once after cloning

set -e

echo "=== Astock Setup ==="

# Backend
echo "[1/3] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate 2>/dev/null || true

echo "[2/3] Installing Python dependencies..."
if command -v uv &>/dev/null; then
    uv pip install -r requirements.txt
else
    pip install -r requirements.txt
fi

# Frontend
echo "[3/3] Setting up frontend..."
cd frontend
npm install
cd ..

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start:"
echo "  Terminal 1: source venv/bin/activate && uvicorn backend.api.main:app --reload --port 8000"
echo "  Terminal 2: cd frontend && npm run dev"
echo ""
echo "Then open: http://localhost:7777/Astock"
