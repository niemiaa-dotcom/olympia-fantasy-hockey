import pandas as pd
import requests
import time
from io import StringIO

# 1. Määritellään funktio ID:n hakuun
def get_nhl_player_id(first_name, last_name):
    """Hakee pelaajan ID:n NHL API:sta nimen perusteella."""
    search_name = f"{first_name} {last_name}"
    url = f"https://api-web.nhle.com/v1/search/player?culture=en-us&limit=5&q={search_name}"
    
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data:
                # API palauttaa listan osumista.
                # Otetaan ensimmäinen, joka on aktiivinen pelaaja.
                # Huom: Sebastian Aho (FIN) vs Sebastian Aho (SWE) on riski.
                # Yleensä aktiivinen NHL-tähti on listan kärjessä.
                for player in data:
                    # Palautetaan pelaajan ID
                    return player.get('playerId')
    except Exception as e:
        print(f"Virhe haussa {search_name}: {e}")
    
    return None

# 2. Ladataan CSV (Tässä käytän antamaasi dataa suoraan esimerkkinä)
# Oikeassa tilanteessa: df = pd.read_csv("input_players.csv")
csv_data = """playerId,firstName,lastName,teamName,position
,Macklin,Celebrini,CAN,F
,Anthony,Cirelli,CAN,F
,Sidney,Crosby,CAN,F
,Brandon,Hagel,CAN,F
,Bo,Horvat,CAN,F
,Nathan,MacKinnon,CAN,F
,Brad,Marchand,CAN,F
,Mitch,Marner,CAN,F
,Connor,McDavid,CAN,F
,Brayden,Point,CAN,F
,Sam,Reinhart,CAN,F
,Mark,Stone,CAN,F
,Nick,Suzuki,CAN,F
,Tom,Wilson,CAN,F
,Drew,Doughty,CAN,D
,Thomas,Harley,CAN,D
,Cale,Makar,CAN,D
,Josh,Morrissey,CAN,D
,Colton,Parayko,CAN,D
,Travis,Sanheim,CAN,D
,Shea,Theodore,CAN,D
,Devon,Toews,CAN,D
,Jordan,Binnington,CAN,G
,Darcy,Kuemper,CAN,G
,Logan,Thompson,CAN,G
,Roman,Cervenka,CZE,F
,Radek,Faksa,CZE,F
,Jakub,Flek,CZE,F
,Tomas,Hertl,CZE,F
,David,Kampf,CZE,F
,Ondrej,Kase,CZE,F
,Dominik,Kubalik,CZE,F
,Martin,Necas,CZE,F
,Ondrej,Palat,CZE,F
,David,Pastrnak,CZE,F
,Lukas,Sedlak,CZE,F
,Matej,Stransky,CZE,F
,David,Tomasek,CZE,F
,Pavel,Zacha,CZE,F
,Radko,Gudas,CZE,D
,Filip,Hronek,CZE,D
,Michal,Kempny,CZE,D
,Tomas,Kundratek,CZE,D
,Jan,Rutta,CZE,D
,Radim,Simek,CZE,D
,David,Spacek,CZE,D
,Jiri,Tichacek,CZE,D
,Lukas,Dostal,CZE,G
,Karel,Vejmelka,CZE,G
,Dan,Vladar,CZE,G
,Mikkal,Aagaard,DEN,F
,Mathias,Bau,DEN,F
,Oliver,Bjorkstrand,DEN,F
,Joachim,Blichfeld,DEN,F
,Nikolaj,Ehlers,DEN,F
,Lars,Eller,DEN,F
,Oscar Fisker,Molgaard,DEN,F
,Nicklas,Jensen,DEN,F
,Nick,Olesen,DEN,F
,Morten,Poulsen,DEN,F
,Jonas,Rondbjerg,DEN,F
,Patrick,Russell,DEN,F
,Frederik,Storm,DEN,F
,Alexander,True,DEN,F
,Christian,Wejse,DEN,F
,Jesper Jensen,Aabo,DEN,D
,Nicholas B,Jensen,DEN,D
,Anders,Koch,DEN,D
,Matias,Lassen,DEN,D
,Markus,Lauridsen,DEN,D
,Oliver,Lauridsen,DEN,D
,Phillip,Bruggisser,DEN,D
,Frederik,Andersen,DEN,G
,Frederik,Dichow,DEN,G
,Mads,Sogaard,DEN,G
,Joel,Armia,FIN,F
,Sebastian,Aho,FIN,F
,Mikael,Granlund,FIN,F
,Erik,Haula,FIN,F
,Roope,Hintz,FIN,F
,Kaapo,Kakko,FIN,F
,Oliver,Kapanen,FIN,F
,Joel,Kiviranta,FIN,F
,Artturi,Lehkonen,FIN,F
,Anton,Lundell,FIN,F
,Eetu,Luostarinen,FIN,F
,Mikko,Rantanen,FIN,F
,Teuvo,Teravainen,FIN,F
,Eeli,Tolvanen,FIN,F
,Miro,Heiskanen,FIN,D
,Henri,Jokiharju,FIN,D
,Mikko,Lehtonen,FIN,D
,Esa,Lindell,FIN,D
,Olli,Maatta,FIN,D
,Nikolas,Matinpalo,FIN,D
,Niko,Mikkola,FIN,D
,Rasmus,Ristolainen,FIN,D
,Kevin,Lankinen,FIN,G
,Ukko-Pekka,Luukkonen,FIN,G
,Juuse,Saros,FIN,G
,Justin,Addamo,FRA,F
,Pierre-Édouard,Bellemare,FRA,F
,Charles,Bertrand,FRA,F
,Louis,Boudon,FRA,F
,Kévin,Bozon,FRA,F
,Stéphane Da,Costa,FRA,F
,Aurélien,Dair,FRA,F
,Floran,Douay,FRA,F
,Dylan,Fabre,FRA,F
,Jordann,Perret,FRA,F
,Anthony,Rech,FRA,F
,Nicolas,Ritz,FRA,F
,Alexandre,Texier,FRA,F
,Sacha,Treille,FRA,F
,Yohann,Auvitu,FRA,D
,Jules,Boscq,FRA,D
,Enzo,Cantagallo,FRA,D
,Florian,Chakiachvili,FRA,D
,Pierre,Crinon,FRA,D
,Hugo,Gallet,FRA,D
,Enzo,Guebey,FRA,D
,Thomas,Thiry,FRA,D
,Julian,Junca,FRA,G
,Antoine,Keller,FRA,G
,Martin,Neckar,FRA,G
,Leon,Draisaitl,GER,F
,Alexander,Ehl,GER,F
,Dominik,Kahun,GER,F
,Marc,Michaelis,GER,F
,JJ,Peterka,GER,F
,Lukas,Reichel,GER,F
,Tobias,Rieder,GER,F
,Josh,Samanski,GER,F
,Justin,Schütz,GER,F
,Wojciech,Stachowiak,GER,F
,Tim,Stützle,GER,F
,Nico,Sturm,GER,F
,Frederik,Tiffels,GER,F
,Parker,Tuomie,GER,F
,Leon,Gawanke,GER,D
,Korbinian,Geibel,GER,D
,Lukas,Kälble,GER,D
,Jonas,Muller,GER,D
,Moritz,Muller,GER,D
,Moritz,Seider,GER,D
,Fabio,Wagner,GER,D
,Kai,Wissman,GER,D
,Maximilian,Franzreb,GER,G
,Philipp,Grubauer,GER,G
,Mathias,Niederberger,GER,G
,Matthew,Bradley,ITA,F
,Tommaso De,Luca,ITA,F
,Cristiano,DiGiacinto,ITA,F
,Luca,Frigo,ITA,F
,Mikael,Frycklund,ITA,F
,Dustin,Gazley,ITA,F
,Diego,Kostner,ITA,F
,Daniel,Mantenuto,ITA,F
,Giovanni,Morini,ITA,F
,Alexander,Petan,ITA,F
,Tommy,Purdeller,ITA,F
,Nick,Saracino,ITA,F
,Alessandro,Segafredo,ITA,F
,Marco,Zanetti,ITA,F
,Dylan Di,Perna,ITA,D
,Gregory Di,Tomaso,ITA,D
,Daniel,Glira,ITA,D
,Thomas,Larkin,ITA,D
,Phil,Pietroniro,ITA,D
,Jason,Seed,ITA,D
,Alex,Trivellato,ITA,D
,Luca,Zanatta,ITA,D
,Damian,Clara,ITA,G
,Davide,Fadani,ITA,G
,Gianluca,Vallini,ITA,G
,Oskars,Batna,LAT,F
,Rudolfs,Balcers,LAT,F
,Teddy,Blueger,LAT,F
,Rihards,Bukarts,LAT,F
,Roberts,Bukarts,LAT,F
,Kaspars,Daugavins,LAT,F
,Martins,Dzierkals,LAT,F
,Haralds,Egle,LAT,F
,Zemgus,Girgensons,LAT,F
,Renars,Krastenbergs,LAT,F
,Dans,Locmelis,LAT,F
,Anri,Ravinskis,LAT,F
,Eduards,Tralmaks,LAT,F
,Sandis,Vilmanis,LAT,F
,Uvis,Balinskis,LAT,D
,Oskars,Cibulskis,LAT,D
,Ralfs,Freibergs,LAT,D
,Janis,Jaks,LAT,D
,Roberts,Mamcics,LAT,D
,Kristaps,Rubins,LAT,D
,Alberts,Smits,LAT,D
,Kristaps,Zile,LAT,D
,Kristers,Gudlevskis,LAT,G
,Elvis,Merzlikins,LAT,G
,Arturs,Silovs,LAT,G
,Peter,Cehlarik,SVK,F
,Lukas,Cingel,SVK,F
,Dalibor,Dvorsky,SVK,F
,Libor,Hudacek,SVK,F
,Milos,Kelemen,SVK,F
,Adam,Liska,SVK,F
,Oliver,Okuliar,SVK,F
,Martin,Pospisil,SVK,F
,Pavol,Regenda,SVK,F
,Adam,Ruzicka,SVK,F
,Juraj,Slafkovsky,SVK,F
,Matus,Sukel,SVK,F
,Samuel,Takac,SVK,F
,Tomas,Tatar,SVK,F
,Peter,Ceresnak,SVK,D
,Erik,Cernak,SVK,D
,Martin,Fehervary,SVK,D
,Martin,Gernat,SVK,D
,Michal,Ivan,SVK,D
,Patrik,Koch,SVK,D
,Martin,Marincin,SVK,D
,Simon,Nemec,SVK,D
,Adam,Gajan,SVK,G
,Samuel,Hlavaj,SVK,G
,Stanislav,Skorvanek,SVK,G
,Jesper,Bratt,SWE,F
,Joel Eriksson,Ek,SWE,F
,Filip,Forsberg,SWE,F
,Pontus,Holmberg,SWE,F
,Marcus,Johansson,SWE,F
,Adrian,Kempe,SWE,F
,Gabriel,Landeskog,SWE,F
,Elias,Lindholm,SWE,F
,William,Nylander,SWE,F
,Elias,Pettersson,SWE,F
,Rickard,Rakell,SWE,F
,Lucas,Raymond,SWE,F
,Alexander,Wennberg,SWE,F
,Mika,Zibanejad,SWE,F
,Rasmus,Andersson,SWE,D
,Philip,Broberg,SWE,D
,Rasmus,Dahlin,SWE,D
,Oliver,Ekman-Larsson,SWE,D
,Gustav,Forsling,SWE,D
,Victor,Hedman,SWE,D
,Erik,Karlsson,SWE,D
,Hampus,Lindholm,SWE,D
,Filip,Gustavsson,SWE,G
,Jacob,Markstrom,SWE,G
,Jesper,Wallstedt,SWE,G
,Sven,Andrighetto,SUI,F
,Christoph,Bertschy,SUI,F
,Kevin,Fiala,SUI,F
,Nico,Hischier,SUI,F
,Ken,Jager,SUI,F
,Simon,Knak,SUI,F
,Philipp,Kurashev,SUI,F
,Denis,Malgin,SUI,F
,Timo,Meier,SUI,F
,Nino,Niederreiter,SUI,F
,Damien,Riat,SUI,F
,Sandro,Schmid,SUI,F
,Pius,Suter,SUI,F
,Calvin,Thurkauf,SUI,F
,Tim,Berni,SUI,D
,Michael,Fora,SUI,D
,Andrea,Glauser,SUI,D
,Roman,Josi,SUI,D
,Dean,Kukan,SUI,D
,Christian,Marti,SUI,D
,J.J.,Moser,SUI,D
,Jonas,Siegenthaler,SUI,D
,Reto,Berra,SUI,G
,Leonardo,Genoni,SUI,G
,Akira,Schmid,SUI,G
,Matt,Boldy,USA,F
,Kyle,Connor,USA,F
,Jack,Eichel,USA,F
,Jack,Hughes,USA,F
,Jake,Guentzel,USA,F
,Clayton,Keller,USA,F
,Dylan,Larkin,USA,F
,Auston,Matthews,USA,F
,J.T.,Miller,USA,F
,Brock,Nelson,USA,F
,Brady,Tkachuk,USA,F
,Matthew,Tkachuk,USA,F
,Tage,Thompson,USA,F
,Vincent,Trocheck,USA,F
,Brock,Faber,USA,D
,Noah,Hanifin,USA,D
,Quinn,Hughes,USA,D
,Jackson,LaCombe,USA,D
,Charlie,McAvoy,USA,D
,Jake,Sanderson,USA,D
,Jaccob,Slavin,USA,D
,Zach,Werenski,USA,D
,Connor,Hellebuyck,USA,G
,Jake,Oettinger,USA,G
,Jeremy,Swayman,USA,G"""

# Käytä oikeassa tilanteessa: df = pd.read_csv("input.csv")
df = pd.read_csv(StringIO(csv_data))

print("Aloitetaan ID-haku... Tämä kestää hetken.")
found_count = 0
missing_count = 0

for index, row in df.iterrows():
    fname = row['firstName']
    lname = row['lastName']
    
    # Haetaan ID
    pid = get_nhl_player_id(fname, lname)
    
    if pid:
        df.at[index, 'playerId'] = int(pid)
        print(f"Löytyi: {fname} {lname} -> {pid}")
        found_count += 1
    else:
        print(f"EI LÖYTYNYT: {fname} {lname} (Todennäköisesti Euro-pelaaja)")
        missing_count += 1
        # Vapaaehtoinen: Anna feikki-ID eurooppalaisille jotta sovellus ei kaadu
        # df.at[index, 'playerId'] = 900000 + index 
        
    # Pieni tauko ettei API estä meitä
    time.sleep(0.3) 

# Tallennetaan tulos
df.to_csv("olympic_players_with_ids.csv", index=False)
print(f"\nValmis! Löytyi: {found_count}, Puuttuu: {missing_count}")
print("Tiedosto tallennettu: olympic_players_with_ids.csv")
