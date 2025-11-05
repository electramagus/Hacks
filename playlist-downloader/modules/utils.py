"""
Shared Utilities Module
=======================
Common functions used across the playlist downloader application.
Includes file operations, sanitization, and validation utilities.
"""

import os
import re
import logging
from pathlib import Path
from typing import Set, Optional
from datetime import datetime


# Supported audio file extensions for detection
AUDIO_EXTENSIONS = {'.mp3', '.m4a', '.opus', '.flac', '.wav', '.ogg', '.aac', '.webm'}


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitize filename for cross-platform compatibility.
    
    Removes invalid characters, normalizes whitespace, and ensures valid length.
    
    Args:
        filename: Raw filename string
        max_length: Maximum filename length (default 200)
        
    Returns:
        Sanitized filename safe for all platforms
        
    Example:
        >>> sanitize_filename("Song: Title/Name?")
        'Song_ Title_Name'
    """
    # Remove invalid characters for Windows/Linux/macOS
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Normalize multiple underscores to single
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Remove leading/trailing dots and spaces (Windows incompatible)
    sanitized = sanitized.strip('. ')
    
    # Truncate to max length while preserving file extension if present
    if len(sanitized) > max_length:
        name, ext = os.path.splitext(sanitized)
        available_length = max_length - len(ext)
        sanitized = name[:available_length] + ext
    
    # Ensure not empty
    return sanitized if sanitized else 'untitled'


def extract_playlist_id(playlist_input: str) -> str:
    """
    Extract Spotify playlist ID from URL or return as-is if already an ID.
    
    Args:
        playlist_input: Spotify playlist URL or ID
        
    Returns:
        Playlist ID string
        
    Example:
        >>> extract_playlist_id("https://open.spotify.com/playlist/ABC123?si=xyz")
        'ABC123'
    """
    if 'spotify.com/playlist/' in playlist_input:
        # Extract ID from URL, removing query parameters
        return playlist_input.split('playlist/')[-1].split('?')[0]
    return playlist_input


def get_downloaded_files(directory: str) -> Set[str]:
    """
    Get set of already downloaded file basenames (without extensions).
    
    Scans directory for audio files and returns their names without extensions
    for quick lookup to avoid re-downloading.
    
    Args:
        directory: Path to directory to scan
        
    Returns:
        Set of file basenames (without extensions)
        
    Example:
        If directory contains "Song.mp3" and "Track.m4a",
        returns {"Song", "Track"}
    """
    if not os.path.exists(directory):
        return set()
    
    downloaded = set()
    try:
        for filename in os.listdir(directory):
            base, ext = os.path.splitext(filename)
            if ext.lower() in AUDIO_EXTENSIONS:
                downloaded.add(base)
    except (OSError, PermissionError) as e:
        logging.warning(f"Error scanning directory {directory}: {e}")
    
    return downloaded


def simplify_search_query(title: str, artist: str) -> str:
    """
    Simplify song title and artist for better YouTube search results.
    
    Removes noise like parenthetical content, remix tags, and features
    to improve search accuracy.
    
    Args:
        title: Song title
        artist: Artist name
        
    Returns:
        Simplified search query string
        
    Example:
        >>> simplify_search_query("Song (Remix) [Official]", "Artist feat. Other")
        'Song Artist'
    """
    # Remove content in parentheses and brackets
    title = re.sub(r'\([^)]*\)', '', title)
    title = re.sub(r'\[[^\]]*\]', '', title)
    
    # Remove common noise words and patterns
    title = re.sub(r'(?i)\bfeat\.?\s*[^-–—]*', '', title)
    title = re.sub(r'(?i)\bft\.?\s*[^-–—]*', '', title)
    title = re.sub(r'(?i)\bremix\b[^-–—]*', '', title)
    title = re.sub(r'(?i)\bremastered\b', '', title)
    title = re.sub(r'(?i)\bofficial\b', '', title)
    
    # Keep only content before dash (often separates title from version info)
    title = title.split('-')[0].split('–')[0].split('—')[0]
    
    # Normalize whitespace
    title = ' '.join(title.split())
    artist = ' '.join(artist.split())
    
    return f"{title} {artist}".strip()


def ensure_directory(path: str) -> None:
    """
    Ensure directory exists, creating it if necessary.
    
    Args:
        path: Directory path to ensure exists
        
    Raises:
        OSError: If directory cannot be created
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def validate_url(url: str, url_type: str = 'spotify') -> bool:
    """
    Validate playlist URL format.
    
    Args:
        url: URL string to validate
        url_type: Type of URL ('spotify' or 'youtube')
        
    Returns:
        True if URL is valid, False otherwise
        
    Example:
        >>> validate_url("https://open.spotify.com/playlist/ABC", 'spotify')
        True
    """
    if url_type == 'spotify':
        pattern = r'https?://open\.spotify\.com/playlist/[\w\d]+'
    elif url_type == 'youtube':
        pattern = r'https?://(www\.)?(youtube\.com/playlist\?list=|youtu\.be/)[\w\-]+'
    else:
        return False
    
    return bool(re.match(pattern, url))


def setup_logging(log_dir: str = "logs", log_level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging with both file and console handlers.
    
    Args:
        log_dir: Directory to store log files
        log_level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """
    # Create log directory
    ensure_directory(log_dir)
    
    # Generate timestamped log filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f"playlist_downloader_{timestamp}.log")
    
    # Configure logging format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Create handlers
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format))
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[file_handler, console_handler]
    )
    
    logger = logging.getLogger('playlist_downloader')
    logger.info(f"Logging initialized. Log file: {log_file}")
    
    return logger


def format_duration(milliseconds: int) -> str:
    """
    Format duration from milliseconds to human-readable format.
    
    Args:
        milliseconds: Duration in milliseconds
        
    Returns:
        Formatted duration string (MM:SS or HH:MM:SS)
        
    Example:
        >>> format_duration(185000)
        '03:05'
    """
    seconds = milliseconds // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def calculate_statistics(total: int, downloaded: int, failed: int) -> dict:
    """
    Calculate download statistics.
    
    Args:
        total: Total number of tracks
        downloaded: Number of successfully downloaded tracks
        failed: Number of failed downloads
        
    Returns:
        Dictionary with statistics including success rate
    """
    success_rate = (downloaded / total * 100) if total > 0 else 0
    
    return {
        'total': total,
        'downloaded': downloaded,
        'failed': failed,
        'success_rate': round(success_rate, 2),
        'pending': total - downloaded - failed
    }
