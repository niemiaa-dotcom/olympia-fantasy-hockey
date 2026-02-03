import streamlit as st
import hashlib
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import requests
import pandas as pd
import unicodedata

# --- SETTINGS ---
st.set_page_config(page_title="Olympics Fantasy Hockey 2026", page_icon="🏒")

# --- FIREBASE INITIALIZATION ---
def init_firebase():
    try:
        firebase_admin.get_app()
    except ValueError:
        # Hae salaisuudet .streamlit/secrets.toml tiedostosta
        if "FIREBASE_PROJECT_ID" not in st.secrets:
            st.error("Firebase secrets missing!")
            return None
            
        cred_dict = {
            "type": st.secrets.get("FIREBASE_TYPE", "service_account"),
            "project_id": st.secrets["FIREBASE_PROJECT_ID"],
            "private_key_id": st.secrets["FIREBASE_PRIVATE_KEY_ID"],
            "private_key": st.secrets["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
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

# --- DATA PROCESSING FUNCTIONS ---

def clean_name(name):
    """Siivoaa nimen vertailua varten (esim. Stützle -> stutzle)."""
    if not name: return ""
    n = unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8')
    return n.lower().strip()

@st.cache_data(ttl=300)
def fetch_live_scoring_by_name():
    """Hakee pisteet APIsta ja tallentaa ne avaimella 'nimi_maa'."""
    # Kisojen aikataulu
    start_date = "2026-02-12"
    end_date = "2026-02-22"
    
    live_stats = {} 
    
    # Jos kisat eivät ole alkaneet, palautetaan tyhjä (nopeuttaa latausta)
    if datetime.now() < datetime.strptime("2026-02-01", "%Y-%m-%d"):
        return {}

    dates = pd.date_range(start=start_date, end=end_date).strftime('%Y-%m-%d')
    
    for date_str in dates:
        if date_str > datetime.now().strftime('%Y-%m-%d'): break
            
        try:
            schedule_url = f"https://api-web.nhle.com/v1/schedule/{date_str}"
            r = requests.get(schedule_url, timeout=2).json()
            
            day_data = next((d for d in r.get('gameWeek', []) if d['date'] == date_str), None)
            if day_data:
                for game in day_data.get('games', []):
                    if game.get('gameType') == 9: # Olympiapeli
                        
                        away_abbr = game.get('awayTeam', {}).get('abbrev')
                        home_abbr = game.get('homeTeam', {}).get('abbrev')
                        
                        box_url = f"https://api-web.nhle.com/v1/gamecenter/{game['id']}/boxscore"
                        box = requests.get(box_url, timeout=2).json()
                        
                        for team_type, country_code in [('awayTeam', away_abbr), ('homeTeam', home_abbr)]:
                            for group in ['forwards', 'defense', 'goalies']:
                                players = box.get('playerByGameStats', {}).get(team_type, {}).get(group, [])
                                
                                for p in players:
                                    full_name = p.get('name', {}).get('default')
                                    if not full_name:
                                        fn = p.get('firstName', {}).get('default', '')
                                        ln = p.get('lastName', {}).get('default', '')
                                        full_name = f"{fn} {ln}"
                                    
                                    # YKSILÖIVÄ AVAIN
                                    key = f"{clean_name(full_name)}_{clean_name(country_code)}"
                                    
                                    goals = int(p.get('goals', 0))
                                    assists = int(p.get('assists', 0))
                                    
                                    if key not in live_stats:
                                        live_stats[key] = {'goals': 0, 'assists': 0}
                                    
                                    live_stats[key]['goals'] += goals
                                    live_stats[key]['assists'] += assists
        except Exception:
            continue
            
    return live_stats

@st.cache_data(ttl=60)
def get_all_players_data():
    """
    PÄÄFUNKTIO: Lataa pelaajat CSV:stä ja yhdistää live-pisteet.
    Korvaa vanhan 'get_nhl_stats' funktion.
    """
    try:
        # Luetaan CSV
        df = pd.read_csv("olympic_players.csv")
        base_roster = df.to_dict('records')
    except Exception as e:
        # FALLBACK TEST DATA (Jos CSV puuttuu)
        st.warning("Pelaajalistaa (CSV) ei löytynyt, käytetään testidataa.")
        base_roster = [
            {"firstName": "Connor", "lastName": "McDavid", "teamName": "CAN", "position": "F"},
            {"firstName": "Sebastian", "lastName": "Aho", "teamName": "FIN", "position": "F"},
            {"firstName": "Cale", "lastName": "Makar", "teamName": "CAN", "position": "D"},
        ]

    # Lataa live-pisteet
    live_scores = fetch_live_scoring_by_name()
    
    final_list = []
    
    for player in base_roster:
        f_name = str(player['firstName'])
        l_name = str(player['lastName'])
        country = str(player['teamName'])
        pos = str(player['position'])
        
        full_name_csv = f"{f_name} {l_name}"
        # Luodaan sama avain kuin API-haussa
        search_key = f"{clean_name(full_name_csv)}_{clean_name(country)}"
        
        # Haetaan pisteet
        stats = live_scores.get(search_key, {'goals': 0, 'assists': 0})
        
        final_list.append({
            "playerId": search_key, # Nyt ID on "connormcdavid_can"
            "firstName": {"default": f_name},
            "lastName": {"default": l_name},
            "teamName": {"default": country},
            "position": pos,
            "goals": stats['goals'],
            "assists": stats['assists'],
            "points": stats['goals'] + stats['assists']
        })
        
    return final_list

# --- HELPER FUNCTIONS ---
def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def calculate_points(player):
    return player.get("points", 0)

# --- DATABASE FUNCTIONS ---
def save_team(team_name, pin, player_ids):
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

# --- USER INTERFACE ---
st.title("🏒 Olympics Fantasy Hockey 2026")
st.caption("Keeping Karlsson Community Fantasy Game")

# Lataa pelaajat heti alussa
PLAYERS_DATA = get_all_players_data()
st.sidebar.success(f"Loaded {len(PLAYERS_DATA)} players from database.")

page = st.sidebar.radio("Menu", ["Home", "Create Team", "My Team", "Leaderboard"])

if page == "Home":
    st.write("""
    ## Welcome to Olympics Fantasy Hockey 2026!
    
    Build your dream team for the 2026 Winter Olympics.
    
    ### Scoring System
    | Action | Points |
    |--------|--------|
    | Goal | 1 pt |
    | Assist | 1 pt |
    """)

elif page == "Create Team":
    st.header("📝 Create Your Olympic Roster")
    
    # --- 1. LASKETAAN NYKYISET VALINNAT (LIVENÄ) ---
    # Streamlit muistaa checkboxien tilat session_statessa avaimen (key) perusteella.
    # Käymme läpi kaikki pelaajat ja katsomme, onko heidän checkboxinsa 'True'.
    
    current_selection = []
    
    # Luodaan nopea hakemisto pelaajista
    player_map = {p['playerId']: p for p in PLAYERS_DATA}
    
    # Tarkistetaan session_state suoraan
    for pid, p in player_map.items():
        # Avain on muotoa "chk_pelaajaID"
        chk_key = f"chk_{pid}"
        if st.session_state.get(chk_key, False):
            current_selection.append(p)

    # Analysoidaan valinnat
    count_f = 0
    count_d = 0
    countries_selected = []
    
    for p in current_selection:
        # Tulkitaan pelipaikat
        pos = p['position']
        if pos == 'D':
            count_d += 1
        else:
            count_f += 1 # Kaikki muut (F, C, L, R) lasketaan hyökkääjiksi
            
        countries_selected.append(p['teamName']['default'])

    # Etsitään maat, joista on valittu useampi pelaaja
    from collections import Counter
    country_counts = Counter(countries_selected)
    violation_countries = [c for c, count in country_counts.items() if count > 1]

    # --- 2. LIVE DASHBOARD (NÄYTETÄÄN YLÄREUNASSA) ---
    # Käytetään container-elementtiä, jotta se erottuu
    with st.container(border=True):
        st.markdown("### 📊 Live Draft Status")
        
        col1, col2, col3 = st.columns(3)
        
        # Hyökkääjät (Tavoite 7)
        f_delta = count_f - 7
        f_color = "normal"
        if count_f == 7: f_color = "off" # Vihreä efekti metricissä on 'off' kun delta on 0? Ei, käytetään väriä tekstissä.
        
        col1.metric(
            label="Forwards (Goal: 7)", 
            value=f"{count_f} / 7", 
            delta="OK" if count_f == 7 else f"{f_delta}",
            delta_color="normal" if count_f == 7 else "inverse"
        )
        
        # Puolustajat (Tavoite 3)
        d_delta = count_d - 3
        col2.metric(
            label="Defense (Goal: 3)", 
            value=f"{count_d} / 3",
            delta="OK" if count_d == 3 else f"{d_delta}",
            delta_color="normal" if count_d == 3 else "inverse"
        )
        
        # Maa-sääntö
        if not violation_countries:
            col3.success("Country Rule: ✅ OK")
        else:
            col3.error(f"❌ Too many from: {', '.join(violation_countries)}")

    st.divider()

    # --- 3. TEAM DETAILS ---
    c1, c2 = st.columns(2)
    team_name = c1.text_input("Team Name", placeholder="e.g. Miracle on Ice")
    pin = c2.text_input("PIN Code", type="password", placeholder="4-10 digits")
    
    st.subheader("Select Players by Country")

    # --- 4. RENDER PLAYERS (CHECKBOXES) ---
    
    # Ryhmitellään pelaajat maittain
    players_by_country = {}
    for p in PLAYERS_DATA:
        country = p['teamName']['default']
        if country not in players_by_country:
            players_by_country[country] = {'F': [], 'D': []}
        
        pos = p['position']
        if pos == 'D':
            players_by_country[country]['D'].append(p)
        else:
            players_by_country[country]['F'].append(p)
            
    sorted_countries = sorted(players_by_country.keys())
    
    # Luodaan käyttöliittymä
    for country in sorted_countries:
        # Näytetään maan nimi ja onko sieltä valittu joku (visuaalinen apu)
        is_selected = country in countries_selected
        icon = "✅" if is_selected else "🏁"
        
        # Jos maasta on valittu liikaa, väritetään expaderin otsikko punaiseksi (Streamlit ei tue väriä otsikossa suoraan, mutta ikoni auttaa)
        if country in violation_countries: icon = "❌"
        
        with st.expander(f"{icon} {country}"):
            col_f, col_d = st.columns(2)
            
            with col_f:
                st.caption("Forwards")
                for p in players_by_country[country]['F']:
                    # TÄRKEÄÄ: Checkbox päivittää session_statea heti
                    st.checkbox(
                        f"{p['firstName']['default']} {p['lastName']['default']}", 
                        key=f"chk_{p['playerId']}"
                    )
            
            with col_d:
                st.caption("Defensemen")
                for p in players_by_country[country]['D']:
                    st.checkbox(
                        f"{p['firstName']['default']} {p['lastName']['default']}", 
                        key=f"chk_{p['playerId']}"
                    )

    # --- 5. TALLENNUSNAPPI ---
    st.divider()
    
    # Nappi on nyt erillinen, ei formin sisällä.
    if st.button("💾 Save Team", type="primary", use_container_width=True):
        errors = []
        
        # Validointi (uudestaan varmuuden vuoksi)
        if not team_name: errors.append("Missing Team Name.")
        if not pin or len(pin) < 4: errors.append("Invalid PIN (min 4 digits).")
        if count_f != 7: errors.append(f"Select exactly 7 Forwards (Currently: {count_f}).")
        if count_d != 3: errors.append(f"Select exactly 3 Defensemen (Currently: {count_d}).")
        if violation_countries: errors.append(f"Rule violation: Multiple players from {', '.join(violation_countries)}.")
        
        if errors:
            for e in errors:
                st.error(e)
        else:
            # Kerätään ID:t tallennusta varten
            final_ids = [p['playerId'] for p in current_selection]
            
            success, msg = save_team(team_name, pin, final_ids)
            if success:
                st.balloons()
                st.success(f"Team '{team_name}' saved successfully!")
            else:
                st.error(msg)
elif page == "My Team":
    st.header("👤 View Your Team")
    
    with st.form("login_form"):
        c1, c2 = st.columns(2)
        login_name = c1.text_input("Team Name")
        login_pin = c2.text_input("PIN", type="password")
        submit = st.form_submit_button("🔓 Log In")
    
    if submit:
        # Etsi joukkue
        target_team = None
        for t in get_all_teams():
            if t['team_name'] == login_name:
                target_team = t
                break
        
        if target_team and hash_pin(login_pin) == target_team['pin_hash']:
            st.success(f"Team: {target_team['team_name']}")
            
            # Luo hakukartta ID -> Pelaaja
            player_map = {p['playerId']: p for p in PLAYERS_DATA}
            
            team_roster = []
            total_pts = 0
            
            for pid in target_team.get('player_ids', []):
                if pid in player_map:
                    p = player_map[pid]
                    team_roster.append({
                        "Player": f"{p['firstName']['default']} {p['lastName']['default']}",
                        "Country": p['teamName']['default'],
                        "G": p['goals'],
                        "A": p['assists'],
                        "FP": p['points']
                    })
                    total_pts += p['points']
            
            st.dataframe(pd.DataFrame(team_roster), use_container_width=True)
            st.metric("Total Points", total_pts)
            
        else:
            st.error("Invalid Team Name or PIN")

elif page == "Leaderboard":
    st.header("🏆 Leaderboard")
    
    all_teams = get_all_teams()
    player_map = {p['playerId']: p for p in PLAYERS_DATA}
    
    rankings = []
    
    for team in all_teams:
        t_points = 0
        for pid in team.get('player_ids', []):
            if pid in player_map:
                t_points += player_map[pid]['points']
        
        rankings.append({
            "Team": team['team_name'],
            "Points": t_points
        })
    
    df = pd.DataFrame(rankings).sort_values("Points", ascending=False).reset_index(drop=True)
    df.index += 1
    st.dataframe(df, use_container_width=True)
