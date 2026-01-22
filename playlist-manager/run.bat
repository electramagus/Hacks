@echo off
REM Playlist Manager Launcher (Windows)
REM Double-click this file to run the application

setlocal EnableDelayedExpansion

REM Get script directory
cd /d "%~dp0"

REM Clear screen for better visibility
cls

echo.
echo ================================================================
echo          [*] Playlist Manager - Starting... [*]
echo ================================================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo [X] Virtual environment not found!
    echo.
    echo Please run setup first:
    echo   setup.bat
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

if errorlevel 1 (
    echo [X] Failed to activate virtual environment
    pause
    exit /b 1
)

echo [OK] Virtual environment activated
echo.

REM Check for yt-dlp updates
echo [*] Checking for yt-dlp updates...
pip install --upgrade yt-dlp --quiet >nul 2>&1

if errorlevel 1 (
    echo [!] Could not check for updates (continuing anyway^)
) else (
    echo [OK] yt-dlp is up to date
)
echo.

REM Run the application
echo [*] Starting Playlist Manager...
echo ================================================================
echo.

python main.py

REM Capture exit code
set EXIT_CODE=%ERRORLEVEL%

echo.
echo ================================================================

if %EXIT_CODE%==0 (
    echo [OK] Application closed successfully
) else (
    echo [X] Application exited with errors (code: %EXIT_CODE%)
)

echo.
pause
exit /b %EXIT_CODE%
