"""
Download Manager Module
=======================
Handles YouTube search and download operations with retry logic,
rate limiting, and concurrent execution.
"""

import asyncio
import logging
import os
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass
from enum import Enum

from modules.utils import simplify_search_query


class DownloadStatus(Enum):
    """Download status enumeration."""
    PENDING = "pending"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DownloadJob:
    """Represents a single download job."""
    track_name: str
    artist: str
    filename: str
    output_dir: str
    search_query: Optional[str] = None
    youtube_url: Optional[str] = None
    status: DownloadStatus = DownloadStatus.PENDING
    error_message: Optional[str] = None
    retries: int = 0
    
    def __post_init__(self):
        """Initialize search query if not provided."""
        if not self.search_query:
            self.search_query = simplify_search_query(self.track_name, self.artist)


@dataclass
class DownloadResult:
    """Result of a download operation."""
    job: DownloadJob
    success: bool
    output_path: Optional[str] = None
    error: Optional[str] = None


class YouTubeSearcher:
    """Handles YouTube search operations with rate limiting."""
    
    def __init__(
        self,
        delay_min: float = 0.5,
        delay_max: float = 1.5,
        max_retries: int = 3,
        cookies_file: Optional[str] = None
    ):
        """
        Initialize YouTube searcher.
        
        Args:
            delay_min: Minimum delay between searches (seconds)
            delay_max: Maximum delay between searches (seconds)
            max_retries: Maximum number of retry attempts
            cookies_file: Path to cookies file for authenticated access
        """
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.cookies_file = cookies_file
        self.logger = logging.getLogger(__name__)
    
    async def search(self, query: str) -> Optional[str]:
        """
        Search for video on YouTube using yt-dlp.
        
        Args:
            query: Search query string
            
        Returns:
            YouTube video URL or None if not found
        """
        for attempt in range(self.max_retries):
            try:
                cmd = [
                    "yt-dlp",
                    f"ytsearch1:{query}",
                    "--get-id",
                    "--skip-download",
                    "--no-warnings",
                    # Add user agent to appear more like a browser
                    "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                ]
                
                # Add cookies if available
                if self.cookies_file and os.path.exists(self.cookies_file):
                    cmd.extend(["--cookies", self.cookies_file])
                
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await proc.communicate()
                
                if proc.returncode == 0:
                    video_id = stdout.decode().strip()
                    if video_id:
                        self.logger.debug(f"Found video for '{query}': {video_id}")
                        # Add random delay to avoid rate limiting
                        import random
                        delay = random.uniform(self.delay_min, self.delay_max)
                        await asyncio.sleep(delay)
                        return f"https://www.youtube.com/watch?v={video_id}"
                
                # Rate limiting delay with randomization
                import random
                delay = random.uniform(self.delay_min, self.delay_max)
                await asyncio.sleep(delay)
                
            except Exception as e:
                self.logger.warning(f"Search attempt {attempt + 1} failed for '{query}': {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        self.logger.error(f"Failed to find video after {self.max_retries} attempts: {query}")
        return None


class YouTubeDownloader:
    """Handles YouTube download operations with retry logic."""
    
    def __init__(
        self,
        audio_format: str = "best",
        audio_quality: str = "320K",
        max_retries: int = 3,
        cookies_file: Optional[str] = None
    ):
        """
        Initialize YouTube downloader.
        
        Args:
            audio_format: Audio format (mp3, m4a, best, etc.)
            audio_quality: Audio quality (128K, 192K, 256K, 320K)
            max_retries: Maximum number of retry attempts
            cookies_file: Path to cookies file for authenticated access
        """
        self.audio_format = audio_format
        self.audio_quality = audio_quality
        self.max_retries = max_retries
        self.cookies_file = cookies_file
        self.logger = logging.getLogger(__name__)
    
    async def download(self, url: str, output_template: str) -> bool:
        """
        Download audio from YouTube URL.
        
        Args:
            url: YouTube video URL
            output_template: Output file path template (including %(ext)s)
            
        Returns:
            True if download successful, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                cmd = [
                    "yt-dlp",
                    "--extract-audio",
                    "--audio-format", self.audio_format,
                    "--audio-quality", self.audio_quality,
                    "--format", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
                    "--output", output_template,
                    "--no-playlist",
                    "--embed-metadata",
                    "--add-metadata",
                    "--no-mtime",
                    "--no-warnings",
                    "--quiet",
                    "--retries", "10",
                    "--fragment-retries", "10",
                    "--geo-bypass",
                    "--age-limit", "21",
                ]
                
                # Add cookies if available
                if self.cookies_file and os.path.exists(self.cookies_file):
                    cmd.extend(["--cookies", self.cookies_file])
                
                cmd.append(url)
                
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await proc.communicate()
                
                if proc.returncode == 0:
                    self.logger.debug(f"Successfully downloaded: {url}")
                    return True
                else:
                    self.logger.warning(f"Download attempt {attempt + 1} failed: {stderr.decode()}")
                
                # Exponential backoff
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                self.logger.warning(f"Download attempt {attempt + 1} exception: {e}")
                await asyncio.sleep(2 ** attempt)
        
        self.logger.error(f"Failed to download after {self.max_retries} attempts: {url}")
        return False


class DownloadManager:
    """
    Manages concurrent download operations with search and download workers.
    """
    
    def __init__(
        self,
        searcher: YouTubeSearcher,
        downloader: YouTubeDownloader,
        search_workers: int = 3,
        download_workers: int = 3,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ):
        """
        Initialize download manager.
        
        Args:
            searcher: YouTubeSearcher instance
            downloader: YouTubeDownloader instance
            search_workers: Number of concurrent search workers
            download_workers: Number of concurrent download workers
            progress_callback: Optional callback for progress updates (status, completed, total)
        """
        self.searcher = searcher
        self.downloader = downloader
        self.search_workers = search_workers
        self.download_workers = download_workers
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)
        
        # Queues for work distribution
        self.search_queue: asyncio.Queue = asyncio.Queue()
        self.download_queue: asyncio.Queue = asyncio.Queue()
        
        # Results storage
        self.results: List[DownloadResult] = []
        self.failed_searches: List[DownloadJob] = []
    
    async def _search_worker(self):
        """Worker coroutine for searching YouTube."""
        while True:
            job = await self.search_queue.get()
            
            if job is None:  # Sentinel value to stop worker
                self.search_queue.task_done()
                break
            
            try:
                job.status = DownloadStatus.SEARCHING
                url = await self.searcher.search(job.search_query)
                
                if url:
                    job.youtube_url = url
                    await self.download_queue.put(job)
                else:
                    job.status = DownloadStatus.FAILED
                    job.error_message = "YouTube video not found"
                    self.failed_searches.append(job)
                    
            except Exception as e:
                self.logger.error(f"Search worker exception for {job.track_name}: {e}")
                job.status = DownloadStatus.FAILED
                job.error_message = str(e)
                self.failed_searches.append(job)
            
            finally:
                self.search_queue.task_done()
    
    async def _download_worker(self):
        """Worker coroutine for downloading from YouTube."""
        while True:
            job = await self.download_queue.get()
            
            if job is None:  # Sentinel value to stop worker
                self.download_queue.task_done()
                break
            
            try:
                job.status = DownloadStatus.DOWNLOADING
                
                if not job.youtube_url:
                    raise ValueError("No YouTube URL provided for download")
                
                import os
                output_template = os.path.join(job.output_dir, f"{job.filename}.%(ext)s")
                success = await self.downloader.download(job.youtube_url, output_template)
                
                if success:
                    job.status = DownloadStatus.COMPLETED
                    result = DownloadResult(job=job, success=True, output_path=output_template)
                else:
                    job.status = DownloadStatus.FAILED
                    job.error_message = "Download failed after retries"
                    result = DownloadResult(job=job, success=False, error="Download failed")
                
                self.results.append(result)
                
                # Update progress
                if self.progress_callback:
                    completed = sum(1 for r in self.results if r.success)
                    total = len(self.results) + self.search_queue.qsize() + self.download_queue.qsize()
                    self.progress_callback("downloaded", completed, total)
                    
            except Exception as e:
                self.logger.error(f"Download worker exception for {job.track_name}: {e}")
                job.status = DownloadStatus.FAILED
                job.error_message = str(e)
                result = DownloadResult(job=job, success=False, error=str(e))
                self.results.append(result)
            
            finally:
                self.download_queue.task_done()
    
    async def process_jobs(self, jobs: List[DownloadJob]) -> Dict[str, List[DownloadResult]]:
        """
        Process all download jobs concurrently.
        
        Args:
            jobs: List of DownloadJob objects to process
            
        Returns:
            Dictionary with 'completed', 'failed', and 'searches_failed' lists
        """
        self.results = []
        self.failed_searches = []
        
        # Start workers
        search_tasks = [
            asyncio.create_task(self._search_worker())
            for _ in range(self.search_workers)
        ]
        
        download_tasks = [
            asyncio.create_task(self._download_worker())
            for _ in range(self.download_workers)
        ]
        
        # Queue jobs
        for job in jobs:
            # Jobs with direct YouTube URLs skip search
            if job.youtube_url:
                await self.download_queue.put(job)
            else:
                await self.search_queue.put(job)
        
        # Send sentinel values to stop workers
        for _ in range(self.search_workers):
            await self.search_queue.put(None)
        
        # Wait for all searches to complete
        await self.search_queue.join()
        
        # Send sentinel values to download workers
        for _ in range(self.download_workers):
            await self.download_queue.put(None)
        
        # Wait for all downloads to complete
        await self.download_queue.join()
        
        # Wait for all workers to finish
        await asyncio.gather(*search_tasks, *download_tasks)
        
        # Organize results
        completed = [r for r in self.results if r.success]
        failed_downloads = [r for r in self.results if not r.success]
        
        return {
            'completed': completed,
            'failed': failed_downloads,
            'searches_failed': [
                DownloadResult(job=job, success=False, error=job.error_message)
                for job in self.failed_searches
            ]
        }
