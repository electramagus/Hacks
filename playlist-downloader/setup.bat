@echo off
REM Smart Setup Script for Playlist Downloader (Windows)
REM Checks all dependencies and guides user through setup
REM Run this before using the application, it will ensure everything is ready

setlocal EnableDelayedExpansion

echo.
echo ================================================================
echo          [*] Playlist Downloader - Smart Setup [*]
echo ================================================================
echo.

REM Get script directory
cd /d "%~dp0"

REM Flags to track what needs to be done
set NEEDS_VENV=0
set NEEDS_DEPS=0
set NEEDS_YTDLP=0
set NEEDS_CONFIG=0
set NEEDS_CREDENTIALS=0
set IS_FIRST_TIME=0

REM Check Python version
echo [1/7] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python not found!
    echo Please install Python 3.8+ from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION%
echo.

REM Check if virtual environment exists
echo [2/7] Checking virtual environment...
if exist "venv\" (
    echo [OK] Virtual environment exists
) else (
    set NEEDS_VENV=1
    set IS_FIRST_TIME=1
    echo [X] Virtual environment not found
)
echo.

REM Check dependencies
echo [3/7] Checking Python dependencies...
if !NEEDS_VENV!==1 (
    set NEEDS_DEPS=1
    echo [X] Need to install dependencies
) else (
    call venv\Scripts\activate.bat >nul 2>&1
    python -c "import spotipy, dotenv, aiofiles, rich, tqdm, psutil" >nul 2>&1
    if errorlevel 1 (
        set NEEDS_DEPS=1
        set IS_FIRST_TIME=1
        echo [X] Some packages are missing
    ) else (
        echo [OK] All Python packages installed
    )
)
echo.

REM Check yt-dlp
echo [4/7] Checking yt-dlp...
if !NEEDS_VENV!==1 (
    set NEEDS_YTDLP=1
    echo [X] Need to install yt-dlp
) else (
    call venv\Scripts\activate.bat >nul 2>&1
    python -c "import yt_dlp" >nul 2>&1
    if errorlevel 1 (
        where yt-dlp >nul 2>&1
        if errorlevel 1 (
            set NEEDS_YTDLP=1
            set IS_FIRST_TIME=1
            echo [X] yt-dlp not found
        ) else (
            echo [OK] yt-dlp installed
        )
    ) else (
        echo [OK] yt-dlp installed
    )
)
echo.

REM Check for FFmpeg
echo [5/7] Checking FFmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [!] FFmpeg not found (required for audio conversion^)
) else (
    echo [OK] FFmpeg installed
)
echo.

REM Check config.json
echo [6/7] Checking system configuration...
if exist "config.json" (
    echo [OK] config.json exists
) else (
    set NEEDS_CONFIG=1
    set IS_FIRST_TIME=1
    echo [X] config.json not found
)
echo.

REM Check Spotify credentials
echo [7/8] Checking Spotify credentials...
if not exist ".config\.env" (
    set NEEDS_CREDENTIALS=1
    set IS_FIRST_TIME=1
    echo [X] .config\.env not found
) else (
    findstr /C:"your_spotify_client_id_here" .config\.env >nul 2>&1
    if not errorlevel 1 (
        set NEEDS_CREDENTIALS=1
        echo [X] Spotify credentials not configured
    ) else (
        findstr /R /C:"SPOTIFY_CLIENT_ID=..*" .config\.env >nul 2>&1
        if errorlevel 1 (
            set NEEDS_CREDENTIALS=1
            echo [X] Spotify credentials not configured
        ) else (
            echo [OK] Spotify credentials configured
        )
    )
)
echo.

REM Check browser authentication
echo [8/8] Checking browser authentication...
if exist ".config\.env" (
    findstr /C:"YOUTUBE_COOKIES=" .config\.env >nul 2>&1
    if errorlevel 1 (
        echo [!] Browser cookies not set up (optional)
        echo     For age-restricted videos, run: python -m modules.browser_auth
    ) else (
        echo [OK] Browser cookies configured
    )
) else (
    echo [X] Browser cookies not configured
    echo     Run: python -m modules.browser_auth
)
echo.

echo ================================================================

REM Determine what to do based on checks
if !IS_FIRST_TIME!==1 (
    echo First-time setup required. Let's get everything ready!
    echo ================================================================
    echo.
    
    REM Create virtual environment
    if !NEEDS_VENV!==1 (
        echo [*] Creating virtual environment...
        python -m venv venv
        if errorlevel 1 (
            echo [X] Error creating virtual environment
            pause
            exit /b 1
        )
        echo [OK] Virtual environment created
        echo.
    )
    
    REM Activate venv
    call venv\Scripts\activate.bat
    
    REM Install/upgrade pip
    if !NEEDS_DEPS!==1 (
        echo [*] Upgrading pip...
        python -m pip install --upgrade pip --quiet
        echo [OK] pip upgraded
        echo.
    )
    
    if !NEEDS_YTDLP!==1 (
        if !NEEDS_DEPS!==0 (
            echo [*] Upgrading pip...
            python -m pip install --upgrade pip --quiet
            echo [OK] pip upgraded
            echo.
        )
    )
    
    REM Install dependencies
    if !NEEDS_DEPS!==1 (
        echo [*] Installing Python dependencies...
        echo    This may take a minute...
        pip install -r requirements.txt --quiet
        if errorlevel 1 (
            echo [X] Error installing dependencies
            pause
            exit /b 1
        )
        echo [OK] Dependencies installed
        echo.
    )
    
    REM Install yt-dlp
    if !NEEDS_YTDLP!==1 (
        echo [*] Installing yt-dlp...
        pip install yt-dlp --quiet
        if errorlevel 1 (
            echo [X] Error installing yt-dlp
            pause
            exit /b 1
        )
        echo [OK] yt-dlp installed
        echo.
    )
    
    REM Run configure.py
    if !NEEDS_CONFIG!==1 (
        echo [*] Running interactive setup (including folder selection)...
        python -m modules.configure
        echo.
    )
    
    REM Setup credentials
    if !NEEDS_CREDENTIALS!==1 (
        call :setup_credentials
    )
    
    REM Create downloads directory
    if not exist "downloads\" mkdir downloads
    
    REM Check FFmpeg warning
    where ffmpeg >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [!] IMPORTANT: FFmpeg Required
        echo FFmpeg is needed for audio conversion but was not found.
        echo.
        echo Download from: https://www.gyan.dev/ffmpeg/builds/
        echo After downloading, add FFmpeg to your PATH or place ffmpeg.exe here.
        echo.
    )
    
    echo.
    echo ================================================================
    echo              [*] Setup Complete! [*]
    echo ================================================================
    echo.
    echo You're ready to go! Run: python main.py
    echo.
    
) else (
    echo [OK] All checks passed! Everything is already set up.
    echo ================================================================
    echo.
    
    REM Offer to set up browser authentication if not configured
    findstr /C:"YOUTUBE_COOKIES=" .config\.env >nul 2>&1
    if errorlevel 1 (
        echo [!] Browser authentication not configured
        echo.
        echo Setting up browser authentication allows you to download:
        echo   - Age-restricted videos
        echo   - Region-locked content
        echo   - Videos requiring login
        echo.
        set /p SETUP_BROWSER="Would you like to set up browser authentication now? (y/n): "
        if /i "!SETUP_BROWSER!"=="y" (
            call venv\Scripts\activate.bat
            python -m modules.browser_auth
            echo.
        )
    )
    
    echo You're all set! Run: python main.py
    echo.
)

pause
exit /b 0

:setup_credentials
echo.
echo ================================================================
echo          Setting up Spotify API Credentials
echo ================================================================
echo.
echo To download Spotify playlists, you need Spotify API credentials.
echo.
echo Follow these steps:
echo 1. Go to: https://developer.spotify.com/dashboard
echo 2. Log in with your Spotify account
echo 3. Click 'Create an App'
echo 4. Fill in any app name and description
echo 5. After creation, you'll see your Client ID and Client Secret
echo 6. Click 'Edit Settings' and add this Redirect URI:
echo    http://127.0.0.1:8000/callback
echo.
pause
echo.

set /p CLIENT_ID="Enter your Spotify Client ID: "
set /p CLIENT_SECRET="Enter your Spotify Client Secret: "

if "!CLIENT_ID!"=="" (
    echo [X] Client ID is required!
    pause
    exit /b 1
)

if "!CLIENT_SECRET!"=="" (
    echo [X] Client Secret is required!
    pause
    exit /b 1
)

REM Create .config directory
if not exist ".config\" mkdir .config

REM Create .env file
(
    echo # Spotify API Credentials
    echo SPOTIFY_CLIENT_ID=!CLIENT_ID!
    echo SPOTIFY_CLIENT_SECRET=!CLIENT_SECRET!
    echo SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/callback
    echo.
    echo # Download Settings
    echo OUTPUT_DIR=./downloads
    echo AUDIO_QUALITY=320K
    echo AUDIO_FORMAT=mp3
    echo DOWNLOAD_DELAY=1.5
    echo MAX_RETRIES=3
    echo SEARCH_DELAY_MIN=0.5
    echo SEARCH_DELAY_MAX=1.5
    echo START_DOWNLOAD_THRESHOLD=27
    echo.
    echo # FFmpeg Path ^(leave as 'ffmpeg' if it's in PATH^)
    echo FFMPEG_PATH=ffmpeg
) > .config\.env

echo.
echo [OK] Credentials saved to .config\.env
set NEEDS_CREDENTIALS=0
exit /b 0
