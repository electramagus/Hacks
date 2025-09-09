#!/usr/bin/env python3
"""
Enhanced Music Metadata Tagger
Automatically fetches and applies metadata to audio files using Spotify API
Self-contained script that creates its own virtual environment and installs dependencies
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

# Bootstrap configuration
REQUIRED_PACKAGES = ["mutagen", "spotipy", "requests"]
VENV_DIR = ".music_tagger_venv"

# Add a bypass flag to prevent infinite loops
BOOTSTRAP_COMPLETE_FLAG = ".bootstrap_complete"

def get_permission_for_setup():
    """Ask user for permission to set up virtual environment"""
    # Check if bootstrap was recently completed
    flag_file = Path(BOOTSTRAP_COMPLETE_FLAG)
    if flag_file.exists():
        # Check if flag is recent (within last 5 minutes)
        import time
        if time.time() - flag_file.stat().st_mtime < 300:  # 5 minutes
            print("🔄 Bootstrap recently completed, skipping setup...")
            return False

    print("=" * 60)
    print("🔧 Initial Setup Required")
    print("=" * 60)
    print("This script needs to:")
    print("1. Create a virtual environment")
    print("2. Install required Python packages (mutagen, spotipy, requests)")
    print("3. Run the music tagging application")
    print()

    while True:
        choice = input("Do you want to proceed with setup? (y/n): ").lower().strip()
        if choice in ['y', 'yes']:
            return True
        elif choice in ['n', 'no']:
            print("Setup cancelled. Exiting...")
            return False
        else:
            print("Please enter 'y' for yes or 'n' for no.")

def run_command(cmd, description="Running command", check_output=False):
    """Run a command with error handling and permission checks"""
    try:
        print(f"📦 {description}...")
        if check_output:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        if "permission" in str(e).lower() or "access" in str(e).lower():
            print(f"❌ Permission error: {e}")
            print("This might be due to insufficient permissions.")

            # Suggest solutions based on platform
            if platform.system() == "Windows":
                print("Try running as Administrator or in a different directory.")
            else:
                print("Try running with 'sudo' or in a directory you have write access to.")

            retry = input("Do you want to try again? (y/n): ").lower().strip()
            if retry in ['y', 'yes']:
                return run_command(cmd, description, check_output)
            else:
                print("Setup cancelled.")
                return False
        else:
            print(f"❌ Error {description}: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error {description}: {e}")
        return False

def get_python_executable():
    """Get the appropriate Python executable"""
    # Try to find python3 first, then python
    python_commands = ["python3", "python"]

    for cmd in python_commands:
        try:
            result = subprocess.run([cmd, "--version"], capture_output=True, text=True)
            if result.returncode == 0 and "Python 3" in result.stdout:
                return cmd
        except FileNotFoundError:
            continue

    print("❌ Python 3 not found. Please ensure Python 3 is installed and in your PATH.")
    sys.exit(1)

def create_virtual_environment():
    """Create and setup virtual environment"""
    venv_path = Path(VENV_DIR)
    python_cmd = get_python_executable()

    # Check if venv already exists and is valid
    if venv_path.exists():
        # Check if it's a valid venv by trying to activate it
        if platform.system() == "Windows":
            python_venv = venv_path / "Scripts" / "python.exe"
            pip_venv = venv_path / "Scripts" / "pip.exe"
        else:
            python_venv = venv_path / "bin" / "python"
            pip_venv = venv_path / "bin" / "pip"

        if python_venv.exists() and pip_venv.exists():
            print("✅ Virtual environment already exists")
            return str(python_venv), str(pip_venv)

    # Create new virtual environment
    print("🔧 Creating virtual environment...")
    if not run_command(f"{python_cmd} -m venv {VENV_DIR}", "Creating virtual environment"):
        return None, None

    # Return paths to executables
    if platform.system() == "Windows":
        python_venv = venv_path / "Scripts" / "python.exe"
        pip_venv = venv_path / "Scripts" / "pip.exe"
    else:
        python_venv = venv_path / "bin" / "python"
        pip_venv = venv_path / "bin" / "pip"

    return str(python_venv), str(pip_venv)

def check_and_install_packages(pip_executable):
    """Check if packages are installed and install if needed"""
    print("🔍 Checking required packages...")

    for package in REQUIRED_PACKAGES:
        try:
            # Check if package is installed
            result = subprocess.run([pip_executable, "show", package],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {package} already installed")
            else:
                print(f"📦 Installing {package}...")
                if not run_command(f'"{pip_executable}" install {package}', f"Installing {package}"):
                    return False
        except Exception as e:
            print(f"❌ Error checking {package}: {e}")
            return False

    return True

def bootstrap_environment():
    """Bootstrap the virtual environment and dependencies"""
    print("🚀 Bootstrapping environment...")

    # Get permission
    if not get_permission_for_setup():
        sys.exit(0)

    # Create virtual environment
    python_venv, pip_venv = create_virtual_environment()
    if not python_venv or not pip_venv:
        print("❌ Failed to create virtual environment")
        sys.exit(1)

    # Install packages
    if not check_and_install_packages(pip_venv):
        print("❌ Failed to install required packages")
        sys.exit(1)

    print("✅ Environment setup complete!")
    print("🔄 Restarting script with virtual environment...")

    # Create bootstrap completion flag
    try:
        with open(BOOTSTRAP_COMPLETE_FLAG, 'w') as f:
            f.write("Bootstrap completed")
    except Exception as e:
        print(f"⚠️  Warning: Could not create bootstrap flag: {e}")

    # Restart script with virtual environment Python
    try:
        os.execv(python_venv, [python_venv, __file__] + sys.argv[1:])
    except Exception as e:
        print(f"❌ Failed to restart with virtual environment: {e}")
        print("You can manually run the script using:")
        print(f"{python_venv} {__file__}")
        sys.exit(1)

def is_in_virtual_env():
    """Check if we're already running in our virtual environment"""
    # If bootstrap flag exists, check if packages are importable
    if Path(BOOTSTRAP_COMPLETE_FLAG).exists():
        try:
            import mutagen
            import spotipy
            import requests
            return True
        except ImportError:
            print("❌ Required packages are missing, even though bootstrap flag exists.")
            print("Please delete .bootstrap_complete and .music_tagger_venv, then rerun the script.")
            return False

    venv_path = Path(VENV_DIR).resolve()
    if not venv_path.exists():
        return False
    current_python = Path(sys.executable).resolve()
    try:
        return str(venv_path) in str(current_python)
    except:
        return False

# Bootstrap check - run this before importing other dependencies
if __name__ == "__main__" and not is_in_virtual_env():
    bootstrap_environment()

# Now import the rest of the dependencies (after potential bootstrap)
import json
import base64
from typing import Optional, Dict, List
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
CONFIG_FILE = "spotify_config.json"

class MusicTagger:
    def __init__(self):
        self.sp = None
        self.stats = {
            'processed': 0,
            'tagged': 0,
            'errors': 0,
            'skipped': 0
        }
    
    def display_banner(self):
        """Display script information banner"""
        print("=" * 60)
        print("🎵 Enhanced Music Metadata Tagger")
        print("=" * 60)
        print("This script automatically attaches missing metadata to your music files")
        print("using the Spotify API. It supports multiple audio formats and provides")
        print("comprehensive tagging including album artwork.")
        print("=" * 60)
        print()
    
    def get_spotify_credentials(self) -> tuple:
        """Get Spotify API credentials from user or config file"""
        config_path = Path(CONFIG_FILE)
        
        # Try to load existing credentials
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    client_id = config.get('client_id')
                    client_secret = config.get('client_secret')
                    
                if client_id and client_secret:
                    use_saved = input(f"Use saved Spotify credentials? (y/n): ").lower().strip()
                    if use_saved in ['y', 'yes', '']:
                        return client_id, client_secret
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Get new credentials
        print("\n🔑 Spotify API Credentials Required")
        print("Get your credentials at: https://developer.spotify.com/dashboard/applications")
        print("-" * 50)
        
        while True:
            client_id = input("Enter Spotify Client ID: ").strip()
            if client_id:
                break
            print("❌ Client ID cannot be empty!")
        
        while True:
            client_secret = input("Enter Spotify Client Secret: ").strip()
            if client_secret:
                break
            print("❌ Client Secret cannot be empty!")
        
        # Save credentials
        save_creds = input("\n💾 Save credentials for future use? (y/n): ").lower().strip()
        if save_creds in ['y', 'yes', '']:
            try:
                with open(config_path, 'w') as f:
                    json.dump({
                        'client_id': client_id,
                        'client_secret': client_secret
                    }, f, indent=2)
                print("✅ Credentials saved!")
            except Exception as e:
                print(f"⚠️  Warning: Could not save credentials: {e}")
        
        return client_id, client_secret
    
    def setup_spotify(self):
        """Initialize Spotify client"""
        client_id, client_secret = self.get_spotify_credentials()
        
        try:
            auth_manager = SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret
            )
            self.sp = Spotify(auth_manager=auth_manager)
            
            # Test the connection
            self.sp.search(q="test", type="track", limit=1)
            print("✅ Spotify API connection successful!")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to Spotify API: {e}")
            print("Please check your credentials and try again.")
            return False
    
    def get_music_directory(self) -> Path:
        """Get music directory from user"""
        print("\n📁 Music Directory Selection")
        print("-" * 30)
        
        # Suggest common music directories based on platform
        suggestions = self.get_common_music_dirs()
        
        if suggestions:
            print("Common music directories found:")
            for i, path in enumerate(suggestions, 1):
                print(f"  {i}. {path}")
            print(f"  {len(suggestions) + 1}. Enter custom path")
            
            while True:
                try:
                    choice = input(f"\nSelect directory (1-{len(suggestions) + 1}): ").strip()
                    
                    if choice.isdigit():
                        choice = int(choice)
                        if 1 <= choice <= len(suggestions):
                            return Path(suggestions[choice - 1])
                        elif choice == len(suggestions) + 1:
                            break
                    
                    print("❌ Invalid selection!")
                except (ValueError, KeyboardInterrupt):
                    print("\n👋 Exiting...")
                    sys.exit(0)
        
        # Get custom path
        while True:
            try:
                path_input = input("Enter music directory path: ").strip().strip('"\'')
                if not path_input:
                    print("❌ Path cannot be empty!")
                    continue
                
                music_dir = Path(path_input).expanduser().resolve()
                
                if not music_dir.exists():
                    print(f"❌ Directory does not exist: {music_dir}")
                    continue
                
                if not music_dir.is_dir():
                    print(f"❌ Path is not a directory: {music_dir}")
                    continue
                
                return music_dir
                
            except KeyboardInterrupt:
                print("\n👋 Exiting...")
                sys.exit(0)
            except Exception as e:
                print(f"❌ Invalid path: {e}")
    
    def get_common_music_dirs(self) -> List[str]:
        """Get platform-specific common music directories"""
        common_dirs = []
        
        if platform.system() == "Windows":
            # Windows paths
            music_paths = [
                Path.home() / "Music",
                Path("C:/Users/Public/Music"),
                Path("D:/Music"),
                Path("E:/Music")
            ]
        elif platform.system() == "Darwin":  # macOS
            # macOS paths
            music_paths = [
                Path.home() / "Music",
                Path.home() / "iTunes" / "iTunes Media" / "Music",
                Path("/Users/Shared/Music")
            ]
        else:  # Linux and others
            # Linux paths
            music_paths = [
                Path.home() / "Music",
                Path.home() / ".local/share/music",
                Path("/media") / os.environ.get('USER', 'user') / "Music",
                Path("/mnt/music")
            ]
        
        for path in music_paths:
            try:
                if path.exists() and path.is_dir():
                    # Check if directory has audio files
                    if any(path.rglob(f"*{ext}") for ext in SUPPORTED_FORMATS[:3]):  # Quick check
                        common_dirs.append(str(path))
            except (PermissionError, OSError):
                continue
        
        return common_dirs
    
    def find_audio_files(self, root_dir: Path):
        """Recursively find audio files"""
        for file_path in root_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_FORMATS:
                yield file_path
    
    def extract_info_from_filename(self, filename: str) -> Dict[str, str]:
        """Extract track info from filename using common patterns"""
        filename = Path(filename).stem
        
        # Remove common prefixes/suffixes
        cleanup_patterns = [
            r'\d+\.\s*',  # Track numbers
            r'\[\d+\]\s*',  # Bracketed numbers
            r'\(\d{4}\)',  # Years in parentheses
            r'\.mp3$|\.flac$|\.m4a$',  # Extensions
        ]
        
        import re
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
        """Search Spotify for track metadata"""
        if not self.sp:
            return None
        
        # Build search query
        queries = []
        
        if 'artist' in query_info and 'title' in query_info:
            queries.append(f"track:\"{query_info['title']}\" artist:\"{query_info['artist']}\"")
            queries.append(f"{query_info['artist']} {query_info['title']}")
        
        if 'title' in query_info:
            queries.append(f"track:\"{query_info['title']}\"")
            queries.append(query_info['title'])
        
        # Try each query
        for query in queries:
            try:
                results = self.sp.search(q=query, type="track", limit=5)
                if results["tracks"]["items"]:
                    # Return the best match (first result for now)
                    return results["tracks"]["items"][0]
            except Exception as e:
                print(f"⚠️  Spotify search error: {e}")
                continue
        
        return None
    
    def download_cover_art(self, url: str) -> Optional[bytes]:
        """Download album artwork"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"⚠️  Failed to download cover art: {e}")
            return None
    
    def apply_metadata(self, file_path: Path, spotify_data: Dict) -> bool:
        """Apply metadata to audio file based on format"""
        try:
            file_ext = file_path.suffix.lower()
            
            # Extract metadata
            title = spotify_data["name"]
            artists = [a["name"] for a in spotify_data["artists"]]
            album = spotify_data["album"]["name"]
            release_date = spotify_data["album"]["release_date"]
            track_number = spotify_data.get("track_number", 0)
            total_tracks = spotify_data["album"].get("total_tracks", 0)
            album_artist = spotify_data["album"]["artists"][0]["name"] if spotify_data["album"]["artists"] else artists[0]
            
            # Download cover art
            cover_data = None
            if spotify_data["album"]["images"]:
                cover_url = spotify_data["album"]["images"][0]["url"]
                cover_data = self.download_cover_art(cover_url)
            
            if file_ext == ".mp3":
                return self._tag_mp3(file_path, title, artists, album, release_date, 
                                   track_number, total_tracks, album_artist, cover_data)
            
            elif file_ext == ".flac":
                return self._tag_flac(file_path, title, artists, album, release_date,
                                    track_number, total_tracks, album_artist, cover_data)
            
            elif file_ext in [".m4a", ".aac", ".alac"]:
                return self._tag_mp4(file_path, title, artists, album, release_date,
                                   track_number, total_tracks, album_artist, cover_data)
            
            else:
                # Fallback to mutagen easy interface
                return self._tag_generic(file_path, title, artists, album, release_date,
                                       track_number, total_tracks, album_artist)
        
        except Exception as e:
            print(f"❌ Error tagging {file_path.name}: {e}")
            return False
    
    def _tag_mp3(self, file_path, title, artists, album, release_date, track_num, total_tracks, album_artist, cover_data):
        """Tag MP3 files using ID3"""
        try:
            audio = ID3(str(file_path))
            
            # Clear existing tags
            audio.clear()
            
            # Basic tags
            audio.add(TIT2(encoding=3, text=title))
            audio.add(TPE1(encoding=3, text=artists))
            audio.add(TALB(encoding=3, text=album))
            audio.add(TPE2(encoding=3, text=album_artist))
            audio.add(TDRC(encoding=3, text=release_date))
            
            if track_num:
                track_text = f"{track_num}/{total_tracks}" if total_tracks else str(track_num)
                audio.add(TRCK(encoding=3, text=track_text))
            
            # Album artwork
            if cover_data:
                audio.add(APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,  # Cover (front)
                    desc="Cover",
                    data=cover_data
                ))
            
            audio.save()
            return True
            
        except Exception as e:
            print(f"❌ MP3 tagging error: {e}")
            return False
    
    def _tag_flac(self, file_path, title, artists, album, release_date, track_num, total_tracks, album_artist, cover_data):
        """Tag FLAC files"""
        try:
            audio = FLAC(str(file_path))
            
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
            
            # Album artwork
            if cover_data:
                picture = Picture()
                picture.type = 3  # Cover (front)
                picture.mime = "image/jpeg"
                picture.desc = "Cover"
                picture.data = cover_data
                audio.clear_pictures()
                audio.add_picture(picture)
            
            audio.save()
            return True
            
        except Exception as e:
            print(f"❌ FLAC tagging error: {e}")
            return False
    
    def _tag_mp4(self, file_path, title, artists, album, release_date, track_num, total_tracks, album_artist, cover_data):
        """Tag MP4/M4A files"""
        try:
            audio = MP4(str(file_path))
            
            # Basic tags
            audio["\xa9nam"] = title
            audio["\xa9ART"] = artists
            audio["\xa9alb"] = album
            audio["aART"] = album_artist
            audio["\xa9day"] = release_date
            
            if track_num:
                audio["trkn"] = [(track_num, total_tracks)]
            
            # Album artwork
            if cover_data:
                audio["covr"] = [MP4Cover(cover_data, MP4Cover.FORMAT_JPEG)]
            
            audio.save()
            return True
            
        except Exception as e:
            print(f"❌ MP4 tagging error: {e}")
            return False
    
    def _tag_generic(self, file_path, title, artists, album, release_date, track_num, total_tracks, album_artist):
        """Generic tagging using mutagen easy interface"""
        try:
            audio = mutagen.File(str(file_path), easy=True)
            if not audio:
                return False
            
            audio["title"] = title
            audio["artist"] = artists
            audio["album"] = album
            audio["albumartist"] = album_artist
            audio["date"] = release_date
            
            if track_num:
                audio["tracknumber"] = str(track_num)
            
            audio.save()
            return True
            
        except Exception as e:
            print(f"❌ Generic tagging error: {e}")
            return False
    
    def process_file(self, file_path: Path) -> bool:
        """Process a single audio file"""
        self.stats['processed'] += 1
        
        try:
            # Check if file already has complete metadata
            audio = mutagen.File(str(file_path), easy=True)
            if not audio:
                print(f"⚠️  Unsupported file format: {file_path.name}")
                self.stats['errors'] += 1
                return False
            
            # Check existing metadata
            existing_title = audio.get("title", [""])[0] if audio.get("title") else ""
            existing_artist = audio.get("artist", [""])[0] if audio.get("artist") else ""
            
            if existing_title and existing_artist:
                print(f"⏭️  Already tagged: {file_path.name}")
                self.stats['skipped'] += 1
                return True
            
            # Extract info from filename
            query_info = self.extract_info_from_filename(file_path.name)
            
            # If we have some existing metadata, prefer it
            if existing_title:
                query_info['title'] = existing_title
            if existing_artist:
                query_info['artist'] = existing_artist
            
            print(f"🔍 Searching: {file_path.name}")
            
            # Search Spotify
            spotify_data = self.search_spotify(query_info)
            
            if not spotify_data:
                print(f"❌ No match found for: {file_path.name}")
                self.stats['errors'] += 1
                return False
            
            # Apply metadata
            if self.apply_metadata(file_path, spotify_data):
                print(f"✅ Tagged: {spotify_data['artists'][0]['name']} - {spotify_data['name']}")
                self.stats['tagged'] += 1
                return True
            else:
                self.stats['errors'] += 1
                return False
                
        except Exception as e:
            print(f"❌ Error processing {file_path.name}: {e}")
            self.stats['errors'] += 1
            return False
    
    def print_stats(self):
        """Print processing statistics"""
        print("\n" + "=" * 50)
        print("📊 Processing Complete!")
        print("=" * 50)
        print(f"Files processed: {self.stats['processed']}")
        print(f"Successfully tagged: {self.stats['tagged']}")
        print(f"Already tagged (skipped): {self.stats['skipped']}")
        print(f"Errors: {self.stats['errors']}")
        print("=" * 50)
    
    def run(self):
        """Main execution method"""
        self.display_banner()
        
        # Setup Spotify API
        if not self.setup_spotify():
            return
        
        # Get music directory
        music_dir = self.get_music_directory()
        
        print(f"\n🎵 Scanning directory: {music_dir}")
        print("Processing audio files...")
        print("-" * 50)
        
        # Process all audio files
        audio_files = list(self.find_audio_files(music_dir))
        
        if not audio_files:
            print("❌ No supported audio files found in the specified directory.")
            return
        
        print(f"Found {len(audio_files)} audio files")
        
        try:
            for file_path in audio_files:
                self.process_file(file_path)
        except KeyboardInterrupt:
            print("\n\n⚠️  Process interrupted by user")
        
        self.print_stats()

def main():
    """Main entry point"""
    tagger = MusicTagger()
    tagger.run()

if __name__ == "__main__":
    main()
