import pandas as pd
import requests
import time

# 1. Määritellään funktio ID:n hakuun selaimen valepuvussa
def get_nhl_player_id(first_name, last_name):
    """Hakee pelaajan ID:n NHL API:sta nimen perusteella."""
    search_name = f"{first_name} {last_name}"
    url = f"https://api-web.nhle.com/v1/search/player?culture=en-us&limit=5&q={search_name}"
    
    # TÄRKEÄ: User-Agent estää NHL:ää torjumasta pyyntöä "bottina"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            if data:
                # Palautetaan listan ensimmäisen pelaajan ID
                return data[0].get('playerId')
            else:
                print(f"  -> API vastasi, mutta ei löytänyt nimeä: '{search_name}'")
        else:
            print(f"  -> HTTP Virhe {r.status_code} nimelle {search_name}")
            
    except Exception as e:
        print(f"  -> Tekninen virhe: {e}")
    
    return None

# 2. Pääohjelma
if __name__ == "__main__":
    input_file = "input_players.csv"
    output_file = "olympic_players_with_ids.csv"
    
    try:
        # Ladataan CSV
        # dtype=str varmistaa ettei ID-sarakkeet mene sekaisin jos siellä on jo jotain
        df = pd.read_csv(input_file, dtype={'playerId': str})
    except FileNotFoundError:
        print(f"VIRHE: Tiedostoa '{input_file}' ei löydy.")
        exit()

    print(f"Aloitetaan haku {len(df)} pelaajalle...")
    print("-" * 50)

    found_count = 0
    missing_count = 0

    for index, row in df.iterrows():
        # Puhdistetaan nimet ylimääräisistä väleistä
        fname = str(row['firstName']).strip()
        lname = str(row['lastName']).strip()
        
        # Jos ID puuttuu (on NaN tai tyhjä), haetaan se
        if pd.isna(row['playerId']) or row['playerId'] == "":
            pid = get_nhl_player_id(fname, lname)
            
            if pid:
                df.at[index, 'playerId'] = str(pid)
                print(f"✅ Löytyi: {fname} {lname} -> {pid}")
                found_count += 1
            else:
                print(f"❌ EI LÖYTYNYT: {fname} {lname}")
                missing_count += 1
            
            # Pieni tauko pyyntöjen välissä
            time.sleep(0.2)
        else:
            # ID oli jo olemassa
            pass

    print("-" * 50)
    
    # Tallennetaan tulos
    df.to_csv(output_file, index=False)
    print(f"Valmis! Löytyi: {found_count}, Puuttui: {missing_count}")
    print(f"Tiedot tallennettu tiedostoon: {output_file}")
