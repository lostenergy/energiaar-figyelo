"""Az Energiaár-figyelő beállításai. Itt érdemes módosítani, ha más csúcsidő vagy időtáv kell."""

VERZIO = "v13"
VERZIO_NAPJA = "2026-09-24"

IDOZONA = "Europe/Budapest"

# Villamos energia: Energy-Charts (Fraunhofer ISE), magyar ajánlati zóna
VILLAMOS_ZONA = "HU"
ENERGY_CHARTS_URL = "https://api.energy-charts.info/price"
# Villamosenergia-termelés forrásonként, ugyanabból a forrásból (ENTSO-E adat alapján)
TERMELES_URL = "https://api.energy-charts.info/public_power"
# Ennyi napnyi termelési előzményt tölt be az első futáskor
TERMELES_ELOZMENY_NAP = 120
# Beépített (telepített) erőművi teljesítmény forrásonként, évenként; ugyanabból a forrásból
KAPACITAS_URL = "https://api.energy-charts.info/installed_power"
KAPACITAS_ELTARTHATOSAG = 24 * 3600

# Csúcsidőszak: 8 órától 20 óráig (a 20 óra már nem része)
CSUCS_KEZDET = 8
CSUCS_VEGE = 20

# Villamos előzmény ennyi napra visszamenőleg (a heti, havi, negyedéves és éves átlagokhoz).
# Nagyobb érték lassabb első betöltést jelent.
ELOZMENY_NAP = 400
# A legutóbbi napok és a holnapi ár, gyakori frissítéssel
FRISS_NAP = 3

# Meddig őrzi meg a program a lekért adatot, mielőtt magától újra kérné (másodperc)
ELOZMENY_ELTARTHATOSAG = 6 * 3600
FRISS_ELTARTHATOSAG = 15 * 60

# Földgáz: CEEGEX nyilvános oldalai
CEEGEX_MASNAPI_URL = "https://ceegex.hu/en/market-data/daily-data"
CEEGEX_NAPON_BELUL_URL = "https://ceegex.hu/en/market-data/hourly-data"

# Euró-forint árfolyam: az Európai Központi Bank referenciaárfolyama, tartalékként a Frankfurter
# szolgáltatás (szintén EKB-adat). Ha egyik sem érhető el, a tartalék értékkel számol, és jelzi.
EKB_ARFOLYAM_URL = ("https://data-api.ecb.europa.eu/service/data/EXR/D.HUF.EUR.SP00.A"
                    "?lastNObservations=1&format=csvdata")
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest?base=EUR&symbols=HUF"
EUR_HUF_TARTALEK = 365.0
ARFOLYAM_ELTARTHATOSAG = 6 * 3600

HTTP_FEJLEC = {"User-Agent": "Energiaar-figyelo/3.0 (belso hasznalat)"}
HTTP_IDOKORLAT = 30

# CPIFM arculati színek
SZIN = {
    "tinta": "#0F2A44",       # fő szöveg, holnapi görbe, sötét sáv
    "tinta_mely": "#0A1E31",  # a sötét sáv mélyebb árnyalata
    "sargarez": "#C8923D",    # arany kiemelés, csúcsidő
    "arany_hatter": "#F0E2C2",  # világos arany háttér
    "acel": "#6B7785",        # másodlagos szöveg, mai görbe
    "kod": "#F4F6F8",         # kártyaháttér
    "vonal": "#D6DDE3",       # elválasztók, rács
    "emelkedes": "#B85042",   # drágulás, kockázat
    "csokkenes": "#5A8F6B",   # olcsóbbodás, előny
}

# A Lehetőségek fül alapértelmezései (a felületen átírhatók)
ALAP_EVES_ARAM_MWH = 1000
ALAP_EVES_GAZ_MWH = 800
# Irodaház: az áramfogyasztás ekkora része esik a csúcsidőszakba (hétköznap 8 és 20 óra között)
ALAP_CSUCS_ARANY = 0.62
# Irodaházi gázfelhasználás negyedéves megoszlása (fűtési idény súlyával): I., II., III., IV. negyedév
GAZ_NEGYEDEVES_SULY = (0.42, 0.11, 0.04, 0.43)
