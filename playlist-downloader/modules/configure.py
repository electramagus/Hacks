#!/usr/bin/env python3
"""
System Resource Detection and Configuration
============================================
Automatically detects CPU and memory resources to optimize concurrent operations.
Cross-platform compatible: Works on Windows, macOS, and Linux.

This script analyzes your system and creates optimal configuration settings
for maximum download performance without overwhelming system resources.
"""

import os
import json
import sys
from pathlib import Path
from typing import Dict, Any, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠ Warning: psutil not installed. Using conservative defaults.")
    print("For better system detection, install with: pip install psutil\n")

try:
    from modules.folder_selector import select_download_folder
    FOLDER_SELECTOR_AVAILABLE = True
except ImportError:
    FOLDER_SELECTOR_AVAILABLE = False
    print("⚠ Warning: folder_selector module not found. Will use default location.")

try:
    from modules.browser_auth import setup_browser_cookies, get_cookies_file
    BROWSER_AUTH_AVAILABLE = True
except ImportError:
    BROWSER_AUTH_AVAILABLE = False
    print("⚠ Warning: browser_auth module not found. Will skip browser login setup.")

CONFIG_FILE = 'config.json'
ENV_FILE = '.config/.env'


def detect_resources() -> Tuple[int, float]:
    """
    Detect system CPU and memory resources.
    
    Returns:
        Tuple of (cpu_cores, total_mem_gb)
    """
    # CPU detection - works on all platforms
    cpu_cores = os.cpu_count() or 1
    
    # Memory detection - requires psutil
    if PSUTIL_AVAILABLE:
        try:
            virtual_mem = psutil.virtual_memory()
            total_mem_gb = virtual_mem.total / (1024 ** 3)  # Convert to GB
        except Exception as e:
            print(f"Warning: Failed to detect memory: {e}")
            total_mem_gb = 4.0  # Conservative default
    else:
        # Conservative default if psutil not available
        total_mem_gb = 4.0
    
    return cpu_cores, total_mem_gb


def recommend_settings(cpu_cores: int, total_mem_gb: float) -> Dict[str, Any]:
    """
    Recommend optimal concurrency settings based on system resources.
    
    Strategy:
    - Search workers: IO-bound task, can use more threads (2x cores, max 32)
    - Download workers: CPU/IO-bound, more conservative (up to cores, max 8)
    - Memory consideration: Ensure we don't overwhelm RAM
    
    Args:
        cpu_cores: Number of CPU cores
        total_mem_gb: Total system memory in GB
    
    Returns:
        dict: Configuration settings with recommended values
    """
    # Search workers: IO-bound, can use more threads
    # Use 2x cores for better parallelism, but cap at 32 to avoid overhead
    max_threads = min(32, max(3, cpu_cores * 2))
    
    # Download workers: CPU/IO-bound (ffmpeg conversions), more conservative
    # Assume each process needs ~256MB, cap at CPU cores for efficiency
    mem_based_limit = int(total_mem_gb / 0.25)  # How many can fit in RAM
    max_processes = min(cpu_cores, mem_based_limit, 8)  # Cap at 8 for stability
    max_processes = max(2, max_processes)  # At least 2
    
    return {
        'cpu_cores': cpu_cores,
        'total_mem_gb': round(total_mem_gb, 2),
        'max_threads': max_threads,
        'max_processes': max_processes,
        'platform': sys.platform
    }


def print_system_info(settings: Dict[str, Any]) -> None:
    """
    Print detected system information in a readable format.
    
    Args:
        settings: Configuration settings dictionary
    """
    print("\n" + "=" * 60)
    print("  System Resource Detection")
    print("=" * 60)
    print(f"Platform:          {settings['platform']}")
    print(f"CPU Cores:         {settings['cpu_cores']}")
    print(f"Total Memory:      {settings['total_mem_gb']:.2f} GB")
    print(f"Search Workers:    {settings['max_threads']} (concurrent searches)")
    print(f"Download Workers:  {settings['max_processes']} (concurrent downloads)")
    print("=" * 60)
    print()
    print("These settings are optimized for your system to maximize")
    print("performance while avoiding resource exhaustion.")
    print()


def create_config_directory() -> Path:
    """
    Create .config directory if it doesn't exist.
    
    Returns:
        Path to config directory
    """
    config_dir = Path('.config')
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created configuration directory: {config_dir}")
    return config_dir


def setup_download_location() -> str:
    """
    Interactive setup for download location.
    Allows users to browse and select or create a folder.
    
    Returns:
        Path to download folder
    """
    print("\n" + "=" * 60)
    print("  Download Location Setup")
    print("=" * 60)
    print()
    print("Let's set up where your downloaded music will be saved.")
    print()
    
    # Check if download location already configured
    env_path = Path(ENV_FILE)
    existing_location = None
    
    if env_path.exists():
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('OUTPUT_DIR='):
                        existing_location = line.split('=', 1)[1].strip().strip('"\'')
                        break
        except Exception:
            pass
    
    if existing_location and os.path.exists(existing_location):
        print(f"Current download location: {existing_location}")
        print()
        
        # Ask if user wants to change it
        response = input("Keep this location? (y/n) [y]: ").strip().lower()
        if response != 'n':
            print(f"✓ Using existing location: {existing_location}")
            return existing_location
        print()
    
    # Select new location
    download_folder = None
    
    if FOLDER_SELECTOR_AVAILABLE:
        # Try GUI first for better user experience
        print("Would you like to use:")
        print("  1. Graphical folder browser (recommended for beginners)")
        print("  2. Type path manually")
        print()
        
        choice = input("Choose option (1/2) [1]: ").strip()
        
        if choice == "2":
            # CLI selection
            download_folder = select_download_folder(use_gui=False)
        else:
            # Try GUI, fall back to CLI if it fails
            download_folder = select_download_folder(use_gui=True)
    else:
        # Fallback: simple input
        print("Available options:")
        print("  1. Use default location (./downloads)")
        print("  2. Enter custom path")
        print()
        
        choice = input("Choose option (1/2) [1]: ").strip()
        
        if choice == "2":
            custom_path = input("Enter full path for downloads: ").strip()
            custom_path = os.path.expanduser(custom_path)
            custom_path = os.path.abspath(custom_path)
            
            try:
                os.makedirs(custom_path, exist_ok=True)
                print(f"✓ Created/using folder: {custom_path}")
                download_folder = custom_path
            except Exception as e:
                print(f"✗ Error creating folder: {e}")
                print("Using default location instead.")
                download_folder = None
        
        if not download_folder:
            # Use default
            download_folder = os.path.join(os.getcwd(), 'downloads')
            os.makedirs(download_folder, exist_ok=True)
            print(f"✓ Using default location: {download_folder}")
    
    if not download_folder:
        # Last resort fallback
        download_folder = os.path.join(os.getcwd(), 'downloads')
        os.makedirs(download_folder, exist_ok=True)
        print(f"✓ Using default location: {download_folder}")
    
    print()
    print(f"Download location set to: {download_folder}")
    print()
    
    return download_folder


def save_download_location_to_env(download_folder: str) -> None:
    """
    Save download location to .env file.
    Creates or updates OUTPUT_DIR in .env file.
    
    Args:
        download_folder: Path to download folder
    """
    env_path = Path(ENV_FILE)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read existing .env content
    env_lines = []
    output_dir_exists = False
    
    if env_path.exists():
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('OUTPUT_DIR='):
                        env_lines.append(f'OUTPUT_DIR="{download_folder}"\n')
                        output_dir_exists = True
                    else:
                        env_lines.append(line)
        except Exception as e:
            print(f"Warning: Could not read existing .env: {e}")
    
    # Add OUTPUT_DIR if it doesn't exist
    if not output_dir_exists:
        env_lines.append(f'OUTPUT_DIR="{download_folder}"\n')
    
    # Write back to .env
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        print(f"✓ Saved download location to {ENV_FILE}")
    except Exception as e:
        print(f"✗ Error saving to .env: {e}")
        print(f"Please manually add this line to {ENV_FILE}:")
        print(f'OUTPUT_DIR="{download_folder}"')


def save_cookies_path_to_env(cookies_file: str) -> None:
    """
    Save YouTube cookies path to .env file.
    Creates or updates YOUTUBE_COOKIES in .env file.
    
    Args:
        cookies_file: Path to cookies file
    """
    env_path = Path(ENV_FILE)
    env_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read existing .env content
    env_lines = []
    cookies_exists = False
    
    if env_path.exists():
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('YOUTUBE_COOKIES='):
                        env_lines.append(f'YOUTUBE_COOKIES="{cookies_file}"\n')
                        cookies_exists = True
                    else:
                        env_lines.append(line)
        except Exception as e:
            print(f"Warning: Could not read existing .env: {e}")
    
    # Add YOUTUBE_COOKIES if it doesn't exist
    if not cookies_exists:
        env_lines.append(f'YOUTUBE_COOKIES="{cookies_file}"\n')
    
    # Write back to .env
    try:
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        print(f"✓ Saved YouTube cookies path to {ENV_FILE}")
    except Exception as e:
        print(f"✗ Error saving cookies path to .env: {e}")


def validate_settings(settings: Dict[str, Any]) -> bool:
    """
    Validate configuration settings.
    
    Args:
        settings: Settings dictionary to validate
    
    Returns:
        True if valid, False otherwise
    """
    required_keys = ['cpu_cores', 'total_mem_gb', 'max_threads', 'max_processes', 'platform']
    
    for key in required_keys:
        if key not in settings:
            print(f"Error: Missing required setting: {key}")
            return False
    
    # Validate numeric values
    if settings['max_threads'] < 1:
        print("Error: max_threads must be at least 1")
        return False
    
    if settings['max_processes'] < 1:
        print("Error: max_processes must be at least 1")
        return False
    
    return True


def main() -> int:
    """
    Main configuration function.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    print("\n" + "=" * 60)
    print("  🎵 Spotify Playlist Downloader - Initial Setup")
    print("=" * 60)
    print()
    print("Welcome! This setup will configure your system for downloading")
    print("Spotify playlists. Let's get started!")
    print()
    
    try:
        # Step 1: Setup download location
        print("[Step 1/4] Download Location Setup")
        download_folder = setup_download_location()
        
        # Step 2: Browser login for YouTube access
        print("\n[Step 2/4] Browser Login Setup (Optional)")
        cookies_file = None
        if BROWSER_AUTH_AVAILABLE:
            cookies_file = setup_browser_cookies()
            if cookies_file:
                # Save cookies path to .env
                print(f"✓ Browser login configured")
            else:
                print("⚠ Browser login skipped - some videos may not be downloadable")
        else:
            print("⚠ Browser authentication not available - skipping")
        
        # Step 3: Detect resources
        print("\n[Step 3/4] System Resource Detection")
        print("Detecting system resources...")
        print()
        
        cpu_cores, total_mem_gb = detect_resources()
        settings = recommend_settings(cpu_cores, total_mem_gb)
        
        # Validate settings
        if not validate_settings(settings):
            print("Error: Invalid configuration generated")
            return 1
        
        # Print system info
        print_system_info(settings)
        
        # Step 4: Save configuration
        print("[Step 4/4] Saving Configuration")
        print()
        
        # Create config directory if needed
        create_config_directory()
        
        # Save download location to .env
        save_download_location_to_env(download_folder)
        
        # Save cookies path to .env if available
        if cookies_file:
            save_cookies_path_to_env(cookies_file)
        
        # Write config file
        config_path = Path(CONFIG_FILE)
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            print(f"✓ System configuration saved to {CONFIG_FILE}")
            print()
        except (IOError, OSError) as e:
            print(f"✗ Error writing config file: {e}", file=sys.stderr)
            return 1
        
        # Display next steps
        print("=" * 60)
        print("  Setup Complete! 🎉")
        print("=" * 60)
        print()
        print("Next steps:")
        print(f"1. Configure your Spotify API credentials in {ENV_FILE}")
        print("   (You'll need SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET)")
        print("2. Run: python main.py")
        print()
        print(f"Your music will be downloaded to: {download_folder}")
        print()
        
        return 0
        
    except Exception as e:
        print(f"✗ Fatal error during configuration: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
 