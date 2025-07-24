# Spotify & YouTube Playlist Downloader

A powerful Python script that downloads songs from Spotify and YouTube playlists by searching for them on YouTube and saving them as high-quality audio files. Features a user-friendly interface, supports multiple playlists, and includes smart features like progress tracking and automatic retries.

> **Yes, [SpotDL](https://github.com/spotDL/spotify-downloader) exists. But I still built this — because reinventing the wheel is how you learn to drive.**

---

## What Does This Script Do?
- Reads your Spotify playlist (public or private)
- Searches YouTube for each song
- Downloads the best match
- Saves all songs to a folder you choose
- If you stop the script, you can run it again and it will continue where it left off
- Downloads many songs at the same time for speed

---

## 📋 Prerequisites

1. **Python 3.8 or higher**
   - Download from [python.org](https://www.python.org/downloads/)

2. **FFmpeg**
   - Required for audio conversion
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Add to your system PATH

3. **Spotify Developer Account**
   - Required for API access
   - Register at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

## 🚀 Installation

1. **Download the zip**:
   

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   
   Or install them manually:
   ```bash
   pip install spotipy python-dotenv yt-dlp tqdm rich
   ```

3. **Set up Spotify Developer Application**:
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create a new application
   - Add `http://127.0.0.1:8000/callback` as a Redirect URI
   - Note down your Client ID and Client Secret

4. **Configure the application**:
   - edit the `.env` file in the `.config` directory
   - fill in the values for the following variables:
   - `SPOTIFY_CLIENT_ID`: Your Spotify Client ID
   - `SPOTIFY_CLIENT_SECRET`: Your Spotify Client Secret


---

## 🎛️ Usage

### Starting the Application
```bash
python main.py
```

### Adding Playlists
1. Select "Add a new playlist" from the main menu
2. Choose between Spotify or YouTube playlist
3. Enter a name for the playlist (for your reference)
4. Paste the playlist URL or ID

### Managing Playlists
- **Sync All Playlists**: Downloads missing tracks from all added playlists
- **Check Missing Tracks**: Shows which tracks haven't been downloaded yet
- **List All Playlists**: View all added playlists
- **Remove Playlist**: Remove a playlist from tracking

### Advanced Usage (Command Line)
```bash
python async_downloader.py \
  --output-dir ./downloads \
  --spotify-client-id YOUR_ID \
  --spotify-client-secret YOUR_SECRET \
  --playlists-file .config/playlists.txt
```

### Configuration Options
You can customize these settings in `.config/.env`:
- `OUTPUT_DIR`: Where to save downloaded files (default: `./downloads`)
- `AUDIO_QUALITY`: Audio quality (default: `320K`)
- `AUDIO_FORMAT`: Output format (default: `mp3`)
- `DOWNLOAD_DELAY`: Delay between downloads in seconds (default: `1.5`)
- `MAX_RETRIES`: Number of retry attempts (default: `3`)
- `SEARCH_WORKERS`: Concurrent search workers (default: `3`)
- `DOWNLOAD_WORKERS`: Concurrent download workers (default: `3`)

---

## 🛠️ Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Ensure your Spotify Developer application has the correct redirect URI
   - Check that your client ID and secret are correct
   - Try deleting the `.cache` file and re-authenticating

2. **FFmpeg Not Found**
   - Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Add it to your system PATH or specify the full path in the config

3. **Download Failures**
   - Check your internet connection
   - Try reducing the number of concurrent downloads
   - Increase the download delay if you're being rate-limited

4. **Missing Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Permission Issues**
   - Ensure you have write permissions for the output directory
   - On Linux/macOS, you might need to use `sudo` or adjust directory permissions

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
