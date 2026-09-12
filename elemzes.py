"""Piaci kép: számokban összefoglalt helyzetkép a meglévő adatokból, és ingyenes elemzési források."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

import szamitas as S

# Ingyenesen elérhető, rendszeresen frissülő elemzések és adattárak
FORRASOK = [
    {"nev": "MEKH havi és negyedéves energiapiaci jelentések", "tav": "rövid és közép",
     "leiras": "Magyar hatósági összefoglaló a villamosenergia- és gázpiac áráról, fogyasztásáról.",
     "cim": "https://www.mekh.hu/statisztika"},
    {"nev": "MAVIR üzemirányítási adatok", "tav": "rövid",
     "leiras": "Magyar rendszerterhelés, termelés és határkeresztező forgalom, napi bontásban.",
     "cim": "https://www.mavir.hu/web/mavir/uzemi-adatok"},
    {"nev": "ENTSO-E Transparency Platform", "tav": "rövid",
     "leiras": "Európai termelési, fogyasztási és határkeresztező adatok, ingyenes regisztrációval.",
     "cim": "https://transparency.entsoe.eu/"},
    {"nev": "Energy-Charts (Fraunhofer ISE)", "tav": "rövid és közép",
     "leiras": "Európai árak, termelési szerkezet és importfüggőség, letölthető grafikonokkal.",
     "cim": "https://energy-charts.info/"},
    {"nev": "Európai Bizottság negyedéves piaci jelentései", "tav": "közép és hosszú",
     "leiras": "Részletes negyedéves elemzés az európai villamosenergia- és gázpiacról, ábrákkal.",
     "cim": "https://energy.ec.europa.eu/data-and-analysis/market-analysis_en"},
    {"nev": "GIE AGSI gáztárolói töltöttség", "tav": "rövid és közép",
     "leiras": "Európai és magyar gáztárolói szintek; a téli árak egyik fő mozgatója.",
     "cim": "https://agsi.gie.eu/"},
    {"nev": "Ember európai villamosenergia-elemzések", "tav": "közép és hosszú",
     "leiras": "Havi és éves elemzések az európai áramtermelés szerkezetéről és áráról.",
     "cim": "https://ember-energy.org/data/european-electricity-review/"},
    {"nev": "Bruegel energiapiaci adattárak", "tav": "közép és hosszú",
     "leiras": "Kutatóintézeti adatsorok és elemzések az európai energiaárakról.",
     "cim": "https://www.bruegel.org/datasets"},
    {"nev": "IEA Electricity és Gas Market Report", "tav": "hosszú",
     "leiras": "Féléves nemzetközi kitekintés kereslet-kínálati előrejelzésekkel.",
     "cim": "https://www.iea.org/topics/electricity"},
]


def _atlag(napi: pd.DataFrame, ma: date, tol_nap: int, ig_nap: int = 0, oszlop: str = "zsinor"):
    """Átlag a mai naptól visszaszámított időszakra."""
    if napi.empty:
        return None
    t = napi.copy()
    t["datum"] = pd.to_datetime(t["nap"])
    kezdet = pd.Timestamp(ma) - pd.Timedelta(days=tol_nap)
    veg = pd.Timestamp(ma) - pd.Timedelta(days=ig_nap)
    resz = t[(t["datum"] >= kezdet) & (t["datum"] <= veg)]
    return round(float(resz[oszlop].mean()), 2) if not resz.empty else None


def villamos_kep(napi: pd.DataFrame, ma: date) -> dict:
    """Villamos helyzetkép: mostani szint, mozgás, csúcsprémium, tavalyi összevetés."""
    ki = {"mai": None, "holnapi": None, "holnap_valtozas": None, "het": None, "honap": None,
          "negyedev": None, "elozo_honap": None, "honap_valtozas": None, "egy_eve": None,
          "ev_valtozas": None, "csucs_premium": None, "legolcsobb": None, "legdragabb": None}
    if napi.empty:
        return ki
    terkep = napi.set_index("nap")
    if ma.isoformat() in terkep.index:
        ki["mai"] = terkep.at[ma.isoformat(), "zsinor"]
    holnap = (ma + timedelta(days=1)).isoformat()
    if holnap in terkep.index:
        ki["holnapi"] = terkep.at[holnap, "zsinor"]
        ki["holnap_valtozas"] = S.valtozas(ki["holnapi"], ki["mai"])
        ki["legolcsobb"] = (terkep.at[holnap, "min_ido"], terkep.at[holnap, "min_ar"])
        ki["legdragabb"] = (terkep.at[holnap, "max_ido"], terkep.at[holnap, "max_ar"])
        ki["csucs_premium"] = S.valtozas(terkep.at[holnap, "csucs"], terkep.at[holnap, "csucson_kivul"])
    elif ma.isoformat() in terkep.index:
        ki["legolcsobb"] = (terkep.at[ma.isoformat(), "min_ido"], terkep.at[ma.isoformat(), "min_ar"])
        ki["legdragabb"] = (terkep.at[ma.isoformat(), "max_ido"], terkep.at[ma.isoformat(), "max_ar"])
        ki["csucs_premium"] = S.valtozas(terkep.at[ma.isoformat(), "csucs"],
                                         terkep.at[ma.isoformat(), "csucson_kivul"])
    ki["het"] = _atlag(napi, ma, 6)
    ki["honap"] = _atlag(napi, ma, 29)
    ki["negyedev"] = _atlag(napi, ma, 89)
    ki["elozo_honap"] = _atlag(napi, ma, 59, 30)
    ki["honap_valtozas"] = S.valtozas(ki["honap"], ki["elozo_honap"])
    ki["egy_eve"] = _atlag(napi, ma, 394, 335)  # az egy évvel korábbi azonos harminc nap
    ki["ev_valtozas"] = S.valtozas(ki["honap"], ki["egy_eve"])
    return ki


def gaz_kep(gaz: pd.DataFrame) -> dict:
    """Gáz helyzetkép a CEEGEX másnapi árakból."""
    ki = {"mai": None, "het_valtozas": None, "honap": None, "elozo_honap": None, "honap_valtozas": None,
          "legkisebb": None, "legnagyobb": None, "napok": 0}
    if gaz.empty:
        return ki
    da = gaz[(gaz["termek"] == "DA") & gaz["atlagar"].notna()].sort_values("kereskedesi_nap")
    if da.empty:
        return ki
    arak = da["atlagar"].astype(float)
    ki["mai"] = round(float(arak.iloc[-1]), 2)
    ki["napok"] = len(da)
    if len(da) > 5:
        ki["het_valtozas"] = S.valtozas(arak.iloc[-1], arak.iloc[-6])
    utolso21 = arak.tail(21)
    ki["honap"] = round(float(utolso21.mean()), 2)
    if len(arak) > 42:
        ki["elozo_honap"] = round(float(arak.iloc[-42:-21].mean()), 2)
        ki["honap_valtozas"] = S.valtozas(ki["honap"], ki["elozo_honap"])
    ki["legkisebb"] = round(float(arak.min()), 2)
    ki["legnagyobb"] = round(float(arak.max()), 2)
    return ki


def arany(villamos_ar: float | None, gaz_ar: float | None) -> float | None:
    """A villamos és a gáz árának hányadosa. Nagyjából 2,0 alatt a gáztüzelés olcsó árammal jár."""
    if villamos_ar is None or gaz_ar is None or pd.isna(villamos_ar) or pd.isna(gaz_ar) or not gaz_ar:
        return None
    return round(float(villamos_ar) / float(gaz_ar), 2)


def _sz(x, tizedes: int = 2) -> str:
    """Magyar tizedesjel, ezres tagolás nélkül."""
    return f"{float(x):.{tizedes}f}".replace(".", ",")


def helyzet_szoveg(v: dict, g: dict, ar: float | None) -> list[str]:
    """Néhány mondat a számokról, magyarul. Csak azt írja le, ami az adatokból következik."""
    mondatok = []
    if v.get("honap") is not None:
        alap = f"A villamos zsinórár utóbbi harminc napi átlaga {_sz(v['honap'])} EUR/MWh"
        if v.get("honap_valtozas") is not None:
            irany = "magasabb" if v["honap_valtozas"] > 0 else "alacsonyabb"
            alap += (f", ami {_sz(abs(v['honap_valtozas']) * 100, 1)} százalékkal {irany} "
                     "az azt megelőző harminc napnál")
        mondatok.append(alap + ".")
    if v.get("ev_valtozas") is not None:
        irany = "drágább" if v["ev_valtozas"] > 0 else "olcsóbb"
        mondatok.append(f"Egy évvel korábbi azonos időszakhoz mérve "
                        f"{_sz(abs(v['ev_valtozas']) * 100, 1)} százalékkal {irany}.")
    if v.get("csucs_premium") is not None:
        if v["csucs_premium"] >= 0:
            mondatok.append(f"A csúcsidőszak {_sz(v['csucs_premium'] * 100, 1)} százalékkal drágább "
                            "a csúcson kívüli időszaknál.")
        else:
            mondatok.append(f"A csúcsidőszak most {_sz(abs(v['csucs_premium']) * 100, 1)} százalékkal "
                            "olcsóbb a csúcson kívüli időszaknál, ezt jellemzően a déli naperőművi "
                            "termelés okozza.")
    if g.get("mai") is not None:
        alap = f"A földgáz másnapi ára {_sz(g['mai'])} EUR/MWh"
        if g.get("honap_valtozas") is not None:
            irany = "emelkedett" if g["honap_valtozas"] > 0 else "csökkent"
            alap += (f", a havi átlag pedig {_sz(abs(g['honap_valtozas']) * 100, 1)} százalékkal "
                     f"{irany} az előző harminc naphoz képest")
        mondatok.append(alap + ".")
    if ar is not None:
        mondatok.append(f"A villamos és a gáz árának hányadosa {_sz(ar)}; minél közelebb van kettőhöz, "
                        "annál inkább a gáztüzelés szabja meg az áramárat.")
    return mondatok
