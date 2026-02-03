import streamlit as st
import hashlib
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import requests
import pandas as pd

# --- SETTINGS ---
st.set_page_config(page_title="Olympics Fantasy Hockey 2026", page_icon="◯‍◯‍◯‍◯‍◯")

# --- FIREBASE INITIALIZATION ---
def init_firebase():
    try:
        firebase_admin.get_app()
    except ValueError:
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

import unicodedata

def clean_name(name):
    """
    Siivoaa nimen vertailua varten.
    Muuttaa kaiken pieneksi ja poistaa aksentit (esim. Stützle -> stutzle).
    """
    if not name: return ""
    # Normalisointi: é -> e, ü -> u, jne.
    n = unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8')
    return n.lower().strip()

@st.cache_data(ttl=300)
def fetch_live_scoring_by_name():
    """
    Hakee pisteet ja tallentaa ne avaimella "etunimisukunimi_maa".
    Esim: "sebastianaho_fin": {goals: 1, assists: 1}
    """
    start_date = "2026-02-12"
    end_date = "2026-02-22"
    
    # Sanakirja pisteille: avaimena "nimi_maa"
    live_stats = {} 
    
    # (Tässä sama päivämäärälooppi kuin aiemmin...)
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
                        
                        # Selvitetään joukkueiden lyhenteet (esim. FIN, SWE)
                        away_abbr = game.get('awayTeam', {}).get('abbrev')
                        home_abbr = game.get('homeTeam', {}).get('abbrev')
                        
                        box_url = f"https://api-web.nhle.com/v1/gamecenter/{game['id']}/boxscore"
                        box = requests.get(box_url, timeout=2).json()
                        
                        # Käsitellään pelaajat
                        for team_type, country_code in [('awayTeam', away_abbr), ('homeTeam', home_abbr)]:
                            for group in ['forwards', 'defense', 'goalies']:
                                players = box.get('playerByGameStats', {}).get(team_type, {}).get(group, [])
                                
                                for p in players:
                                    # Rakennetaan nimi APIsta
                                    # NHL API:ssa nimi on usein objektissa name: {default: "Matti Meikäläinen"}
                                    full_name = p.get('name', {}).get('default')
                                    if not full_name:
                                        fn = p.get('firstName', {}).get('default', '')
                                        ln = p.get('lastName', {}).get('default', '')
                                        full_name = f"{fn} {ln}"
                                    
                                    # Luodaan YKSILÖIVÄ avain: "nimi_maa"
                                    # Esim: "sebastianaho_fin"
                                    key = f"{clean_name(full_name)}_{clean_name(country_code)}"
                                    
                                    goals = int(p.get('goals', 0))
                                    assists = int(p.get('assists', 0))
                                    
                                    if key not in live_stats:
                                        live_stats[key] = {'goals': 0, 'assists': 0}
                                    
                                    live_stats[key]['goals'] += goals
                                    live_stats[key]['assists'] += assists
                                    
        except Exception as e:
            print(f"Virhe päivässä {date_str}: {e}")
            
    return live_stats

def get_combined_stats():
    """Yhdistää CSV:n ja API-pisteet nimen+maan perusteella."""
    
    # 1. Lataa CSV (jossa ei tarvitse olla ID:tä)
    try:
        df = pd.read_csv("olympic_players.csv") # Nyt luetaan se alkuperäinen tiedosto
        base_roster = df.to_dict('records')
    except:
        return [] # Tai palauta testidataa

    # 2. Lataa live-pisteet (avaimena "nimi_maa")
    live_scores = fetch_live_scoring_by_name()
    
    final_list = []
    
    for player in base_roster:
        # Rakennetaan sama avain CSV-datasta
        f_name = player['firstName']
        l_name = player['lastName']
        country = player['teamName'] # Esim "FIN", "CAN"
        
        full_name_csv = f"{f_name} {l_name}"
        search_key = f"{clean_name(full_name_csv)}_{clean_name(country)}"
        
        # Haetaan pisteet avaimella
        stats = live_scores.get(search_key, {'goals': 0, 'assists': 0})
        
        # Lisätään listaan
        final_list.append({
            # Huom: Emme tarvitse enää ID:tä UI:ssa, mutta voimme luoda feikin jos tarpeen
            "playerId": search_key, # Käytetään avainta ID:nä, se on uniikki!
            "firstName": {"default": f_name},
            "lastName": {"default": l_name},
            "teamName": {"default": country},
            "position": player['position'],
            "goals": stats['goals'],
            "assists": stats['assists'],
            "points": stats['goals'] + stats['assists']
        })
        
    return final_list


def get_db():
    return init_firebase()

# --- HELPER FUNCTIONS ---
def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def get_nhl_stats():
    """Fetch scoring leaders - use test data if API fails"""
    
    # TEST DATA (4 Nations 2025 players)
    test_players = [
        {"playerId": 8478402, "firstName": {"default": "Connor"}, "lastName": {"default": "McDavid"}, "teamName": {"default": "CAN"}, "position": "C", "goals": 4, "assists": 6, "points": 10},
        {"playerId": 8476453, "firstName": {"default": "Nathan"}, "lastName": {"default": "MacKinnon"}, "teamName": {"default": "CAN"}, "position": "C", "goals": 3, "assists": 7, "points": 10},
        {"playerId": 8477934, "firstName": {"default": "David"}, "lastName": {"default": "Pastrnak"}, "teamName": {"default": "CZE"}, "position": "R", "goals": 5, "assists": 3, "points": 8},
        {"playerId": 8479318, "firstName": {"default": "Auston"}, "lastName": {"default": "Matthews"}, "teamName": {"default": "USA"}, "position": "C", "goals": 4, "assists": 2, "points": 6},
        {"playerId": 8478864, "firstName": {"default": "Kirill"}, "lastName": {"default": "Kaprizov"}, "teamName": {"default": "RUS"}, "position": "L", "goals": 3, "assists": 4, "points": 7},
        {"playerId": 8480027, "firstName": {"default": "Adam"}, "lastName": {"default": "Fox"}, "teamName": {"default": "USA"}, "position": "D", "goals": 1, "assists": 5, "points": 6},
        {"playerId": 8474600, "firstName": {"default": "Roman"}, "lastName": {"default": "Josi"}, "teamName": {"default": "SUI"}, "position": "D", "goals": 2, "assists": 4, "points": 6},
        {"playerId": 8475166, "firstName": {"default": "Johnny"}, "lastName": {"default": "Gaudreau"}, "teamName": {"default": "USA"}, "position": "L", "goals": 2, "assists": 5, "points": 7},
        {"playerId": 8477492, "firstName": {"default": "Elias"}, "lastName": {"default": "Pettersson"}, "teamName": {"default": "SWE"}, "position": "C", "goals": 3, "assists": 3, "points": 6},
        {"playerId": 8478872, "firstName": {"default": "Rasmus"}, "lastName": {"default": "Dahlin"}, "teamName": {"default": "SWE"}, "position": "D", "goals": 1, "assists": 6, "points": 7},
    ]
    
    try:
        url = "https://api-web.nhle.com/v1/skater-stats-leaders/20242025/3?categories=points&limit=50"
        response = requests.get(url, timeout=10)
        data = response.json()
        api_players = data.get("data", [])
        
        if len(api_players) > 0:
            return api_players
            
    except Exception as e:
        st.sidebar.warning("API not responding, using test data")
    
    return test_players

players = get_nhl_stats()
st.sidebar.write(f"Players loaded: {len(players)}")

def calculate_points(player):
    """Calculate fantasy points - 1 point per goal, 1 point per assist"""
    goals = player.get("goals", 0)
    assists = player.get("assists", 0)
    return goals * 1 + assists * 1

# --- DATABASE FUNCTIONS ---
def save_team(team_name, pin, player_ids):
    db = get_db()
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
    teams = []
    for doc in db.collection("teams").stream():
        data = doc.to_dict()
        data["id"] = doc.id
        teams.append(data)
    return teams

# --- USER INTERFACE ---
st.title("◯‍◯‍◯‍◯‍◯ Olympics Fantasy Hockey 2026")
st.caption("Keeping Karlsson Community Fantasy Game")

page = st.sidebar.radio("Menu", ["Home", "Create Team", "My Team", "Leaderboard"])

if page == "Home":
    st.write("""
    ## Welcome to Olympics Fantasy Hockey 2026!
    
    Compete with the Keeping Karlsson community by building your dream team 
    for the 2026 Winter Olympics hockey tournament.
    
    ### How to Play
    1. **Create Your Team**: Select 3 forwards, 2 defensemen, and 1 goalie
    2. **Earn Points**: Players earn points based on their real-life performance
    3. **Climb the Leaderboard**: Compete for the top spot!
    
    ### Scoring System
    | Action | Points |
    |--------|--------|
    | Goal | 1 pt |
    | Assist | 1 pt |
    
    ### Tournament Teams
    🇨🇦 Canada | 🇺🇸 USA | 🇸🇪 Sweden | 🇫🇮 Finland
    
    *More teams to be announced for 2026 Olympics*
    
    **Get started by selecting "Create Team" from the menu!**
    """)

elif page == "Create Team":
    st.header("📝 Create or Edit Your Team")
    
    with st.expander("📋 Team Creation Guide"):
        st.write("""
        **Team Composition:**
        - 3 Forwards (Centers, Left Wing, Right Wing)
        - 2 Defensemen
        - 1 Goalie (coming soon)
        
        **Important:**
        - Choose a unique team name
        - Remember your PIN - you'll need it to edit your team!
        - You can update your team anytime during the tournament
        """)
    
    with st.form("team_form"):
        col1, col2 = st.columns(2)
        with col1:
            team_name = st.text_input("Team Name", placeholder="e.g., Puck Dynasty")
        with col2:
            pin = st.text_input("PIN Code", type="password", placeholder="4-10 digits", help="Used to secure your team")
        
        st.divider()
        st.subheader("Select Your Players")
        
        players = get_nhl_stats()
        
        forwards = [p for p in players if p.get("position") in ["C", "L", "R"]] [:20]
        defense = [p for p in players if p.get("position") == "D"] [:15]
        
        f_options = [f"{p['firstName']['default']} {p['lastName']['default']} ({p['teamName']['default']} - {p['position']})" 
                     for p in forwards]
        d_options = [f"{p['firstName']['default']} {p['lastName']['default']} ({p['teamName']['default']} - {p['position']})" 
                     for p in defense]
        
        st.write(f"**Available Forwards:** {len(f_options)}")
        selected_f = st.multiselect("Choose 3 Forwards (Required)", f_options, max_selections=3)
        
        st.write(f"**Available Defensemen:** {len(d_options)}")
        selected_d = st.multiselect("Choose 2 Defensemen (Required)", d_options, max_selections=2)
        
        st.info(f"Selected: {len(selected_f)} forwards, {len(selected_d)} defensemen (Need: 3F, 2D)")
        
        submit = st.form_submit_button("💾 Save Team", type="primary")
        
        if submit:
            if not team_name:
                st.error("Please enter a team name!")
            elif not pin:
                st.error("Please enter a PIN code!")
            elif len(pin) < 4:
                st.error("PIN must be at least 4 characters!")
            elif len(selected_f) != 3:
                st.error(f"Please select exactly 3 forwards (you selected {len(selected_f)})")
            elif len(selected_d) != 2:
                st.error(f"Please select exactly 2 defensemen (you selected {len(selected_d)})")
            else:
                selected_names = selected_f + selected_d
                player_ids = []
                for name in selected_names:
                    for p in forwards + defense:
                        full_name = f"{p['firstName']['default']} {p['lastName']['default']}"
                        if full_name in name:
                            player_ids.append(str(p["playerId"]))
                            break
                
                success, msg = save_team(team_name, pin, player_ids)
                if success:
                    st.success(msg)
                    st.balloons()
                    st.info(f"Team '{team_name}' created with {len(player_ids)} players!")
                else:
                    st.error(msg)

elif page == "My Team":
    st.header("👤 View Your Team")
    
    st.info("Log in with your team name and PIN to view your roster and points.")
    
    with st.form("login_form"):
        col1, col2 = st.columns(2)
        with col1:
            login_name = st.text_input("Team Name", placeholder="Enter your team name")
        with col2:
            login_pin = st.text_input("PIN Code", type="password", placeholder="Enter your PIN")
        submit = st.form_submit_button("🔓 Log In")
    
    if submit:
        if not login_name or not login_pin:
            st.error("Please enter both team name and PIN!")
        else:
            team = None
            for t in get_all_teams():
                if t["team_name"] == login_name:
                    team = t
                    break
            
            if not team:
                st.error("Team not found! Check your team name or create a new team.")
            elif hash_pin(login_pin) != team.get("pin_hash", ""):
                st.error("Incorrect PIN code! Please try again.")
            else:
                st.success(f"Welcome back, {team['team_name']}!")
                
                st.subheader("Team Roster")
                
                all_players = get_nhl_stats()
                stats_dict = {str(p["playerId"]): p for p in all_players}
                
                total_points = 0
                player_data = []
                
                for pid in team.get("player_ids", []):
                    if pid in stats_dict:
                        p = stats_dict[pid]
                        points = calculate_points(p)
                        total_points += points
                        
                        player_data.append({
                            "Player": f"{p['firstName']['default']} {p['lastName']['default']}",
                            "Team": p['teamName']['default'],
                            "Pos": p['position'],
                            "Goals": p['goals'],
                            "Assists": p['assists'],
                            "Points": points
                        })
                
                if player_data:
                    df = pd.DataFrame(player_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
                    st.divider()
                    cols = st.columns(3)
                    with cols[1]:
                        st.metric("Total Fantasy Points", total_points)
                else:
                    st.warning("No player data available.")

elif page == "Leaderboard":
    st.header("🏆 Tournament Leaderboard")
    
    teams = get_all_teams()
    if not teams:
        st.info("🏒 No teams registered yet. Be the first to create a team!")
    else:
        st.write(f"**{len(teams)} teams competing**")
        
        stats = get_nhl_stats()
        stats_dict = {str(p["playerId"]): p for p in stats}
        
        leaderboard = []
        for team in teams:
            total = 0
            player_count = 0
            top_player = ""
            top_points = 0
            
            for pid in team.get("player_ids", []):
                if pid in stats_dict:
                    p = stats_dict[pid]
                    pts = calculate_points(p)
                    total += pts
                    player_count += 1
                    
                    if pts > top_points:
                        top_points = pts
                        top_player = f"{p['firstName']['default']} {p['lastName']['default']}"
            
            leaderboard.append({
                "Team": team["team_name"],
                "Players": player_count,
                "Top Scorer": top_player if top_player else "-",
                "Fantasy Points": total
            })
        
        df = pd.DataFrame(leaderboard).sort_values("Fantasy Points", ascending=False)
        df.index = range(1, len(df)+1)
        df.index.name = "Rank"
        
        # Highlight top 3
        def highlight_top3(row):
            if row.name <= 3:
                return ['background-color: gold'] * len(row)
            return [''] * len(row)
        
        styled_df = df.style.apply(highlight_top3, axis=1)
        st.dataframe(styled_df, use_container_width=True)
        
        # Show medals for top 3
        if len(df) >= 3:
            st.divider()
            cols = st.columns(3)
            medals = ["🥇", "🥈", "🥉"]
            
            for i in range(3):
                with cols[i]:
                    team = df.iloc[i]
                    st.markdown(f"""
                    <div style='text-align: center; padding: 20px; background-color: {"#FFD700" if i==0 else "#C0C0C0" if i==1 else "#CD7F32"}; border-radius: 10px;'>
                        <div style='font-size: 3rem;'>{medals[i]}</div>
                        <div style='font-size: 1.3rem; font-weight: bold;'>{team['Team']}</div>
                        <div style='font-size: 1.1rem;'>{team['Fantasy Points']} points</div>
                    </div>
                    """, unsafe_allow_html=True)
