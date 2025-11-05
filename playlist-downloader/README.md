# Spotify & YouTube Playlist Downloader

The script downloads songs from Spotify and YouTube playlists by searching for them on YouTube and saving them as high-quality audio files. 
Features a user-friendly interface, supports multiple playlists, and includes smart features like progress tracking and automatic retries.

-------------------------------------------------------------------------------------
## Whats New
-------------------------------------------------------------------------------------










----------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------


## 📋 Prerequisites

1. **Python 3.8 or higher**
   - Download from [python.org](https://www.python.org/downloads/)
   - Make sure to check "Add Python to PATH" during installation (Windows)

2. **FFmpeg** (required for audio conversion)
   - **Windows**: Download from [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/) and add to PATH
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian) or `sudo dnf install ffmpeg` (Fedora)

3. **Spotify Developer Account**
   - Required for API access
   - Register at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a new application
   - Add `http://127.0.0.1:8000/callback` as a Redirect URI
   - Note your Client ID and Client Secret

---

## Quick Start

### Windows

1. **Run the setup script**:
   ```cmd
   setup.bat
   ```
   This will:
   - Create a virtual environment
   - Install all dependencies
   - Create configuration files
   - Detect your system resources

2. **Configure your Spotify credentials**:
   - Edit `.config\.env`
   - Add your `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`


### macOS / Linux

1. **Run the setup script**:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   This will:
   - Create a virtual environment
   - Install all dependencies
   - Create configuration files
   - Detect your system resources

2. **Configure your Spotify credentials**:
   - Edit `.config/.env`
   - Add your `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`

---

## Detailed Installation (Manual Setup)

If you prefer to set up manually or need more control:

1. **Clone or download the repository**

2. **Create a virtual environment**:
   ```bash
   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate
   
   # Windows
   python -m venv venv
   venv\Scripts\activate.bat
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Create configuration**:
   - Create a `.config` directory
   - Copy/create `.config/.env` with your settings (see Configuration section below)

5. **Set up Spotify Developer Application**:
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a new application
   - Add `http://127.0.0.1:8000/callback` as a Redirect URI
   - Note down your Client ID and Client Secret
   - Add them to `.config/.env`


---

## ⚙️ Configuration

The `.config/.env` file contains all configuration options:

```env
# Spotify API Credentials
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/callback

# Download Settings
OUTPUT_DIR=./downloads              # Where to save files
AUDIO_QUALITY=320K                  # Audio bitrate (128K, 192K, 256K, 320K)
AUDIO_FORMAT=mp3                    # Output format (mp3, m4a, opus, etc.)
DOWNLOAD_DELAY=1.5                  # Delay between downloads (seconds)
MAX_RETRIES=3                       # Number of retry attempts
SEARCH_DELAY_MIN=0.5               # Minimum search delay
SEARCH_DELAY_MAX=1.5               # Maximum search delay
START_DOWNLOAD_THRESHOLD=27        # Start downloading after this many searches

# FFmpeg Path (leave as 'ffmpeg' if it's in PATH)
FFMPEG_PATH=ffmpeg
```

The setup script also creates `config.json` with optimized settings for your system:
- `max_threads`: Concurrent search workers (auto-detected)
- `max_processes`: Concurrent download workers (auto-detected)
- `cpu_cores`: Your CPU core count
- `total_mem_gb`: Your system memory

---


### Main Menu Options

1. **Add a Playlist**
   - Choose between Spotify or YouTube playlist
   - Enter a descriptive label
   - Paste the playlist URL
   - Preview playlist details before adding

2. **Check Undownloaded Songs**
   - View missing tracks for each playlist
   - See download statistics
   - Export missing songs list
   - Quick-download all missing songs

3. **Sync and Download**
   - Downloads all missing tracks from all playlists
   - Shows real-time progress
   - Auto-resumes if interrupted

4. **Exit**
   - Safely closes the application

### Adding Playlists

**Spotify Playlists:**
```
URL format: https://open.spotify.com/playlist/PLAYLIST_ID
```

**YouTube Playlists:**
```
URL format: https://www.youtube.com/playlist?list=PLAYLIST_ID
```

### Advanced Usage (Command Line)

You can run the async downloader directly with custom parameters:

```bash
# Activate virtual environment first
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate.bat  # Windows

# Run with custom settings
python async_downloader.py \
  --output-dir ./downloads \
  --spotify-client-id YOUR_ID \
  --spotify-client-secret YOUR_SECRET \
  --playlists-file .config/playlists.txt \
  --search-workers 5 \
  --download-workers 3 \
  --audio-quality 320K
```

### File Organization

Downloaded files are organized as:
```
downloads/
├── Playlist Name 1/
│   ├── Artist - Song 1.mp3
│   ├── Artist - Song 2.mp3
│   └── ...
├── Playlist Name 2/
│   └── ...
└── playlists.txt
```

---

## 🛠️ Troubleshooting

### Common Issues

#### 1. **Setup Script Fails**

**Windows:**
- Make sure Python is in your PATH: `python --version`
- Run PowerShell/CMD as Administrator if you get permission errors
- Disable antivirus temporarily if it blocks script execution

**macOS/Linux:**
- Make sure scripts are executable: `chmod +x setup.sh run.sh`
- Install Python 3 if needed: `sudo apt install python3 python3-venv` (Ubuntu)
- Check Python version: `python3 --version` (should be 3.8+)

#### 2. **Virtual Environment Activation Issues**

**Windows:**
```cmd
# If activation fails, try:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
# Then run setup.bat again
```

**Linux/macOS:**
```bash
# If you get permission denied:
chmod +x venv/bin/activate
source venv/bin/activate
```

#### 3. **FFmpeg Not Found**

**Windows:**
- Download FFmpeg from [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/)
- Extract and add `bin` folder to system PATH
- Or place `ffmpeg.exe` directly in the project folder
- Restart your terminal/command prompt

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Arch
sudo pacman -S ffmpeg
```

#### 4. **Authentication Errors**
- Ensure your Spotify Developer application has the correct redirect URI: `http://127.0.0.1:8000/callback`
- Check that your client ID and secret in `.config/.env` are correct
- Try deleting the `.cache` file and re-authenticating
- Make sure your Spotify app is not in "Development Mode" restrictions

#### 5. **Download Failures**
- Check your internet connection
- Try reducing concurrent downloads in `config.json`
- Increase the download delay in `.config/.env`
- Some videos may be region-locked or age-restricted
- Check that yt-dlp is up to date: `pip install --upgrade yt-dlp`

#### 6. **Permission Issues**

**Windows:**
- Run as Administrator if you get "Access Denied" errors
- Check that your antivirus isn't blocking file creation
- Ensure the downloads folder isn't read-only

**macOS/Linux:**
```bash
# Fix permissions on download directory
chmod -R 755 downloads/

# If you installed in a system directory, don't use sudo
# Instead, move the project to your home directory
```

#### 7. **Missing Dependencies**

If packages fail to install:

**All Platforms:**
```bash
# Activate virtual environment first
# Then upgrade pip and try again:
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Linux specific:**
```bash
# You may need development headers
sudo apt install python3-dev build-essential  # Ubuntu/Debian
sudo dnf install python3-devel gcc            # Fedora
```

#### 8. **Module Not Found Errors**

Make sure your virtual environment is activated:

**Windows:**
```cmd
venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

#### 9. **"Python not found" on Windows**

During Python installation:
1. Check "Add Python to PATH"
2. Or manually add Python to PATH:
   - Search "Environment Variables" in Windows
   - Add Python installation directory to PATH
   - Add Python Scripts directory to PATH

#### 10. **Slow Downloads**

- Increase `DOWNLOAD_WORKERS` in `config.json` (be careful not to exceed your bandwidth)
- Check your internet speed
- Try downloading during off-peak hours
- Some videos may be throttled by YouTube

---

## 🔧 Platform-Specific Notes

### Windows
- Scripts use `.bat` extension
- Paths use backslashes (`\`)
- Virtual environment: `venv\Scripts\activate.bat`
- May need to run as Administrator for some operations

### macOS
- Scripts use `.sh` extension  
- May need to install Xcode Command Line Tools: `xcode-select --install`
- FFmpeg easily installed via Homebrew: `brew install ffmpeg`
- Virtual environment: `source venv/bin/activate`

### Linux
- Scripts use `.sh` extension
- May need to install build tools and Python dev headers
- Package manager varies by distro (apt, dnf, pacman, etc.)
- Virtual environment: `source venv/bin/activate`

---

## 📁 Project Structure

```
playlist-downloader/
├── setup.sh              # Setup script (Linux/macOS)
├── setup.bat            # Setup script (Windows)
├── main.py              # Main interactive application
├── async_downloader.py  # Async download engine
├── configure.py         # System resource detection
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── .config/
│   ├── .env            # Configuration (created by setup)
│   └── user.json       # User preferences
├── downloads/          # Downloaded music (created by setup)
└── venv/              # Virtual environment (created by setup)
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Credits

- Built with:
  - [spotipy](https://spotipy.readthedocs.io/) - Spotify Web API wrapper
  - [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube video downloader
  - [python-dotenv](https://pypi.org/project/python-dotenv/) - Environment variable management
  - [rich](https://github.com/Textualize/rich) - Beautiful terminal output

## ⚠️ Legal Notice

This tool is for personal use only. Please respect copyright laws and the terms of service of Spotify and YouTube. Downloading copyrighted content may be against their terms of service in your country.

---

🎵 Happy listening! If you enjoy this tool, consider giving it a ⭐ on GitHub!
