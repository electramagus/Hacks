#!/bin/bash
# Smart Setup Script for Playlist Downloader (Linux/macOS)
# Checks all dependencies and guides user through setup
# Run this before using the application, it will ensure everything is ready

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Flags to track what needs to be done
NEEDS_VENV=false
NEEDS_DEPS=false
NEEDS_YTDLP=false
NEEDS_CONFIG=false
NEEDS_CREDENTIALS=false
IS_FIRST_TIME=false

echo -e "${BOLD}${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║        🎵 Playlist Downloader - Smart Setup 🎵             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Function to check Python
check_python() {
    echo -e "${BLUE}[1/7]${NC} Checking Python installation..."
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}✗ Python 3 not found!${NC}"
        echo "Please install Python 3.8+ from: https://www.python.org/downloads/"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        echo -e "${RED}✗ Python $PYTHON_VERSION found. Need Python 3.8+${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"
}

# Function to check/create virtual environment
check_venv() {
    echo -e "${BLUE}[2/7]${NC} Checking virtual environment..."
    if [ ! -d "venv" ]; then
        NEEDS_VENV=true
        IS_FIRST_TIME=true
        echo -e "${YELLOW}✗ Virtual environment not found${NC}"
    else
        echo -e "${GREEN}✓ Virtual environment exists${NC}"
    fi
}

# Function to check dependencies
check_dependencies() {
    echo -e "${BLUE}[3/7]${NC} Checking Python dependencies..."
    
    if [ "$NEEDS_VENV" = true ]; then
        NEEDS_DEPS=true
        echo -e "${YELLOW}✗ Need to install dependencies${NC}"
        return
    fi
    
    # Check for required packages using venv python directly
    MISSING_DEPS=()
    for pkg in spotipy python-dotenv aiofiles rich tqdm psutil; do
        if ! venv/bin/python -c "import ${pkg//-/_}" &> /dev/null; then
            MISSING_DEPS+=("$pkg")
        fi
    done
    
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        NEEDS_DEPS=true
        IS_FIRST_TIME=true
        echo -e "${YELLOW}✗ Missing packages: ${MISSING_DEPS[*]}${NC}"
    else
        echo -e "${GREEN}✓ All Python packages installed${NC}"
    fi
}

# Function to check yt-dlp
check_ytdlp() {
    echo -e "${BLUE}[4/7]${NC} Checking yt-dlp..."
    
    if [ "$NEEDS_VENV" = true ]; then
        NEEDS_YTDLP=true
        echo -e "${YELLOW}✗ Need to install yt-dlp${NC}"
        return
    fi
    
    # Check using venv python directly
    if ! venv/bin/python -c "import yt_dlp" &> /dev/null && ! command -v yt-dlp &> /dev/null; then
        NEEDS_YTDLP=true
        IS_FIRST_TIME=true
        echo -e "${YELLOW}✗ yt-dlp not found${NC}"
    else
        echo -e "${GREEN}✓ yt-dlp installed${NC}"
    fi
}

# Function to check FFmpeg
check_ffmpeg() {
    echo -e "${BLUE}[5/7]${NC} Checking FFmpeg..."
    if command -v ffmpeg &> /dev/null; then
        FFMPEG_VERSION=$(ffmpeg -version 2>/dev/null | head -n1 | cut -d' ' -f3)
        echo -e "${GREEN}✓ FFmpeg ${FFMPEG_VERSION} installed${NC}"
    else
        echo -e "${YELLOW}⚠ FFmpeg not found (required for audio conversion)${NC}"
    fi
}

# Function to check config.json
check_config_json() {
    echo -e "${BLUE}[6/7]${NC} Checking system configuration..."
    if [ ! -f "config.json" ]; then
        NEEDS_CONFIG=true
        IS_FIRST_TIME=true
        echo -e "${YELLOW}✗ config.json not found${NC}"
    else
        echo -e "${GREEN}✓ config.json exists${NC}"
    fi
}

# Function to check Spotify credentials
check_credentials() {
    echo -e "${BLUE}[7/7]${NC} Checking Spotify credentials..."
    
    if [ ! -f ".config/.env" ]; then
        NEEDS_CREDENTIALS=true
        IS_FIRST_TIME=true
        echo -e "${YELLOW}✗ .config/.env not found${NC}"
        return
    fi
    
    # Check if credentials are configured
    if grep -q "your_spotify_client_id_here" .config/.env 2>/dev/null; then
        NEEDS_CREDENTIALS=true
        echo -e "${YELLOW}✗ Spotify credentials not configured${NC}"
    else
        # Basic check if CLIENT_ID is set
        if grep -q "SPOTIFY_CLIENT_ID=.\+" .config/.env 2>/dev/null && \
           ! grep -q "SPOTIFY_CLIENT_ID=$" .config/.env 2>/dev/null && \
           ! grep -q "SPOTIFY_CLIENT_ID=your_" .config/.env 2>/dev/null; then
            echo -e "${GREEN}✓ Spotify credentials configured${NC}"
        else
            NEEDS_CREDENTIALS=true
            echo -e "${YELLOW}✗ Spotify credentials not configured${NC}"
        fi
    fi
}

# Function to check browser authentication
check_browser_auth() {
    echo -e "${BLUE}[8/8]${NC} Checking browser authentication..."
    
    if [ ! -f ".config/.env" ]; then
        echo -e "${YELLOW}✗ Browser cookies not configured${NC}"
        return
    fi
    
    # Check if YouTube cookies are configured
    if grep -q "YOUTUBE_COOKIES=" .config/.env 2>/dev/null; then
        COOKIES_PATH=$(grep "YOUTUBE_COOKIES=" .config/.env | cut -d'=' -f2)
        if [ -n "$COOKIES_PATH" ] && [ -f "$COOKIES_PATH" ]; then
            echo -e "${GREEN}✓ Browser cookies configured${NC}"
        else
            echo -e "${YELLOW}⚠ Browser cookies configured but file not found${NC}"
            echo -e "${CYAN}   Run: python -m modules.browser_auth${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Browser cookies not set up (optional)${NC}"
        echo -e "${CYAN}   For age-restricted videos, run: python -m modules.browser_auth${NC}"
    fi
}

# Function to setup Spotify credentials
setup_credentials() {
    echo ""
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${YELLOW}  Setting up Spotify API Credentials${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "To download Spotify playlists, you need Spotify API credentials."
    echo ""
    echo -e "${BOLD}Follow these steps:${NC}"
    echo -e "1. Go to: ${CYAN}https://developer.spotify.com/dashboard${NC}"
    echo "2. Log in with your Spotify account"
    echo -e "3. Click '${GREEN}Create an App${NC}'"
    echo "4. Fill in any app name and description"
    echo "5. After creation, you'll see your Client ID and Client Secret"
    echo -e "6. Click '${GREEN}Edit Settings${NC}' and add this Redirect URI:"
    echo -e "   ${GREEN}http://127.0.0.1:8000/callback${NC}"
    echo ""
    
    read -p "Press Enter when you're ready to enter your credentials..."
    echo ""
    
    # Prompt for Client ID
    echo -e "${CYAN}Enter your Spotify Client ID:${NC}"
    read -r CLIENT_ID
    
    # Prompt for Client Secret  
    echo -e "${CYAN}Enter your Spotify Client Secret:${NC}"
    read -r CLIENT_SECRET
    
    # Validate input
    if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
        echo -e "${RED}Error: Both Client ID and Secret are required!${NC}"
        return 1
    fi
    
    # Create .config directory if it doesn't exist
    mkdir -p .config
    
    # Create/update .env file
    cat > .config/.env << EOF
# Spotify API Credentials
SPOTIFY_CLIENT_ID=$CLIENT_ID
SPOTIFY_CLIENT_SECRET=$CLIENT_SECRET
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/callback

# Download Settings
OUTPUT_DIR=./downloads
AUDIO_QUALITY=320K
AUDIO_FORMAT=mp3
DOWNLOAD_DELAY=1.5
MAX_RETRIES=3
SEARCH_DELAY_MIN=0.5
SEARCH_DELAY_MAX=1.5
START_DOWNLOAD_THRESHOLD=27

# FFmpeg Path (leave as 'ffmpeg' if it's in PATH)
FFMPEG_PATH=ffmpeg
EOF
    
    echo ""
    echo -e "${GREEN}✓ Credentials saved to .config/.env${NC}"
    NEEDS_CREDENTIALS=false
}

# Run all checks
check_python
check_venv
check_dependencies
check_ytdlp
check_ffmpeg
check_config_json
check_credentials
check_browser_auth

echo ""
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"

# Determine what to do based on checks
if [ "$IS_FIRST_TIME" = true ]; then
    echo -e "${YELLOW}First-time setup required. Let's get everything ready!${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Create virtual environment
    if [ "$NEEDS_VENV" = true ]; then
        echo -e "${YELLOW}➜ Creating virtual environment...${NC}"
        python3 -m venv venv
        echo -e "${GREEN}✓ Virtual environment created${NC}"
        echo ""
    fi
    
    # Activate venv
    source venv/bin/activate
    
    # Install/upgrade pip
    if [ "$NEEDS_DEPS" = true ] || [ "$NEEDS_YTDLP" = true ]; then
        echo -e "${YELLOW}➜ Upgrading pip...${NC}"
        python -m pip install --upgrade pip --quiet
        echo -e "${GREEN}✓ pip upgraded${NC}"
        echo ""
    fi
    
    # Install dependencies
    if [ "$NEEDS_DEPS" = true ]; then
        echo -e "${YELLOW}➜ Installing Python dependencies...${NC}"
        echo "   This may take a minute..."
        pip install -r requirements.txt --quiet
        echo -e "${GREEN}✓ Dependencies installed${NC}"
        echo ""
    fi
    
    # Install yt-dlp
    if [ "$NEEDS_YTDLP" = true ]; then
        echo -e "${YELLOW}➜ Installing yt-dlp...${NC}"
        pip install yt-dlp --quiet
        echo -e "${GREEN}✓ yt-dlp installed${NC}"
        echo ""
    fi
    
    # Run configure.py
    if [ "$NEEDS_CONFIG" = true ]; then
        echo -e "${YELLOW}➜ Running interactive setup (including folder selection)...${NC}"
        python -m modules.configure
        echo ""
    fi
    
    # Setup credentials
    if [ "$NEEDS_CREDENTIALS" = true ]; then
        setup_credentials
        echo ""
    fi
    
    # Create downloads directory
    mkdir -p downloads
    
    # Check FFmpeg and show warning if needed
    if ! command -v ffmpeg &> /dev/null; then
        echo -e "${BOLD}${YELLOW}⚠ IMPORTANT: FFmpeg Required${NC}"
        echo "FFmpeg is needed for audio conversion but was not found."
        echo ""
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Install on macOS: ${GREEN}brew install ffmpeg${NC}"
        else
            echo "Install on Ubuntu/Debian: ${GREEN}sudo apt install ffmpeg${NC}"
            echo "Install on Fedora: ${GREEN}sudo dnf install ffmpeg${NC}"
            echo "Install on Arch: ${GREEN}sudo pacman -S ffmpeg${NC}"
        fi
        echo ""
    fi
    
    echo -e "${BOLD}${GREEN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║              ✓ Setup Complete! ✓                          ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "You're ready to go! Run: ${GREEN}${BOLD}python main.py${NC}"
    echo ""
    
else
    echo -e "${GREEN}✓ All checks passed! Everything is already set up.${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    
    # Offer to set up browser authentication if not configured
    if ! grep -q "YOUTUBE_COOKIES=" .config/.env 2>/dev/null; then
        echo -e "${YELLOW}⚠ Browser authentication not configured${NC}"
        echo ""
        echo "Setting up browser authentication allows you to download:"
        echo "  • Age-restricted videos"
        echo "  • Region-locked content"
        echo "  • Videos requiring login"
        echo ""
        read -p "Would you like to set up browser authentication now? (y/n): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            source venv/bin/activate 2>/dev/null || true
            python -m modules.browser_auth
            echo ""
        fi
    fi
    
    echo -e "You're all set! Run: ${GREEN}${BOLD}python main.py${NC}"
    echo ""
fi
