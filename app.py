import streamlit as st
import hashlib
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import requests
import pandas as pd

# --- ASETUKSET ---
st.set_page_config(page_title="Olympia Fantasy Hockey 2026", page_icon="🏒")

# --- FIREBASE ALUSTUS ---
def init_firebase():
    try:
        firebase_admin.get_app()
    except ValueError:
        # Lue secrets erillisistä muuttujista (EI ["firebase"] -listaa)
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

# --- APUFUNKTIOT ---
def hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()

def get_nhl_stats():
    """Hae pistepörssi - käytä testidataa jos API ei toimi"""
    
    # TESTIDATA (4 Nations 2025 -pelaajia)
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
        # Yritä oikeaa API:a ensin
        url = "https://api-web.nhle.com/v1/skater-stats-leaders/20242025/3?categories=points&limit=50"
        response = requests.get(url, timeout=10)
        data = response.json()
        api_players = data.get("data", [])
        
        # Jos saadaan dataa, käytä sitä
        if len(api_players) > 0:
            return api_players
            
    except Exception as e:
        st.sidebar.warning(f"API ei vastaa, käytetään testidataa")
    
    # Palaa testidataan
    return test_players

# --- DEBUG: Näytä API-vastaus ---
players = get_nhl_stats()
st.sidebar.write(f"Ladattu {len(players)} pelaajaa")  # Näytä määrä sivupalkissa

def calculate_points(player):
    """Laske fantasy-pisteet"""
    goals = player.get("goals", 0)
    assists = player.get("assists", 0)
    return goals * 3 + assists * 2

# --- TIETOKANTAFUNKTIOT ---
def save_team(team_name, pin, player_ids):
    db = get_db()
    team_ref = db.collection("teams").document(team_name)
    
    # Tarkista onko jo olemassa
    if team_ref.get().exists:
        old_data = team_ref.get().to_dict()
        if hash_pin(pin) != old_data.get("pin_hash"):
            return False, "Väärä PIN-koodi!"
    
    team_ref.set({
        "team_name": team_name,
        "pin_hash": hash_pin(pin),
        "player_ids": player_ids,
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    })
    return True, "Joukkue tallennettu!"

def get_all_teams():
    db = get_db()
    teams = []
    for doc in db.collection("teams").stream():
        data = doc.to_dict()
        data["id"] = doc.id
        teams.append(data)
    return teams

# --- KÄYTTÖLIITTYMÄ ---
st.title("🏒 Olympia Fantasy Hockey 2026")
st.caption("Keeping Karlsson -yhteisön fantasy-peli")


# Sivun valinta
page = st.sidebar.radio("Valikko", ["Etusivu", "Luo joukkue", "Oma joukkue", "Sarjataulukko"])

if page == "Etusivu":
    st.write("""
    ## Tervetuloa!
    
    Tässä pelissä kokoat 6 pelaajan joukkueen (3H, 2P, 1V) ja keräät pisteitä 
    heidän onnistumistensa perusteella.
    
    ### Pisteytys:
    - Maali: 3 pistettä
    - Syöttö: 2 pistettä
    
    Valitse sivulta "Luo joukkue" aloittaaksesi!
    """)

elif page == "Luo joukkue":
    st.header("📝 Luo tai muokkaa joukkuetta")
    
    with st.form("team_form"):
        col1, col2 = st.columns(2)
        with col1:
            team_name = st.text_input("Joukkueen nimi")
        with col2:
            pin = st.text_input("PIN-koodi", type="password")
        
        st.write("---")
        st.subheader("Valitse pelaajat")
        
        # Hae pelaajat
        players = get_nhl_stats()
        
        # Jaa positioihin (yksinkertaistettu)
        forwards = [p for p in players if p.get("position") in ["C", "L", "R"]] [:20]
        defense = [p for p in players if p.get("position") == "D"] [:15]
        
        # Näytä valinnat
        f_options = [f"{p['firstName']['default']} {p['lastName']['default']} ({p['teamName']['default']})" 
                     for p in forwards]
        d_options = [f"{p['firstName']['default']} {p['lastName']['default']} ({p['teamName']['default']})" 
                     for p in defense]
        
        selected_f = st.multiselect("Valitse 3 hyökkääjää", f_options, max_selections=3)
        selected_d = st.multiselect("Valitse 2 puolustajaa", d_options, max_selections=2)
        
        submit = st.form_submit_button("Tallenna joukkue", type="primary")
        
        if submit:
            if not team_name or not pin:
                st.error("Täytä nimi ja PIN!")
            elif len(selected_f) != 3 or len(selected_d) != 2:
                st.error(f"Valitse täsmälleen 3H ja 2P (valitsit {len(selected_f)}H, {len(selected_d)}P)")
            else:
                # Kerää ID:t
                selected_names = selected_f + selected_d
                player_ids = []
                for name in selected_names:
                    # Etsi ID
                    for p in forwards + defense:
                        full_name = f"{p['firstName']['default']} {p['lastName']['default']}"
                        if full_name in name:
                            player_ids.append(str(p["playerId"]))
                            break
                
                success, msg = save_team(team_name, pin, player_ids)
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

elif page == "Oma joukkue":
    st.header("👤 Oma Joukkue")
    
    # Kirjautuminen
    with st.form("login_form"):
        st.write("Kirjaudu nähdäksesi joukkueesi")
        login_name = st.text_input("Joukkueen nimi")
        login_pin = st.text_input("PIN-koodi", type="password")
        submit = st.form_submit_button("Kirjaudu")
    
    if submit:
        team = None
        for t in get_all_teams():
            if t["team_name"] == login_name:
                team = t
                break
        
        if not team:
            st.error("Joukkuetta ei löydy!")
        elif hash_pin(login_pin) != team.get("pin_hash", ""):
            st.error("Väärä PIN-koodi!")
        else:
            st.success(f"Tervetuloa, {team['team_name']}!")
            
            # Hae pelaajien tiedot
            st.subheader("Kokoonpano")
            
            all_players = get_nhl_stats()
            stats_dict = {str(p["playerId"]): p for p in all_players}
            
            total_points = 0
            
            for pid in team.get("player_ids", []):
                if pid in stats_dict:
                    p = stats_dict[pid]
                    points = calculate_points(p)
                    total_points += points
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**{p['firstName']['default']} {p['lastName']['default']}**")
                    with col2:
                        st.write(f"{p['teamName']['default']} | {p['position']}")
                    with col3:
                        st.write(f"🎯 {p['goals']}M + {p['assists']}S = {points} pts")
                else:
                    st.write(f"Pelaaja ID {pid} (ei tilastoja)")
            
            st.divider()
            st.write(f"### Yhteensä: {total_points} pistettä")

elif page == "Sarjataulukko":
    st.header("🏆 Sarjataulukko")
    
    teams = get_all_teams()
    if not teams:
        st.info("Ei vielä joukkueita. Luo ensimmäinen joukkue!")
    else:
        # Laske pisteet
        stats = get_nhl_stats()
        stats_dict = {str(p["playerId"]): p for p in stats}
        
        leaderboard = []
        for team in teams:
            total = 0
            player_names = []
            for pid in team.get("player_ids", []):
                if pid in stats_dict:
                    p = stats_dict[pid]
                    pts = calculate_points(p)
                    total += pts
                    player_names.append(f"{p['firstName']['default']} {p['lastName']['default']}: {pts}p")
            
            leaderboard.append({
                "Joukkue": team["team_name"],
                "Pisteet": total,
                "Pelaajat": ", ".join(player_names)
            })
        
        # Järjestä ja näytä
        df = pd.DataFrame(leaderboard).sort_values("Pisteet", ascending=False)
        df.index = range(1, len(df)+1)
        df.index.name = "Sija"
        
        st.dataframe(df, use_container_width=True)
