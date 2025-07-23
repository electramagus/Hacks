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
from concurrent.futures import ThreadPoolExecutor
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

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich import box

console = Console()

# === CONFIG PATHS ===
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '.config')
USER_FILE = os.path.join(CONFIG_DIR, 'user.json')
ENV_FILE = os.path.join(CONFIG_DIR, '.env')
CONFIG_JSON = os.path.join(os.path.dirname(__file__), 'config.json')

# === LOAD CONFIG FROM .env ===
def load_config_json():
    if not os.path.exists(CONFIG_JSON) or os.stat(CONFIG_JSON).st_size == 0:
        print('Config file missing or empty. Running configure.py...')
        try:
            subprocess.run([sys.executable, 'configure.py'], check=True)
        except Exception as e:
            print(f'Failed to run configure.py: {e}')
    try:
        with open(CONFIG_JSON, 'r', encoding='utf-8') as f:
            config = json.load(f)
            if not isinstance(config, dict) or not config:
                raise ValueError('Config file is empty or invalid')
            return config
    except Exception as e:
        print(f'Could not load config.json: {e}')
        return {}

os.makedirs(CONFIG_DIR, exist_ok=True)
load_dotenv(dotenv_path=ENV_FILE)

# Set default worker values before config_json is loaded
DEFAULT_SEARCH_WORKERS = 3
DEFAULT_DOWNLOAD_WORKERS = 3

config_json = load_config_json()
SEARCH_WORKERS = int(config_json.get('max_threads', DEFAULT_SEARCH_WORKERS))
DOWNLOAD_WORKERS = int(config_json.get('max_processes', DEFAULT_DOWNLOAD_WORKERS))

# Print device config summary
# Remove or comment out the following block:
# print("\n=== Device Configuration ===")
# if config_json:
#     for k, v in config_json.items():
#         print(f"{k}: {v}")
# else:
#     print("No config.json found or config is empty. Using defaults.")
# print(f"Search workers: {SEARCH_WORKERS}")
# print(f"Download workers: {DOWNLOAD_WORKERS}")
# print("===========================\n")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")
OUTPUT_DIR = os.getenv("OUTPUT_DIR")
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
AUDIO_QUALITY = os.getenv("AUDIO_QUALITY", "320K")
AUDIO_FORMAT = os.getenv("AUDIO_FORMAT", "best")
DOWNLOAD_DELAY = float(os.getenv("DOWNLOAD_DELAY", "1.5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
SEARCH_DELAY_RANGE = (
    float(os.getenv("SEARCH_DELAY_MIN", "0.5")),
    float(os.getenv("SEARCH_DELAY_MAX", "1.5"))
)
START_DOWNLOAD_THRESHOLD = int(os.getenv("START_DOWNLOAD_THRESHOLD", "27"))

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

def migrate_playlists_file():
    if not os.path.exists(PLAYLISTS_FILE):
        return
    migrated = False
    lines = []
    with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(':', 2)
            # Check if already migrated: label:type:link
            if len(parts) == 3 and parts[1] in ('spotify', 'youtube'):
                lines.append(line)
                continue

            # If not migrated, it's an old format. Mark for migration.
            migrated = True
            if ':' in line:
                # Handles "label: link" or corrupted "label:type:type:link"
                label, link = line.split(':', 1)
                label = label.strip()
                link = link.strip()
            else:
                label = "Unnamed Playlist"
                link = line.strip()

            if 'spotify.com/playlist/' in link:
                ptype = 'spotify'
            elif 'youtube.com/playlist' in link or 'youtu.be' in link:
                ptype = 'youtube'
            else:
                # If a line is corrupted, it might not have a valid link.
                # Attempt to clean it up.
                if 'spotify:https' in link:
                    link = link.replace('spotify:https', 'https')
                ptype = 'spotify' # Default assumption

            lines.append(f"{label}:{ptype}:{link}")

    if migrated:
        console.print("[yellow]Detected old playlist format. Migrating playlists.txt...[/yellow]")
        with open(PLAYLISTS_FILE, 'w', encoding='utf-8') as f:
            for l in lines:
                f.write(l + '\n')
        console.print("[green]Migration complete.[/green]")


def playlist_labels_and_links():
    labels = []
    links = []
    types = []
    if os.path.exists(PLAYLISTS_FILE):
        with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                label, ptype, link = "Unknown", "unknown", ""
                
                parts = line.split(':', 2)
                
                # New format: label:type:link
                if len(parts) == 3 and parts[1] in ('spotify', 'youtube'):
                    label, ptype, link = parts[0].strip(), parts[1].strip(), parts[2].strip()
                # Old format: label: link
                elif ':' in line:
                    label_part, link_part = line.split(':', 1)
                    label = label_part.strip()
                    link = link_part.strip()
                    if 'spotify.com' in link:
                        ptype = 'spotify'
                    elif 'youtube.com' in link:
                        ptype = 'youtube'
                # Link only
                else:
                    link = line.strip()
                    label = link
                    if 'spotify.com' in link:
                        ptype = 'spotify'
                    elif 'youtube.com' in link:
                        ptype = 'youtube'
                
                if ptype != "unknown":
                    labels.append(label)
                    links.append((label, ptype, link))
                    types.append(ptype)

    if not links:
        print(f"Warning: No valid playlists found in {PLAYLISTS_FILE}.")
    return labels, links, types

def add_playlist_interactive():
    labels, _, _ = playlist_labels_and_links()
    console.rule("[bold cyan]Add a Playlist[/bold cyan]")
    if labels:
        table = Table(title="Your Current Playlists", box=box.SIMPLE)
        table.add_column("#", style="bold")
        table.add_column("Label", style="green")
        for i, label in enumerate(labels, 1):
            table.add_row(str(i), label)
        console.print(table)
    else:
        console.print("[yellow]No playlists yet.[/yellow]")
    console.print("[dim]Type 'm' at any prompt to go back to the main menu.[/dim]")
    while True:
        label = Prompt.ask("[bold]Enter a label for your new playlist[/bold]", default="", console=console).strip()
        if label.lower() == 'm':
            console.print("[cyan]Returning to main menu.[/cyan]")
            break
        ptype = Prompt.ask("[bold]Is this a Spotify or YouTube playlist?[/bold]", choices=["spotify", "youtube"], default="spotify", console=console).strip().lower()
        if ptype == 'm':
            console.print("[cyan]Returning to main menu.[/cyan]")
            break
        if ptype == 'spotify':
            link = Prompt.ask("[bold]Paste the Spotify playlist link[/bold]", default="", console=console).strip()
            if link.lower() == 'm':
                console.print("[cyan]Returning to main menu.[/cyan]")
                break
            if not re.match(r'https?://open\.spotify\.com/playlist/[\w\d]+', link):
                console.print("[red]Invalid Spotify playlist link. Please try again or type 'm' to go back.[/red]")
                continue
            # Fetch playlist info for preview (as before)
            try:
                sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                    client_id=SPOTIFY_CLIENT_ID,
                    client_secret=SPOTIFY_CLIENT_SECRET,
                    redirect_uri=SPOTIFY_REDIRECT_URI,
                    scope="playlist-read-private playlist-read-collaborative"
                ))
                playlist_id = extract_playlist_id(link)
                playlist_info = sp.playlist(playlist_id)
                preview_table = Table(title="[bold magenta]Playlist Preview[/bold magenta]", box=box.ROUNDED)
                preview_table.add_column("Field", style="cyan", no_wrap=True)
                preview_table.add_column("Value", style="white")
                preview_table.add_row("Name", f"[bold green]{playlist_info['name']}[/bold green]")
                preview_table.add_row("Owner", playlist_info['owner']['display_name'])
                preview_table.add_row("Tracks", str(playlist_info['tracks']['total']))
                preview_table.add_row("Cover Art", playlist_info['images'][0]['url'] if playlist_info['images'] else "[dim]No image[/dim]")
                console.print(preview_table)
                confirm = Prompt.ask("[bold green]Add this playlist?[/bold green] (y/n)", choices=["y", "n"], default="y", console=console)
                if confirm.lower() != 'y':
                    console.print("[yellow]Playlist not added. Returning to main menu.[/yellow]")
                    break
            except Exception as e:
                console.print(f"[red]Failed to fetch playlist info: {e}[/red]")
                continue
        else:  # YouTube
            link = Prompt.ask("[bold]Paste the YouTube playlist link[/bold]", default="", console=console).strip()
            if link.lower() == 'm':
                console.print("[cyan]Returning to main menu.[/cyan]")
                break
            if not re.match(r'https?://(www\.)?(youtube\.com/playlist\?list=|youtu\.be/)[\w\-]+', link):
                console.print("[red]Invalid YouTube playlist link. Please try again or type 'm' to go back.[/red]")
                continue
            # Optionally preview YouTube playlist (not implemented)
        with open(PLAYLISTS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{label}:{ptype}:{link}\n")
        console.print(Panel.fit(f"Playlist '[bold]{label}[/bold]' added successfully! 🎉", style="green"))
        # Show summary table of all playlists
        labels, _, _ = playlist_labels_and_links()
        table = Table(title="[bold]All Playlists[/bold]", box=box.SIMPLE)
        table.add_column("#", style="bold")
        table.add_column("Label", style="green")
        for i, label in enumerate(labels, 1):
            table.add_row(str(i), label)
        console.print(table)
        again = Prompt.ask("[bold]Add another playlist?[/bold] (y/n, or 'm' to go back)", choices=["y", "n", "m"], default="n", console=console).lower()
        if again == 'm' or again != 'y':
            console.print("[cyan]Returning to main menu.[/cyan]")
            break

# === Helper: Fetch all tracks from a Spotify playlist ===
def get_spotify_tracks(sp, playlist_url):
    try:
        playlist_id = extract_playlist_id(playlist_url)
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
                    }
                    tracks.append(track_info)
            if results['next']:
                results = sp.next(results)
            else:
                break
        return playlist_name, tracks
    except Exception as e:
        print(f"Error fetching Spotify tracks: {e}")
        return None, []

def get_youtube_playlist_tracks_sync(playlist_url: str):
    """Fetches the YouTube playlist name and videos, returns (playlist_name, [track dicts with name, artist, url])"""
    import subprocess
    import json
    try:
        result = subprocess.run(
            ["yt-dlp", "-J", "--flat-playlist", playlist_url],
            capture_output=True, text=True, check=True, encoding='utf-8'
        )
        data = json.loads(result.stdout)
        playlist_name = data.get('title', None)
        tracks = []
        for entry in data.get('entries', []):
            if entry and entry.get('title') and entry.get('id'):
                track_info = {
                    'name': entry['title'],
                    'artist': entry.get('uploader', 'Unknown Uploader'),
                    'url': f"https://www.youtube.com/watch?v={entry['id']}"
                }
                tracks.append(track_info)
        return playlist_name, tracks
    except Exception as e:
        console.print(f"[red]Failed to fetch YouTube playlist info: {e}[/red]")
        return None, []

def main():
    # Beautified Device Configuration
    console.clear()
    console.rule("[bold magenta]🎵 Spotify Playlist Downloader (Interactive Edition)[/bold magenta]", style="magenta")
    # Device config as a table
    device_table = Table(title="[bold cyan]Device Configuration[/bold cyan]", box=box.SIMPLE)
    device_table.add_column("Key", style="bold yellow")
    device_table.add_column("Value", style="white")
    if config_json:
        for k, v in config_json.items():
            device_table.add_row(str(k), str(v))
    else:
        device_table.add_row("[dim]No config.json found or config is empty. Using defaults.[/dim]", "")
    device_table.add_row("Search workers", str(SEARCH_WORKERS))
    device_table.add_row("Download workers", str(DOWNLOAD_WORKERS))
    console.print(device_table)
    # Welcome message as a panel
    logger = setup_logging()
    name = get_user()
    welcome_panel = Panel.fit(f"Welcome back, [bold green]{name}[/bold green]!", style="bold magenta")
    console.print(welcome_panel)
    # Playlists list as a table
    if os.path.exists(PLAYLISTS_FILE):
        with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
            playlist_labels = []
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if ':' in line:
                    label = line.split(':', 1)[0].strip()
                else:
                    label = "Unnamed Playlist"
                playlist_labels.append(label)
        if playlist_labels:
            pl_table = Table(title="[bold green]Your Playlists[/bold green]", box=box.MINIMAL_DOUBLE_HEAD)
            pl_table.add_column("#", style="bold", width=4)
            pl_table.add_column("Label", style="cyan")
            for i, label in enumerate(playlist_labels, 1):
                pl_table.add_row(str(i), label)
            console.print(pl_table)
        else:
            console.print("[yellow]No playlists found in playlists.txt.[/yellow]")
    else:
        console.print("[red]playlists.txt not found![/red]")
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-read-private playlist-read-collaborative"
    ))
    # Call migration at startup
    migrate_playlists_file()
    while True:
        # Main menu as a panel
        menu_table = Table.grid(padding=1)
        menu_table.add_column(justify="right", style="bold yellow")
        menu_table.add_column(justify="left", style="white")
        menu_table.add_row("1.", "Add a playlist")
        menu_table.add_row("2.", "Check undownloaded songs")
        menu_table.add_row("3.", "Sync and download")
        menu_table.add_row("4.", "Exit")
        menu_panel = Panel(menu_table, title="[bold blue]Home Menu[/bold blue]", expand=False, border_style="blue")
        console.print(menu_panel)
        choice = Prompt.ask("[bold green]Choose an option (1-4)[/bold green]", choices=["1", "2", "3", "4"], default="4", console=console)
        if choice == '1':
            add_playlist_interactive()
        elif choice == '2':
            # Check for undownloaded songs
            _, links, _ = playlist_labels_and_links()
            if not links:
                console.print("[red]No playlists found! Please add playlists to playlists.txt in your output directory.[/red]")
                input("Press Enter to return to the menu.")
                continue
            from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
            all_missing = []  # List of (playlist_name, label, missing list)
            with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), transient=True, console=console) as progress:
                task = progress.add_task("[cyan]Checking playlists...", total=len(links))
                for label, ptype, link in links:
                    playlist_name, tracks = None, []

                    if ptype == 'spotify':
                        playlist_name, tracks = get_spotify_tracks(sp, link)
                    elif ptype == 'youtube':
                        playlist_name, tracks = get_youtube_playlist_tracks_sync(link)
                        if playlist_name:
                            playlist_name = sanitize_filename(playlist_name)
                        else:
                            playlist_name = sanitize_filename(label)

                    else:
                        console.print(f"[yellow]Skipping unsupported playlist type '{ptype}' for: {label}[/yellow]")
                        progress.advance(task)
                        continue
                        
                    if not playlist_name or not tracks:
                        console.print(f"[red]Could not fetch playlist or no tracks found for {label}.[/red]")
                        progress.advance(task)
                        continue
                    playlist_dir = os.path.join(OUTPUT_DIR, playlist_name)
                    os.makedirs(playlist_dir, exist_ok=True)
                    audio_exts = ['.mp3', '.m4a', '.opus', '.flac', '.wav', '.ogg', '.aac']
                    local_files = set()
                    for f in os.listdir(playlist_dir):
                        base, ext = os.path.splitext(f)
                        if ext.lower() in audio_exts:
                            local_files.add(base)
                    missing = []
                    for t in tracks:
                        fname = sanitize_filename(f"{t['artist']} - {t['name']}")
                        if fname not in local_files:
                            missing.append(f"{t['artist']} - {t['name']}")
                    downloaded = len(tracks) - len(missing)
                    # Playlist summary panel (improved)
                    summary = Table.grid(expand=True)
                    summary.add_row("")  # Spacer
                    name_table = Table.grid(expand=True)
                    name_table.add_column(justify="center")
                    name_table.add_row(Text(playlist_name, style="bold magenta", justify="center"))
                    summary.add_row(name_table)
                    summary.add_row("")  # Spacer
                    info_table = Table.grid(expand=True)
                    info_table.add_column(justify="right", ratio=1)
                    info_table.add_row(Text(f"Label: {label}", style="dim", justify="right"))
                    info_table.add_row(Text(f"Tracks: {len(tracks)}", style="dim", justify="right"))
                    info_table.add_row(Text(f"Downloaded: {downloaded}", style="dim", justify="right"))
                    info_table.add_row(Text(f"Missing: {len(missing)}", style="dim", justify="right"))
                    summary.add_row(info_table)
                    summary.add_row("")  # Spacer
                    console.print(Panel(summary, title="[bold magenta]Playlist Summary[/bold magenta]", expand=False))
                    # Missing songs table
                    if not missing:
                        console.print("[bold green]All songs are downloaded! You're all caught up! 🎶[/bold green]")
                    else:
                        console.print(f"[yellow]Missing {len(missing)} songs:[/yellow]")
                        song_table = Table(title="Missing Songs", box=box.MINIMAL_DOUBLE_HEAD)
                        song_table.add_column("#", style="dim", width=4)
                        song_table.add_column("Song", style="white")
                        for i, m in enumerate(missing, 1):
                            song_table.add_row(str(i), m)
                        console.print(song_table)
                        if len(missing) <= 5:
                            console.print("[bold cyan]Almost there! Only a few songs left to download.[/bold cyan]")
                        elif len(missing) > 20:
                            console.print("[bold]Keep going! Your collection is growing![/bold]")
                    all_missing.append((playlist_name, label, missing))
                    progress.advance(task)
            # Quick Download/Export/Back prompt
            options = {'d': 'Download all missing songs now', 'e': 'Export all missing lists', 'm': 'Main menu'}
            opt_str = ", ".join([f"[{k.upper()}]{v[1:]}" for k, v in options.items()])
            choice = Prompt.ask(f"\n[bold yellow]What would you like to do?[/bold yellow] {opt_str}", choices=list(options.keys()), default='m', console=console).lower()
            if choice == 'd':
                # Launch async_downloader.py for all playlists
                console.print("[green]Starting download of all missing songs...[/green]")
                args = [
                    sys.executable, 
                    'async_downloader.py',
                    '--search-workers', str(SEARCH_WORKERS),
                    '--download-workers', str(DOWNLOAD_WORKERS),
                    '--audio-format', AUDIO_FORMAT,
                    '--audio-quality', AUDIO_QUALITY,
                    '--download-delay', str(DOWNLOAD_DELAY),
                    '--output-dir', OUTPUT_DIR,
                    '--playlists-file', PLAYLISTS_FILE,
                    '--progress-file', PROGRESS_FILE,
                    '--spotify-client-id', SPOTIFY_CLIENT_ID,
                    '--spotify-client-secret', SPOTIFY_CLIENT_SECRET,
                    '--spotify-redirect-uri', SPOTIFY_REDIRECT_URI
                ]
                subprocess.run(args)
                console.print("[bold green]Download complete![/bold green]")
            elif choice == 'e':
                # Export missing songs for each playlist
                for playlist_name, label, missing in all_missing:
                    if missing:
                        fname = f"missing_{playlist_name}.txt"
                        with open(fname, 'w', encoding='utf-8') as f:
                            for song in missing:
                                f.write(song + '\n')
                        console.print(f"[cyan]Exported missing songs for [bold]{playlist_name}[/bold] to [bold]{fname}[/bold].[/cyan]")
                console.print("[green]Export complete![/green]")
            else:
                console.print("[cyan]Returning to main menu.[/cyan]")
        elif choice == '3':
            # Call async_downloader.py with all config as arguments
            print('Launching async_downloader.py for sync and download...')
            try:
                args = [
                    sys.executable, 'async_downloader.py',
                    '--search-workers', str(SEARCH_WORKERS),
                    '--download-workers', str(DOWNLOAD_WORKERS),
                    '--audio-format', AUDIO_FORMAT,
                    '--audio-quality', AUDIO_QUALITY,
                    '--download-delay', str(DOWNLOAD_DELAY),
                    '--output-dir', OUTPUT_DIR,
                    '--playlists-file', PLAYLISTS_FILE,
                    '--progress-file', PROGRESS_FILE,
                    '--spotify-client-id', SPOTIFY_CLIENT_ID,
                    '--spotify-client-secret', SPOTIFY_CLIENT_SECRET,
                    '--spotify-redirect-uri', SPOTIFY_REDIRECT_URI
                ]
                result = subprocess.run(args, check=True)
            except Exception as e:
                print(f'Failed to run async_downloader.py: {e}')
        elif choice == '4':
            console.print(f"[bold magenta]Goodbye, {name}! 👋[/bold magenta]")
            break
        else:
            console.print("[red]Invalid option. Please try again.[/red]")

if __name__ == "__main__":
    main()