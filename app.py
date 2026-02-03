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

st.set_page_config(page_title="Olympics Fantasy Hockey 2026", page_icon="🏒")

# --- FLAGS ---
def get_flag_image_html(country_code, size=30):
    code = country_code.lower() if country_code else "xx"
    return f'<img src="https://flagcdn.com/w{size}/{code}.png" width="{size}" alt="{country_code}">'

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

# --- DATA ---
@st.cache_data(ttl=60)
def get_all_players_data():
    test_players = [
        {"playerId": "mcdavid_can", "firstName": {"default": "Connor"}, "lastName": {"default": "McDavid"}, "teamName": {"default": "CAN"}, "position": "F", "goals": 4, "assists": 6, "points": 10},
        {"playerId": "mackinnon_can", "firstName": {"default": "Nathan"}, "lastName": {"default": "MacKinnon"}, "teamName": {"default": "CAN"}, "position": "F", "goals": 3, "assists": 7, "points": 10},
        {"playerId": "makara_can", "firstName": {"default": "Cale"}, "lastName": {"default": "Makar"}, "teamName": {"default": "CAN"}, "position": "D", "goals": 2, "assists": 5, "points": 7},
        {"playerId": "crosby_can", "firstName": {"default": "Sidney"}, "lastName": {"default": "Crosby"}, "teamName": {"default": "CAN"}, "position": "F", "goals": 2, "assists": 4, "points": 6},
        {"playerId": "aho_fin", "firstName": {"default": "Sebastian"}, "lastName": {"default": "Aho"}, "teamName": {"default": "FIN"}, "position": "F", "goals": 3, "assists": 3, "points": 6},
        {"playerId": "laine_fin", "firstName": {"default": "Patrik"}, "lastName": {"default": "Laine"}, "teamName": {"default": "FIN"}, "position": "F", "goals": 4, "assists": 1, "points": 5},
        {"playerId": "heiskanen_fin", "firstName": {"default": "Miro"}, "lastName": {"default": "Heiskanen"}, "teamName": {"default": "FIN"}, "position": "D", "goals": 1, "assists": 4, "points": 5},
        {"playerId": "nylander_swe", "firstName": {"default": "William"}, "lastName": {"default": "Nylander"}, "teamName": {"default": "SWE"}, "position": "F", "goals": 4, "assists": 2, "points": 6},
        {"playerId": "pettersson_swe", "firstName": {"default": "Elias"}, "lastName": {"default": "Pettersson"}, "teamName": {"default": "SWE"}, "position": "F", "goals": 3, "assists": 3, "points": 6},
        {"playerId": "dahlin_swe", "firstName": {"default": "Rasmus"}, "lastName": {"default": "Dahlin"}, "teamName": {"default": "SWE"}, "position": "D", "goals": 1, "assists": 6, "points": 7},
        {"playerId": "eichel_usa", "firstName": {"default": "Jack"}, "lastName": {"default": "Eichel"}, "teamName": {"default": "USA"}, "position": "F", "goals": 3, "assists": 4, "points": 7},
        {"playerId": "matthews_usa", "firstName": {"default": "Auston"}, "lastName": {"default": "Matthews"}, "teamName": {"default": "USA"}, "position": "F", "goals": 4, "assists": 2, "points": 6},
        {"playerId": "fox_usa", "firstName": {"default": "Adam"}, "lastName": {"default": "Fox"}, "teamName": {"default": "USA"}, "position": "D", "goals": 1, "assists": 5, "points": 6},
    ]
    return test_players

def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

# --- DATABASE ---
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

# --- UI ---
st.title("🏒 Olympics Fantasy Hockey 2026")
st.caption("Keeping Karlsson Community Fantasy Game")

PLAYERS_DATA = get_all_players_data()
player_map = {p['playerId']: p for p in PLAYERS_DATA}

# Prepare data by country
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

page = st.sidebar.radio("Menu", ["Create Team"])

if page == "Create Team":
    st.header("📝 Create Your Team")
    
    # Initialize session state for selected players
    if 'selected_players' not in st.session_state:
        st.session_state.selected_players = []
    
    # TEAM INFO
    col1, col2 = st.columns(2)
    team_name = col1.text_input("Team Name", placeholder="e.g. Miracle on Ice")
    pin = col2.text_input("PIN Code", type="password", placeholder="4-10 digits")
    
    # MANAGER COUNTRY
    st.subheader("🌍 Manager Nationality")
    
    manager_country = st.selectbox(
        "Select your country",
        options=list(ALL_COUNTRIES.keys()),
        format_func=lambda x: ALL_COUNTRIES[x]
    )
    
    flag_img = get_flag_image_html(manager_country, 60)
    st.markdown(f"""
    <div style="margin: 10px 0;">
        {flag_img}
        <span style="font-size: 1.2rem; margin-left: 10px;"><b>{ALL_COUNTRIES[manager_country]}</b></span>
    </div>
    """, unsafe_allow_html=True)
    
    # --- REAL-TIME DRAFT STATUS ---
    # Calculate current status from session state
    current_selected = st.session_state.selected_players
    
    stats_counts = {'F': 0, 'D': 0}
    country_counts = {}
    
    for pid in current_selected:
        if pid in player_map:
            p = player_map[pid]
            pos = 'D' if p['position'] == 'D' else 'F'
            stats_counts[pos] += 1
            ctry = p['teamName']['default']
            country_counts[ctry] = country_counts.get(ctry, 0) + 1
    
    # Show status BEFORE player selection (updates in real-time!)
    st.divider()
    status_container = st.container()
    
    with status_container:
        st.subheader("📊 Draft Status")
        
        s1, s2, s3 = st.columns(3)
        
        f_color = "🟢" if stats_counts['F'] == 7 else "🔴"
        s1.metric("Forwards", f"{stats_counts['F']} / 7")
        
        d_color = "🟢" if stats_counts['D'] == 3 else "🔴"
        s2.metric("Defensemen", f"{stats_counts['D']} / 3")
        
        violation_countries = [c for c, count in country_counts.items() if count > 1]
        if not violation_countries:
            s3.success("1-Player/Nation: OK")
        else:
            s3.error(f"1-Player/Nation: VIOLATION")
            s3.write(f"Duplicates: {', '.join(violation_countries)}")
    
    # --- PLAYER SELECTION (Outside form for real-time updates) ---
    st.divider()
    st.subheader("Select Players")
    
    # Use checkboxes outside form - updates session state immediately
    for country in sorted(players_by_country.keys()):
        flag_html = get_flag_image_html(country, 25)
        
        with st.expander(f"{ALL_COUNTRIES[country]} {flag_html}", expanded=False):
            cols = st.columns(2)
            
            with cols[0]:
                st.markdown("**Forwards**")
                for p in players_by_country[country]['F']:
                    player_id = p['playerId']
                    is_selected = player_id in st.session_state.selected_players
                    
                    if st.checkbox(
                        f"{p['firstName']['default']} {p['lastName']['default']}", 
                        value=is_selected,
                        key=f"cb_{player_id}"
                    ):
                        if player_id not in st.session_state.selected_players:
                            st.session_state.selected_players.append(player_id)
                    else:
                        if player_id in st.session_state.selected_players:
                            st.session_state.selected_players.remove(player_id)
                            
            with cols[1]:
                st.markdown("**Defensemen**")
                for p in players_by_country[country]['D']:
                    player_id = p['playerId']
                    is_selected = player_id in st.session_state.selected_players
                    
                    if st.checkbox(
                        f"{p['firstName']['default']} {p['lastName']['default']}", 
                        value=is_selected,
                        key=f"cb_{player_id}"
                    ):
                        if player_id not in st.session_state.selected_players:
                            st.session_state.selected_players.append(player_id)
                    else:
                        if player_id in st.session_state.selected_players:
                            st.session_state.selected_players.remove(player_id)
    
    # Show selected players summary
    if st.session_state.selected_players:
        st.divider()
        st.subheader("Selected Players")
        selected_data = []
        for pid in st.session_state.selected_players:
            if pid in player_map:
                p = player_map[pid]
                selected_data.append({
                    "Player": f"{p['firstName']['default']} {p['lastName']['default']}",
                    "Country": p['teamName']['default'],
                    "Pos": p['position']
                })
        st.dataframe(pd.DataFrame(selected_data), hide_index=True)
    
    # SAVE BUTTON (separate form only for validation and saving)
    st.divider()
    
    if st.button("💾 Validate & Save Team", type="primary"):
        errors = []
        
        if not team_name:
            errors.append("Missing Team Name.")
        if not pin or len(pin) < 4:
            errors.append("Invalid PIN.")
        if stats_counts['F'] != 7:
            errors.append(f"Need 7 Forwards (Selected: {stats_counts['F']}).")
        if stats_counts['D'] != 3:
            errors.append(f"Need 3 Defensemen (Selected: {stats_counts['D']}).")
        if violation_countries:
            errors.append(f"Multiple players from: {', '.join(violation_countries)}")
        
        if errors:
            for e in errors:
                st.error(e)
        else:
            success, msg = save_team(team_name, pin, st.session_state.selected_players, manager_country)
            if success:
                st.balloons()
                st.success(f"Team '{team_name}' saved! Representing {ALL_COUNTRIES[manager_country]}!")
                st.session_state.selected_players = []  # Clear after save
                st.rerun()
            else:
                st.error(msg)

