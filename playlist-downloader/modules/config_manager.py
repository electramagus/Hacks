"""
Configuration Manager Module
=============================
Centralized configuration loading and validation.
Handles environment variables, JSON config, and provides defaults.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv


@dataclass
class AppConfig:
    """
    Application configuration data class.
    Provides type-safe access to all configuration parameters.
    """
    # Spotify API Configuration
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str = "http://127.0.0.1:8000/callback"
    
    # Download Settings
    output_dir: str = "./downloads"
    audio_quality: str = "320K"
    audio_format: str = "best"
    download_delay: float = 1.5
    max_retries: int = 3
    
    # Search Settings
    search_delay_min: float = 0.5
    search_delay_max: float = 1.5
    
    # Worker Settings (auto-detected or from config.json)
    search_workers: int = 3
    download_workers: int = 3
    
    # System Paths
    ffmpeg_path: str = "ffmpeg"
    playlists_file: str = ""
    progress_file: str = ""
    
    # Advanced Settings
    start_download_threshold: int = 7
    
    def __post_init__(self):
        """Validate and normalize configuration after initialization."""
        # Ensure output directory exists
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Set dependent file paths if not set
        if not self.playlists_file:
            self.playlists_file = os.path.join(self.output_dir, "playlists.txt")
        if not self.progress_file:
            self.progress_file = os.path.join(self.output_dir, "progress.json")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create config from dictionary."""
        # Filter to only valid fields
        valid_fields = {k: v for k, v in data.items() if k in cls.__annotations__}
        return cls(**valid_fields)


class ConfigManager:
    """
    Manages loading and validation of application configuration.
    
    Loads configuration from multiple sources in priority order:
    1. Environment variables (.env file)
    2. config.json (system resource settings)
    3. Default values
    """
    
    def __init__(self, config_dir: str = ".config", config_json_path: str = "config.json"):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Directory containing .env file
            config_json_path: Path to config.json file
        """
        self.config_dir = Path(config_dir)
        self.env_file = self.config_dir / ".env"
        self.config_json_path = Path(config_json_path)
        self.logger = logging.getLogger(__name__)
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self) -> AppConfig:
        """
        Load complete application configuration.
        
        Returns:
            AppConfig instance with loaded configuration
            
        Raises:
            ValueError: If required configuration is missing
        """
        # Load environment variables
        if self.env_file.exists():
            load_dotenv(dotenv_path=self.env_file)
            self.logger.info(f"Loaded environment from {self.env_file}")
        else:
            self.logger.warning(f"Environment file not found: {self.env_file}")
        
        # Load system resource config
        system_config = self._load_system_config()
        
        # Build configuration from environment variables
        config_data = {
            # Spotify API
            'spotify_client_id': os.getenv('SPOTIFY_CLIENT_ID', ''),
            'spotify_client_secret': os.getenv('SPOTIFY_CLIENT_SECRET', ''),
            'spotify_redirect_uri': os.getenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:8000/callback'),
            
            # Download Settings
            'output_dir': os.getenv('OUTPUT_DIR', './downloads'),
            'audio_quality': os.getenv('AUDIO_QUALITY', '320K'),
            'audio_format': os.getenv('AUDIO_FORMAT', 'best'),
            'download_delay': float(os.getenv('DOWNLOAD_DELAY', '1.5')),
            'max_retries': int(os.getenv('MAX_RETRIES', '3')),
            
            # Search Settings
            'search_delay_min': float(os.getenv('SEARCH_DELAY_MIN', '0.5')),
            'search_delay_max': float(os.getenv('SEARCH_DELAY_MAX', '1.5')),
            
            # Worker Settings (prefer system config)
            'search_workers': system_config.get('max_threads', 3),
            'download_workers': system_config.get('max_processes', 3),
            
            # System Paths
            'ffmpeg_path': os.getenv('FFMPEG_PATH', 'ffmpeg'),
            
            # Advanced Settings
            'start_download_threshold': int(os.getenv('START_DOWNLOAD_THRESHOLD', '7')),
        }
        
        config = AppConfig.from_dict(config_data)
        
        # Validate required fields
        self._validate_config(config)
        
        return config
    
    def _load_system_config(self) -> Dict[str, Any]:
        """
        Load system resource configuration from config.json.
        
        Returns:
            Dictionary with system configuration or empty dict if not found
        """
        if not self.config_json_path.exists():
            self.logger.warning(f"System config not found: {self.config_json_path}")
            return {}
        
        try:
            with open(self.config_json_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.logger.info(f"Loaded system config: {config}")
                return config
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Failed to load system config: {e}")
            return {}
    
    def _validate_config(self, config: AppConfig) -> None:
        """
        Validate that required configuration is present.
        
        Args:
            config: AppConfig instance to validate
            
        Raises:
            ValueError: If required configuration is missing
        """
        if not config.spotify_client_id or not config.spotify_client_secret:
            raise ValueError(
                "Spotify API credentials not configured. "
                f"Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in {self.env_file}"
            )
        
        # Validate numeric ranges
        if config.download_delay < 0:
            raise ValueError("DOWNLOAD_DELAY must be non-negative")
        
        if config.max_retries < 1:
            raise ValueError("MAX_RETRIES must be at least 1")
        
        if config.search_workers < 1 or config.download_workers < 1:
            raise ValueError("Worker counts must be at least 1")
        
        if config.search_delay_min < 0 or config.search_delay_max < config.search_delay_min:
            raise ValueError("Invalid search delay range")
    
    def save_user_preference(self, key: str, value: Any) -> None:
        """
        Save user preference to user.json.
        
        Args:
            key: Preference key
            value: Preference value
        """
        user_file = self.config_dir / "user.json"
        
        # Load existing preferences
        preferences = {}
        if user_file.exists():
            try:
                with open(user_file, 'r', encoding='utf-8') as f:
                    preferences = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        # Update and save
        preferences[key] = value
        try:
            with open(user_file, 'w', encoding='utf-8') as f:
                json.dump(preferences, f, indent=2)
        except IOError as e:
            self.logger.error(f"Failed to save user preference: {e}")
    
    def get_user_preference(self, key: str, default: Any = None) -> Any:
        """
        Get user preference from user.json.
        
        Args:
            key: Preference key
            default: Default value if key not found
            
        Returns:
            Preference value or default
        """
        user_file = self.config_dir / "user.json"
        
        if not user_file.exists():
            return default
        
        try:
            with open(user_file, 'r', encoding='utf-8') as f:
                preferences = json.load(f)
                return preferences.get(key, default)
        except (json.JSONDecodeError, IOError):
            return default


def get_config() -> AppConfig:
    """
    Convenience function to get application configuration.
    
    Returns:
        Loaded AppConfig instance
    """
    manager = ConfigManager()
    return manager.load_config()
