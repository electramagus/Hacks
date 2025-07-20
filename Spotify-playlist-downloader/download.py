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

# === CONFIG ===
SPOTIFY_CLIENT_ID = "b8921d57517644cdbbf5365f26d9461a"
SPOTIFY_CLIENT_SECRET = "48079909c1e745679ac19fc6f3b92938" 
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8000/callback"
PLAYLIST_ID = "https://open.spotify.com/playlist/1k9c2hqwepK5KzEldgTWQS?si=oOZWlk-1RCiL_2-UTy3DIQ&pt=3c7a8e6fafb538538f7e00eef35efe7d&pi=IJfN2zw8RcC1n"  # Can also be playlist URL
OUTPUT_DIR = r"C:\Users\Creed\OneDrive\Desktop\Music"
FFMPEG_PATH = "ffmpeg"  # Assumes it's in PATH

# Audio quality options: 320K, 256K, 192K, 128K, 64K
AUDIO_QUALITY = "320K"
AUDIO_FORMAT = "mp3"  # mp3, flac, m4a, wav

# Delay between downloads (seconds) - be respectful to YouTube
DOWNLOAD_DELAY = 2

# Maximum retries for failed downloads
MAX_RETRIES = 3

# Concurrent search settings
SEARCH_WORKERS = 10
DOWNLOAD_WORKERS = 10
SEARCH_DELAY_RANGE = (0.5, 1.5)
START_DOWNLOAD_THRESHOLD = 20

LINKS_FILE = os.path.join(OUTPUT_DIR, "links.json")
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "progress.json")

# === SETUP LOGGING ===
def setup_logging():
    log_dir = Path(OUTPUT_DIR) / "logs"
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

# === UTILITY FUNCTIONS ===
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

# === STEP 1: Get Songs from Spotify ===
def get_spotify_tracks(logger) -> List[Dict]:
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="playlist-read-private playlist-read-collaborative"
        ))
        playlist_id = extract_playlist_id(PLAYLIST_ID)
        logger.info(f"Fetching tracks from playlist: {playlist_id}")
        playlist_info = sp.playlist(playlist_id)
        logger.info(f"Playlist: {playlist_info['name']} by {playlist_info['owner']['display_name']}")
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
        logger.info(f"Found {len(tracks)} tracks in playlist")
        return tracks
    except spotipy.exceptions.SpotifyException as e:
        logger.error(f"Spotify API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching Spotify tracks: {e}")
        return []

# === CONCURRENT YOUTUBE SEARCH ===
def search_youtube(query: str, logger) -> Optional[str]:
    """Search for a video on YouTube using yt-dlp and return the best match URL"""
    try:
        logger.info(f"Searching YouTube for: {query}")
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
            logger.info(f"Found video: {youtube_url}")
            return youtube_url
        else:
            logger.warning(f"Could not find YouTube video for: {query}")
            return None
    except subprocess.CalledProcessError as e:
        logger.warning(f"yt-dlp search failed for '{query}': {e.stderr or e}")
        return None
    except Exception as e:
        logger.error(f"Error searching YouTube for '{query}': {e}")
        return None

def load_links() -> Dict[str, Dict]:
    if os.path.exists(LINKS_FILE):
        try:
            with open(LINKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_links(links: Dict[str, Dict]):
    with open(LINKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(links, f, indent=2, ensure_ascii=False)

def load_progress_file() -> Dict[str, list]:
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {'completed': [], 'failed': []}
    return {'completed': [], 'failed': []}

def save_progress_file(progress: Dict[str, list]):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

def producer_consumer_search_and_download(tracks: List[Dict], logger):
    links = load_links()
    progress = load_progress_file()
    completed = set(track['search_query'] for track in progress.get('completed', []))
    failed = set(track['search_query'] for track in progress.get('failed', []))
    to_search = [track for track in tracks if track['search_query'] not in links]
    to_download = [info for query, info in links.items() if query not in completed]
    q = queue.Queue(maxsize=100)  # Prevents memory bloat
    search_done = threading.Event()
    lock = threading.Lock()

    def search_task(track):
        query = track['search_query']
        url = search_youtube(query, logger)
        time.sleep(random.uniform(*SEARCH_DELAY_RANGE))
        if url:
            link_info = {
                'youtube_url': url,
                'name': track['name'],
                'artist': track['artist'],
                'album': track['album'],
                'duration_ms': track['duration_ms'],
                'search_query': track['search_query']
            }
            with lock:
                links[query] = link_info
                save_links(links)
            q.put(link_info)
            logger.info(f"Queued for download: {query}")
        else:
            logger.warning(f"No YouTube result for: {query}")

    def download_task():
        while True:
            item = q.get()
            if item is None:
                q.task_done()
                break
            track_info = item
            url = track_info['youtube_url']
            success = download_audio(url, track_info, OUTPUT_DIR, logger)
            with lock:
                if success:
                    progress.setdefault('completed', []).append(track_info)
                    logger.info(f"Completed: {track_info['name']} - {track_info['artist']}")
                else:
                    progress.setdefault('failed', []).append(track_info)
                    logger.warning(f"Failed: {track_info['name']} - {track_info['artist']}")
                save_progress_file(progress)
            q.task_done()

    # Start download workers (but they will block until enough links are queued)
    download_threads = []
    for _ in range(DOWNLOAD_WORKERS):
        t = threading.Thread(target=download_task)
        t.start()
        download_threads.append(t)

    # Queue already found links for download
    for info in to_download:
        q.put(info)

    # Start searching in parallel
    logger.info(f"Starting concurrent YouTube search for {len(to_search)} tracks (skipping {len(links)} already searched)")
    with ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
        futures = []
        for track in to_search:
            futures.append(executor.submit(search_task, track))
            # Start downloaders after threshold is reached
            if q.qsize() >= START_DOWNLOAD_THRESHOLD and not search_done.is_set():
                logger.info(f"{START_DOWNLOAD_THRESHOLD} links found, downloads are running...")
                search_done.set()
        for future in as_completed(futures):
            pass  # Just wait for all searches to finish
    logger.info("YouTube search complete.")
    # Signal downloaders to finish
    for _ in range(DOWNLOAD_WORKERS):
        q.put(None)
    for t in download_threads:
        t.join()
    logger.info(f"Download phase complete. {len(progress.get('completed', []))} completed, {len(progress.get('failed', []))} failed.")
    print(f"\nDownload phase complete. {len(progress.get('completed', []))} completed, {len(progress.get('failed', []))} failed.")
    if progress.get('failed', []):
        print("\n❌ Failed tracks:")
        for track in progress['failed'][-10:]:
            print(f"  - {track['name']} - {track['artist']}")

# === STEP 3: Download Audio with yt-dlp ===
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
            logger.info(f"Downloading: {track_info['name']} by {track_info['artist']} (Attempt {attempt + 1})")
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            logger.info(f"Successfully downloaded: {safe_filename}")
            return True
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.warning(f"Download attempt {attempt + 1} failed: {error_msg}")
            if attempt < MAX_RETRIES - 1:
                wait_time = (attempt + 1) * 5
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to download after {MAX_RETRIES} attempts: {track_info['name']}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error downloading {track_info['name']}: {e}")
            return False
    return False

# === PROGRESS TRACKING ===
def save_progress(completed_tracks: List, failed_tracks: List, output_dir: str):
    progress_file = Path(output_dir) / "download_progress.json"
    progress_data = {
        'completed': completed_tracks,
        'failed': failed_tracks,
        'timestamp': datetime.now().isoformat()
    }
    with open(progress_file, 'w', encoding='utf-8') as f:
        json.dump(progress_data, f, indent=2, ensure_ascii=False)

def load_progress(output_dir: str) -> tuple:
    progress_file = Path(output_dir) / "download_progress.json"
    if progress_file.exists():
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('completed', []), data.get('failed', [])
        except Exception:
            pass
    return [], []

# === MAIN FUNCTION ===
def main():
    print("🎵 Spotify to YouTube Downloader")
    print("=" * 40)
    if not check_dependencies():
        return
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger = setup_logging()
    logger.info("Starting Spotify to YouTube download process")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    try:
        tracks = get_spotify_tracks(logger)
        if not tracks:
            logger.error("No tracks found. Check your Spotify configuration.")
            return
        # --- Producer-consumer search and download phase ---
        producer_consumer_search_and_download(tracks, logger)
    except KeyboardInterrupt:
        logger.info("Download interrupted by user")
        print(f"\n⏸️ Download interrupted. Progress saved to {OUTPUT_DIR}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    main()