#!/bin/bash

# Define colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}Starting the Synchronized Arena Project...${NC}\n"

# 1. Sync the uv environment
echo -e "${GREEN}[1/3] Verifying uv environment...${NC}"
uv sync

# 2. Start the FastAPI backend
# We use the 'pythonpath' flag or dot notation to ensure it finds the modules inside /backend
echo -e "${GREEN}[2/3] Starting FastAPI Backend on port 8000...${NC}"
uv run uvicorn backend.phase2:app --reload --port 8000 --host 0.0.0.0 &
BACKEND_PID=$!

# Give the backend a moment to initialize
sleep 2

# 3. Start the Frontend
# We navigate into the frontend folder so it serves index.html as the root
echo -e "${GREEN}[3/3] Starting Frontend Server on port 5500...${NC}"
uv run python -m http.server 5500 --directory frontend &
FRONTEND_PID=$!

echo -e "\n${CYAN}====================================================${NC}"
echo -e "${GREEN}All systems operational!${NC}"
echo -e "Frontend: http://127.0.0.1:5500"
echo -e "Backend:  http://127.0.0.1:8000"
echo -e "${YELLOW}Note: Ensure MySQL and MongoDB are running.${NC}"
echo -e "${CYAN}Press Ctrl+C to shut down both servers.${NC}"
echo -e "${CYAN}====================================================${NC}\n"

# Trap Ctrl+C to kill background processes
trap "echo -e '\nShutting down servers...'; kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM

wait
#fuser -k 8000/tcp
