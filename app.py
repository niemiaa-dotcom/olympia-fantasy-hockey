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

# --- COUNTRY FLAGS USING REGIONAL INDICATOR SYMBOLS ---
# Nämä toimivat paremmin kuin valmiit emoji-liput
def get_flag_emoji(country_code):
    """Luo lippu emoji maatunnuksesta käyttäen Regional Indicator Symbol Letters"""
    OFFSET = 127397  # Unicode offset for regional indicator symbols
    
    if len(country_code) != 2:
        return "🏳️"
    
    flag = ""
    for char in country_code.upper():
        flag += chr(ord(char) + OFFSET)
    return flag

# Fallback jos ylläoleva ei toimi
COUNTRY_FLAGS = {
    "AUS": "🇦🇺", "AUT": "🇦🇹", "BEL": "🇧🇪", "BRA": "🇧🇷", "CAN": "🇨🇦", 
    "CHN": "🇨🇳", "CZE": "🇨🇿", "DEN": "🇩🇰", "EST": "🇪🇪", "FIN": "🇫🇮", 
    "FRA": "🇫🇷", "GER": "🇩🇪", "GBR": "🇬🇧", "HUN": "🇭🇺", "IND": "🇮🇳",
    "IRL": "🇮🇪", "ITA": "🇮🇹", "JPN": "🇯🇵", "KOR": "🇰🇷", "LAT": "🇱🇻",
    "LTU": "🇱🇹", "MEX": "🇲🇽", "NED": "🇳🇱", "NOR": "🇳🇴", "NZL": "🇳🇿",
    "POL": "🇵🇱", "RUS": "🇷🇺", "SVK": "🇸🇰", "SLO": "🇸🇮", "ESP": "🇪🇸",
    "SWE": "🇸🇪", "SUI": "🇨🇭", "UKR": "🇺🇦", "USA": "🇺🇸", "OTHERS": "🌍"
}

def get_flag(code):
    """Hae lippu - yritä ensin dictionaryä, sitten generoi"""
    code = code.upper() if code else "OTHERS"
    if code in COUNTRY_FLAGS:
        return COUNTRY_FLAGS[code]
    elif len(code) == 2:
        return get_flag_emoji(code)
    return "🏒"

# Olympics participants + major countries
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
def clean_name(name):
    if not name: return ""
    n = unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8')
    return n.lower().strip()

@st.cache_data(ttl=300)
def fetch_live_scoring_by_name():
    return {}  # Simplified for now

@st.cache_data(ttl=60)
def get_all_players_data():
    # Simplified test data
    test_players = [
        {"playerId": "1_CAN", "firstName": {"default": "Connor"}, "lastName": {"default": "McDavid"}, "teamName": {"default": "CAN"}, "position": "F", "goals": 4, "assists": 6, "points": 10},
        {"playerId": "2_CAN", "firstName": {"default": "Nathan"}, "lastName": {"default": "MacKinnon"}, "teamName": {"default": "CAN"}, "position": "F", "goals": 3, "assists": 7, "points": 10},
        {"playerId": "3_CAN", "firstName": {"default": "Cale"}, "lastName": {"default": "Makar"}, "teamName": {"default": "CAN"}, "position": "D", "goals": 2, "assists": 5, "points": 7},
        {"playerId": "4_CAN", "firstName": {"default": "Sidney"}, "lastName": {"default": "Crosby"}, "teamName": {"default": "CAN"}, "position": "F", "goals": 2, "assists": 4, "points": 6},
        {"playerId": "1_FIN", "firstName": {"default": "Sebastian"}, "lastName": {"default": "Aho"}, "teamName": {"default": "FIN"}, "position": "F", "goals": 3, "assists": 3, "points": 6},
        {"playerId": "2_FIN", "firstName": {"default": "Patrik"}, "lastName": {"default": "Laine"}, "teamName": {"default": "FIN"}, "position": "F", "goals": 4, "assists": 1, "points": 5},
        {"playerId": "3_FIN", "firstName": {"default": "Miro"}, "lastName": {"default": "Heiskanen"}, "teamName": {"default": "FIN"}, "position": "D", "goals": 1, "assists": 4, "points": 5},
        {"playerId": "1_SWE", "firstName": {"default": "William"}, "lastName": {"default": "Nylander"}, "teamName": {"default": "SWE"}, "position": "F", "goals": 4, "assists": 2, "points": 6},
        {"playerId": "2_SWE", "firstName": {"default": "Elias"}, "lastName": {"default": "Pettersson"}, "teamName": {"default": "SWE"}, "position": "F", "goals": 3, "assists": 3, "points": 6},
        {"playerId": "3_SWE", "firstName": {"default": "Rasmus"}, "lastName": {"default": "Dahlin"}, "teamName": {"default": "SWE"}, "position": "D", "goals": 1, "assists": 6, "points": 7},
        {"playerId": "1_USA", "firstName": {"default": "Jack"}, "lastName": {"default": "Eichel"}, "teamName": {"default": "USA"}, "position": "F", "goals": 3, "assists": 4, "points": 7},
        {"playerId": "2_USA", "firstName": {"default": "Auston"}, "lastName": {"default": "Matthews"}, "teamName": {"default": "USA"}, "position": "F", "goals": 4, "assists": 2, "points": 6},
        {"playerId": "3_USA", "firstName": {"default": "Adam"}, "lastName": {"default": "Fox"}, "teamName": {"default": "USA"}, "position": "D", "goals": 1, "assists": 5, "points": 6},
    ]
    return test_players

def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def calculate_points(player):
    return player.get("points", 0)

# --- DATABASE FUNCTIONS ---
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

def get_country_leaderboard():
    """Calculate country leaderboard with 'Others' grouping"""
    teams = get_all_teams()
    player_map = {p['playerId']: p for p in PLAYERS_DATA}
    
    country_points = defaultdict(list)
    
    for team in teams:
        manager_country = team.get("manager_country", "OTHERS")
        total = 0
        for pid in team.get('player_ids', []):
            if pid in player_map:
                total += player_map[pid]['points']
        country_points[manager_country].append(total)
    
    final_stats = defaultdict(lambda: {"points": [], "managers": 0, "countries": []})
    
    for country, points_list in country_points.items():
        if len(points_list) <= 3:
            final_stats["OTHERS"]["points"].extend(points_list)
            final_stats["OTHERS"]["managers"] += len(points_list)
            final_stats["OTHERS"]["countries"].append(country)
        else:
            final_stats[country]["points"] = points_list
            final_stats[country]["managers"] = len(points_list)
            final_stats[country]["countries"] = [country]
    
    results = []
    for group_code, data in final_stats.items():
        if data["managers"] > 0:
            avg = sum(data["points"]) / len(data["points"]) if data["points"] else 0
            results.append({
                "code": group_code,
                "name": "Others" if group_code == "OTHERS" else ALL_COUNTRIES.get(group_code, group_code),
                "managers": data["managers"],
                "countries": data["countries"],
                "avg_points": round(avg, 1),
                "total_points": sum(data["points"]),
                "best_score": max(data["points"]) if data["points"] else 0
            })
    
    results.sort(key=lambda x: x["avg_points"], reverse=True)
    return results

# --- USER INTERFACE ---
st.title("🏒 Olympics Fantasy Hockey 2026")
st.caption("Keeping Karlsson Community Fantasy Game")

PLAYERS_DATA = get_all_players_data()

page = st.sidebar.radio("Menu", ["Home", "Create Team", "Countries"])

if page == "Home":
    st.write("Testaa lippuja:")
    cols = st.columns(5)
    test_countries = ["FIN", "SWE", "CAN", "USA", "CZE"]
    for i, code in enumerate(test_countries):
        with cols[i]:
            flag = get_flag(code)
            st.markdown(f"<div style='font-size: 4rem; text-align: center;'>{flag}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align: center;'>{code}</div>", unsafe_allow_html=True)

elif page == "Create Team":
    st.header("📝 Create Your Team")
    
    # MANAGER COUNTRY - YKSINKERTAISTETTU VERSIO
    st.subheader("🌍 Manager Nationality")
    
    # Käytä selectboxia ilman lippuja labelissa, näytä lippu erikseen
    manager_country = st.selectbox(
        "Select your country",
        options=list(ALL_COUNTRIES.keys()),
        format_func=lambda x: f"{ALL_COUNTRIES[x]}"
    )
    
    # Näytä valittu lippu isona
    selected_flag = get_flag(manager_country)
    st.markdown(f"<div style='font-size: 5rem; margin: -20px 0 20px 0;'>{selected_flag}</div>", unsafe_allow_html=True)
    
    # Testaa pelaajien liput
    st.subheader("Available Players")
    
    players_by_country = {}
    for p in PLAYERS_DATA:
        country = p['teamName']['default']
        if country not in players_by_country:
            players_by_country[country] = {'F': [], 'D': []}
        
        pos = p['position']
        if pos in ['C', 'L', 'R', 'F']:
            players_by_country[country]['F'].append(p)
        elif pos == 'D':
            players_by_country[country]['D'].append(p)
    
    for country in sorted(players_by_country.keys()):
        flag = get_flag(country)
        
        # Käytä HTML:n emoji-merkkejä suoraan
        with st.expander(f"{flag} {country}"):
            for p in players_by_country[country]['F']:
                st.write(f"- {p['firstName']['default']} {p['lastName']['default']}")

elif page == "Countries":
    st.header("🌍 Countries Competition")
    
    # Testaa lippuja
    st.write("Flag test:")
    for code in ["FIN", "SWE", "CAN", "USA", "CZE", "SUI", "GER"]:
        flag = get_flag(code)
        st.write(f"{flag} {code} = {ALL_COUNTRIES[code]}")

