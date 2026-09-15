"""Az Energiaár-figyelő beállításai. Itt érdemes módosítani, ha más csúcsidő vagy időtáv kell."""

VERZIO = "v7"
VERZIO_NAPJA = "2026-09-15"

IDOZONA = "Europe/Budapest"

# Villamos energia: Energy-Charts (Fraunhofer ISE), magyar ajánlati zóna
VILLAMOS_ZONA = "HU"
ENERGY_CHARTS_URL = "https://api.energy-charts.info/price"

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

HTTP_FEJLEC = {"User-Agent": "Energiaar-figyelo/3.0 (belso hasznalat)"}
HTTP_IDOKORLAT = 30

SZIN = {
    "tinta": "#0F2A44",      # fő szöveg, holnapi görbe
    "sargarez": "#C8923D",   # kiemelés, csúcsidő
    "acel": "#7D8A97",       # másodlagos szöveg, mai görbe
    "kod": "#EEF2F5",        # panelháttér
    "vonal": "#D6DDE3",      # elválasztók, rács
    "emelkedes": "#B04A3A",  # drágulás
    "csokkenes": "#3F7D58",  # olcsóbbodás
}
