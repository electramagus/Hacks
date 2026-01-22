#!/bin/bash
# Playlist Manager Launcher (Linux/macOS)
# Double-click this file to run the application
# Or run from terminal: ./run.sh

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Clear screen for better visibility
clear

echo -e "${BOLD}${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║          🎵 Playlist Manager - Starting... 🎵             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}✗ Virtual environment not found!${NC}"
    echo ""
    echo "Please run setup first:"
    echo -e "  ${GREEN}./setup.sh${NC}"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Activate virtual environment
echo -e "${CYAN}➜ Activating virtual environment...${NC}"
source venv/bin/activate

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Failed to activate virtual environment${NC}"
    read -p "Press Enter to exit..."
    exit 1
fi

echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Check for yt-dlp updates
echo -e "${CYAN}➜ Checking for yt-dlp updates...${NC}"
pip install --upgrade yt-dlp --quiet 2>&1 | grep -v "Requirement already satisfied" || true

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ yt-dlp is up to date${NC}"
else
    echo -e "${YELLOW}⚠ Could not check for updates (continuing anyway)${NC}"
fi
echo ""

# Run the application
echo -e "${CYAN}➜ Starting Playlist Manager...${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

python3 main.py

# Capture exit code
EXIT_CODE=$?

echo ""
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Application closed successfully${NC}"
else
    echo -e "${RED}✗ Application exited with errors (code: $EXIT_CODE)${NC}"
fi

echo ""
read -p "Press Enter to exit..."
exit $EXIT_CODE
