#!/bin/bash

# ARGUS Command Center - Startup Script
# Starts both backend (FastAPI) and frontend (Next.js)

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║     █████╗ ██████╗  ██████╗ ██╗   ██╗███████╗           ║"
echo "║    ██╔══██╗██╔══██╗██╔════╝ ██║   ██║██╔════╝           ║"
echo "║    ███████║██████╔╝██║  ███╗██║   ██║███████╗           ║"
echo "║    ██╔══██║██╔══██╗██║   ██║██║   ██║╚════██║           ║"
echo "║    ██║  ██║██║  ██║╚██████╔╝╚██████╔╝███████║           ║"
echo "║    ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚══════╝           ║"
echo "║                                                           ║"
echo "║         Command Center - Starting Services 👁️            ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "Please copy .env.example to .env and configure your settings"
    exit 1
fi

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Start backend in background
echo "🚀 Starting FastAPI backend..."
cd api || exit 1
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found"
    exit 1
fi
python3 server.py &
BACKEND_PID=$!
cd "$SCRIPT_DIR"

# Wait for backend to start
echo "⏳ Waiting for backend to initialize..."
sleep 3

# Check if backend is running
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Error: Backend failed to start"
    exit 1
fi

# Start frontend
echo "🚀 Starting Next.js frontend..."
cd web || exit 1
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm not found. Please install Node.js"
    exit 1
fi

# Check if node_modules exists, if not run npm install
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"

echo ""
echo "✅ ARGUS Command Center is now running!"
echo ""
echo "📡 Backend API: http://localhost:8000"
echo "🌐 Frontend UI: http://localhost:3000"
echo "🔌 WebSocket: ws://localhost:8000/ws/live"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Handle Ctrl+C gracefully
trap "echo ''; echo '🛑 Shutting down ARGUS Command Center...'; kill $BACKEND_PID $FRONTEND_PID; exit" INT

# Wait for processes
wait
