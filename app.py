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

# --- COUNTRY FLAGS & LIST ---
COUNTRY_FLAGS = {
    "AUS": "🇦🇺", "AUT": "🇦🇹", "BEL": "🇧🇪", "BRA": "🇧🇷", "CAN": "🇨🇦", 
    "CHN": "🇨🇳", "CZE": "🇨🇿", "DEN": "🇩🇰", "EST": "🇪🇪", "FIN": "🇫🇮", 
    "FRA": "🇫🇷", "GER": "🇩🇪", "GBR": "🇬🇧", "HUN": "🇭🇺", "IND": "🇮🇳",
    "IRL": "🇮🇪", "ITA": "🇮🇹", "JPN": "🇯🇵", "KOR": "🇰🇷", "LAT": "🇱🇻",
    "LTU": "🇱🇹", "MEX": "🇲🇽", "NED": "🇳🇱", "NOR": "🇳🇴", "NZL": "🇳🇿",
    "POL": "🇵🇱", "RUS": "🇷🇺", "SVK": "🇸🇰", "SLO": "🇸🇮", "ESP": "🇪🇸",
    "SWE": "🇸🇪", "SUI": "🇨🇭", "UKR": "🇺🇦", "USA": "🇺🇸", "OTHERS": "🌍"
}

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

def get_flag(code):
    return COUNTRY_FLAGS.get(code, "🏒")

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

# --- DATA FUNCTIONS ---
def clean_name(name):
    if not name: return ""
    n = unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8')
    return n.lower().strip()

@st.cache_data(ttl=300)
def fetch_live_scoring_by_name():
    start_date = "2026-02-12"
    end_date = "2026-02-22"
    live_stats = {}
    
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
                    if game.get('gameType') == 9:
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
    try:
        df = pd.read_csv("olympic_players.csv")
        base_roster = df.to_dict('records')
    except Exception:
        # Fallback test data
        base_roster = [
            {"firstName": "Connor", "lastName": "McDavid", "teamName": "CAN", "position": "F"},
            {"firstName": "Nathan", "lastName": "MacKinnon", "teamName": "CAN", "position": "F"},
            {"firstName": "Cale", "lastName": "Makar", "teamName": "CAN", "position": "D"},
            {"firstName": "Sidney", "lastName": "Crosby", "teamName": "CAN", "position": "F"},
            {"firstName": "Leon", "lastName": "Draisaitl", "teamName": "GER", "position": "F"},
            {"firstName": "Tim", "lastName": "Stutzle", "teamName": "GER", "position": "F"},
            {"firstName": "Moritz", "lastName": "Seider", "teamName": "GER", "position": "D"},
            {"firstName": "Sebastian", "lastName": "Aho", "teamName": "FIN", "position": "F"},
            {"firstName": "Patrik", "lastName": "Laine", "teamName": "FIN", "position": "F"},
            {"firstName": "Miro", "lastName": "Heiskanen", "teamName": "FIN", "position": "D"},
            {"firstName": "William", "lastName": "Nylander", "teamName": "SWE", "position": "F"},
            {"firstName": "Elias", "lastName": "Pettersson", "teamName": "SWE", "position": "F"},
            {"firstName": "Rasmus", "lastName": "Dahlin", "teamName": "SWE", "position": "D"},
            {"firstName": "Jack", "lastName": "Eichel", "teamName": "USA", "position": "F"},
            {"firstName": "Auston", "lastName": "Matthews", "teamName": "USA", "position": "F"},
            {"firstName": "Adam", "lastName": "Fox", "teamName": "USA", "position": "D"},
            {"firstName": "David", "lastName": "Pastrnak", "teamName": "CZE", "position": "F"},
            {"firstName": "Roman", "lastName": "Josi", "teamName": "SUI", "position": "D"},
            {"firstName": "Kevin", "lastName": "Fiala", "teamName": "SUI", "position": "F"},
        ]

    live_scores = fetch_live_scoring_by_name()
    
    final_list = []
    for player in base_roster:
        f_name = str(player['firstName'])
        l_name = str(player['lastName'])
        country = str(player['teamName'])
        pos = str(player['position'])
        
        full_name = f"{f_name} {l_name}"
        search_key = f"{clean_name(full_name)}_{clean_name(country)}"
        
        stats = live_scores.get(search_key, {'goals': 0, 'assists': 0})
        
        final_list.append({
            "playerId": search_key,
            "firstName": {"default": f_name},
            "lastName": {"default": l_name},
            "teamName": {"default": country},
            "position": pos,
            "goals": stats['goals'],
            "assists": stats['assists'],
            "points": stats['goals'] + stats['assists']
        })
    return final_list

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
        "manager_country": manager_country,  # NEW FIELD
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
    
    # Collect all points by manager's country
    country_points = defaultdict(list)
    
    for team in teams:
        manager_country = team.get("manager_country", "OTHERS")
        total = 0
        for pid in team.get('player_ids', []):
            if pid in player_map:
                total += player_map[pid]['points']
        country_points[manager_country].append(total)
    
    # Group small countries (<=3 managers) into OTHERS
    final_stats = defaultdict(lambda: {"points": [], "managers": 0, "countries": []})
    
    for country, points_list in country_points.items():
        if len(points_list) <= 3:
            # Add to OTHERS
            final_stats["OTHERS"]["points"].extend(points_list)
            final_stats["OTHERS"]["managers"] += len(points_list)
            final_stats["OTHERS"]["countries"].append(country)
        else:
            # Keep separate
            final_stats[country]["points"] = points_list
            final_stats[country]["managers"] = len(points_list)
            final_stats[country]["countries"] = [country]
    
    # Calculate averages
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
    
    # Sort by average points
    results.sort(key=lambda x: x["avg_points"], reverse=True)
    return results

# --- UI ---
st.title("🏒 Olympics Fantasy Hockey 2026")
st.caption("Keeping Karlsson Community Fantasy Game")

PLAYERS_DATA = get_all_players_data()

page = st.sidebar.radio("Menu", ["Home", "Create Team", "My Team", "Leaderboard", "Countries"])

if page == "Home":
    st.write("""
    ## Welcome to Olympics Fantasy Hockey 2026!
    
    ### New: Countries Competition! 🌍
    Managers compete not only individually but also for their country's honor!
    Countries with 4+ managers appear separately. Smaller countries are grouped as "Others".
    
    ### Scoring
    | Action | Points |
    |--------|--------|
    | Goal | 1 pt |
    | Assist | 1 pt |
    """)

elif page == "Create Team":
    st.header("📝 Create Your Olympic Roster")
    
    with st.expander("ℹ️ Rules", expanded=True):
        st.write("""
        - **7 Forwards + 3 Defensemen**
        - **Max 1 player per Olympic nation** (CAN, USA, SWE, FIN, CZE, SUI, GER)
        - Select your **manager nationality** for country competition!
        """)

    with st.form("team_form"):
        col1, col2 = st.columns(2)
        team_name = col1.text_input("Team Name", placeholder="e.g. Miracle on Ice")
        pin = col2.text_input("PIN Code", type="password", placeholder="4-10 digits")
        
        # MANAGER COUNTRY SELECTION
        st.subheader("🌍 Manager Nationality")
        
        col_flag, col_select = st.columns([1, 4])
        
        with col_select:
            manager_country = st.selectbox(
                "Select your country",
                options=list(ALL_COUNTRIES.keys()),
                format_func=lambda x: f"{get_flag(x)} {ALL_COUNTRIES[x]}"
            )
        
        with col_flag:
            st.markdown(f"<div style='font-size: 3rem; margin-top: 1.8rem;'>{get_flag(manager_country)}</div>", unsafe_allow_html=True)
        
        st.divider()
        st.subheader("Select Players by Country")
        
        # Data prep
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

        sorted_countries = sorted(players_by_country.keys())
        selected_player_ids = []
        
        # Render with flags
        for country in sorted_countries:
            flag = get_flag(country)
            is_olympic = country in OLYMPIC_TEAMS
            olympic_badge = "🏒" if is_olympic else ""
            
            with st.expander(f"{flag} {country} {olympic_badge}"):
                col_f, col_d = st.columns(2)
                
                with col_f:
                    st.markdown("**Forwards**")
                    for p in players_by_country[country]['F']:
                        label = f"{p['firstName']['default']} {p['lastName']['default']}"
                        if st.checkbox(label, key=f"chk_{p['playerId']}"):
                            selected_player_ids.append(p['playerId'])
                            
                with col_d:
                    st.markdown("**Defensemen**")
                    for p in players_by_country[country]['D']:
                        label = f"{p['firstName']['default']} {p['lastName']['default']}"
                        if st.checkbox(label, key=f"chk_{p['playerId']}"):
                            selected_player_ids.append(p['playerId'])

        # Validation
        stats_counts = {'F': 0, 'D': 0}
        country_counts = {}
        player_map = {p['playerId']: p for p in PLAYERS_DATA}
        
        for pid in selected_player_ids:
            p = player_map[pid]
            pos = 'D' if p['position'] == 'D' else 'F'
            stats_counts[pos] += 1
            ctry = p['teamName']['default']
            country_counts[ctry] = country_counts.get(ctry, 0) + 1

        # Status display
        st.divider()
        st.subheader("Draft Status")
        
        s1, s2, s3 = st.columns(3)
        f_color = "green" if stats_counts['F'] == 7 else "red"
        s1.markdown(f"Forwards: :{f_color}[**{stats_counts['F']} / 7**]")
        
        d_color = "green" if stats_counts['D'] == 3 else "red"
        s2.markdown(f"Defensemen: :{d_color}[**{stats_counts['D']} / 3**]")
        
        violation_countries = [c for c, count in country_counts.items() if count > 1]
        if not violation_countries:
            s3.markdown("1-Player/Nation: :green[**OK**]")
        else:
            s3.markdown(f"1-Player/Nation: :red[**VIOLATION**]")

        submit = st.form_submit_button("💾 Save Team", type="primary")
        
        if submit:
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
                success, msg = save_team(team_name, pin, selected_player_ids, manager_country)
                if success:
                    st.balloons()
                    st.success(f"Team '{team_name}' saved! Representing {get_flag(manager_country)} {ALL_COUNTRIES[manager_country]}!")
                else:
                    st.error(msg)

elif page == "My Team":
    st.header("👤 View Your Team")
    
    with st.form("login_form"):
        col1, col2 = st.columns(2)
        login_name = col1.text_input("Team Name")
        login_pin = col2.text_input("PIN", type="password")
        submit = st.form_submit_button("🔓 Log In")
    
    if submit:
        target_team = None
        for t in get_all_teams():
            if t['team_name'] == login_name:
                target_team = t
                break
        
        if target_team and hash_pin(login_pin) == target_team['pin_hash']:
            manager_country = target_team.get("manager_country", "UNK")
            flag = get_flag(manager_country)
            
            st.success(f"Team: {target_team['team_name']} | Manager: {flag} {ALL_COUNTRIES.get(manager_country, manager_country)}")
            
            player_map = {p['playerId']: p for p in PLAYERS_DATA}
            
            team_roster = []
            total_pts = 0
            
            for pid in target_team.get('player_ids', []):
                if pid in player_map:
                    p = player_map[pid]
                    flag = get_flag(p['teamName']['default'])
                    team_roster.append({
                        "Player": f"{p['firstName']['default']} {p['lastName']['default']}",
                        "Country": f"{flag} {p['teamName']['default']}",
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
    st.header("🏆 Individual Leaderboard")
    
    all_teams = get_all_teams()
    player_map = {p['playerId']: p for p in PLAYERS_DATA}
    
    rankings = []
    
    for team in all_teams:
        t_points = 0
        for pid in team.get('player_ids', []):
            if pid in player_map:
                t_points += player_map[pid]['points']
        
        manager_country = team.get("manager_country", "UNK")
        
        rankings.append({
            "Team": team['team_name'],
            "Manager Country": f"{get_flag(manager_country)} {ALL_COUNTRIES.get(manager_country, manager_country)}",
            "Points": t_points
        })
    
    df = pd.DataFrame(rankings).sort_values("Points", ascending=False).reset_index(drop=True)
    df.index += 1
    st.dataframe(df, use_container_width=True)

elif page == "Countries":
    st.header("🌍 Countries Competition")
    st.write("Managers compete for national pride! Countries with 4+ managers shown separately. Smaller countries grouped as 'Others'.")
    
    country_stats = get_country_leaderboard()
    
    if not country_stats:
        st.info("No teams registered yet!")
    else:
        # Display table
        display_data = []
        for i, stats in enumerate(country_stats, 1):
            countries_text = ", ".join([f"{get_flag(c)} {ALL_COUNTRIES.get(c, c)}" for c in stats['countries']]) if stats['code'] == "OTHERS" else f"{get_flag(stats['code'])} {stats['name']}"
            
            display_data.append({
                "Rank": i,
                "Country/Group": countries_text,
                "Managers": stats['managers'],
                "Avg Points": stats['avg_points'],
                "Best Score": stats['best_score']
            })
        
        df = pd.DataFrame(display_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Podium for top 3
        if len(country_stats) >= 3:
            st.divider()
            cols = st.columns(3)
            medals = ["🥇", "🥈", "🥉"]
            colors = ["#FFD700", "#C0C0C0", "#CD7F32"]
            
            for i in range(3):
                stats = country_stats[i]
                with cols[i]:
                    flag = get_flag(stats['code'])
                    name = "Others" if stats['code'] == "OTHERS" else stats['name']
                    
                    st.markdown(f"""
                    <div style='text-align: center; padding: 20px; background-color: {colors[i]}; border-radius: 10px;'>
                        <div style='font-size: 4rem;'>{medals[i]}</div>
                        <div style='font-size: 2rem;'>{flag}</div>
                        <div style='font-size: 1.3rem; font-weight: bold;'>{name}</div>
                        <div style='font-size: 1.1rem;'>{stats['avg_points']} avg pts</div>
                        <div style='font-size: 0.9rem;'>({stats['managers']} managers)</div>
                    </div>
                    """, unsafe_allow_html=True)

