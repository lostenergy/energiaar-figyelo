"""A Kitekintő fül összegzései: területenként néhány mondat a hírek mögötti képről.

Az összegzés kétféleképpen készülhet. Kézzel: beírod a szerkesztői változatban, és a
tárolóba kerül. Gépi segítséggel: ha a beállításokban van nyelvi modell kulcsa, egy
gombnyomásra a mai hírekből készül, és ugyanoda mentődik. A nézegethető változat
mindkét esetben a tárolóból olvassa, tehát a weboldalon is ez látszik.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta

import pandas as pd
import requests

import beallitas as B

OSZLOPOK = ["terulet", "szoveg", "frissitve", "mod"]
MODOK = {"kez": "kézzel írva", "gep": "a hírekből készült", "auto": "magától készült a címekből"}
# Ennyi nap után a kézzel írt összegzést már nem tekintjük időszerűnek
ELAVULAS_NAP = 7

# Témák, amikbe a hírcímeket soroljuk. A sorrend számít: az első illeszkedő téma nyer.
TEMAK = [
    ("leállások", ["leállás", "leáll", "karbantartás", "kiesés", "üzemzavar",
                                 "sztrájk", "outage", "maintenance", "shutdown", "strike",
                                 "disruption", "halt"]),
    ("geopolitika", ["szankció", "embargó", "háború", "orosz", "ukrajn", "közel-kelet",
                                  "sanction", "embargo", "war", "russia", "ukrain", "opec",
                                  "gulf", "tariff", "vám"]),
    ("időjárás", ["hideg", "lehűlés", "meleg", "aszály", "vízállás", "időjárás",
                              "hőmérséklet", "cold", "heat", "drought", "weather", "storm",
                              "river", "snap", "temperature"]),
    ("készletek", ["tároló", "készlet", "feltölt", "storage", "stocks", "inventor",
                              "reserve", "lng"]),
    ("szabályozás", ["kormány", "brüsszel", "európai bizottság", "törvény", "rendelet",
                                 "szabályoz", "adó", "támogatás", "rezsi", "pályázat", "hatóság",
                                 "regulation", "policy", "plan", "target", "subsid", "tax",
                                 "auction", "ruling", "commission"]),
    ("megújulók", ["naperőmű", "napelem", "szélerőmű", "megújuló", "akkumulátor",
                              "solar", "wind", "renewable", "battery", "storage system",
                              "hydrogen", "hidrogén"]),
    ("atomenergia", ["atom", "paks", "nuclear"]),
    ("olaj", ["olaj", "kőolaj", "benzin", "gázolaj", "üzemanyag", "oil", "crude",
                           "diesel", "petrol", "fuel"]),
    ("földgáz", ["földgáz", "gázár", "gáz ", " gáz", "gas"]),
    ("villamos energia", ["áram", "villamos", "erőmű", "hálózat", "tőzsd",
                                     "electricity", "power", "grid", "utility"]),
]

FEL_SZAVAK = ["emelked", "drágul", "drágít", "nő ", "növek", "rekord", "szűkül", "hiány",
              "felfelé", "csúcs", "surge", "rise", "rises", "jump", "soar", "high", "tight",
              "shortage", "record", "up "]
LE_SZAVAK = ["csökken", "olcsób", "zuhan", "mérsékl", "esik", "bővül", "többlet", "lefelé",
             "fall", "falls", "drop", "plunge", "slump", "low", "cheaper", "glut", "down "]

UTASITAS = """Energiapiaci elemző vagy. Magyar irodaházakat üzemeltető cég energiabeszerzéséért
felelős igazgatónak írsz, aki villamos energiát és földgázt vásárol a magyar piacon.

Alább három csoportban kapsz hírcímeket: magyar, európai és világszintű hírek.
Mindhárom csoportról írj egy összegzést, egyenként 3-6 mondatban, magyarul.

Követelmények:
- Csak arra térj ki, aminek köze van a magyar villamosenergia- és földgázárak alakulásához.
- Mondd meg azt is, hogy az adott hír felfelé vagy lefelé hat az árakra, és milyen időtávon.
- Ha egy hírcsoportban nincs érdemi árhatás, írd le ezt is, ne találj ki összefüggést.
- Ne használj gondolatjelet. Vesszőt, pontosvesszőt vagy külön mondatot használj helyette.
- Az idegen szakszavakat kerüld, vagy írd melléjük zárójelben a magyar megfelelőt.
- Ne sorold fel a címeket, hanem foglald össze őket.

A válasz csak egy JSON objektum legyen, pontosan ezzel a három kulccsal:
{"magyar": "...", "europa": "...", "vilag": "..."}"""


def ures() -> pd.DataFrame:
    return pd.DataFrame(columns=OSZLOPOK)


def beallit(tabla: pd.DataFrame | None, terulet: str, szoveg: str, mod: str,
            frissitve: str) -> pd.DataFrame:
    """Egy terület összegzésének felülírása; a többi területé marad."""
    alap = ures() if tabla is None or tabla.empty else tabla.copy()
    alap = alap[alap["terulet"] != terulet]
    uj = pd.DataFrame([{"terulet": terulet, "szoveg": (szoveg or "").strip(),
                        "frissitve": frissitve, "mod": mod}], columns=OSZLOPOK)
    egyben = pd.concat([alap, uj], ignore_index=True)
    return egyben.dropna(subset=["terulet"]).reset_index(drop=True)[OSZLOPOK]


def olvas(tabla: pd.DataFrame | None, terulet: str) -> dict:
    """Egy terület összegzése: szöveg, mikor készült, és milyen módon."""
    ures_valasz = {"szoveg": "", "frissitve": "", "mod": ""}
    if tabla is None or tabla.empty or "terulet" not in tabla.columns:
        return ures_valasz
    sor = tabla[tabla["terulet"] == terulet]
    if sor.empty:
        return ures_valasz
    utolso = sor.iloc[-1]
    szoveg = utolso.get("szoveg")
    return {"szoveg": "" if pd.isna(szoveg) else str(szoveg),
            "frissitve": "" if pd.isna(utolso.get("frissitve")) else str(utolso.get("frissitve")),
            "mod": "" if pd.isna(utolso.get("mod")) else str(utolso.get("mod"))}


def _json_kiszed(szoveg: str) -> dict:
    """A válaszból kiszedi a JSON objektumot, akkor is, ha szöveg van körülötte."""
    try:
        return json.loads(szoveg)
    except (json.JSONDecodeError, TypeError):
        pass
    talalat = re.search(r"\{.*\}", szoveg or "", re.S)
    if not talalat:
        raise ValueError("A válasz nem tartalmazott JSON objektumot.")
    return json.loads(talalat.group(0))


def keszit(hirek_szovegek: dict, kulcs: str, modell: str | None = None,
           idokorlat: int = 90) -> dict:
    """Összegzés készítése a hírcímekből nyelvi modellel.

    A hirek_szovegek szótár kulcsai: magyar, europa, vilag; értéke a hírcímek listája
    szövegként. Visszaad ugyanilyen kulcsokkal egy-egy összegzést.
    """
    if not kulcs:
        raise ValueError("Nincs beállítva nyelvi modell kulcsa.")
    kerdes = "\n\n".join([
        "MAGYAR HÍREK:\n" + (hirek_szovegek.get("magyar") or "(nincs hír)"),
        "EURÓPAI HÍREK:\n" + (hirek_szovegek.get("europa") or "(nincs hír)"),
        "VILÁGSZINTŰ HÍREK:\n" + (hirek_szovegek.get("vilag") or "(nincs hír)"),
    ])
    csomag = {"model": modell or B.OSSZEGZO_MODELL, "max_tokens": 1500,
              "system": UTASITAS, "messages": [{"role": "user", "content": kerdes}]}
    fejlec = {"x-api-key": kulcs, "anthropic-version": "2023-06-01",
              "content-type": "application/json"}
    try:
        valasz = requests.post(B.OSSZEGZO_URL, headers=fejlec, json=csomag, timeout=idokorlat)
    except requests.RequestException as e:
        raise RuntimeError(f"A szolgáltatás nem érhető el: {e}") from e
    if valasz.status_code == 401:
        raise RuntimeError("A kulcsot elutasította a szolgáltatás. Ellenőrizd a beállításokban.")
    if valasz.status_code != 200:
        reszlet = ""
        try:
            reszlet = valasz.json().get("error", {}).get("message", "")
        except Exception:
            pass
        raise RuntimeError(f"Hiba a lekérésnél ({valasz.status_code}). {reszlet}".strip())
    adat = valasz.json()
    darabok = [r.get("text", "") for r in adat.get("content", []) if r.get("type") == "text"]
    eredmeny = _json_kiszed("".join(darabok))
    return {t: str(eredmeny.get(t, "")).strip() for t in ("magyar", "europa", "vilag")}


# ------------------------------------------------------------------ önműködő összegzés

def _tema(szoveg: str) -> str | None:
    kicsi = " " + (szoveg or "").lower() + " "
    for nev, szavak in TEMAK:
        if any(szo in kicsi for szo in szavak):
            return nev
    return None


def _irany(szovegek: list[str]) -> tuple[int, int]:
    fel = le = 0
    for szoveg in szovegek:
        kicsi = " " + (szoveg or "").lower() + " "
        fel += any(szo in kicsi for szo in FEL_SZAVAK)
        le += any(szo in kicsi for szo in LE_SZAVAK)
    return fel, le


def _idojeloles(ido, ma) -> str:
    """Mikor jelent meg a hír, helyi idő szerint, röviden."""
    if ido is None or pd.isna(ido):
        return ""
    jel = pd.Timestamp(ido)
    if jel.tzinfo is not None:
        jel = jel.tz_convert(B.IDOZONA)
    nap = jel.date()
    if nap == ma:
        return "ma"
    if nap == ma - timedelta(days=1):
        return "tegnap"
    return f"{nap.month}. {nap.day}."


def _felsorolas(elemek: list[str]) -> str:
    if len(elemek) == 1:
        return elemek[0]
    return ", ".join(elemek[:-1]) + " és " + elemek[-1]


def magatol(hirek: pd.DataFrame, jelzo: str, ma) -> str:
    """Összegzés a hírcímekből, nyelvi modell nélkül.

    Azt mondja el, hány hír jött, milyen témák köré csoportosulnak, melyik a két
    legfontosabbnak látszó hír, és merre mutatnak a címek szavai. Szándékosan
    óvatosan fogalmaz: a címekből dolgozik, nem a cikkek tartalmából.
    """
    if hirek is None or hirek.empty:
        return ""
    sorok = list(hirek.itertuples())
    szovegek = [str(s.cim) for s in sorok]
    temak = [t for t in (_tema(cim) for cim in szovegek) if t]
    mondatok = []

    darab = len(sorok)
    if temak:
        szamlalo = {}
        for t in temak:
            szamlalo[t] = szamlalo.get(t, 0) + 1
        rangsor = sorted(szamlalo.items(), key=lambda p: (-p[1], p[0]))[:3]
        nevek = _felsorolas([nev for nev, _ in rangsor])
        mondatok.append(f"A {jelzo} hírek közül {darab} kapcsolódik az energiaárakhoz, és ezek "
                        f"főként a következők köré rendeződnek: {nevek}.")
    else:
        mondatok.append(f"A {jelzo} hírek közül {darab} kapcsolódik az energiaárakhoz.")

    kiemelt = [s for s in sorok if getattr(s, "pont", 0) > 0][:2] or sorok[:1]
    for i, sor in enumerate(kiemelt):
        bevezeto = "A címek alapján a leginkább árérzékeny hír" if i == 0 else "Mellette figyelmet érdemel"
        mikor = _idojeloles(sor.ido, ma)
        mikor_resz = f", {mikor}" if mikor else ""
        mondatok.append(f"{bevezeto}: „{str(sor.cim).rstrip('.')}” ({sor.forras}{mikor_resz}).")

    fel, le = _irany(szovegek)
    if fel >= le + 2:
        mondatok.append("A címek szóhasználata inkább emelkedő árak felé mutat, de ez csak jelzés, "
                        "nem előrejelzés.")
    elif le >= fel + 2:
        mondatok.append("A címek szóhasználata inkább mérséklődő árak felé mutat, de ez csak jelzés, "
                        "nem előrejelzés.")

    mondatok.append("A részletekért érdemes megnyitni a cikkeket.")
    return " ".join(mondatok)


def _nap(frissitve: str):
    """A mentés időpontjából a dátum, ha olvasható."""
    try:
        return pd.Timestamp(str(frissitve)).date()
    except (ValueError, TypeError):
        return None


def valaszt(info: dict, hirek: pd.DataFrame, jelzo: str, ma) -> dict:
    """Melyik összegzés jelenjen meg.

    A kézzel írt vagy modellel készült szöveg az elsődleges, amíg időszerű. Ha nincs ilyen,
    vagy már elavult, a hírcímekből magától készülő összegzés jelenik meg, ami minden
    frissítéssel együtt mozog.
    """
    info = info or {}
    szoveg = (info.get("szoveg") or "").strip()
    frissitve = info.get("frissitve") or ""
    if szoveg:
        nap = _nap(frissitve)
        if nap is None or (ma - nap).days <= ELAVULAS_NAP:
            return {"szoveg": szoveg, "mod": info.get("mod") or "kez",
                    "frissitve": frissitve, "regi_irt": ""}
    return {"szoveg": magatol(hirek, jelzo, ma), "mod": "auto", "frissitve": "",
            "regi_irt": frissitve if szoveg else ""}
