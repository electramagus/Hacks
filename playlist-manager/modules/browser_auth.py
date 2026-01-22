#!/usr/bin/env python3
"""
Browser Authentication Module
==============================
Extracts YouTube cookies from the user's browser to enable downloading
age-restricted, private, or region-locked content.

Designed for non-technical users - they just need to be logged into YouTube
in their browser and answer simple prompts.
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def detect_browsers() -> list[str]:
    """
    Detect which browsers are installed on the system.
    
    Returns:
        List of detected browser names
    """
    browsers = []
    
    # Common browser names for yt-dlp
    browser_checks = {
        'chrome': ['google-chrome', 'chrome', 'chromium'],
        'firefox': ['firefox'],
        'edge': ['microsoft-edge', 'msedge'],
        'opera': ['opera'],
        'brave': ['brave-browser', 'brave'],
        'safari': ['safari'],  # macOS only
    }
    
    # Platform-specific detection
    if sys.platform == 'win32':
        # Windows - check common install paths
        import winreg
        browser_paths = {
            'chrome': r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe',
            'firefox': r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe',
            'edge': r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe',
        }
        
        for browser, reg_path in browser_paths.items():
            try:
                winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                browsers.append(browser)
            except:
                try:
                    winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path)
                    browsers.append(browser)
                except:
                    pass
    
    elif sys.platform == 'darwin':
        # macOS - check Applications folder
        apps_dir = Path('/Applications')
        browser_apps = {
            'chrome': 'Google Chrome.app',
            'firefox': 'Firefox.app',
            'edge': 'Microsoft Edge.app',
            'opera': 'Opera.app',
            'brave': 'Brave Browser.app',
            'safari': 'Safari.app',
        }
        
        for browser, app_name in browser_apps.items():
            if (apps_dir / app_name).exists():
                browsers.append(browser)
    
    else:
        # Linux - check if command exists
        for browser, commands in browser_checks.items():
            for cmd in commands:
                try:
                    result = subprocess.run(['which', cmd], capture_output=True, text=True)
                    if result.returncode == 0:
                        browsers.append(browser)
                        break
                except:
                    pass
    
    # Remove duplicates and return
    return list(dict.fromkeys(browsers))


def extract_cookies(browser: str, cookies_file: str) -> Tuple[bool, str]:
    """
    Extract cookies from browser using yt-dlp.
    
    Args:
        browser: Browser name (chrome, firefox, edge, etc.)
        cookies_file: Path where to save cookies
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Use yt-dlp to extract cookies from browser
        # We'll use a dummy URL and just extract cookies
        cmd = [
            'yt-dlp',
            '--cookies-from-browser', browser,
            '--cookies', cookies_file,
            '--skip-download',
            '--no-warnings',
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ'  # Dummy video
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check if cookies file was created
        if os.path.exists(cookies_file) and os.path.getsize(cookies_file) > 0:
            return True, f"Successfully extracted cookies from {browser.title()}"
        else:
            return False, f"Could not extract cookies from {browser}. Make sure you're logged into YouTube in {browser.title()}."
            
    except subprocess.TimeoutExpired:
        return False, "Cookie extraction timed out. Please try again."
    except FileNotFoundError:
        return False, "yt-dlp not found. Please install it first: pip install yt-dlp"
    except Exception as e:
        return False, f"Error extracting cookies: {e}"


def setup_browser_cookies(cookies_dir: str = ".config") -> Optional[str]:
    """
    Interactive setup for browser cookies.
    Guides non-technical users through the process.
    
    Args:
        cookies_dir: Directory to store cookies file
        
    Returns:
        Path to cookies file if successful, None otherwise
    """
    print("\n" + "=" * 60)
    print("  YouTube Browser Login Setup")
    print("=" * 60)
    print()
    print("To download age-restricted or region-locked videos, we need")
    print("to use your YouTube login from your browser.")
    print()
    print("Don't worry - this is safe! We'll just copy your browser's")
    print("YouTube login cookies so the downloader can access the same")
    print("videos you can watch in your browser.")
    print()
    
    # Ask if user wants to set this up
    response = input("Would you like to set this up now? (y/n) [y]: ").strip().lower()
    if response == 'n':
        print("Skipping browser login setup.")
        print("Note: You may not be able to download some videos.")
        return None
    
    print()
    print("=" * 60)
    print()
    
    # Detect browsers
    print("Detecting your installed browsers...")
    browsers = detect_browsers()
    
    if not browsers:
        print("\n⚠ Could not detect any browsers automatically.")
        print("Please try one of these common names:")
        browsers = ['chrome', 'firefox', 'edge', 'opera', 'brave', 'safari']
    else:
        print(f"\n✓ Found: {', '.join([b.title() for b in browsers])}")
    
    print()
    print("Which browser do you use for YouTube?")
    print("(Make sure you're currently logged into YouTube in that browser)")
    print()
    
    for i, browser in enumerate(browsers, 1):
        print(f"  {i}. {browser.title()}")
    
    print()
    
    # Get user choice
    while True:
        choice = input(f"Choose browser (1-{len(browsers)}) or type name: ").strip().lower()
        
        # Check if it's a number
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(browsers):
                selected_browser = browsers[idx]
                break
        # Check if it's a browser name
        elif choice in ['chrome', 'firefox', 'edge', 'opera', 'brave', 'safari', 'chromium']:
            selected_browser = choice
            break
        
        print("Invalid choice. Please try again.")
    
    print()
    print(f"Using {selected_browser.title()}...")
    print()
    
    # Create cookies directory
    cookies_path = Path(cookies_dir)
    cookies_path.mkdir(parents=True, exist_ok=True)
    
    cookies_file = str(cookies_path / "youtube_cookies.txt")
    
    # Extract cookies
    print("Extracting YouTube cookies from your browser...")
    print("(This may take a few seconds)")
    print()
    
    success, message = extract_cookies(selected_browser, cookies_file)
    
    if success:
        print(f"✓ {message}")
        print(f"✓ Cookies saved to {cookies_file}")
        print()
        print("You're all set! The downloader will now be able to access")
        print("the same videos you can watch when logged into YouTube.")
        return cookies_file
    else:
        print(f"✗ {message}")
        print()
        print("Tips:")
        print("  1. Make sure you're logged into YouTube in your browser")
        print("  2. Try opening YouTube in your browser and logging in")
        print("  3. Close and reopen your browser, then try again")
        print("  4. Try a different browser")
        print()
        
        retry = input("Would you like to try again? (y/n) [y]: ").strip().lower()
        if retry != 'n':
            return setup_browser_cookies(cookies_dir)
        
        return None


def get_cookies_file(cookies_dir: str = ".config") -> Optional[str]:
    """
    Get the path to the cookies file if it exists.
    
    Args:
        cookies_dir: Directory where cookies are stored
        
    Returns:
        Path to cookies file if it exists, None otherwise
    """
    cookies_file = Path(cookies_dir) / "youtube_cookies.txt"
    if cookies_file.exists() and cookies_file.stat().st_size > 0:
        return str(cookies_file)
    return None


def main():
    """Standalone browser authentication setup."""
    from rich.console import Console
    from rich.panel import Panel
    
    console = Console()
    
    console.print(Panel.fit(
        "[bold cyan]🔐 Browser Authentication Setup[/bold cyan]\n\n"
        "This will extract YouTube cookies from your browser\n"
        "to enable downloading age-restricted and region-locked videos.",
        border_style="cyan"
    ))
    console.print()
    
    cookies_file = setup_browser_cookies()
    
    if cookies_file:
        console.print(f"\n[green]✓ Cookies saved to: {cookies_file}[/green]")
        
        # Save to .env file
        env_file = Path(__file__).parent.parent / '.config' / '.env'
        if env_file.exists():
            # Read existing .env
            env_content = env_file.read_text()
            
            # Update or add YOUTUBE_COOKIES
            if 'YOUTUBE_COOKIES=' in env_content:
                # Replace existing line
                lines = env_content.split('\n')
                new_lines = []
                for line in lines:
                    if line.startswith('YOUTUBE_COOKIES='):
                        new_lines.append(f'YOUTUBE_COOKIES={cookies_file}')
                    else:
                        new_lines.append(line)
                env_content = '\n'.join(new_lines)
            else:
                # Append new line
                if not env_content.endswith('\n'):
                    env_content += '\n'
                env_content += f'\n# YouTube Browser Cookies (for age-restricted content)\nYOUTUBE_COOKIES={cookies_file}\n'
            
            env_file.write_text(env_content)
            console.print(f"[green]✓ Cookie path saved to .env[/green]")
        else:
            console.print("[yellow]⚠ .env file not found - you may need to run full setup[/yellow]")
        
        console.print("\n[bold green]Browser authentication setup complete![/bold green]")
    else:
        console.print("\n[yellow]⚠ Setup skipped or failed.[/yellow]")


if __name__ == "__main__":
    main()
