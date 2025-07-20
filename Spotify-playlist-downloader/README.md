# Spotify Playlist to YouTube MP3 Downloader

This script lets you download all the songs from any Spotify playlist (even private ones) as MP3 files, by searching for them on YouTube and saving them to your computer. It works fast, can resume if interrupted, and downloads multiple songs at once.

---

## What Does This Script Do?
- Reads your Spotify playlist (public or private)
- Searches YouTube for each song
- Downloads the best match as an MP3 file
- Saves all songs to a folder you choose
- If you stop the script, you can run it again and it will continue where it left off
- Downloads many songs at the same time for speed

---

## What You Need Before You Start

1. **Python 3.8 or newer**
   - Download from [python.org](https://www.python.org/downloads/)
2. **pip** (comes with Python, used to install packages)
3. **ffmpeg**
   - Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Make sure it's in your system PATH (so the script can find it)
4. **A Spotify account**
   - You need to log in to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
5. **A Spotify playlist**
   - Can be public or private

---

## Step-by-Step Setup

### 1. Download the download.py code file.


### 2. Install Python Packages
Open a terminal/command prompt in the script folder and run:
```sh
pip install spotipy yt-dlp
```

### 3. Install ffmpeg
- Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- Follow the instructions for your operating system
- Make sure `ffmpeg` is in your system PATH (so you can run `ffmpeg -version` from any terminal)

### 4. Get Spotify API Credentials
- Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
- Log in with your Spotify account
- Click "Create an App"
- Give it any name and description
- Set the Redirect URI to: `http://127.0.0.1:8000/callback`
- Click "Save"
- Copy your **Client ID** and **Client Secret**

### 5. Configure the Script
- Open downloaded `download.py` in a text editor
- Fill in these lines near the top:
  ```python
  SPOTIFY_CLIENT_ID = "your client id"
  SPOTIFY_CLIENT_SECRET = "your client secret"
  SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8000/callback"  # leave as is unless you know what you're doing
  PLAYLIST_ID = "your spotify playlist url"
  OUTPUT_DIR = r"C:\Users\YourName\Music"  # or any folder you want
  FFMPEG_PATH = "ffmpeg"  # leave as is if ffmpeg is in your PATH
  ```
- Save the file

---

## How to Run the Script

1. Open a terminal/command prompt in the script folder
2. Run:
   ```sh
   python download.py
   ```
3. The script will:
   - Ask you to log in to Spotify (a browser window will open)
   - Ask you to paste a URL from your browser (for authentication)
   - Start searching YouTube and downloading songs
   - Save progress as it goes (you can stop and restart any time)

---

## Features
- **Fast:** Downloads up to 10 songs at once
- **Resumable:** If you stop or lose connection, just run again and it will continue
- **Works with private playlists:** As long as you use your own Spotify credentials
- **No YouTube API key needed:** Uses yt-dlp for searching and downloading

---

## Troubleshooting

- **ffmpeg not found:**
  - Make sure you installed ffmpeg and added it to your PATH
  - Try running `ffmpeg -version` in your terminal
- **Spotify authentication fails:**
  - Double-check your Client ID, Client Secret, and Redirect URI
  - Make sure the Redirect URI in your Spotify app matches exactly what’s in the script
- **Downloads are slow:**
  - Your internet connection or YouTube rate limits may affect speed
  - The script waits a little between searches to avoid being blocked
- **Script stops or crashes:**
  - Just run it again; it will pick up where it left off
- **Permission errors:**
  - Make sure you have write access to the OUTPUT_DIR folder

---

## For Beginners
- You don’t need to know Python to use this script—just follow the steps above
- If you get stuck, search for the error message online or ask for help 
- This script does not require any paid services or subscriptions

---

## Credits
- Built with [spotipy](https://spotipy.readthedocs.io/) and [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- Inspired by the need to easily save Spotify playlists as MP3s

---

Enjoy your music! 