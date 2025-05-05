"""
Configuration settings for Twistle
"""
import os
import json
from pathlib import Path

# Get the base directory
BASE_DIR = Path(__file__).resolve().parent.parent

def load_google_credentials():
    """Load Google OAuth credentials from JSON file or environment variables"""
    creds_file = BASE_DIR / 'credentials' / 'google_client_secret.json'
    
    try:
        with open(creds_file) as f:
            creds = json.load(f)
            return {
                'client_id': creds.get('web', {}).get('client_id'),
                'client_secret': creds.get('web', {}).get('client_secret')
            }
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # Fallback to environment variables
        return {
            'client_id': os.getenv('GOOGLE_CLIENT_ID', ''),
            'client_secret': os.getenv('GOOGLE_CLIENT_SECRET', '')
        }

# Game settings
GAME_CONFIG = {
    'random_mode': False,  # Set to True to get random games instead of daily games
    'word_time_limit': 30,  # Time limit per word in seconds
    'max_attempts': 3,     # Maximum attempts per word
    'hint_delay': 10,      # Seconds before hint becomes available
    'shuffle_limit': 2,    # Maximum number of shuffles allowed per word
    'anagram_bonus': 10,  # Bonus points for using an anagram
    'bonus_time': 10,  # Bonus time for using an anagram
    'time_boost': 15,  # Amount of time added by the time boost button
    'debug_mode': False,  # Enable debug controls (should be False in production)
}

# Load from environment variables if present
GAME_CONFIG['random_mode'] = os.getenv('TWISTLE_RANDOM_MODE', '').lower() == 'true'

# Load Google OAuth Settings
google_creds = load_google_credentials()
GOOGLE_CLIENT_ID = google_creds['client_id']
GOOGLE_CLIENT_SECRET = google_creds['client_secret']
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
