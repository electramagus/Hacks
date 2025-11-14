"""
High-Quality Music Metadata Tagger Module
Automatically fetches and applies high-quality metadata to audio files using Spotify API
Optimized for maximum quality - prioritizes image quality over file size

IMPORTANT BEHAVIOR:
- This module ONLY modifies metadata tags INSIDE audio files (ID3, FLAC, MP4 tags)
- Filenames are NEVER changed - they remain exactly as they are
- The filename is used as the SOURCE OF TRUTH to search for the correct metadata
- Audio content is NEVER modified - only metadata tags are added/updated

Usage:
    from modules.metadata_tagger import MetadataTagger
    
    # Initialize with Spotify credentials
    tagger = MetadataTagger(client_id="...", client_secret="...")
    
    # Process a single file (filename stays unchanged!)
    success, status = tagger.process_file(Path("Artist - Song.mp3"))
    
    # Process entire directory
    stats = tagger.process_directory(Path("/music/folder"), recursive=True)
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import requests
import mutagen
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TDRC, TRCK, TPE2, TPOS
from mutagen.flac import FLAC, Picture
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4, MP4Cover
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials

# Configuration
SUPPORTED_FORMATS = (".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".alac", ".wav", ".aiff", ".wma", ".dsf")

logger = logging.getLogger(__name__)


class MetadataTagger:
    """High-quality metadata tagger for audio files using Spotify API"""
    
    def __init__(self, client_id: str = None, client_secret: str = None, sp: Spotify = None):
        """
        Initialize the metadata tagger
        
        Args:
            client_id: Spotify client ID (optional if sp is provided)
            client_secret: Spotify client secret (optional if sp is provided)
            sp: Pre-configured Spotify client (optional)
        """
        if sp:
            self.sp = sp
        elif client_id and client_secret:
            auth_manager = SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret
            )
            self.sp = Spotify(auth_manager=auth_manager)
        else:
            self.sp = None
        
        self.stats = {
            'processed': 0,
            'tagged': 0,
            'errors': 0,
            'skipped': 0,
            'already_tagged': 0
        }
    
    def get_highest_quality_image_url(self, images: List[Dict]) -> Optional[str]:
        """
        Get the highest quality image URL from Spotify images list
        Spotify typically returns images in descending order by size
        
        Args:
            images: List of image dictionaries from Spotify API
            
        Returns:
            URL of the highest resolution image, or None if no images
        """
        if not images:
            return None
        
        # Find the image with the largest dimensions (width * height)
        largest_image = max(images, key=lambda x: x.get('width', 0) * x.get('height', 0))
        width = largest_image.get('width', 0)
        height = largest_image.get('height', 0)
        
        logger.info(f"Selected highest quality image: {width}x{height}px")
        return largest_image.get('url')
    
    def download_cover_art(self, url: str) -> Optional[bytes]:
        """
        Download album artwork in highest quality
        No size restrictions - quality over file size
        
        Args:
            url: The image URL to download
            
        Returns:
            Image data as bytes, or None if download fails
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            image_data = response.content
            
            size_mb = len(image_data) / 1024 / 1024
            logger.info(f"Downloaded cover art: {size_mb:.2f}MB")
            
            return image_data
        except Exception as e:
            logger.error(f"Failed to download cover art from {url}: {e}")
            return None
    
    def extract_info_from_filename(self, filename: str) -> Dict[str, str]:
        """
        Extract track info from filename using common patterns
        
        Args:
            filename: The filename to parse
            
        Returns:
            Dictionary with 'artist' and/or 'title' keys
        """
        import re
        
        filename = Path(filename).stem
        
        # Remove common prefixes/suffixes
        cleanup_patterns = [
            r'\d+\.\s*',  # Track numbers
            r'\[\d+\]\s*',  # Bracketed numbers
            r'\(\d{4}\)',  # Years in parentheses
            r'\.mp3$|\.flac$|\.m4a$',  # Extensions
        ]
        
        for pattern in cleanup_patterns:
            filename = re.sub(pattern, '', filename, flags=re.IGNORECASE)
        
        # Common separators for artist - title
        separators = [' - ', ' – ', ' — ', '_-_', ' | ']
        
        for sep in separators:
            if sep in filename:
                parts = filename.split(sep, 1)
                if len(parts) == 2:
                    return {
                        'artist': parts[0].strip(),
                        'title': parts[1].strip()
                    }
        
        # If no separator found, assume it's just the title
        return {'title': filename.strip()}
    
    def search_spotify(self, query_info: Dict[str, str]) -> Optional[Dict]:
        """
        Search Spotify for track metadata
        
        Args:
            query_info: Dictionary with 'artist' and/or 'title' keys
            
        Returns:
            Spotify track data dictionary, or None if not found
        """
        if not self.sp:
            logger.error("Spotify client not initialized")
            return None
        
        # Build search queries in order of specificity
        queries = []
        
        if 'artist' in query_info and 'title' in query_info:
            queries.append(f'track:"{query_info["title"]}" artist:"{query_info["artist"]}"')
            queries.append(f'{query_info["artist"]} {query_info["title"]}')
        
        if 'title' in query_info:
            queries.append(f'track:"{query_info["title"]}"')
            queries.append(query_info['title'])
        
        # Try each query
        for query in queries:
            try:
                results = self.sp.search(q=query, type="track", limit=5)
                if results["tracks"]["items"]:
                    track = results["tracks"]["items"][0]
                    logger.info(f"Found match: {track['artists'][0]['name']} - {track['name']}")
                    return track
            except Exception as e:
                logger.warning(f"Spotify search error for query '{query}': {e}")
                continue
        
        return None
    
    def has_complete_metadata(self, file_path: Path) -> bool:
        """
        Check if file already has complete metadata (title, artist, and artwork)
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            True if file has complete metadata, False otherwise
        """
        try:
            audio = mutagen.File(str(file_path))
            if not audio:
                return False
            
            # For MP3/ID3
            if isinstance(audio, mutagen.id3.ID3FileType):
                has_title = 'TIT2' in audio.tags if audio.tags else False
                has_artist = 'TPE1' in audio.tags if audio.tags else False
                has_artwork = 'APIC:' in str(audio.tags) if audio.tags else False
                return has_title and has_artist and has_artwork
            
            # For FLAC
            elif isinstance(audio, FLAC):
                has_title = bool(audio.get('title'))
                has_artist = bool(audio.get('artist'))
                has_artwork = bool(audio.pictures)
                return has_title and has_artist and has_artwork
            
            # For MP4/M4A
            elif isinstance(audio, MP4):
                has_title = '\xa9nam' in audio.tags if audio.tags else False
                has_artist = '\xa9ART' in audio.tags if audio.tags else False
                has_artwork = 'covr' in audio.tags if audio.tags else False
                return has_title and has_artist and has_artwork
            
            # For other formats, use easy interface
            else:
                audio_easy = mutagen.File(str(file_path), easy=True)
                if not audio_easy:
                    return False
                has_title = bool(audio_easy.get("title"))
                has_artist = bool(audio_easy.get("artist"))
                # Can't easily check artwork for other formats
                return has_title and has_artist
                
        except Exception as e:
            logger.debug(f"Error checking metadata for {file_path}: {e}")
            return False
    
    def apply_metadata(self, file_path: Path, spotify_data: Dict, force: bool = False) -> bool:
        """
        Apply high-quality metadata to audio file based on format
        
        IMPORTANT: This ONLY modifies the metadata tags INSIDE the file.
        The actual filename and audio content remain completely unchanged!
        
        Args:
            file_path: Path to the audio file (will NOT be renamed)
            spotify_data: Track data from Spotify API
            force: If True, overwrite existing metadata tags
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_ext = file_path.suffix.lower()
            
            # Extract metadata from Spotify
            title = spotify_data["name"]
            artists = [a["name"] for a in spotify_data["artists"]]
            album = spotify_data["album"]["name"]
            release_date = spotify_data["album"]["release_date"]
            track_number = spotify_data.get("track_number", 0)
            total_tracks = spotify_data["album"].get("total_tracks", 0)
            album_artist = spotify_data["album"]["artists"][0]["name"] if spotify_data["album"]["artists"] else artists[0]
            
            logger.info(f"📝 Adding metadata tags (not renaming file):")
            logger.info(f"   Title: {title}")
            logger.info(f"   Artist: {', '.join(artists)}")
            logger.info(f"   Album: {album}")
            
            # Download highest quality cover art
            cover_data = None
            if spotify_data["album"]["images"]:
                cover_url = self.get_highest_quality_image_url(spotify_data["album"]["images"])
                if cover_url:
                    cover_data = self.download_cover_art(cover_url)
            
            # Apply metadata based on format
            if file_ext == ".mp3":
                success = self._tag_mp3(file_path, title, artists, album, release_date, 
                                       track_number, total_tracks, album_artist, cover_data, force)
            elif file_ext == ".flac":
                success = self._tag_flac(file_path, title, artists, album, release_date,
                                        track_number, total_tracks, album_artist, cover_data, force)
            elif file_ext in [".m4a", ".aac", ".alac"]:
                success = self._tag_mp4(file_path, title, artists, album, release_date,
                                       track_number, total_tracks, album_artist, cover_data, force)
            else:
                # Fallback to generic tagging
                success = self._tag_generic(file_path, title, artists, album, release_date,
                                           track_number, total_tracks, album_artist, force)
            
            if success:
                logger.info(f"Successfully tagged: {artists[0]} - {title}")
            
            return success
        
        except Exception as e:
            logger.error(f"Error tagging {file_path.name}: {e}")
            return False
    
    def _tag_mp3(self, file_path, title, artists, album, release_date, track_num, 
                 total_tracks, album_artist, cover_data, force=False):
        """Tag MP3 files using ID3v2.4"""
        try:
            try:
                audio = ID3(str(file_path))
            except mutagen.id3.ID3NoHeaderError:
                audio = ID3()
            
            # Clear existing tags if force
            if force:
                audio.clear()
            
            # Basic tags (using encoding=3 for UTF-8)
            audio.add(TIT2(encoding=3, text=title))
            audio.add(TPE1(encoding=3, text=artists))
            audio.add(TALB(encoding=3, text=album))
            audio.add(TPE2(encoding=3, text=album_artist))
            audio.add(TDRC(encoding=3, text=release_date))
            
            if track_num:
                track_text = f"{track_num}/{total_tracks}" if total_tracks else str(track_num)
                audio.add(TRCK(encoding=3, text=track_text))
            
            # Album artwork - highest quality
            if cover_data:
                # Detect image format
                mime = "image/jpeg"
                if cover_data[:4] == b'\x89PNG':
                    mime = "image/png"
                
                audio.add(APIC(
                    encoding=3,
                    mime=mime,
                    type=3,  # Cover (front)
                    desc="Cover",
                    data=cover_data
                ))
                logger.info(f"Added high-quality cover art ({len(cover_data) / 1024:.1f}KB) to MP3")
            
            audio.save(str(file_path), v2_version=4)
            return True
            
        except Exception as e:
            logger.error(f"MP3 tagging error: {e}")
            return False
    
    def _tag_flac(self, file_path, title, artists, album, release_date, track_num, 
                  total_tracks, album_artist, cover_data, force=False):
        """Tag FLAC files"""
        try:
            audio = FLAC(str(file_path))
            
            # Clear existing tags if force
            if force:
                audio.clear()
                audio.clear_pictures()
            
            # Basic tags
            audio["TITLE"] = title
            audio["ARTIST"] = artists
            audio["ALBUM"] = album
            audio["ALBUMARTIST"] = album_artist
            audio["DATE"] = release_date
            
            if track_num:
                audio["TRACKNUMBER"] = str(track_num)
                if total_tracks:
                    audio["TRACKTOTAL"] = str(total_tracks)
            
            # Album artwork - highest quality
            if cover_data:
                # Detect image format
                mime = "image/jpeg"
                if cover_data[:4] == b'\x89PNG':
                    mime = "image/png"
                
                picture = Picture()
                picture.type = 3  # Cover (front)
                picture.mime = mime
                picture.desc = "Cover"
                picture.data = cover_data
                
                audio.clear_pictures()
                audio.add_picture(picture)
                logger.info(f"Added high-quality cover art ({len(cover_data) / 1024:.1f}KB) to FLAC")
            
            audio.save()
            return True
            
        except Exception as e:
            logger.error(f"FLAC tagging error: {e}")
            return False
    
    def _tag_mp4(self, file_path, title, artists, album, release_date, track_num, 
                 total_tracks, album_artist, cover_data, force=False):
        """Tag MP4/M4A files"""
        try:
            audio = MP4(str(file_path))
            
            # Clear existing tags if force
            if force:
                audio.clear()
            
            # Basic tags
            audio["\xa9nam"] = title
            audio["\xa9ART"] = artists
            audio["\xa9alb"] = album
            audio["aART"] = album_artist
            audio["\xa9day"] = release_date
            
            if track_num:
                audio["trkn"] = [(track_num, total_tracks)]
            
            # Album artwork - highest quality
            if cover_data:
                # Detect image format
                cover_format = MP4Cover.FORMAT_JPEG
                if cover_data[:4] == b'\x89PNG':
                    cover_format = MP4Cover.FORMAT_PNG
                
                audio["covr"] = [MP4Cover(cover_data, cover_format)]
                logger.info(f"Added high-quality cover art ({len(cover_data) / 1024:.1f}KB) to M4A")
            
            audio.save()
            return True
            
        except Exception as e:
            logger.error(f"MP4 tagging error: {e}")
            return False
    
    def _tag_generic(self, file_path, title, artists, album, release_date, track_num, 
                     total_tracks, album_artist, force=False):
        """Generic tagging using mutagen easy interface (no artwork support)"""
        try:
            audio = mutagen.File(str(file_path), easy=True)
            if not audio:
                return False
            
            # Clear existing tags if force
            if force:
                audio.clear()
            
            audio["title"] = title
            audio["artist"] = artists
            audio["album"] = album
            audio["albumartist"] = album_artist
            audio["date"] = release_date
            
            if track_num:
                audio["tracknumber"] = str(track_num)
            
            audio.save()
            logger.warning(f"Generic tagging used - artwork not supported for {file_path.suffix}")
            return True
            
        except Exception as e:
            logger.error(f"Generic tagging error: {e}")
            return False
    
    def process_file(self, file_path: Path, force: bool = False, use_filename_as_source: bool = True) -> Tuple[bool, str]:
        """
        Process a single audio file - search for metadata and apply it
        
        IMPORTANT: The filename is the source of truth! It represents the actual audio content.
        We use the filename to search for metadata, NOT to rename the file.
        
        Args:
            file_path: Path to the audio file (filename stays unchanged!)
            force: If True, overwrite existing metadata tags
            use_filename_as_source: If True, use filename as primary source for search (recommended)
            
        Returns:
            Tuple of (success: bool, status: str)
            Status can be: 'tagged', 'skipped', 'no_match', 'error'
        """
        self.stats['processed'] += 1
        
        try:
            # Check if file is supported
            if file_path.suffix.lower() not in SUPPORTED_FORMATS:
                logger.warning(f"Unsupported file format: {file_path.name}")
                self.stats['errors'] += 1
                return False, 'error'
            
            # Check if already has complete metadata
            if not force and self.has_complete_metadata(file_path):
                logger.info(f"Already has complete metadata: {file_path.name}")
                self.stats['already_tagged'] += 1
                return True, 'skipped'
            
            # PRIORITY: Use filename as the source of truth for what the song actually is
            query_info = self.extract_info_from_filename(file_path.name)
            
            # Only use existing metadata if filename doesn't provide enough info
            # AND we're not using filename as source
            if not use_filename_as_source:
                try:
                    audio = mutagen.File(str(file_path), easy=True)
                    if audio:
                        existing_title = audio.get("title", [""])[0] if audio.get("title") else ""
                        existing_artist = audio.get("artist", [""])[0] if audio.get("artist") else ""
                        
                        if existing_title and not query_info.get('title'):
                            query_info['title'] = existing_title
                        if existing_artist and not query_info.get('artist'):
                            query_info['artist'] = existing_artist
                except:
                    pass
            
            logger.info(f"🔍 Searching based on FILENAME: {file_path.name}")
            logger.info(f"   Query: {query_info.get('artist', 'Unknown')} - {query_info.get('title', 'Unknown')}")
            
            # Search Spotify
            spotify_data = self.search_spotify(query_info)
            
            if not spotify_data:
                logger.warning(f"❌ No match found for: {file_path.name}")
                logger.warning(f"   The filename will stay unchanged. Try renaming to: 'Artist - Title.ext'")
                self.stats['errors'] += 1
                return False, 'no_match'
            
            # Show what we found
            found_artist = spotify_data['artists'][0]['name']
            found_title = spotify_data['name']
            logger.info(f"✓ Found match: {found_artist} - {found_title}")
            
            # Apply metadata (this only changes internal tags, NOT the filename)
            if self.apply_metadata(file_path, spotify_data, force):
                logger.info(f"✓ Tagged file (filename unchanged): {file_path.name}")
                self.stats['tagged'] += 1
                return True, 'tagged'
            else:
                self.stats['errors'] += 1
                return False, 'error'
                
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")
            self.stats['errors'] += 1
            return False, 'error'
    
    def process_directory(self, directory: Path, recursive: bool = True, force: bool = False):
        """
        Process all audio files in a directory
        
        Args:
            directory: Path to the directory
            recursive: If True, process subdirectories recursively
            force: If True, overwrite existing metadata
            
        Returns:
            Statistics dictionary
        """
        logger.info(f"Processing directory: {directory}")
        
        # Find all audio files
        if recursive:
            audio_files = [f for f in directory.rglob("*") if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS]
        else:
            audio_files = [f for f in directory.glob("*") if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS]
        
        logger.info(f"Found {len(audio_files)} audio files")
        
        for file_path in audio_files:
            self.process_file(file_path, force)
        
        return self.stats
    
    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset processing statistics"""
        self.stats = {
            'processed': 0,
            'tagged': 0,
            'errors': 0,
            'skipped': 0,
            'already_tagged': 0
        }


def refresh_metadata_for_directory(directory: str, client_id: str = None, 
                                   client_secret: str = None, sp: Spotify = None,
                                   recursive: bool = True, force: bool = False) -> Dict[str, int]:
    """
    Convenience function to refresh metadata for all audio files in a directory
    
    Args:
        directory: Path to the directory containing audio files
        client_id: Spotify client ID (optional if sp is provided)
        client_secret: Spotify client secret (optional if sp is provided)
        sp: Pre-configured Spotify client (optional)
        recursive: If True, process subdirectories recursively
        force: If True, overwrite existing metadata
        
    Returns:
        Statistics dictionary with processing results
    """
    tagger = MetadataTagger(client_id=client_id, client_secret=client_secret, sp=sp)
    
    directory_path = Path(directory)
    if not directory_path.exists():
        raise ValueError(f"Directory does not exist: {directory}")
    
    if not directory_path.is_dir():
        raise ValueError(f"Path is not a directory: {directory}")
    
    return tagger.process_directory(directory_path, recursive=recursive, force=force)
