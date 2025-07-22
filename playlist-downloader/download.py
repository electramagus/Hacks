import os
import subprocess
import time
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
import sys
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import threading

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError as e:
    print(f"Missing required packages. Please install with:")
    print("pip install spotipy")
    exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("Missing required package 'python-dotenv'. Please install with:")
    print("pip install python-dotenv")
    exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("Missing required package 'tqdm'. Please install with:")
    print("pip install tqdm")
    exit(1)

# === CONFIG PATHS ===
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '.config')
USER_FILE = os.path.join(CONFIG_DIR, 'user.json')
ENV_FILE = os.path.join(CONFIG_DIR, '.env')

# === LOAD CONFIG FROM .env ===
os.makedirs(CONFIG_DIR, exist_ok=True)
load_dotenv(dotenv_path=ENV_FILE)

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")
OUTPUT_DIR = os.getenv("OUTPUT_DIR")
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
AUDIO_QUALITY = os.getenv("AUDIO_QUALITY", "320K")
AUDIO_FORMAT = os.getenv("AUDIO_FORMAT", "mp3")
DOWNLOAD_DELAY = float(os.getenv("DOWNLOAD_DELAY", "2"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
SEARCH_WORKERS = int(os.getenv("SEARCH_WORKERS", "10"))
DOWNLOAD_WORKERS = int(os.getenv("DOWNLOAD_WORKERS", "10"))
SEARCH_DELAY_RANGE = (
    float(os.getenv("SEARCH_DELAY_MIN", "0.5")),
    float(os.getenv("SEARCH_DELAY_MAX", "1.5"))
)
START_DOWNLOAD_THRESHOLD = int(os.getenv("START_DOWNLOAD_THRESHOLD", "20"))

PLAYLISTS_FILE = os.path.join(OUTPUT_DIR, "playlists.txt")
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "progress.json")

# === LOGGING ===
def setup_logging():
    log_dir = Path(os.path.dirname(__file__)) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"download_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[file_handler, stream_handler]
    )
    return logging.getLogger(__name__)

def sanitize_filename(filename: str) -> str:
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    sanitized = re.sub('_+', '_', sanitized)
    sanitized = sanitized.strip('. ')
    return sanitized

def extract_playlist_id(playlist_input: str) -> str:
    if 'spotify.com/playlist/' in playlist_input:
        return playlist_input.split('playlist/')[-1].split('?')[0]
    return playlist_input

def check_dependencies():
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ yt-dlp is not installed or not in PATH")
        print("Install it with: pip install yt-dlp")
        return False
    try:
        subprocess.run([FFMPEG_PATH, '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ ffmpeg is not installed or not in PATH")
        print("Download from: https://ffmpeg.org/download.html")
        return False
    return True

def get_user():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'name' in data:
                    return data['name']
        except Exception:
            pass
    # First run: intro and ask for name
    print("""
Hey! 👋 I am your Spotify Playlist Downloader.
I can help you download all the songs from your Spotify playlists as MP3s, organized by playlist, and keep them in sync with your local folders.

Features:
- Add and manage multiple playlists
- Check which songs are missing locally
- Download and sync your music library
- All with a simple interactive menu!
""")
    name = input("What's your name? ").strip()
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump({'name': name}, f)
    print(f"Welcome, {name}! Let's get started.")
    return name

def get_spotify_tracks(sp, playlist_id, logger) -> (str, List[Dict]):
    try:
        playlist_id = extract_playlist_id(playlist_id)
        playlist_info = sp.playlist(playlist_id)
        playlist_name = sanitize_filename(playlist_info['name'])
        tracks = []
        results = sp.playlist_tracks(playlist_id)
        while results:
            for item in results['items']:
                if item['track'] and item['track']['name']:
                    track = item['track']
                    track_info = {
                        'name': track['name'],
                        'artist': track['artists'][0]['name'] if track['artists'] else 'Unknown Artist',
                        'album': track['album']['name'] if track['album'] else 'Unknown Album',
                        'duration_ms': track.get('duration_ms', 0),
                        'search_query': f"{track['name']} {track['artists'][0]['name']}" if track['artists'] else track['name']
                    }
                    tracks.append(track_info)
            if results['next']:
                results = sp.next(results)
            else:
                break
        return playlist_name, tracks
    except Exception as e:
        logger.error(f"Error fetching Spotify tracks: {e}")
        return None, []

def search_youtube(query: str, logger) -> Optional[str]:
    try:
        command = [
            "yt-dlp",
            f"ytsearch1:{query}",
            "--get-id",
            "--skip-download"
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        video_id = result.stdout.strip()
        if video_id:
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            return youtube_url
        else:
            return None
    except Exception as e:
        logger.warning(f"yt-dlp search failed for '{query}': {e}")
        return None

def playlist_labels_and_links():
    labels = []
    links = []
    if os.path.exists(PLAYLISTS_FILE):
        with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Extract label and link
                label = None
                link = None
                if ':' in line:
                    parts = line.split(':', 1)
                    label = parts[0].strip()
                    match = re.search(r'(https?://open\.spotify\.com/playlist/[\w\d]+[\S]*)', parts[1])
                    if match:
                        link = match.group(1)
                else:
                    match = re.search(r'(https?://open\.spotify\.com/playlist/[\w\d]+[\S]*)', line)
                    if match:
                        link = match.group(1)
                if label and link:
                    labels.append(label)
                    links.append((label, link))
                elif link:
                    labels.append(link)
                    links.append((link, link))
    return labels, links

def add_playlist_interactive():
    labels, _ = playlist_labels_and_links()
    print("\nYour current playlists:")
    if labels:
        for i, label in enumerate(labels, 1):
            print(f"  {i}. {label}")
    else:
        print("  (none yet)")
    while True:
        label = input("Enter a label for your new playlist: ").strip()
        link = input("Paste the Spotify playlist link: ").strip()
        if not re.match(r'https?://open\.spotify\.com/playlist/[\w\d]+', link):
            print("Invalid playlist link. Please try again.")
            continue
        with open(PLAYLISTS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{label}: {link}\n")
        print(f"Playlist '{label}' added successfully!")
        again = input("Add another playlist? (y/n): ").strip().lower()
        if again != 'y':
            break

def check_undownloaded_songs(sp, logger):
    _, links = playlist_labels_and_links()
    for label, link in tqdm(links, desc="Scanning playlists", unit="playlist"):
        playlist_name, tracks = get_spotify_tracks(sp, link, logger)
        if not playlist_name or not tracks:
            print(f"\nCould not fetch playlist: {label}")
            continue
        playlist_dir = os.path.join(OUTPUT_DIR, playlist_name)
        os.makedirs(playlist_dir, exist_ok=True)
        local_files = set()
        for file in os.listdir(playlist_dir):
            if file.endswith(f'.{AUDIO_FORMAT}'):
                local_files.add(os.path.splitext(file)[0])
        spotify_tracks = set(sanitize_filename(f"{t['artist']} - {t['name']}") for t in tracks)
        missing = spotify_tracks - local_files
        print(f"\nPlaylist: {label}")
        print(f"  Total on Spotify: {len(spotify_tracks)}")
        print(f"  Downloaded: {len(spotify_tracks) - len(missing)}")
        print(f"  Missing: {len(missing)}")
        if missing:
            print(f"  Missing tracks:")
            for t in tracks:
                fname = sanitize_filename(f"{t['artist']} - {t['name']}")
                if fname in missing:
                    print(f"    - {t['name']} by {t['artist']}")

def download_audio(url: str, track_info: Dict, output_dir: str, logger) -> bool:
    for attempt in range(MAX_RETRIES):
        try:
            safe_filename = sanitize_filename(f"{track_info['artist']} - {track_info['name']}")
            output_template = os.path.join(output_dir, f"{safe_filename}.%(ext)s")
            command = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", AUDIO_FORMAT,
                "--audio-quality", AUDIO_QUALITY,
                "--format", "bestaudio[ext=m4a]/bestaudio[ext=mp4]/bestaudio",
                "--output", output_template,
                "--no-playlist",
                "--embed-metadata",
                "--add-metadata",
                "--no-mtime",
                url
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return True
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep((attempt + 1) * 5)
            else:
                return False
    return False

def sync_and_download(sp, logger):
    _, links = playlist_labels_and_links()
    for label, link in tqdm(links, desc="Syncing playlists", unit="playlist"):
        playlist_name, tracks = get_spotify_tracks(sp, link, logger)
        if not playlist_name or not tracks:
            print(f"\nCould not fetch playlist: {label}")
            continue
        playlist_dir = os.path.join(OUTPUT_DIR, playlist_name)
        os.makedirs(playlist_dir, exist_ok=True)
        local_files = set()
        for file in os.listdir(playlist_dir):
            if file.endswith(f'.{AUDIO_FORMAT}'):
                local_files.add(os.path.splitext(file)[0])
        spotify_tracks = set(sanitize_filename(f"{t['artist']} - {t['name']}") for t in tracks)
        missing = spotify_tracks - local_files
        print(f"\nSyncing playlist: {label}")
        print(f"  Total on Spotify: {len(spotify_tracks)}")
        print(f"  Downloaded: {len(spotify_tracks) - len(missing)}")
        print(f"  Missing: {len(missing)}")
        # Progress bar for downloading missing tracks
        for t in tqdm(tracks, desc=f"Downloading {label}", unit="song"):
            fname = sanitize_filename(f"{t['artist']} - {t['name']}")
            if fname in missing:
                url = search_youtube(t['search_query'], logger)
                if not url:
                    print(f"  Could not find YouTube for: {t['name']} by {t['artist']}")
                    continue
                print(f"  Downloading: {t['name']} by {t['artist']}")
                success = download_audio(url, t, playlist_dir, logger)
                if success:
                    print(f"    Downloaded!")
                else:
                    print(f"    Failed after retries.")
                time.sleep(DOWNLOAD_DELAY)
        print(f"  Done syncing playlist: {label}")

def main():
    print("🎵 Spotify Playlist Downloader (Interactive Edition)")
    print("=" * 40)
    if not check_dependencies():
        return
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger = setup_logging()
    name = get_user()
    print(f"\nWelcome back, {name}!")
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-read-private playlist-read-collaborative"
    ))
    while True:
        print("\nHome Menu:")
        print("1. Add a playlist")
        print("2. Check undownloaded songs")
        print("3. Sync and download")
        print("4. Exit")
        choice = input("Choose an option (1-4): ").strip()
        if choice == '1':
            add_playlist_interactive()
        elif choice == '2':
            check_undownloaded_songs(sp, logger)
        elif choice == '3':
            sync_and_download(sp, logger)
        elif choice == '4':
            print(f"Goodbye, {name}! 👋")
            break
        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    main()