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
import logging
logging.basicConfig(level=logging.INFO)

# --- SETTINGS ---
st.set_page_config(page_title="Olympics Fantasy Hockey 2025", page_icon="🏒")

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

def get_country_display(code):
    flag = get_flag(code)
    name = ALL_COUNTRIES.get(code, code)
    return f"{flag} {name}"

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

def clean_name(name):
    """Normalisoi nimen: poistaa erikoismerkit, välilyönnit, alaviivat ja PI STEET"""
    if not name: 
        return ""
    n = unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8')
    # Poista VÄLILYÖNIT, ALAVIIVAT ja PISTEET
    return n.lower().strip().replace(" ", "").replace("_", "").replace(".", "")

def create_short_key(first_name, last_name):
    """
    Luo lyhennetty avain API:n mukaan: eka kirjain + sukunimi (EI pistettä!)
    Esimerkki: "Tomas", "Hertl" → "thertl"
    """
    if not first_name or not last_name:
        return ""
    first_initial = first_name[0].lower()
    last_clean = clean_name(last_name)
    return f"{first_initial}{last_clean}"  # EI pistettä väliin!

@st.cache_data(ttl=60)
def fetch_live_scoring_by_name():
    start_date = "2025-02-12"
    end_date = "2025-02-20"
    live_stats = {}
    
    dates = pd.date_range(start=start_date, end=end_date).strftime('%Y-%m-%d')
    
    for date_str in dates:
        if date_str > datetime.now().strftime('%Y-%m-%d'):
            continue
            
        try:
            schedule_url = f"https://api-web.nhle.com/v1/schedule/{date_str}"
            r = requests.get(schedule_url, timeout=5).json()
            
            game_week = r.get('gameWeek', [])
            day_data = next((d for d in game_week if d.get('date') == date_str), None)
            
            if not day_data:
                continue
            
            games = day_data.get('games', [])
            
            for game in games:
                game_id = game.get('id')
                game_type = game.get('gameType')
                away_abbr = game.get('awayTeam', {}).get('abbrev')
                home_abbr = game.get('homeTeam', {}).get('abbrev')
                
                if game_type in [9, 19]:
                    box_url = f"https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore"
                    
                    try:
                        box = requests.get(box_url, timeout=5).json()
                        
                        for team_type, country_code in [('awayTeam', away_abbr), ('homeTeam', home_abbr)]:
                            team_stats = box.get('playerByGameStats', {}).get(team_type, {})
                            
                            for group in ['forwards', 'defense', 'goalies']:
                                players = team_stats.get(group, [])
                                
                                for p in players:
                                    # Käytä lyhennettyä nimeä API:sta (esim. "T. Konecny")
                                    name_default = p.get('name', {}).get('default', '')
                                    
                                    if name_default:
                                        # Muunna "T. Konecny" → "tkonecny" (poista piste!)
                                        key = f"{clean_name(name_default)}_{clean_name(country_code)}"
                                    else:
                                        # Fallback
                                        fn = p.get('firstName', {}).get('default', '')
                                        ln = p.get('lastName', {}).get('default', '')
                                        key = create_short_key(fn, ln) + f"_{clean_name(country_code)}"
                                    
                                    goals = int(p.get('goals', 0))
                                    assists = int(p.get('assists', 0))
                                    
                                    if key not in live_stats:
                                        live_stats[key] = {'goals': 0, 'assists': 0}
                                    
                                    live_stats[key]['goals'] += goals
                                    live_stats[key]['assists'] += assists
                                    
                    except Exception:
                        continue
                        
        except Exception:
            continue
    
    return live_stats

@st.cache_data(ttl=60)
def get_all_players_data():
    try:
        df = pd.read_csv("olympic_players.csv")
        base_roster = df.to_dict('records')
        csv_loaded = True
    except Exception as e:
        base_roster = [...]  # fallback
        csv_loaded = False

    live_scores = fetch_live_scoring_by_name()
    api_keys = list(live_scores.keys())
    
    matched_players = 0
    total_points = 0
    sample_matches = []
    debug_comparison = []
    
    final_list = []
    for player in base_roster:
        f_name = str(player['firstName'])
        l_name = str(player['lastName'])
        country = str(player['teamName'])
        pos = str(player['position'])
        
        # Yritä täsmätä lyhennetyllä avaimella ILMAN pistettä
        short_key = create_short_key(f_name, l_name) + f"_{clean_name(country)}"
        
        # Hae stats
        stats = live_scores.get(short_key, {'goals': 0, 'assists': 0})
        
        # Debug
        if len(debug_comparison) < 10:
            debug_comparison.append({
                'name': f"{f_name} {l_name}",
                'country': country,
                'short_key': short_key,
                'found': stats['goals'] > 0 or stats['assists'] > 0,
                'stats': stats
            })
        
        if stats['goals'] > 0 or stats['assists'] > 0:
            matched_players += 1
            total_points += stats['goals'] + stats['assists']
            if len(sample_matches) < 5:
                sample_matches.append(f"{f_name} {l_name} ({country}): {stats['goals']}G {stats['assists']}A")
        
        final_list.append({
            "playerId": short_key,
            "firstName": {"default": f_name},
            "lastName": {"default": l_name},
            "teamName": {"default": country},
            "position": pos,
            "goals": stats['goals'],
            "assists": stats['assists'],
            "points": stats['goals'] + stats['assists']
        })
    
    st.session_state['player_data_debug'] = {
        "csv_loaded": csv_loaded,
        "csv_players": len(base_roster),
        "api_players_with_stats": len(live_scores),
        "matched_in_roster": matched_players,
        "total_points": total_points,
        "api_sample_keys": api_keys[:10],
        "debug_comparison": debug_comparison,
        "sample_matches": sample_matches
    }
    
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

# --- REFRESH UTILITIES ---
def clear_all_cache():
    try:
        fetch_live_scoring_by_name.clear()
        get_all_players_data.clear()
        return True
    except Exception as e:
        st.error(f"Error clearing cache: {e}")
        return False

# --- UI ---
st.title("🏒 Olympics Fantasy Hockey 2025")

PLAYERS_DATA = get_all_players_data()

with st.sidebar:
    st.divider()
    st.subheader("⚙️ Debug & Settings")
    
    if st.button("🔄 Force Refresh", use_container_width=True, type="primary"):
        with st.spinner("Fetching fresh data..."):
            if clear_all_cache():
                st.success("Cache cleared! Reloading...")
                st.rerun()
    
    if st.checkbox("🔍 Show Debug Info", value=True):
        if 'player_data_debug' in st.session_state:
            d = st.session_state['player_data_debug']
            
            st.text("SUMMARY:")
            st.text(f"📁 CSV loaded: {d.get('csv_loaded', 'N/A')}")
            st.text(f"👥 CSV players: {d.get('csv_players', 0)}")
            st.text(f"📡 API players: {d.get('api_players_with_stats', 0)}")
            st.text(f"✅ Matched: {d.get('matched_in_roster', 0)}")  # Käytä get() metodia
            st.text(f"📊 Total pts: {d.get('total_points', 0)}")
            
            st.divider()
            st.text("API SAMPLE KEYS (first 10):")
            for key in d.get('api_sample_keys', [])[:10]:
                st.code(key)
            
            if d.get('debug_comparison'):
                st.divider()
                st.text("KEY COMPARISON:")
                for comp in d['debug_comparison'][:5]:
                    status = "✅" if comp.get('found') else "❌"
                    st.text(f"{status} {comp.get('name')} ({comp.get('country')})")
                    st.text(f"   Short: {comp.get('short_key')}")
                    if comp.get('found'):
                        st.text(f"   Stats: {comp.get('stats', {})}")
            
            if d.get('sample_matches'):
                st.divider()
                st.text("🌟 MATCHES WITH POINTS:")
                for match in d['sample_matches']:
                    st.text(match)
            else:
                st.warning("No matches found!")
        else:
            st.info("No debug data available. Refresh to load.")
page = st.sidebar.radio("Menu", ["Home", "Create Team", "My Team", "Leaderboard", "Countries"])

if page == "Home":
    st.write("""
    ## Welcome to Olympics Fantasy Hockey 2025!
    
    ### New: Countries Competition! 🌍
    Managers compete not only individually but also for their country's honor!
    Countries with 4+ managers appear separately. Smaller countries grouped as "Others".
    
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

    col1, col2 = st.columns(2)
    team_name = col1.text_input("Team Name", placeholder="e.g. Miracle on Ice", key="team_name_input")
    pin = col2.text_input("PIN Code", type="password", placeholder="4-10 digits", key="pin_input")
    
    st.subheader("🌍 Manager Nationality")
    
    col_flag, col_select = st.columns([1, 4])
    
    with col_select:
        manager_country = st.selectbox(
            "Select your country",
            options=list(ALL_COUNTRIES.keys()),
            format_func=lambda x: f"{get_flag(x)} {ALL_COUNTRIES[x]}",
            key="manager_country_select"
        )
    
    with col_flag:
        st.markdown(f"<div style='font-size: 3rem; margin-top: 1.8rem;'>{get_flag(manager_country)}</div>", unsafe_allow_html=True)
    
    st.divider()
    st.subheader("Select Players by Country")
    
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

    stats_counts = {'F': 0, 'D': 0}
    country_counts = {}
    player_map = {p['playerId']: p for p in PLAYERS_DATA}
    
    for pid in selected_player_ids:
        p = player_map[pid]
        pos = 'D' if p['position'] == 'D' else 'F'
        stats_counts[pos] += 1
        ctry = p['teamName']['default']
        country_counts[ctry] = country_counts.get(ctry, 0) + 1

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

    st.divider()
    submit = st.button("💾 Save Team", type="primary", key="save_team_btn")
    
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
                    st.success(f"Team '{team_name}' saved! Representing {get_country_display(manager_country)}!")
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
            
            st.success(f"Team: {target_team['team_name']} | Manager: {get_country_display(manager_country)}")
            
            player_map = {p['playerId']: p for p in PLAYERS_DATA}
            
            team_roster = []
            total_pts = 0
            
            for pid in target_team.get('player_ids', []):
                if pid in player_map:
                    p = player_map[pid]
                    country_code = p['teamName']['default']
                    team_roster.append({
                        "Player": f"{p['firstName']['default']} {p['lastName']['default']}",
                        "Country": get_country_display(country_code),
                        "G": p['goals'],
                        "A": p['assists'],
                        "FP": p['points']
                    })
                    total_pts += p['points']
            
            st.dataframe(
                pd.DataFrame(team_roster),
                use_container_width=True,
                column_config={
                    "Player": st.column_config.TextColumn("Player", width="medium"),
                    "Country": st.column_config.TextColumn("Country", width="medium"),
                    "G": st.column_config.NumberColumn("G", width="small"),
                    "A": st.column_config.NumberColumn("A", width="small"),
                    "FP": st.column_config.NumberColumn("FP", width="small")
                }
            )
            st.metric("Total Points", total_pts)
            
        else:
            st.error("Invalid Team Name or PIN")

elif page == "Leaderboard":
    st.header("🏆 Individual Leaderboard")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Refresh Data", type="secondary", help="Force refresh from NHL API"):
            fetch_live_scoring_by_name.clear()
            get_all_players_data.clear()
            st.success("Cache cleared! Reloading...")
            st.rerun()
    
    all_teams = get_all_teams()
    player_map = {p['playerId']: p for p in PLAYERS_DATA}
    
    rankings = []
    teams_dict = {}
    
    for team in all_teams:
        t_points = 0
        for pid in team.get('player_ids', []):
            if pid in player_map:
                t_points += player_map[pid]['points']
        
        manager_country = team.get("manager_country", "UNK")
        team_name = team['team_name']
        
        rankings.append({
            "Team": team_name,
            "Manager": get_country_display(manager_country),
            "Points": t_points
        })
        
        teams_dict[team_name] = team
    
    df = pd.DataFrame(rankings).sort_values("Points", ascending=False).reset_index(drop=True)
    df.index += 1
    
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Team": st.column_config.TextColumn("Team", width="medium"),
            "Manager": st.column_config.TextColumn("Manager Country", width="medium"),
            "Points": st.column_config.NumberColumn("Points", width="small")
        }
    )
    
    st.divider()
    st.subheader("👥 View Team Roster")
    
    if rankings:
        team_names = [r["Team"] for r in sorted(rankings, key=lambda x: x["Points"], reverse=True)]
        
        selected_team = st.selectbox(
            "Select a team to view their roster:",
            options=team_names,
            format_func=lambda x: f"{x} ({next(r['Points'] for r in rankings if r['Team'] == x)} pts)"
        )
        
        if selected_team:
            team_data = teams_dict[selected_team]
            manager_country = team_data.get("manager_country", "UNK")
            
            st.markdown(f"### {selected_team}")
            st.markdown(f"**Manager:** {get_country_display(manager_country)}")
            
            team_roster = []
            total_pts = 0
            
            for pid in team_data.get('player_ids', []):
                if pid in player_map:
                    p = player_map[pid]
                    country_code = p['teamName']['default']
                    team_roster.append({
                        "Player": f"{p['firstName']['default']} {p['lastName']['default']}",
                        "Pos": p['position'],
                        "Country": get_country_display(country_code),
                        "G": p['goals'],
                        "A": p['assists'],
                        "FP": p['points']
                    })
                    total_pts += p['points']
            
            roster_df = pd.DataFrame(team_roster)
            st.dataframe(
                roster_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Player": st.column_config.TextColumn("Player", width="medium"),
                    "Pos": st.column_config.TextColumn("Pos", width="small"),
                    "Country": st.column_config.TextColumn("Country", width="medium"),
                    "G": st.column_config.NumberColumn("G", width="small"),
                    "A": st.column_config.NumberColumn("A", width="small"),
                    "FP": st.column_config.NumberColumn("FP", width="small")
                }
            )
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Points", total_pts)
            col2.metric("Forwards", len([r for r in team_roster if r['Pos'] in ['C', 'L', 'R', 'F']]))
            col3.metric("Defensemen", len([r for r in team_roster if r['Pos'] == 'D']))
    else:
        st.info("No teams registered yet!")

elif page == "Countries":
    st.header("🌍 Countries Competition")
    st.write("Managers compete for national pride! Countries with 4+ managers shown separately. Smaller countries grouped as 'Others'.")
    
    country_stats = get_country_leaderboard()
    
    if not country_stats:
        st.info("No teams registered yet!")
    else:
        display_data = []
        for i, stats in enumerate(country_stats, 1):
            if stats['code'] == "OTHERS":
                countries_text = ", ".join([get_country_display(c) for c in stats['countries']])
            else:
                countries_text = get_country_display(stats['code'])
            
            display_data.append({
                "Rank": i,
                "Country": countries_text,
                "Managers": stats['managers'],
                "Avg Points": stats['avg_points'],
                "Best": stats['best_score']
            })
        
        df = pd.DataFrame(display_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Rank": st.column_config.NumberColumn("Rank", width="small"),
                "Country": st.column_config.TextColumn("Country/Group", width="large"),
                "Managers": st.column_config.NumberColumn("Managers", width="small"),
                "Avg Points": st.column_config.NumberColumn("Avg Points", width="small"),
                "Best": st.column_config.NumberColumn("Best Score", width="small")
            }
        )
        
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
