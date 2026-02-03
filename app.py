import streamlit as st
import hashlib
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import requests
import pandas as pd
import unicodedata
from collections import defaultdict

# --- SETTINGS ---
st.set_page_config(page_title="Olympics Fantasy Hockey 2026", page_icon="🏒")

# --- COUNTRY FLAGS AS IMAGES ---
def get_flag_image_html(country_code, size=30):
    """Generoi HTML img tagi lipulle flagcdn.com:sta"""
    code = country_code.lower()
    return f'<img src="https://flagcdn.com/w{size}/{code}.png" width="{size}" alt="{country_code}">'

def get_flag_emoji(country_code):
    """Unicode emoji fallback"""
    OFFSET = 127397
    if len(country_code) != 2:
        return "🏳️"
    flag = ""
    for char in country_code.upper():
        flag += chr(ord(char) + OFFSET)
    return flag

# Yhdistä kuva + emoji
ALL_COUNTRIES = {
    "AUS": "Australia", "AUT": "Austria", "BEL": "Belgium", "BRA": "Brazil",
    "CAN": "Canada", "CHN": "China", "CZE": "Czechia", "DEN": "Denmark",
    "EST": "Estonia", "FIN": "Finland", "FRA": "France", "GER": "Germany",
    "GBR": "Great Britain", "HUN": "Hungary", "IND": "India", "IRL": "Ireland",
    "ITA": "Italy", "JPN": "Japan", "KOR": "South Korea", "LAT": "Latvia",
    "LTU": "Lithuania", "MEX": "Mexico", "NED": "Netherlands", "NOR": "Norway",
    "NZL": "New Zealand", "POL": "Poland", "RUS": "Russia", "SVK": "Slovakia",
    "SLO": "Slovenia", "ESP": "Spain", "SWE": "Sweden", "SUI": "Switzerland",
    "UKR": "Ukraine", "USA": "United States"
}

OLYMPIC_TEAMS = ["CAN", "CZE", "DEN", "FIN", "FRA", "GER", "ITA", "LAT", 
                 "SVK", "SWE", "SUI", "USA"]

# --- FIREBASE ---
def init_firebase():
    try:
        firebase_admin.get_app()
    except ValueError:
        if "FIREBASE_PROJECT_ID" not in st.secrets:
            return None
        cred_dict = {
            "type": st.secrets.get("FIREBASE_TYPE", "service_account"),
            "project_id": st.secrets["FIREBASE_PROJECT_ID"],
            "private_key_id": st.secrets["FIREBASE_PRIVATE_KEY_ID"],
            "private_key": st.secrets["FIREBASE_PRIVATE_KEY"].replace("\\\\n", "\n"),
            "client_email": st.secrets["FIREBASE_CLIENT_EMAIL"],
            "client_id": st.secrets["FIREBASE_CLIENT_ID"],
            "auth_uri": st.secrets.get("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": st.secrets.get("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
            "auth_provider_x509_cert_url": st.secrets.get("FIREBASE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs"),
            "client_x509_cert_url": st.secrets["FIREBASE_CLIENT_X509_CERT_URL"],
        }
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

def get_db():
    return init_firebase()

# --- DATA FUNCTIONS ---
@st.cache_data(ttl=60)
def get_all_players_data():
    # Test data
    test_players = [
        {"playerId": "1_CAN", "firstName": {"default": "Connor"}, "lastName": {"default": "McDavid"}, "teamName": {"default": "CAN"}, "position": "F", "goals": 4, "assists": 6, "points": 10},
        {"playerId": "2_CAN", "firstName": {"default": "Nathan"}, "lastName": {"default": "MacKinnon"}, "teamName": {"default": "CAN"}, "position": "F", "goals": 3, "assists": 7, "points": 10},
        {"playerId": "3_CAN", "firstName": {"default": "Cale"}, "lastName": {"default": "Makar"}, "teamName": {"default": "CAN"}, "position": "D", "goals": 2, "assists": 5, "points": 7},
        {"playerId": "1_FIN", "firstName": {"default": "Sebastian"}, "lastName": {"default": "Aho"}, "teamName": {"default": "FIN"}, "position": "F", "goals": 3, "assists": 3, "points": 6},
        {"playerId": "2_FIN", "firstName": {"default": "Miro"}, "lastName": {"default": "Heiskanen"}, "teamName": {"default": "FIN"}, "position": "D", "goals": 1, "assists": 4, "points": 5},
        {"playerId": "1_SWE", "firstName": {"default": "William"}, "lastName": {"default": "Nylander"}, "teamName": {"default": "SWE"}, "position": "F", "goals": 4, "assists": 2, "points": 6},
        {"playerId": "2_SWE", "firstName": {"default": "Rasmus"}, "lastName": {"default": "Dahlin"}, "teamName": {"default": "SWE"}, "position": "D", "goals": 1, "assists": 6, "points": 7},
        {"playerId": "1_USA", "firstName": {"default": "Jack"}, "lastName": {"default": "Eichel"}, "teamName": {"default": "USA"}, "position": "F", "goals": 3, "assists": 4, "points": 7},
        {"playerId": "2_USA", "firstName": {"default": "Adam"}, "lastName": {"default": "Fox"}, "teamName": {"default": "USA"}, "position": "D", "goals": 1, "assists": 5, "points": 6},
    ]
    return test_players

def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def calculate_points(player):
    return player.get("points", 0)

def save_team(team_name, pin, player_ids, manager_country):
    db = get_db()
    if not db: return False, "Database connection failed"
    
    team_ref = db.collection("teams").document(team_name)
    
    if team_ref.get().exists:
        old_data = team_ref.get().to_dict()
        if hash_pin(pin) != old_data.get("pin_hash"):
            return False, "Wrong PIN code!"
    
    team_ref.set({
        "team_name": team_name,
        "pin_hash": hash_pin(pin),
        "player_ids": player_ids,
        "manager_country": manager_country,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    })
    return True, "Team saved successfully!"

def get_all_teams():
    db = get_db()
    if not db: return []
    
    teams = []
    for doc in db.collection("teams").stream():
        data = doc.to_dict()
        data["id"] = doc.id
        teams.append(data)
    return teams

# --- UI ---
st.title("🏒 Olympics Fantasy Hockey 2026")
st.caption("Keeping Karlsson Community Fantasy Game")

PLAYERS_DATA = get_all_players_data()

page = st.sidebar.radio("Menu", ["Home", "Create Team", "Test Flags"])

if page == "Home":
    st.write("Welcome!")

elif page == "Test Flags":
    st.header("Flag Test - Images")
    
    cols = st.columns(4)
    test_countries = ["FIN", "SWE", "CAN", "USA", "CZE", "SUI", "GER", "LAT"]
    
    for i, code in enumerate(test_countries):
        with cols[i % 4]:
            flag_html = get_flag_image_html(code, 80)
            st.markdown(f"""
            <div style="text-align: center; padding: 10px;">
                {flag_html}
                <br>
                <b>{ALL_COUNTRIES.get(code, code)}</b>
            </div>
            """, unsafe_allow_html=True)

elif page == "Create Team":
    st.header("📝 Create Your Team")
    
    # MANAGER COUNTRY WITH FLAG IMAGE
    st.subheader("🌍 Manager Nationality")
    
    manager_country = st.selectbox(
        "Select your country",
        options=list(ALL_COUNTRIES.keys()),
        format_func=lambda x: ALL_COUNTRIES[x]
    )
    
    # Näytä valittu lippu KUVANA
    flag_img = get_flag_image_html(manager_country, 60)
    st.markdown(f"""
    <div style="margin: 10px 0;">
        {flag_img}
        <span style="font-size: 1.2rem; margin-left: 10px;"><b>{ALL_COUNTRIES[manager_country]}</b></span>
    </div>
    """, unsafe_allow_html=True)
    
    # Pelaajat maittain
    st.subheader("Select Players by Country")
    
    players_by_country = {}
    for p in PLAYERS_DATA:
        country = p['teamName']['default']
        if country not in players_by_country:
            players_by_country[country] = []
        players_by_country[country].append(p)
    
    for country in sorted(players_by_country.keys()):
        flag_html = get_flag_image_html(country, 25)
        
        with st.expander(f"{ALL_COUNTRIES[country]}"):
            # Näytä lippu expanderin sisälläkin
            st.markdown(f"Country: {flag_html} <b>{country}</b>", unsafe_allow_html=True)
            
            for p in players_by_country[country]:
                st.checkbox(f"{p['firstName']['default']} {p['lastName']['default']} ({p['position']})")

