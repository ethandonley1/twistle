from flask_login import LoginManager
from oauthlib.oauth2 import WebApplicationClient
import requests
from config import GOOGLE_CLIENT_ID, GOOGLE_DISCOVERY_URL

login_manager = LoginManager()
client = WebApplicationClient(GOOGLE_CLIENT_ID)

def get_google_provider_cfg():
    return requests.get(GOOGLE_DISCOVERY_URL).json()
