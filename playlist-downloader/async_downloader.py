import os
import sys
import re
import json
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from concurrent.futures import ProcessPoolExecutor
import shutil
import aiofiles
import aiofiles.os
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
console = Console()

# === LOAD CONFIG ===
# Remove dotenv, config_json, and os.getenv loading
# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument('--search-workers', type=int, default=3)
parser.add_argument('--download-workers', type=int, default=3)
parser.add_argument('--audio-format', type=str, default='best')
parser.add_argument('--audio-quality', type=str, default='320K')
parser.add_argument('--download-delay', type=float, default=0)
parser.add_argument('--output-dir', type=str, required=True)
parser.add_argument('--playlists-file', type=str, required=True)
parser.add_argument('--progress-file', type=str, required=True)
parser.add_argument('--spotify-client-id', type=str, required=True)
parser.add_argument('--spotify-client-secret', type=str, required=True)
parser.add_argument('--spotify-redirect-uri', type=str, required=True)
parser.add_argument('--search-delay-min', type=float, default=0.5)
parser.add_argument('--search-delay-max', type=float, default=1.5)
args = parser.parse_args()

SEARCH_WORKERS = args.search_workers
DOWNLOAD_WORKERS = args.download_workers
AUDIO_FORMAT = args.audio_format
AUDIO_QUALITY = args.audio_quality
DOWNLOAD_DELAY = args.download_delay
OUTPUT_DIR = args.output_dir
PLAYLISTS_FILE = args.playlists_file
PROGRESS_FILE = args.progress_file
SPOTIFY_CLIENT_ID = args.spotify_client_id
SPOTIFY_CLIENT_SECRET = args.spotify_client_secret
SPOTIFY_REDIRECT_URI = args.spotify_redirect_uri
SEARCH_DELAY_MIN = args.search_delay_min
SEARCH_DELAY_MAX = args.search_delay_max

# === UTILS ===
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

async def load_playlists_async() -> List[Dict]:
    playlists = []
    if await aiofiles.os.path.exists(PLAYLISTS_FILE):
        async with aiofiles.open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
            async for line in f:
                line = line.strip()
                if not line:
                    continue
                label, ptype, link = None, None, None
                parts = line.split(':', 2)
                if len(parts) == 3:
                    label, ptype, link = parts
                elif len(parts) == 2:
                    label, link = parts
                    ptype = 'spotify' if 'spotify.com/playlist/' in link else 'youtube'
                else:
                    link = parts[0]
                    label = link
                    ptype = 'spotify' if 'spotify.com/playlist/' in link else 'youtube'
                playlists.append({"label": label, "type": ptype, "url": link})
    return playlists

async def get_youtube_playlist_videos(playlist_url: str) -> list:
    # Use yt-dlp to get all video metadata from a YouTube playlist
    import subprocess
    import json
    try:
        result = subprocess.run([
            "yt-dlp", "--flat-playlist", "-J", playlist_url
        ], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        entries = data.get('entries', [])
        videos = []
        for entry in entries:
            if entry and entry.get('id') and entry.get('title'):
                videos.append({
                    'title': entry['title'],
                    'uploader': entry.get('uploader', 'Unknown Uploader'),
                    'url': f"https://www.youtube.com/watch?v={entry['id']}"
                })
        return videos
    except Exception as e:
        print(f"Failed to fetch YouTube playlist videos: {e}")
        return []

def get_spotify_tracks(sp, playlist_url) -> (str, List[Dict]):
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
                        'search_query': f"{track['name']} {track['artists'][0]['name']}" if track['artists'] else track['name']
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

def already_downloaded_files(playlist_dir: str) -> set:
    if not os.path.exists(playlist_dir):
        return set()
    # Accept all common audio file extensions
    audio_exts = ['.mp3', '.m4a', '.opus', '.flac', '.wav', '.ogg', '.aac']
    return set(os.path.splitext(f)[0] for f in os.listdir(playlist_dir) if os.path.splitext(f)[1].lower() in audio_exts)

def simplify_search_query(title, artist):
    # Remove content in parentheses or brackets
    import re
    title = re.sub(r'\(.*?\)', '', title)
    title = re.sub(r'\[.*?\]', '', title)
    # Remove 'feat.' and 'remix' and content after dashes
    title = re.sub(r'(?i)feat\.?[^-–—]*', '', title)
    title = re.sub(r'(?i)remix[^-–—]*', '', title)
    title = title.split('-')[0]
    # Remove extra spaces
    title = ' '.join(title.split())
    artist = ' '.join(artist.split())
    return f"{title} {artist}".strip()

async def yt_dlp_search(query: str, retries=3) -> Optional[str]:
    for attempt in range(retries):
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                f"ytsearch1:{query}",
                "--get-id",
                "--skip-download",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                video_id = stdout.decode().strip()
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"
            await asyncio.sleep(SEARCH_DELAY_MIN + (SEARCH_DELAY_MAX - SEARCH_DELAY_MIN) * 0.5)
        except Exception as e:
            print(f"yt-dlp search failed for '{query}' (attempt {attempt+1}): {e}")
            await asyncio.sleep(2)
    return None

async def yt_dlp_download(url: str, output_template: str, retries=3) -> bool:
    for attempt in range(retries):
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--extract-audio",
                "--audio-format", AUDIO_FORMAT,
                "--audio-quality", AUDIO_QUALITY,
                "--format", "bestaudio",
                "--output", output_template,
                "--no-playlist",
                "--embed-metadata",
                "--add-metadata",
                "--no-mtime",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                return True
            await asyncio.sleep(2)
        except Exception as e:
            print(f"yt-dlp download failed for '{url}' (attempt {attempt+1}): {e}")
            await asyncio.sleep(2)
    return False

async def main():
    console.clear()
    console.rule("[bold magenta]🎵 Playlist Async Downloader[/bold magenta]", style="magenta")
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    playlists = await load_playlists_async()
    if not playlists:
        console.print(f"[red]No playlists found in {PLAYLISTS_FILE}[/red]")
        return
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-read-private playlist-read-collaborative"
    ))
    jobs = []
    total_tracks = 0
    already_downloaded = 0
    for pl in playlists:
        if pl['type'] == 'spotify':
            playlist_name, tracks = get_spotify_tracks(sp, pl['url'])
            if not playlist_name or not tracks:
                console.print(f"[red]Could not fetch playlist: {pl['label']}[/red]")
                continue
            playlist_dir = os.path.join(OUTPUT_DIR, playlist_name)
            os.makedirs(playlist_dir, exist_ok=True)
            local_files = already_downloaded_files(playlist_dir)
            for t in tracks:
                total_tracks += 1
                fname = sanitize_filename(f"{t['artist']} - {t['name']}")
                if fname in local_files:
                    already_downloaded += 1
                else:
                    search_query = simplify_search_query(t['name'], t['artist'])
                    t['search_query'] = search_query
                    jobs.append({
                        "track": t,
                        "playlist": pl['label'],
                        "playlist_dir": playlist_dir,
                        "filename": fname
                    })
        elif pl['type'] == 'youtube':
            # Fetch all video metadata from the YouTube playlist
            video_infos = await get_youtube_playlist_videos(pl['url'])
            if not video_infos:
                console.print(f"[red]Could not fetch YouTube playlist: {pl['label']}[/red]")
                continue
            # Fetch playlist name from yt-dlp metadata
            playlist_name = None
            if video_infos and isinstance(video_infos, list) and hasattr(video_infos[0], 'get'):
                # Defensive: check if video_infos contains playlist_name, fallback to label
                playlist_name = video_infos[0].get('playlist_name')
            if not playlist_name:
                # Try to fetch playlist name via yt-dlp again (slower but accurate)
                try:
                    import subprocess, json
                    result = subprocess.run([
                        "yt-dlp", "-J", "--flat-playlist", pl['url']
                    ], capture_output=True, text=True, check=True)
                    data = json.loads(result.stdout)
                    playlist_name = data.get('title')
                except Exception:
                    playlist_name = pl['label']
            playlist_name = sanitize_filename(playlist_name)
            playlist_dir = os.path.join(OUTPUT_DIR, playlist_name)
            os.makedirs(playlist_dir, exist_ok=True)
            local_files = already_downloaded_files(playlist_dir)
            total_tracks += len(video_infos)
            for video in video_infos:
                # Use Uploader - Title for filename, same as spotify flow
                fname = sanitize_filename(f"{video['uploader']} - {video['title']}")
                if fname in local_files:
                    already_downloaded += 1
                else:
                    jobs.append({
                        "track": {"name": video['title'], "artist": video['uploader'], "search_query": None},
                        "playlist": pl['label'],
                        "playlist_dir": playlist_dir,
                        "filename": fname,
                        "youtube_url": video['url'] # Pass direct URL
                    })

    # Beautified summary before download
    summary_table = Table(title="[bold cyan]Download Summary[/bold cyan]", box=box.SIMPLE)
    summary_table.add_column("[bold]Metric[/bold]", style="yellow")
    summary_table.add_column("[bold]Value[/bold]", style="white")
    summary_table.add_row("Total tracks", str(total_tracks))
    summary_table.add_row("Already downloaded", f"[green]{already_downloaded}[/green]")
    summary_table.add_row("Need to download", f"[magenta]{len(jobs)}[/magenta]")
    console.print(summary_table)
    if not jobs:
        console.print("[bold green]All tracks are already downloaded![/bold green]")
        return
    # === Async Search & Download Pipeline ===
    console.print("\n[bold blue]Searching YouTube for missing tracks and downloading as soon as links are found...[/bold blue]")
    search_queue = asyncio.Queue()
    download_queue = asyncio.Queue()
    sem = asyncio.Semaphore(SEARCH_WORKERS)
    sem_dl = asyncio.Semaphore(DOWNLOAD_WORKERS)
    search_results = []
    download_results = []
    failed_searches = []
    # Add a single green progress bar for downloads
    bar = tqdm(total=len(jobs), desc="Downloaded", unit="track", colour="green")
    async def search_worker():
        while True:
            job = await search_queue.get()
            if job is None:
                search_queue.task_done()
                break
            async with sem:
                url = await yt_dlp_search(job['track']['search_query'])
                result = {**job, "youtube_url": url}
                search_results.append(result)
                if url:
                    await download_queue.put(result)
                else:
                    failed_searches.append(result)
            search_queue.task_done()
    async def download_worker():
        while True:
            job = await download_queue.get()
            if job is None:
                download_queue.task_done()
                break
            async with sem_dl:
                output_template = os.path.join(job['playlist_dir'], f"{job['filename']}.%(ext)s")
                # For YouTube jobs, 'youtube_url' is already present.
                # For Spotify jobs, 'youtube_url' is added by the search worker.
                url = job.get('youtube_url')
                if not url:
                    # This can happen if a search fails for a Spotify track
                    download_results.append({**job, "downloaded": False, "output_template": "No URL found"})
                    bar.update(1)
                    download_queue.task_done()
                    continue

                success = await yt_dlp_download(url, output_template)
                download_results.append({**job, "downloaded": success, "output_template": output_template})
                bar.update(1)
            download_queue.task_done()

    # Start workers
    num_search_workers = SEARCH_WORKERS
    num_download_workers = DOWNLOAD_WORKERS
    search_tasks = [asyncio.create_task(search_worker()) for _ in range(num_search_workers)]
    download_tasks = [asyncio.create_task(download_worker()) for _ in range(num_download_workers)]
    # Feed jobs: For YouTube playlist jobs (with 'youtube_url'), skip search and go straight to download queue
    for job in jobs:
        if job.get('youtube_url'):
            await download_queue.put(job)
        else:
            await search_queue.put(job)
    # As soon as 7 links are found, start downloads (already handled by pipeline)
    # Signal end of queue
    for _ in range(num_search_workers):
        await search_queue.put(None)
    await search_queue.join()
    for _ in range(num_download_workers):
        await download_queue.put(None)
    await download_queue.join()
    # Wait for all workers to finish
    await asyncio.gather(*search_tasks)
    await asyncio.gather(*download_tasks)
    bar.close()
    # === Summary ===
    console.rule("[bold magenta]Summary[/bold magenta]", style="magenta")
    result_table = Table(box=box.SIMPLE)
    result_table.add_column("Status", style="bold")
    result_table.add_column("Count", style="white")
    result_table.add_row("[green]✓ Already had[/green]", str(already_downloaded))
    result_table.add_row("[green]✓ Successfully downloaded[/green]", str(sum(1 for r in download_results if r.get('downloaded'))))
    result_table.add_row("[red]✗ Failed to download[/red]", str(sum(1 for r in download_results if not r.get('downloaded'))))
    result_table.add_row("[yellow]✗ Failed to find YouTube link[/yellow]", str(len(failed_searches)))
    console.print(result_table)
    if failed_searches:
        console.print("\n[bold red]❌ Failed to find YouTube for:[/bold red]")
        fail_table = Table(box=box.MINIMAL)
        fail_table.add_column("Song", style="white")
        for r in failed_searches[-10:]:
            t = r['track']
            fail_table.add_row(f"{t['name']} by {t['artist']}")
        console.print(fail_table)
    console.print("[bold green]Download complete![/bold green]")

if __name__ == "__main__":
    asyncio.run(main()) 