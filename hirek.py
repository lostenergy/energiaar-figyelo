"""Kitekintő: energiapiaci hírek gyűjtése nyilvános hírcsatornákból (RSS).

Három területre bontva gyűjt: Magyarország, Európa és a világ. Az általános gazdasági
csatornákból csak az energiával kapcsolatos híreket tartja meg, a szakmai csatornákból
mindent. A híreket fontosság szerint rendezi: előre kerül, ami az árakat mozgatja
(időjárás, leállás, szankció, szabályozás, készlet), mögé a többi.

A csatornák nyilvánosak és díjmentesek. Ha egy csatorna nem válaszol, a többi attól még
működik, és a felület jelzi, melyik maradt ki.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import pandas as pd
import requests

import beallitas as B

OSZLOPOK = ["terulet", "ido", "cim", "link", "forras", "pont"]

TERULETEK = [("magyar", "Magyarország"), ("europa", "Európa"), ("vilag", "Világ")]
TERULET_NEVEK = dict(TERULETEK)
# Az összegzés bevezetéséhez: "A hazai hírek közül..."
TERULET_JELZO = {"magyar": "hazai", "europa": "európai", "vilag": "világszintű"}


@dataclass(frozen=True)
class Forras:
    """Egy hírcsatorna. A szures=True azt jelenti, hogy általános hírfolyam, ezért
    csak az energiával kapcsolatos híreket vesszük ki belőle."""
    nev: str
    cim: str
    terulet: str
    szures: bool = True
    magyar: bool = True


FORRASOK = [
    # Magyarország: általános gazdasági hírfolyamok, energiaszűréssel
    Forras("Portfolio", "https://www.portfolio.hu/rss/all.xml", "magyar"),
    Forras("Világgazdaság", "https://www.vg.hu/feed/", "magyar"),
    Forras("Economx", "https://www.economx.hu/feed/", "magyar"),
    Forras("HVG Gazdaság", "https://hvg.hu/rss/gazdasag", "magyar"),
    # Európa: energiára szakosodott csatornák, és a magyar nyelvű globál rovat
    Forras("Clean Energy Wire", "https://www.cleanenergywire.org/rss.xml", "europa",
           szures=False, magyar=False),
    Forras("Balkan Green Energy News", "https://balkangreenenergynews.com/feed/", "europa",
           szures=False, magyar=False),
    Forras("Portfolio Globál", "https://www.portfolio.hu/rss/global.xml", "europa"),
    # Világ: nyersanyag- és energiapiaci csatornák
    Forras("Oilprice", "https://oilprice.com/rss/main", "vilag", szures=False, magyar=False),
    Forras("pv magazine", "https://www.pv-magazine.com/feed/", "vilag", szures=False, magyar=False),
]

# Energiával kapcsolatos-e a hír. Az általános hírfolyamoknál ez dönti el, hogy bekerül-e.
ENERGIA_SZAVAK = [
    # magyar
    "energi", "áram", "villamos", "földgáz", "gázár", " gáz", "gáz-", "olaj", "kőolaj", "üzemanyag",
    "benzin", "gázolaj", "atomerőmű", "paks", "naperőmű", "napelem", "szélerőmű", "erőmű", "mvm",
    "mol ", "rezsi", "hálózati", "akkumulátor", "hidrogén", "kibocsátás", "szén-dioxid", "lng",
    "vezeték", "fűtés", "hőszivattyú", "tőzsde", "kvóta", "ets", "barátság", "török áramlat",
    # angol
    "energy", "electricity", "power ", "gas", "oil", "crude", "nuclear", "solar", "wind",
    "grid", "battery", "hydrogen", "emission", "carbon", "coal", "pipeline", "opec", "fuel",
    "renewable", "lng", "utility", "heating",
]

# Ami jellemzően mozgatja az árat. Az ilyen hírek kerülnek előre.
AR_SZAVAK = [
    # magyar
    "ár", "árak", "drágul", "olcsób", "emelked", "zuhan", "csökken", "szankció", "embargó",
    "leállás", "karbantartás", "hideg", "meleg", "aszály", "készlet", "tároló", "korlátoz",
    "szabályoz", "adó", "támogatás", "szerződés", "import", "export", "sztrájk", "háború",
    "tárgyalás", "döntés", "bírság", "hiány", "rekord",
    # angol
    "price", "prices", "surge", "plunge", "fall", "rise", "cut", "sanction", "embargo",
    "outage", "maintenance", "cold", "heat", "drought", "storage", "stocks", "curb",
    "regulation", "tax", "subsidy", "contract", "import", "export", "strike", "war",
    "talks", "ruling", "shortage", "record", "cap",
]

NEV_TER = {"{http://www.w3.org/2005/Atom}": "atom"}
HTML_JEL = re.compile(r"<[^>]+>")
TOBB_SZOKOZ = re.compile(r"\s+")


def _tiszta(szoveg: str | None) -> str:
    if not szoveg:
        return ""
    return TOBB_SZOKOZ.sub(" ", HTML_JEL.sub(" ", szoveg)).strip()


def _datum(szoveg: str | None) -> datetime | None:
    """RSS (RFC 822) és Atom (ISO) dátum beolvasása, mindig időzónával."""
    if not szoveg:
        return None
    szoveg = szoveg.strip()
    try:
        d = parsedate_to_datetime(szoveg)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(szoveg.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d is None:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def energia_e(szoveg: str) -> bool:
    kicsi = " " + szoveg.lower() + " "
    return any(szo in kicsi for szo in ENERGIA_SZAVAK)


def fontossag(szoveg: str) -> int:
    """Hány árat mozgató szó van a hírben. Ez adja a sorrendet."""
    kicsi = " " + szoveg.lower() + " "
    return sum(1 for szo in AR_SZAVAK if f" {szo}" in kicsi)


def feldolgoz_csatorna(tartalom: str | bytes, forras: Forras) -> list[dict]:
    """Egy csatorna tartalmából hírek listája. Kezeli az RSS 2.0 és az Atom formátumot is."""
    try:
        gyoker = ElementTree.fromstring(tartalom)
    except ElementTree.ParseError:
        return []
    atom = "{http://www.w3.org/2005/Atom}"
    tetelek = gyoker.findall(".//item") or gyoker.findall(f".//{atom}entry")
    hirek = []
    for tetel in tetelek:
        cim = _tiszta(tetel.findtext("title") or tetel.findtext(f"{atom}title"))
        if not cim:
            continue
        link = (tetel.findtext("link") or "").strip()
        if not link:
            elem = tetel.find(f"{atom}link")
            link = (elem.get("href") if elem is not None else "") or ""
        leiras = _tiszta(tetel.findtext("description") or tetel.findtext(f"{atom}summary"))
        ido = _datum(tetel.findtext("pubDate") or tetel.findtext(f"{atom}updated")
                     or tetel.findtext(f"{atom}published"))
        egyben = f"{cim} {leiras}"
        if forras.szures and not energia_e(egyben):
            continue
        hirek.append({"terulet": forras.terulet, "ido": ido, "cim": cim, "link": link.strip(),
                      "forras": forras.nev, "pont": fontossag(egyben)})
    return hirek


def leker_csatorna(forras: Forras, idokorlat: int = 10) -> list[dict]:
    valasz = requests.get(forras.cim, headers=B.HTTP_FEJLEC, timeout=idokorlat)
    valasz.raise_for_status()
    return feldolgoz_csatorna(valasz.content, forras)


def osszegyujt(forrasok: list[Forras] | None = None, napok: int = 10,
               darab: int = 10, most: datetime | None = None) -> dict:
    """Minden csatorna lekérése párhuzamosan, majd területenként a legfontosabb hírek.

    Visszaad: {"hirek": DataFrame, "hibak": [szöveg], "forrasok": hány csatorna válaszolt}
    """
    forrasok = list(forrasok if forrasok is not None else FORRASOK)
    most = most or datetime.now(timezone.utc)
    sorok, hibak, sikeres = [], [], 0
    with ThreadPoolExecutor(max_workers=6) as vegrehajto:
        eredmenyek = list(vegrehajto.map(lambda f: (f, _biztonsagos(f)), forrasok))
    for forras, (hirek, hiba) in eredmenyek:
        if hiba:
            hibak.append(f"{forras.nev}: {hiba}")
            continue
        sikeres += 1
        sorok.extend(hirek)

    tabla = pd.DataFrame(sorok, columns=OSZLOPOK)
    if tabla.empty:
        return {"hirek": tabla, "hibak": hibak, "forrasok": sikeres}

    hatar = most - timedelta(days=napok)
    tabla = tabla[tabla["ido"].notna() & (tabla["ido"] >= hatar) & (tabla["ido"] <= most + timedelta(hours=6))]
    tabla = tabla.drop_duplicates("link").copy()
    tabla["kulcs"] = tabla["cim"].str.lower().str.replace(r"[^a-záéíóöőúüű0-9 ]", "", regex=True)
    tabla = tabla.drop_duplicates("kulcs").drop(columns=["kulcs"])

    # Frissesség és fontosság együtt adja a sorrendet: a mai hír előnyt élvez.
    kor_ora = (most - tabla["ido"]).dt.total_seconds() / 3600
    tabla["rangsor"] = tabla["pont"] * 2 - (kor_ora / 24)
    reszek = [csoport.sort_values("rangsor", ascending=False).head(darab)
              for _, csoport in tabla.groupby("terulet")]
    egyben = pd.concat(reszek, ignore_index=True) if reszek else tabla
    return {"hirek": egyben.sort_values(["terulet", "rangsor"], ascending=[True, False])
            .drop(columns=["rangsor"]).reset_index(drop=True),
            "hibak": hibak, "forrasok": sikeres}


def _biztonsagos(forras: Forras) -> tuple[list[dict], str]:
    try:
        return leker_csatorna(forras), ""
    except requests.RequestException as e:
        return [], str(e)[:120]
    except Exception as e:  # hibás tartalom esetén se álljon meg a többi
        return [], str(e)[:120]


def terulet_hirei(hirek: pd.DataFrame, terulet: str) -> pd.DataFrame:
    if hirek is None or hirek.empty:
        return pd.DataFrame(columns=OSZLOPOK)
    return hirek[hirek["terulet"] == terulet].reset_index(drop=True)


def hirek_szovegge(hirek: pd.DataFrame, terulet: str, darab: int = 10) -> str:
    """A hírek felsorolása szövegként, az összegzés elkészítéséhez."""
    resz = terulet_hirei(hirek, terulet).head(darab)
    sorok = []
    for sor in resz.itertuples():
        nap = sor.ido.strftime("%Y-%m-%d") if pd.notna(sor.ido) else ""
        sorok.append(f"- ({nap}, {sor.forras}) {sor.cim}")
    return "\n".join(sorok)
