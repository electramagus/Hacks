"""
Async Playlist Downloader
==========================
High-performance concurrent downloader for Spotify and YouTube playlists.

This module orchestrates the entire download process:
- Fetches playlists from Spotify/YouTube
- Searches YouTube for missing tracks
- Downloads audio files concurrently
- Provides real-time progress reporting

Performance optimizations:
- Async I/O for network operations
- Concurrent workers for search and download
- Efficient queueing system
- Smart retry logic with exponential backoff
"""

import os
import sys
import asyncio
import argparse
import logging
from typing import List, Dict
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from tqdm import tqdm

# Import our refactored modules
from modules.config_manager import ConfigManager, AppConfig
from modules.playlist_manager import PlaylistManager, SpotifyPlaylistFetcher, YouTubePlaylistFetcher
from modules.download_manager import (
    DownloadManager,
    YouTubeSearcher,
    YouTubeDownloader,
    DownloadJob,
    DownloadStatus
)
from modules.utils import setup_logging, get_downloaded_files, ensure_directory

# Initialize Rich console for beautiful output
console = Console()


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description='Async Playlist Downloader - Download Spotify and YouTube playlists',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Worker configuration
    parser.add_argument('--search-workers', type=int, default=3,
                        help='Number of concurrent search workers')
    parser.add_argument('--download-workers', type=int, default=3,
                        help='Number of concurrent download workers')
    
    # Audio configuration
    parser.add_argument('--audio-format', type=str, default='best',
                        help='Audio format (mp3, m4a, best, etc.)')
    parser.add_argument('--audio-quality', type=str, default='320K',
                        help='Audio bitrate (128K, 192K, 256K, 320K)')
    parser.add_argument('--download-delay', type=float, default=0,
                        help='Delay between downloads in seconds')
    
    # Path configuration
    parser.add_argument('--output-dir', type=str, required=True,
                        help='Output directory for downloads')
    parser.add_argument('--playlists-file', type=str, required=True,
                        help='Path to playlists file')
    parser.add_argument('--progress-file', type=str, required=True,
                        help='Path to progress tracking file')
    
    # Spotify API configuration
    parser.add_argument('--spotify-client-id', type=str, required=True,
                        help='Spotify API client ID')
    parser.add_argument('--spotify-client-secret', type=str, required=True,
                        help='Spotify API client secret')
    parser.add_argument('--spotify-redirect-uri', type=str, required=True,
                        help='Spotify OAuth redirect URI')
    
    # Search configuration
    parser.add_argument('--search-delay-min', type=float, default=0.5,
                        help='Minimum delay between searches')
    parser.add_argument('--search-delay-max', type=float, default=1.5,
                        help='Maximum delay between searches')
    
    # YouTube cookies (optional)
    parser.add_argument('--youtube-cookies', type=str, default=None,
                        help='Path to YouTube cookies file for authenticated access')
    
    return parser.parse_args()


async def main():
    """
    Main async function that orchestrates the entire download process.
    
    Steps:
    1. Parse arguments and initialize configuration
    2. Load playlists from file
    3. Fetch playlist metadata from Spotify/YouTube
    4. Identify missing tracks
    5. Search and download missing tracks concurrently
    6. Display results summary
    """
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set up logging
    logger = setup_logging()
    logger.info("Starting Async Playlist Downloader")
    
    # Display header
    console.clear()
    console.rule("[bold magenta]🎵 Playlist Async Downloader[/bold magenta]", style="magenta")
    
    # Ensure output directory exists
    ensure_directory(args.output_dir)
    
    # Initialize playlist manager
    try:
        spotify_fetcher = SpotifyPlaylistFetcher(
            client_id=args.spotify_client_id,
            client_secret=args.spotify_client_secret,
            redirect_uri=args.spotify_redirect_uri
        )
        youtube_fetcher = YouTubePlaylistFetcher()
        playlist_manager = PlaylistManager(spotify_fetcher, youtube_fetcher)
        
    except Exception as e:
        console.print(f"[red]Failed to initialize playlist fetchers: {e}[/red]")
        logger.error(f"Initialization failed: {e}")
        return 1
    
    # Load playlist references from file
    playlist_refs = playlist_manager.load_playlist_file(args.playlists_file)
    
    if not playlist_refs:
        console.print(f"[red]No playlists found in {args.playlists_file}[/red]")
        logger.warning("No playlists to process")
        return 1
    
    console.print(f"[cyan]Found {len(playlist_refs)} playlist(s) to process[/cyan]\n")
    
    # Fetch all playlists
    console.print("[blue]Fetching playlist metadata...[/blue]")
    playlists = await playlist_manager.fetch_playlists_async(playlist_refs)
    
    if not playlists:
        console.print("[red]Failed to fetch any playlists[/red]")
        return 1
    
    # Build download jobs
    jobs: List[DownloadJob] = []
    total_tracks = 0
    already_downloaded = 0
    
    for playlist in playlists:
        total_tracks += len(playlist)
        
        # Create directory for playlist
        playlist_dir = os.path.join(args.output_dir, playlist.sanitized_name)
        ensure_directory(playlist_dir)
        
        # Get already downloaded files
        local_files = get_downloaded_files(playlist_dir)
        
        # Create jobs for missing tracks
        for track in playlist.tracks:
            if track.filename in local_files:
                already_downloaded += 1
            else:
                job = DownloadJob(
                    track_name=track.name,
                    artist=track.artist,
                    filename=track.filename,
                    output_dir=playlist_dir,
                    youtube_url=track.url  # Will be None for Spotify tracks
                )
                jobs.append(job)
    
    # Display summary before download
    summary_table = Table(title="[bold cyan]Download Summary[/bold cyan]", box=box.SIMPLE)
    summary_table.add_column("[bold]Metric[/bold]", style="yellow")
    summary_table.add_column("[bold]Value[/bold]", style="white")
    summary_table.add_row("Total tracks", str(total_tracks))
    summary_table.add_row("Already downloaded", f"[green]{already_downloaded}[/green]")
    summary_table.add_row("Need to download", f"[magenta]{len(jobs)}[/magenta]")
    console.print(summary_table)
    
    if not jobs:
        console.print("[bold green]✓ All tracks are already downloaded![/bold green]")
        logger.info("All tracks already downloaded")
        return 0
    
    # Get cookies file if provided
    cookies_file = args.youtube_cookies if args.youtube_cookies and os.path.exists(args.youtube_cookies) else None
    
    if cookies_file:
        console.print(f"[cyan]✓ Using YouTube cookies from: {cookies_file}[/cyan]")
    else:
        console.print("[yellow]⚠ No YouTube cookies - age-restricted videos may fail[/yellow]")
    
    # Initialize download manager
    searcher = YouTubeSearcher(
        delay_min=args.search_delay_min,
        delay_max=args.search_delay_max,
        max_retries=3,
        cookies_file=cookies_file
    )
    
    downloader = YouTubeDownloader(
        audio_format=args.audio_format,
        audio_quality=args.audio_quality,
        max_retries=3,
        cookies_file=cookies_file
    )
    
    # Progress tracking with tqdm
    progress_bar = tqdm(
        total=len(jobs),
        desc="Downloading",
        unit="track",
        colour="green"
    )
    
    def progress_callback(status: str, completed: int, total: int):
        """Update progress bar."""
        progress_bar.n = completed
        progress_bar.refresh()
    
    download_manager = DownloadManager(
        searcher=searcher,
        downloader=downloader,
        search_workers=args.search_workers,
        download_workers=args.download_workers,
        progress_callback=progress_callback
    )
    
    # Process all download jobs
    console.print("\n[bold blue]Searching and downloading tracks...[/bold blue]")
    results = await download_manager.process_jobs(jobs)
    
    progress_bar.close()
    
    # Display results summary
    console.rule("[bold magenta]Summary[/bold magenta]", style="magenta")
    
    result_table = Table(box=box.SIMPLE)
    result_table.add_column("Status", style="bold")
    result_table.add_column("Count", style="white")
    result_table.add_row(
        "[green]✓ Already had[/green]",
        str(already_downloaded)
    )
    result_table.add_row(
        "[green]✓ Successfully downloaded[/green]",
        str(len(results['completed']))
    )
    result_table.add_row(
        "[red]✗ Failed to download[/red]",
        str(len(results['failed']))
    )
    result_table.add_row(
        "[yellow]✗ Failed to find on YouTube[/yellow]",
        str(len(results['searches_failed']))
    )
    console.print(result_table)
    
    # Display failed searches if any
    if results['searches_failed']:
        console.print("\n[bold red]❌ Failed to find on YouTube:[/bold red]")
        fail_table = Table(box=box.MINIMAL)
        fail_table.add_column("Song", style="white")
        
        # Show up to 10 failures
        for result in results['searches_failed'][:10]:
            fail_table.add_row(f"{result.job.track_name} by {result.job.artist}")
        
        if len(results['searches_failed']) > 10:
            fail_table.add_row(f"[dim]... and {len(results['searches_failed']) - 10} more[/dim]")
        
        console.print(fail_table)
    
    # Log final statistics
    logger.info(f"Download complete: {len(results['completed'])} succeeded, "
                f"{len(results['failed']) + len(results['searches_failed'])} failed")
    
    console.print("[bold green]✓ Download complete![/bold green]")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]Download interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Fatal error: {e}[/red]")
        logging.exception("Fatal error in main")
        sys.exit(1)
 
