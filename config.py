import os
import streamlit as st

def get_secret(key, default=None):
    """Hae salaisuus joko Streamlit Cloudista tai ympäristömuuttujasta"""
    try:
        return st.secrets[key]
    except:
        return os.getenv(key, default)

# Firebase-asetukset
FIREBASE_CONFIG = {
    "type": "service_account",
    "project_id": get_secret("FIREBASE_PROJECT_ID"),
    "private_key_id": get_secret("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": get_secret("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
    "client_email": get_secret("FIREBASE_CLIENT_EMAIL"),
    "client_id": get_secret("FIREBASE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": get_secret("FIREBASE_CLIENT_CERT_URL"),
}

# Muut asetukset
NHL_API_BASE_URL = "https://api-web.nhle.com/v1"
TOURNAMENT_SEASON = "20252026"
TOURNAMENT_GAME_TYPE = "3"

# Pelisäännöt
TEAM_CONFIG = {
    "forwards_count": 3,
    "defense_count": 2,
    "goalies_count": 1,
    "total_players": 6,
    "min_pin_length": 4,
}

# Pisteet
SCORING = {
    "goal": 3,
    "assist": 2,
    "win": 5,
    "shutout": 3,
}
