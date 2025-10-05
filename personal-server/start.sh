#!/bin/bash

# Quick start script for personal productivity system
# Runs both the personal server and frontend dev server

echo "🚀 Starting Woodwork Personal Productivity System"
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "❌ npm is required but not found"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUI_DIR="$(dirname "$SCRIPT_DIR")/gui"

echo "${BLUE}📂 Data will be stored in: $SCRIPT_DIR/data${NC}"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "${YELLOW}🛑 Shutting down servers...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup INT TERM

# Start personal server
echo "${GREEN}🔧 Starting Personal API Server (port 8001)...${NC}"
cd "$SCRIPT_DIR"
python3 server.py &
BACKEND_PID=$!
sleep 2

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ Failed to start personal server"
    exit 1
fi

echo "${GREEN}✅ Personal server running${NC}"
echo ""

# Start frontend dev server
echo "${GREEN}🎨 Starting Frontend Dev Server (port 5173)...${NC}"
cd "$GUI_DIR"
npm run dev &
FRONTEND_PID=$!
sleep 3

echo ""
echo "${GREEN}✅ All systems running!${NC}"
echo ""
echo "📍 Access the app:"
echo "   Frontend:     ${BLUE}http://localhost:5173${NC}"
echo "   Personal API: ${BLUE}http://localhost:8001${NC}"
echo ""
echo "💡 Optional: Start main Woodwork agent on port 8000 for AI features"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
