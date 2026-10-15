"""HUPX Labs: a magyar áramtőzsde nyilvános adatai.

Két dolgot hoz, amit eddig nem tudtunk máshonnan:

- a másnapi árakat magától a tőzsdétől, negyedórás bontásban és forgalommal együtt, ezért
  nem kell megvárni, amíg egy külső szolgáltatás átveszi őket,
- a magyar erőművi kieséseket (tervezett karbantartás és üzemzavar), amik a másnapi árat
  a leginkább mozgatják.

A felület nyilvános, belépés és kulcs nélkül olvasható. Az előzmény rövid, körülbelül két
hónap, ezért a hosszú árelőzmény továbbra is a másik forrásból jön.
"""

from __future__ import annotations

import re
from datetime import date

import pandas as pd

import beallitas as B
import forrasok as F

ARAK_OSZLOPOK = F.VILLAMOS_OSZLOPOK + ["forgalom"]
KIESES_OSZLOPOK = ["kezdet", "veg", "egyseg", "tulajdonos", "tipus", "uzemanyag",
                   "kieso_mw", "beepitett_mw", "ok"]

# A forrás angolul adja a tüzelőanyagot
UZEMANYAG = {
    "Fossil Brown coal/Lignite": "lignit", "Fossil Hard coal": "szén", "Fossil Gas": "földgáz",
    "Fossil Oil": "olaj", "Nuclear": "atom", "Biomass": "biomassza", "Waste": "hulladék",
    "Hydro Water Reservoir": "víz", "Hydro Run-of-river and poundage": "víz",
    "Wind Onshore": "szél", "Solar": "nap", "Geothermal": "geotermikus", "Other": "egyéb",
}
# A cégnevek hosszúak, a táblázatban a rövid alak olvashatóbb
CEGFORMA = [("Zártkörűen Működő Részvénytársaság", "Zrt."),
            ("Nyilvánosan Működő Részvénytársaság", "Nyrt."),
            ("Korlátolt Felelősségű Társaság", "Kft."),
            ("Részvénytársaság", "Rt.")]
HTML_JEL = re.compile(r"<[^>]+>")
TOBB_SZOKOZ = re.compile(r"\s+")


def _tiszta(szoveg) -> str:
    if not szoveg or pd.isna(szoveg):
        return ""
    return TOBB_SZOKOZ.sub(" ", HTML_JEL.sub(" ", str(szoveg))).strip()


def _rovid_ceg(nev: str) -> str:
    for hosszu, rovid in CEGFORMA:
        nev = nev.replace(hosszu, rovid)
    return nev.strip()


def _lekerdez(cim: str, szuro: str, nev: str) -> list:
    valasz = F.keres(cim, {"filter": szuro}, nev)
    if valasz.status_code != 200:
        raise F.ForrasHiba(f"{nev}: HTTP {valasz.status_code}")
    adat = valasz.json()
    return adat.get("data") or []


# ------------------------------------------------------------------ másnapi árak

def leker_arak(kezdet: date, veg: date) -> pd.DataFrame:
    """A magyar másnapi árak negyedórás bontásban, a kért szállítási napokra."""
    szuro = (f"DeliveryDay__gte__{kezdet.isoformat()},DeliveryDay__lte__{veg.isoformat()},"
             "Region__in__HU")
    return feldolgoz_arak(_lekerdez(B.HUPX_ARAK_URL, szuro, "HUPX Labs"))


def feldolgoz_arak(sorok: list) -> pd.DataFrame:
    """A válasz átalakítása a program szokásos ártáblájává.

    A forrás szállítási napot és negyedóra-sorszámot ad (1-től 96-ig). Ebből úgy számolunk
    időpontot, hogy a szállítási nap helyi éjfelétől negyedóránként lépünk előre. Így az
    óraátállítás napja is helyes marad, amikor 92 vagy 100 negyedóra van.
    """
    if not sorok:
        return F.ures(ARAK_OSZLOPOK)
    tetelek = []
    for sor in sorok:
        nap = str(sor.get("DeliveryDay") or "")[:10]
        sorszam = pd.to_numeric(sor.get("ProductQH"), errors="coerce")
        ar = pd.to_numeric(sor.get("Price"), errors="coerce")
        if not nap or pd.isna(sorszam) or pd.isna(ar):
            continue
        tetelek.append({"nap_cimke": nap, "sorszam": int(sorszam), "ar": float(ar),
                        "forgalom": pd.to_numeric(sor.get("Volume"), errors="coerce")})
    if not tetelek:
        return F.ures(ARAK_OSZLOPOK)

    tabla = pd.DataFrame(tetelek)
    kezdetek = {n: int(pd.Timestamp(f"{n} 00:00", tz=B.IDOZONA).timestamp())
                for n in tabla["nap_cimke"].unique()}
    tabla["unix"] = tabla["nap_cimke"].map(kezdetek) + (tabla["sorszam"] - 1) * 900

    helyi = pd.to_datetime(tabla["unix"], unit="s", utc=True).dt.tz_convert(B.IDOZONA)
    tabla["ido"] = helyi.dt.strftime("%Y-%m-%d %H:%M")
    tabla["nap"] = helyi.dt.strftime("%Y-%m-%d")
    tabla["negyedora"] = helyi.dt.strftime("%H:%M")
    tabla["ora"] = helyi.dt.hour
    tabla["perc"] = 15
    tabla["ar"] = tabla["ar"].round(2)
    return (tabla.drop_duplicates("unix", keep="last").sort_values("unix")
            .reset_index(drop=True)[ARAK_OSZLOPOK])


def napi_forgalom(tabla: pd.DataFrame) -> dict:
    """Szállítási naponként a megkereskedett mennyiség, megawattórában."""
    if tabla is None or tabla.empty or "forgalom" not in tabla.columns:
        return {}
    t = tabla.dropna(subset=["forgalom"])
    if t.empty:
        return {}
    # A forgalom megawattban értendő negyedóránként, ezért négy negyedóra ad egy órányit.
    osszeg = t.groupby("nap")["forgalom"].sum() / 4
    return {nap: round(float(ertek), 1) for nap, ertek in osszeg.items()}


# ------------------------------------------------------------------ erőművi kiesések

def leker_kiesesek(nap: date) -> pd.DataFrame:
    """Az adott napon érvényes magyar erőművi kiesések."""
    szuro = (f"IntervalStart__lte__{nap.isoformat()},IntervalStop__gte__{nap.isoformat()},"
             "EventStatus__eq__Active")
    return feldolgoz_kiesesek(_lekerdez(B.HUPX_KIESESEK_URL, szuro, "HUPX kiesések"))


def feldolgoz_kiesesek(sorok: list) -> pd.DataFrame:
    """A kiesések táblája: nem tervezett elöl, azon belül a nagyobb kieséssel."""
    if not sorok:
        return F.ures(KIESES_OSZLOPOK)
    tetelek = []
    for sor in sorok:
        kieso = pd.to_numeric(sor.get("UnavailableCapacity"), errors="coerce")
        if pd.isna(kieso):
            continue
        tervezett = str(sor.get("UnavailabilityType") or "").lower().startswith("planned")
        tetelek.append({
            "kezdet": str(sor.get("EventStart") or "")[:16].replace("T", " "),
            "veg": str(sor.get("EventStop") or "")[:16].replace("T", " "),
            "egyseg": _tiszta(sor.get("AffectedAssetUnit")),
            "tulajdonos": _rovid_ceg(_tiszta(sor.get("MarketParticipant"))),
            "tipus": "tervezett" if tervezett else "nem tervezett",
            "uzemanyag": UZEMANYAG.get(str(sor.get("FuelType") or ""),
                                       _tiszta(sor.get("FuelType")).lower()),
            "kieso_mw": float(kieso),
            "beepitett_mw": float(pd.to_numeric(sor.get("InstalledCapacity"), errors="coerce") or 0),
            "ok": _tiszta(sor.get("UnavailabilityReason")),
        })
    tabla = pd.DataFrame(tetelek, columns=KIESES_OSZLOPOK)
    if tabla.empty:
        return tabla
    tabla["rend"] = (tabla["tipus"] == "nem tervezett").astype(int)
    return (tabla.sort_values(["rend", "kieso_mw"], ascending=[False, False])
            .drop(columns=["rend"]).reset_index(drop=True))


def ures_kiesesek() -> pd.DataFrame:
    return F.ures(KIESES_OSZLOPOK)


def kieses_osszegzes(tabla: pd.DataFrame) -> dict:
    """Mennyi kapacitás áll most, tervezetten és nem tervezetten."""
    ures = {"nem_tervezett_mw": 0.0, "tervezett_mw": 0.0, "osszes_mw": 0.0, "darab": 0}
    if tabla is None or tabla.empty:
        return ures
    nem = float(tabla[tabla["tipus"] == "nem tervezett"]["kieso_mw"].sum())
    terv = float(tabla[tabla["tipus"] == "tervezett"]["kieso_mw"].sum())
    return {"nem_tervezett_mw": round(nem, 1), "tervezett_mw": round(terv, 1),
            "osszes_mw": round(nem + terv, 1), "darab": len(tabla)}
