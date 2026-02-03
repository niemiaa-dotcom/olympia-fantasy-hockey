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

# --- OLYMPICS DEADLINE ---
OLYMPICS_START = datetime(2026, 2, 11, 0, 0)  # 11.2.2026 00:00

def is_before_deadline():
    """Check if current time is before Olympics start"""
    return datetime.now() < OLYMPICS_START

def get_deadline_message():
    """Get user-friendly deadline message"""
    if is_before_deadline():
        days_left = (OLYMPICS_START - datetime.now()).days
        return f"⏰ Team changes allowed until February 11, 2026 ({days_left} days remaining)"
    else:
        return "🔒 Olympics have started - team changes are now locked"

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

# --- SIDEBAR ---
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
            st.text(f"✅ Matched: {d.get('matched_in_roster', 0)}")
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

# --- PAGE NAVIGATION (LISÄÄ ADMIN TÄHÄN) ---
page = st.sidebar.radio("Menu", ["Home", "Create Team", "My Team", "Leaderboard", "Countries", "Admin"])

# --- SESSION STATE FOR DELETE CONFIRMATION ---
if 'confirm_delete' not in st.session_state:
    st.session_state['confirm_delete'] = False

if page == "Home":
    st.write("""
    ## Welcome to Olympics Fantasy Hockey 2026!
    
    ### Rules 🏒
    - **12 players**: One from each Olympic nation (CAN, USA, SWE, FIN, CZE, SUI, GER, DEN, FRA, ITA, LAT, SVK)
    - **4 defensemen + 8 forwards**
    - **Countries Competition**: Managers compete for national pride!
    
    ### Scoring
    | Action | Points |
    |--------|--------|
    | Goal | 1 pt |
    | Assist | 1 pt |
    """)
    
# --- COUNTRIES SIVU ---
elif page == "Countries":
    st.header("🌍 Countries Competition")
    st.write("Managers compete for national pride! Countries with **3+ managers** appear separately. Smaller countries grouped as 'Others'.")
    
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
            
            for i in range(min(3, len(country_stats))):
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

# --- MY TEAM SIVU ---
elif page == "My Team":
    st.header("👤 View Your Team")
    
    if 'logged_in_team' not in st.session_state:
        st.session_state['logged_in_team'] = None
    if 'show_delete_confirm' not in st.session_state:
        st.session_state['show_delete_confirm'] = False
    
    if st.session_state['logged_in_team'] is None:
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
                st.session_state['logged_in_team'] = target_team
                st.rerun()
            else:
                st.error("Invalid Team Name or PIN")
    
    else:
        target_team = st.session_state['logged_in_team']
        manager_country = target_team.get("manager_country", "UNK")
        
        st.success(f"Team: {target_team['team_name']} | Manager: {get_country_display(manager_country)}")
        
        # Show deadline status
        if is_before_deadline():
            st.info(get_deadline_message())
        else:
            st.warning(get_deadline_message())
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Refresh Points", type="secondary"):
                st.rerun()
        
        with col2:
            # Only show Edit button before deadline
            if is_before_deadline():
                if st.button("✏️ Edit Team", type="primary"):
                    st.session_state['editing_team'] = True
                    st.rerun()
        
        with col3:
            if not st.session_state['show_delete_confirm']:
                if st.button("🗑️ Delete Team", type="secondary"):
                    st.session_state['show_delete_confirm'] = True
                    st.rerun()
        
        if st.session_state.get('show_delete_confirm', False):
            st.warning("⚠️ Are you sure you want to delete this team? This cannot be undone!")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ Yes, Delete", type="primary", key="confirm_delete_yes"):
                    db = get_db()
                    if db:
                        try:
                            db.collection("teams").document(target_team['team_name']).delete()
                            st.success(f"Team '{target_team['team_name']}' deleted successfully!")
                            st.session_state['logged_in_team'] = None
                            st.session_state['show_delete_confirm'] = False
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting: {e}")
                    else:
                        st.error("Database connection failed")
            
            with col2:
                if st.button("❌ Cancel", key="confirm_delete_no"):
                    st.session_state['show_delete_confirm'] = False
                    st.rerun()
        
        # EDIT TEAM MODE
        if st.session_state.get('editing_team', False):
            st.divider()
            st.subheader("✏️ Edit Your Team")
            st.info("Select new players for your team. Your current selections will be replaced.")
            
            # Initialize temp selections with current team
            if 'edit_temp_selections' not in st.session_state:
                st.session_state['edit_temp_selections'] = {}
                # Pre-select current players
                current_players = target_team.get('player_ids', [])
                player_map_temp = {p['playerId']: p for p in PLAYERS_DATA}
                for pid in current_players:
                    if pid in player_map_temp:
                        p = player_map_temp[pid]
                        country = p['teamName']['default']
                        st.session_state['edit_temp_selections'][f"chk_{country}_{pid}"] = True
                        st.session_state['edit_temp_selections'][country] = pid
            
            # Player selection interface (similar to Create Team)
            players_by_country = {}
            for idx, p in enumerate(PLAYERS_DATA):
                country = p['teamName']['default']
                if country not in players_by_country:
                    players_by_country[country] = {'F': [], 'D': []}
                
                pos = p['position']
                if pos in ['C', 'L', 'R', 'F']:
                    players_by_country[country]['F'].append((idx, p))
                elif pos == 'D':
                    players_by_country[country]['D'].append((idx, p))
            
            sorted_countries = sorted(players_by_country.keys())
            selected_player_ids = []
            
            for country in sorted_countries:
                flag = get_flag(country)
                
                with st.expander(f"{flag} {country} - Select ONE player", expanded=False):
                    col_f, col_d = st.columns(2)
                    
                    with col_f:
                        st.markdown("**Forwards**")
                        for idx, p in players_by_country[country]['F']:
                            label = f"{p['firstName']['default']} {p['lastName']['default']}"
                            checkbox_key = f"chk_{country}_{p['playerId']}"
                            
                            country_already_selected = st.session_state['edit_temp_selections'].get(country) is not None
                            is_selected = st.session_state['edit_temp_selections'].get(checkbox_key, False)
                            disabled = country_already_selected and not is_selected
                            
                            checked = st.checkbox(
                                label, 
                                key=f"edit_{checkbox_key}",
                                value=is_selected,
                                disabled=disabled
                            )
                            
                            if checked:
                                st.session_state['edit_temp_selections'][checkbox_key] = True
                                st.session_state['edit_temp_selections'][country] = p['playerId']
                                selected_player_ids.append(p['playerId'])
                            else:
                                if checkbox_key in st.session_state['edit_temp_selections']:
                                    del st.session_state['edit_temp_selections'][checkbox_key]
                                    if st.session_state['edit_temp_selections'].get(country) == p['playerId']:
                                        del st.session_state['edit_temp_selections'][country]
                    
                    with col_d:
                        st.markdown("**Defensemen**")
                        for idx, p in players_by_country[country]['D']:
                            label = f"{p['firstName']['default']} {p['lastName']['default']}"
                            checkbox_key = f"chk_{country}_{p['playerId']}"
                            
                            country_already_selected = st.session_state['edit_temp_selections'].get(country) is not None
                            is_selected = st.session_state['edit_temp_selections'].get(checkbox_key, False)
                            disabled = country_already_selected and not is_selected
                            
                            checked = st.checkbox(
                                label, 
                                key=f"edit_{checkbox_key}",
                                value=is_selected,
                                disabled=disabled
                            )
                            
                            if checked:
                                st.session_state['edit_temp_selections'][checkbox_key] = True
                                st.session_state['edit_temp_selections'][country] = p['playerId']
                                selected_player_ids.append(p['playerId'])
                            else:
                                if checkbox_key in st.session_state['edit_temp_selections']:
                                    del st.session_state['edit_temp_selections'][checkbox_key]
                                    if st.session_state['edit_temp_selections'].get(country) == p['playerId']:
                                        del st.session_state['edit_temp_selections'][country]
            
            selected_player_ids = list(set(selected_player_ids))
            
            # Validation
            stats_counts = {'F': 0, 'D': 0, 'total': 0}
            countries_selected = set()
            player_map = {p['playerId']: p for p in PLAYERS_DATA}
            
            for pid in selected_player_ids:
                p = player_map[pid]
                pos = 'D' if p['position'] == 'D' else 'F'
                stats_counts[pos] += 1
                stats_counts['total'] += 1
                countries_selected.add(p['teamName']['default'])
            
            st.divider()
            st.subheader("Draft Status")
            
            cols = st.columns(4)
            total_color = "green" if stats_counts['total'] == 12 else "orange" if stats_counts['total'] < 12 else "red"
            cols[0].markdown(f"Total Players: :{total_color}[**{stats_counts['total']} / 12**]")
            
            d_color = "green" if stats_counts['D'] == 4 else "red"
            cols[1].markdown(f"Defensemen: :{d_color}[**{stats_counts['D']} / 4**]")
            
            f_color = "green" if stats_counts['F'] == 8 else "red"
            cols[2].markdown(f"Forwards: :{f_color}[**{stats_counts['F']} / 8**]")
            
            countries_color = "green" if len(countries_selected) == 12 else "orange"
            cols[3].markdown(f"Countries: :{countries_color}[**{len(countries_selected)} / 12**]")
            
            missing_countries = set(OLYMPIC_TEAMS) - countries_selected
            if missing_countries:
                st.warning(f"⚠️ Missing players from: {', '.join(sorted(missing_countries))}")
            
            can_save = (
                stats_counts['total'] == 12 and
                stats_counts['D'] == 4 and
                stats_counts['F'] == 8 and
                len(countries_selected) == 12 and
                len(missing_countries) == 0
            )
            
            col_save, col_cancel = st.columns(2)
            
            with col_save:
                if st.button("💾 Save Changes", type="primary", disabled=not can_save):
                    if can_save:
                        # Update team in database
                        db = get_db()
                        if db:
                            try:
                                db.collection("teams").document(target_team['team_name']).update({
                                    'player_ids': selected_player_ids
                                })
                                st.session_state['logged_in_team']['player_ids'] = selected_player_ids
                                st.session_state['editing_team'] = False
                                st.session_state['edit_temp_selections'] = {}
                                st.success("✅ Team updated successfully!")
                                st.balloons()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating team: {e}")
                        else:
                            st.error("Database connection failed")
            
            with col_cancel:
                if st.button("❌ Cancel Edit", type="secondary"):
                    st.session_state['editing_team'] = False
                    st.session_state['edit_temp_selections'] = {}
                    st.rerun()
            
            st.stop()  # Don't show roster below when editing
        
        # SHOW CURRENT ROSTER
        if st.session_state['logged_in_team']:
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
            
            st.divider()
            if st.button("🔒 Log Out", type="secondary"):
                st.session_state['logged_in_team'] = None
                st.session_state['show_delete_confirm'] = False
                st.session_state['editing_team'] = False
                st.session_state['edit_temp_selections'] = {}
                st.rerun()

# --- CREATE TEAM SIVU (UUDET SÄÄNNÖT) ---
elif page == "Create Team":
    st.header("📝 Create Your Olympic Roster")
    
    # Check deadline
    if not is_before_deadline():
        st.error("🔒 Team creation is closed. The Olympics have started!")
        st.info("The tournament began on February 11, 2026. Team changes are no longer allowed.")
        st.stop()
    
    st.success(get_deadline_message())
    
    with st.expander("ℹ️ Rules", expanded=True):
        st.write("""
        ### Olympics Fantasy Hockey 2026! 🏒
        
        - **Select exactly 12 players** (one from each of the 12 Olympic nations)
        - **Exactly 8 forwards** (F) and **4 defensemen** (D)
        - **Exactly 1 player per country** - you cannot select two players from the same nation!
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
    st.caption("You must select exactly ONE player from each of the 11 Olympic nations!")
    
    # Data prep - vain Olympic maat
    players_by_country = {}
    for idx, p in enumerate(PLAYERS_DATA):
        country = p['teamName']['default']
        if country not in OLYMPIC_TEAMS:
            continue  # Skip non-Olympic teams
            
        if country not in players_by_country:
            players_by_country[country] = {'F': [], 'D': []}
        
        pos = p['position']
        if pos in ['C', 'L', 'R', 'F']:
            players_by_country[country]['F'].append((idx, p))
        elif pos == 'D':
            players_by_country[country]['D'].append((idx, p))
    
    # Järjestä maiden mukaan (vakiojärjestys)
    sorted_countries = sorted(players_by_country.keys())
    
    # Seuraa valittuja pelaajia ja maita
    selected_player_ids = []
    selected_by_country = {}
    
    # Käytä session_statea tallentamaan valinnat sivun päivitysten yli
    if 'temp_selections' not in st.session_state:
        st.session_state['temp_selections'] = {}
    
    # Luo valintalista maittain
    for country in sorted_countries:
        flag = get_flag(country)
        
        with st.expander(f"{flag} {country} - Select ONE player", expanded=False):
            col_f, col_d = st.columns(2)
            
            with col_f:
                st.markdown("**Forwards**")
                for idx, p in players_by_country[country]['F']:
                    label = f"{p['firstName']['default']} {p['lastName']['default']}"
                    checkbox_key = f"chk_{country}_{idx}"
                    
                    # Tarkista onko maa jo valittu toiselta pelaajalta
                    country_already_selected = st.session_state['temp_selections'].get(country) is not None
                    is_selected = st.session_state['temp_selections'].get(checkbox_key, False)
                    
                    # Jos maa on jo valittu mutta tämä ei ole se valittu, disabled
                    disabled = country_already_selected and not is_selected
                    
                    checked = st.checkbox(
                        label, 
                        key=checkbox_key,
                        value=is_selected,
                        disabled=disabled
                    )
                    
                    if checked:
                        st.session_state['temp_selections'][checkbox_key] = True
                        st.session_state['temp_selections'][country] = p['playerId']
                        selected_player_ids.append(p['playerId'])
                    else:
                        if checkbox_key in st.session_state['temp_selections']:
                            del st.session_state['temp_selections'][checkbox_key]
                            if st.session_state['temp_selections'].get(country) == p['playerId']:
                                del st.session_state['temp_selections'][country]
                        
            with col_d:
                st.markdown("**Defensemen**")
                for idx, p in players_by_country[country]['D']:
                    label = f"{p['firstName']['default']} {p['lastName']['default']}"
                    checkbox_key = f"chk_{country}_{idx}"
                    
                    country_already_selected = st.session_state['temp_selections'].get(country) is not None
                    is_selected = st.session_state['temp_selections'].get(checkbox_key, False)
                    
                    disabled = country_already_selected and not is_selected
                    
                    checked = st.checkbox(
                        label, 
                        key=checkbox_key,
                        value=is_selected,
                        disabled=disabled
                    )
                    
                    if checked:
                        st.session_state['temp_selections'][checkbox_key] = True
                        st.session_state['temp_selections'][country] = p['playerId']
                        selected_player_ids.append(p['playerId'])
                    else:
                        if checkbox_key in st.session_state['temp_selections']:
                            del st.session_state['temp_selections'][checkbox_key]
                            if st.session_state['temp_selections'].get(country) == p['playerId']:
                                del st.session_state['temp_selections'][country]
    
    # Poista duplikaatit
    selected_player_ids = list(set(selected_player_ids))
    
    # Reaaliaikainen validointi
    stats_counts = {'F': 0, 'D': 0, 'total': 0}
    countries_selected = set()
    player_map = {p['playerId']: p for p in PLAYERS_DATA}
    
    for pid in selected_player_ids:
        p = player_map[pid]
        pos = 'D' if p['position'] == 'D' else 'F'
        stats_counts[pos] += 1
        stats_counts['total'] += 1
        countries_selected.add(p['teamName']['default'])
    
    # Näytä tila
    st.divider()
    st.subheader("Draft Status")
    
    cols = st.columns(4)
    
    # Total players - 12 maata = 12 pelaajaa
    total_color = "green" if stats_counts['total'] == 12 else "orange" if stats_counts['total'] < 12 else "red"
    cols[0].markdown(f"Total Players: :{total_color}[**{stats_counts['total']} / 12**]")
    
    # Defensemen - TÄSMÄLLEEN 4
    d_color = "green" if stats_counts['D'] == 4 else "red"
    cols[1].markdown(f"Defensemen: :{d_color}[**{stats_counts['D']} / 4**]")
    
    # Forwards - TÄSMÄLLEEN 8
    f_color = "green" if stats_counts['F'] == 8 else "red"
    cols[2].markdown(f"Forwards: :{f_color}[**{stats_counts['F']} / 8**]")
    
    # Countries - 12 maata
    countries_color = "green" if len(countries_selected) == 12 else "orange"
    cols[3].markdown(f"Countries: :{countries_color}[**{len(countries_selected)} / 12**]")
    
    # Listaa puuttuvat maat
    missing_countries = set(OLYMPIC_TEAMS) - countries_selected
    if missing_countries:
        st.warning(f"⚠️ Missing players from: {', '.join(sorted(missing_countries))}")
    
    # Tallenna-nappi - päivitä ehdot
    can_save = (
        stats_counts['total'] == 12 and
        stats_counts['D'] == 4 and  # TÄSMÄLLEEN 4
        stats_counts['F'] == 8 and  # TÄSMÄLLEEN 8
        len(countries_selected) == 12 and
        len(missing_countries) == 0
    )
    
    if not can_save:
        st.info("💡 Select exactly 12 players (one from each of the 12 countries: 4 defensemen + 8 forwards)")
    
    submit = st.button("💾 Save Team", type="primary", key="save_team_btn", disabled=not can_save)
    
    if submit:
        errors = []
        
        if not team_name:
            errors.append("Missing Team Name.")
        if not pin or len(pin) < 4:
            errors.append("Invalid PIN (min 4 characters).")
        if stats_counts['total'] != 12:
            errors.append(f"Must select exactly 12 players (Selected: {stats_counts['total']}).")
        if stats_counts['D'] != 4:
            errors.append(f"Must select exactly 4 Defensemen (Selected: {stats_counts['D']}).")
        if stats_counts['F'] != 8:
            errors.append(f"Must select exactly 8 Forwards (Selected: {stats_counts['F']}).")
        if len(countries_selected) != 12:
            errors.append(f"Must select exactly one player from each of the 12 countries (Selected from: {len(countries_selected)}).")
        
        if errors:
            for e in errors:
                st.error(e)
        else:
            success, msg = save_team(team_name, pin, selected_player_ids, manager_country)
            if success:
                # Tyhjennä valinnat
                st.session_state['temp_selections'] = {}
                st.balloons()
                st.success(f"Team '{team_name}' saved! Representing {get_country_display(manager_country)}!")
                st.info("Go to 'My Team' to view your roster!")
            else:
                st.error(msg)
    
    # --- LEADERBOARD SIVU ---
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
            col2.metric("Forwards", len([r for r in team_roster if r['Pos'] in ['C', 'L', 'R', 'F']]))  # Pitäisi olla 8
            col3.metric("Defensemen", len([r for r in team_roster if r['Pos'] == 'D']))  # Pitäisi olla 4
    else:
        st.info("No teams registered yet!")

# --- COUNTRIES SIVU (MINIMI 3 MANAGERS) ---
elif page == "Admin":
    st.header("🔧 Admin Panel")
    
    admin_pass = st.text_input("Admin Password", type="password", key="admin_password")
    correct_password = st.secrets.get("ADMIN_PASSWORD", "olympics2025")
    
    if admin_pass == correct_password:
        st.success("✅ Admin access granted")
        
        all_teams = get_all_teams()
        
        st.subheader(f"All Teams ({len(all_teams)} total)")
        
        if not all_teams:
            st.info("No teams found in database")
        else:
            team_summary = []
            for team in all_teams:
                team_summary.append({
                    "Team Name": team.get('team_name', 'N/A'),
                    "Manager Country": team.get('manager_country', 'N/A'),
                    "Created": team.get('created_at', 'N/A'),
                    "Players": len(team.get('player_ids', []))
                })
            
            st.dataframe(pd.DataFrame(team_summary), use_container_width=True)
            
            st.divider()
            st.subheader("🗑️ Delete Teams")
            
            team_to_delete = st.selectbox(
                "Select team to delete:",
                options=[t['team_name'] for t in all_teams],
                key="admin_delete_select"
            )
            
            if team_to_delete:
                team_data = next((t for t in all_teams if t['team_name'] == team_to_delete), None)
                if team_data:
                    with st.expander("View Team Details"):
                        st.json(team_data)
                
                confirm = st.checkbox(f"I confirm I want to delete '{team_to_delete}'", key="admin_confirm")
                
                if confirm and st.button("🗑️ Permanently Delete", type="primary", key="admin_delete_btn"):
                    db = get_db()
                    if db:
                        try:
                            db.collection("teams").document(team_to_delete).delete()
                            st.success(f"✅ Team '{team_to_delete}' deleted successfully!")
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error deleting team: {e}")
                    else:
                        st.error("❌ Database connection failed")
        
        st.divider()
        if st.checkbox("Show raw database data"):
            st.json(all_teams)
            
    elif admin_pass:
        st.error("❌ Incorrect password")
        st.info("Hint: Check your secrets.toml or app settings for ADMIN_PASSWORD")
