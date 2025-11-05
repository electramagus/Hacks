"""
Playlist Operations Module
===========================
Handles fetching and managing playlists from Spotify and YouTube.
Provides unified interface for different playlist sources.
"""

import asyncio
import json
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from modules.utils import sanitize_filename, extract_playlist_id


@dataclass
class Track:
    """Represents a single track from a playlist."""
    name: str
    artist: str
    album: str = "Unknown Album"
    duration_ms: int = 0
    url: Optional[str] = None  # Direct URL for YouTube tracks
    
    @property
    def search_query(self) -> str:
        """Generate search query for YouTube."""
        return f"{self.name} {self.artist}"
    
    @property
    def filename(self) -> str:
        """Generate sanitized filename."""
        return sanitize_filename(f"{self.artist} - {self.name}")


@dataclass
class Playlist:
    """Represents a playlist with metadata and tracks."""
    name: str
    label: str
    playlist_type: str  # 'spotify' or 'youtube'
    url: str
    tracks: List[Track]
    
    @property
    def sanitized_name(self) -> str:
        """Get sanitized playlist name for directory creation."""
        return sanitize_filename(self.name)
    
    def __len__(self) -> int:
        """Return number of tracks in playlist."""
        return len(self.tracks)


class PlaylistFetcher(ABC):
    """Abstract base class for playlist fetchers."""
    
    @abstractmethod
    def fetch_playlist(self, url: str, label: str) -> Optional[Playlist]:
        """
        Fetch playlist from source.
        
        Args:
            url: Playlist URL
            label: User-defined label for playlist
            
        Returns:
            Playlist object or None if fetch fails
        """
        pass


class SpotifyPlaylistFetcher(PlaylistFetcher):
    """Fetches playlists from Spotify using the Spotify API."""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """
        Initialize Spotify fetcher.
        
        Args:
            client_id: Spotify API client ID
            client_secret: Spotify API client secret
            redirect_uri: OAuth redirect URI
        """
        self.logger = logging.getLogger(__name__)
        
        try:
            auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope="playlist-read-private playlist-read-collaborative"
            )
            self.sp = spotipy.Spotify(auth_manager=auth_manager)
        except Exception as e:
            self.logger.error(f"Failed to initialize Spotify client: {e}")
            raise
    
    def fetch_playlist(self, url: str, label: str) -> Optional[Playlist]:
        """
        Fetch Spotify playlist.
        
        Args:
            url: Spotify playlist URL
            label: User label for playlist
            
        Returns:
            Playlist object or None if fetch fails
        """
        try:
            playlist_id = extract_playlist_id(url)
            
            # Fetch playlist metadata
            playlist_info = self.sp.playlist(playlist_id)
            playlist_name = playlist_info['name']
            
            self.logger.info(f"Fetching Spotify playlist: {playlist_name}")
            
            # Fetch all tracks with pagination
            tracks = []
            results = self.sp.playlist_tracks(playlist_id)
            
            while results:
                for item in results['items']:
                    if item['track'] and item['track']['name']:
                        track_data = item['track']
                        track = Track(
                            name=track_data['name'],
                            artist=track_data['artists'][0]['name'] if track_data['artists'] else 'Unknown Artist',
                            album=track_data['album']['name'] if track_data['album'] else 'Unknown Album',
                            duration_ms=track_data.get('duration_ms', 0)
                        )
                        tracks.append(track)
                
                # Handle pagination
                if results['next']:
                    results = self.sp.next(results)
                else:
                    break
            
            self.logger.info(f"Fetched {len(tracks)} tracks from {playlist_name}")
            
            return Playlist(
                name=playlist_name,
                label=label,
                playlist_type='spotify',
                url=url,
                tracks=tracks
            )
            
        except Exception as e:
            self.logger.error(f"Failed to fetch Spotify playlist: {e}")
            return None


class YouTubePlaylistFetcher(PlaylistFetcher):
    """Fetches playlists from YouTube using yt-dlp."""
    
    def __init__(self):
        """Initialize YouTube fetcher."""
        self.logger = logging.getLogger(__name__)
    
    async def fetch_playlist_async(self, url: str, label: str) -> Optional[Playlist]:
        """
        Fetch YouTube playlist asynchronously.
        
        Args:
            url: YouTube playlist URL
            label: User label for playlist
            
        Returns:
            Playlist object or None if fetch fails
        """
        try:
            # Run yt-dlp to get playlist metadata
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                "--flat-playlist",
                "-J",
                url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                self.logger.error(f"yt-dlp error: {stderr.decode()}")
                return None
            
            data = json.loads(stdout.decode())
            playlist_name = data.get('title', label)
            entries = data.get('entries', [])
            
            self.logger.info(f"Fetching YouTube playlist: {playlist_name}")
            
            # Convert entries to Track objects
            tracks = []
            for entry in entries:
                if entry and entry.get('id') and entry.get('title'):
                    track = Track(
                        name=entry['title'],
                        artist=entry.get('uploader', 'Unknown Uploader'),
                        album='YouTube',
                        duration_ms=entry.get('duration', 0) * 1000,  # Convert to ms
                        url=f"https://www.youtube.com/watch?v={entry['id']}"
                    )
                    tracks.append(track)
            
            self.logger.info(f"Fetched {len(tracks)} tracks from {playlist_name}")
            
            return Playlist(
                name=playlist_name,
                label=label,
                playlist_type='youtube',
                url=url,
                tracks=tracks
            )
            
        except Exception as e:
            self.logger.error(f"Failed to fetch YouTube playlist: {e}")
            return None
    
    def fetch_playlist(self, url: str, label: str) -> Optional[Playlist]:
        """
        Synchronous wrapper for fetch_playlist_async.
        
        Args:
            url: YouTube playlist URL
            label: User label for playlist
            
        Returns:
            Playlist object or None if fetch fails
        """
        return asyncio.run(self.fetch_playlist_async(url, label))


class PlaylistManager:
    """
    Manages playlist operations including loading from file and fetching.
    """
    
    def __init__(self, spotify_fetcher: SpotifyPlaylistFetcher, youtube_fetcher: YouTubePlaylistFetcher):
        """
        Initialize playlist manager.
        
        Args:
            spotify_fetcher: SpotifyPlaylistFetcher instance
            youtube_fetcher: YouTubePlaylistFetcher instance
        """
        self.spotify_fetcher = spotify_fetcher
        self.youtube_fetcher = youtube_fetcher
        self.logger = logging.getLogger(__name__)
    
    def load_playlist_file(self, filepath: str) -> List[Tuple[str, str, str]]:
        """
        Load playlists from text file.
        
        Expected format: label:type:url (one per line)
        Also supports legacy formats for backward compatibility.
        
        Args:
            filepath: Path to playlists file
            
        Returns:
            List of tuples: (label, type, url)
        """
        playlists = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split(':', 2)
                    
                    # Parse format: label:type:url
                    if len(parts) == 3 and parts[1] in ('spotify', 'youtube'):
                        label, ptype, url = parts
                        playlists.append((label.strip(), ptype.strip(), url.strip()))
                    
                    # Legacy format: label:url or just url
                    else:
                        if ':' in line:
                            label, url = line.split(':', 1)
                            label = label.strip()
                            url = url.strip()
                        else:
                            url = line.strip()
                            label = url
                        
                        # Auto-detect type
                        if 'spotify.com/playlist/' in url:
                            ptype = 'spotify'
                        elif 'youtube.com/playlist' in url or 'youtu.be' in url:
                            ptype = 'youtube'
                        else:
                            self.logger.warning(f"Line {line_num}: Cannot determine playlist type, skipping")
                            continue
                        
                        playlists.append((label, ptype, url))
            
            self.logger.info(f"Loaded {len(playlists)} playlists from {filepath}")
            
        except FileNotFoundError:
            self.logger.warning(f"Playlist file not found: {filepath}")
        except IOError as e:
            self.logger.error(f"Error reading playlist file: {e}")
        
        return playlists
    
    async def fetch_playlists_async(self, playlist_refs: List[Tuple[str, str, str]]) -> List[Playlist]:
        """
        Fetch multiple playlists asynchronously.
        
        Args:
            playlist_refs: List of (label, type, url) tuples
            
        Returns:
            List of fetched Playlist objects
        """
        playlists = []
        
        for label, ptype, url in playlist_refs:
            try:
                if ptype == 'spotify':
                    # Spotify API is synchronous, run in executor
                    loop = asyncio.get_event_loop()
                    playlist = await loop.run_in_executor(
                        None,
                        self.spotify_fetcher.fetch_playlist,
                        url,
                        label
                    )
                elif ptype == 'youtube':
                    playlist = await self.youtube_fetcher.fetch_playlist_async(url, label)
                else:
                    self.logger.warning(f"Unknown playlist type: {ptype}")
                    continue
                
                if playlist:
                    playlists.append(playlist)
                    
            except Exception as e:
                self.logger.error(f"Failed to fetch playlist {label}: {e}")
        
        return playlists
    
    def fetch_playlists(self, playlist_refs: List[Tuple[str, str, str]]) -> List[Playlist]:
        """
        Synchronous wrapper for fetch_playlists_async.
        
        Args:
            playlist_refs: List of (label, type, url) tuples
            
        Returns:
            List of fetched Playlist objects
        """
        return asyncio.run(self.fetch_playlists_async(playlist_refs))
