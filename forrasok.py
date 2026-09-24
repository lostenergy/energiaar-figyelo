"""Adatforrások lekérése és feldolgozása egységes táblákká.

A lekérő függvények hálózatot használnak, a feldolgozók (feldolgoz_*) tiszta függvények, így tesztelhetők.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from html.parser import HTMLParser

import pandas as pd
import requests

import beallitas as B

VILLAMOS_OSZLOPOK = ["unix", "ido", "nap", "negyedora", "ora", "ar", "perc"]
GAZ_MASNAPI_OSZLOPOK = [
    "kulcs", "kereskedesi_nap", "termek", "szallitas_kezdete", "szallitas_vege",
    "mennyiseg_mwh", "kotesek", "atlagar", "ceerep", "ceerep_valtozas",
]
GAZ_NAPON_BELUL_OSZLOPOK = ["kulcs", "gaznap", "gazora", "mennyiseg_mwh", "atlagar", "valtozas"]


class ForrasHiba(Exception):
    """Érthető hibaüzenet egy adatforrás hibájáról."""


# ---------------------------------------------------------------- Villamos energia

def leker_villamos(kezdet: date, veg: date, szakasz_nap: int = 60) -> pd.DataFrame:
    """Magyar másnapi árak az Energy-Charts API-ból, a kért napokra (a vég napját is beleértve)."""
    reszek = []
    aktualis = kezdet
    while aktualis <= veg:
        szakasz_vege = min(aktualis + timedelta(days=szakasz_nap - 1), veg)
        parameterek = {
            "bzn": B.VILLAMOS_ZONA,
            "start": aktualis.isoformat(),
            "end": (szakasz_vege + timedelta(days=1)).isoformat(),
        }
        try:
            valasz = requests.get(B.ENERGY_CHARTS_URL, params=parameterek,
                                  headers=B.HTTP_FEJLEC, timeout=B.HTTP_IDOKORLAT)
        except requests.RequestException as e:
            raise ForrasHiba(f"Energy-Charts nem érhető el: {e}") from e
        if valasz.status_code == 404:
            aktualis = szakasz_vege + timedelta(days=1)
            continue  # erre az időszakra még nincs publikált ár
        if valasz.status_code != 200:
            raise ForrasHiba(f"Energy-Charts HTTP {valasz.status_code}: {valasz.text[:200]}")
        reszek.append(feldolgoz_villamos(valasz.json()))
        aktualis = szakasz_vege + timedelta(days=1)

    if not reszek:
        return ures(VILLAMOS_OSZLOPOK)
    tabla = pd.concat(reszek, ignore_index=True)
    tabla = tabla.drop_duplicates("unix", keep="last").sort_values("unix")
    return tabla[(tabla["nap"] >= kezdet.isoformat()) & (tabla["nap"] <= veg.isoformat())].reset_index(drop=True)


def feldolgoz_villamos(adat: dict) -> pd.DataFrame:
    """Az API válaszából árpontokat készít helyi idővel és időtartammal (15 vagy 60 perc)."""
    idok = adat.get("unix_seconds") or []
    arak = adat.get("price") or []
    if not idok:
        return ures(VILLAMOS_OSZLOPOK)

    tabla = pd.DataFrame({"unix": pd.Series(idok, dtype="int64"),
                          "ar": pd.to_numeric(pd.Series(arak[:len(idok)]), errors="coerce")})
    lepes = tabla["unix"].shift(-1) - tabla["unix"]
    lepes = lepes.fillna(tabla["unix"].diff()).fillna(3600)
    tabla["perc"] = (lepes / 60).round().astype(int).clip(upper=60)
    tabla = tabla.dropna(subset=["ar"])

    helyi = pd.to_datetime(tabla["unix"], unit="s", utc=True).dt.tz_convert(B.IDOZONA)
    tabla["ido"] = helyi.dt.strftime("%Y-%m-%d %H:%M")
    tabla["nap"] = helyi.dt.strftime("%Y-%m-%d")
    tabla["negyedora"] = helyi.dt.strftime("%H:%M")
    tabla["ora"] = helyi.dt.hour
    tabla["ar"] = tabla["ar"].round(2)
    return tabla[VILLAMOS_OSZLOPOK].reset_index(drop=True)


# ---------------------------------------------------------------- Földgáz, CEEGEX

def leker_html(url: str) -> str:
    try:
        valasz = requests.get(url, headers=B.HTTP_FEJLEC, timeout=B.HTTP_IDOKORLAT)
    except requests.RequestException as e:
        raise ForrasHiba(f"CEEGEX nem érhető el: {e}") from e
    if valasz.status_code != 200:
        raise ForrasHiba(f"CEEGEX HTTP {valasz.status_code} ({url})")
    valasz.encoding = valasz.encoding or "utf-8"
    return valasz.text


def leker_gaz_masnapi() -> pd.DataFrame:
    tabla = feldolgoz_gaz_masnapi(leker_html(B.CEEGEX_MASNAPI_URL))
    if tabla.empty:
        raise ForrasHiba("A CEEGEX másnapi ártáblázata nem található; valószínűleg megváltozott az oldal szerkezete.")
    return tabla


def leker_gaz_napon_belul(most: datetime | None = None) -> pd.DataFrame:
    return feldolgoz_gaz_napon_belul(leker_html(B.CEEGEX_NAPON_BELUL_URL), most)


class _TablaOlvaso(HTMLParser):
    """HTML táblázatok cellaszövegeinek kigyűjtése, külső függőség nélkül."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tablak: list[list[list[str]]] = []
        self._melyseg = 0
        self._sor: list[str] | None = None
        self._cella: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._melyseg += 1
            self.tablak.append([])
        elif tag == "tr" and self._melyseg:
            self._sor = []
        elif tag in ("td", "th") and self._sor is not None:
            self._cella = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cella is not None and self._sor is not None:
            self._sor.append(re.sub(r"\s+", " ", "".join(self._cella)).strip())
            self._cella = None
        elif tag == "tr" and self._sor is not None:
            if self._sor and self.tablak:
                self.tablak[-1].append(self._sor)
            self._sor = None
        elif tag == "table" and self._melyseg:
            self._melyseg -= 1

    def handle_data(self, data):
        if self._cella is not None:
            self._cella.append(data)


def html_tablak(html: str) -> list[list[list[str]]]:
    olvaso = _TablaOlvaso()
    olvaso.feed(html)
    return [t for t in olvaso.tablak if t]


def szam(szoveg) -> float | None:
    """'63,984' -> 63984.0; '80.99' -> 80.99; '-2.87 %' -> -2.87; '-' vagy üres -> None."""
    if szoveg is None:
        return None
    t = str(szoveg).replace(",", "").replace("%", "").replace("\xa0", "").strip()
    if t in ("", "-"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def feldolgoz_gaz_masnapi(html: str) -> pd.DataFrame:
    """Másnapi, hétvégi és egyedi napi termékek; csak a kötéssel vagy CEEREP-pel rendelkező sorok."""
    for tabla in html_tablak(html):
        fejlec = " | ".join(tabla[0])
        if "Contract" not in fejlec or "CEEREP" not in fejlec:
            continue
        sorok = []
        for c in tabla[1:]:
            if len(c) < 8 or not re.match(r"\d{4}-\d{2}-\d{2}", c[0]):
                continue
            atlagar, ceerep = szam(c[6]), szam(c[7])
            if atlagar is None and ceerep is None:
                continue
            sorok.append({
                "kulcs": f"{c[0]}|{c[1]}|{c[2]}",
                "kereskedesi_nap": c[0], "termek": c[1],
                "szallitas_kezdete": c[2], "szallitas_vege": c[3],
                "mennyiseg_mwh": szam(c[4]), "kotesek": szam(c[5]),
                "atlagar": atlagar, "ceerep": ceerep,
                "ceerep_valtozas": szam(c[8]) if len(c) > 8 else None,
            })
        return pd.DataFrame(sorok, columns=GAZ_MASNAPI_OSZLOPOK)
    return ures(GAZ_MASNAPI_OSZLOPOK)


def aktualis_gaznap(most: datetime | None = None) -> tuple[str, int]:
    """A gáznap 6:00-tól másnap 6:00-ig tart. Visszaadja a gáznapot és az aktuális gázórát (1-24)."""
    most = most or pd.Timestamp.now(tz=B.IDOZONA).to_pydatetime()
    eltolt = most - timedelta(hours=6)
    return eltolt.strftime("%Y-%m-%d"), eltolt.hour + 1


def feldolgoz_gaz_napon_belul(html: str, most: datetime | None = None) -> pd.DataFrame:
    """Napon belüli piac, gázóránként halmozott súlyozott átlagár (az első 'Gashour' táblázat)."""
    szoveg = re.sub(r"<[^>]+>", " ", html)
    talalat = re.search(r"Gasday:?\s*(\d{2})\.(\d{2})\.(\d{4})", szoveg)
    gaznap, gazora_most = aktualis_gaznap(most)
    if talalat:
        oldal_gaznap = f"{talalat.group(3)}-{talalat.group(2)}-{talalat.group(1)}"
        if oldal_gaznap != gaznap:
            gazora_most = 24  # lezárt gáznap
        gaznap = oldal_gaznap

    for tabla in html_tablak(html):
        if not tabla[0] or "Gashour" not in tabla[0][0]:
            continue
        sorok = []
        for c in tabla[1:]:
            if len(c) < 3 or not c[0].strip().isdigit():
                continue
            ora = int(c[0])
            atlagar = szam(c[2])
            if atlagar is None or ora > gazora_most:
                continue
            sorok.append({
                "kulcs": f"{gaznap}|{ora:02d}", "gaznap": gaznap, "gazora": ora,
                "mennyiseg_mwh": szam(c[1]), "atlagar": atlagar,
                "valtozas": szam(c[3]) if len(c) > 3 else None,
            })
        return pd.DataFrame(sorok, columns=GAZ_NAPON_BELUL_OSZLOPOK)
    return ures(GAZ_NAPON_BELUL_OSZLOPOK)


def egyesit(reszek: list[pd.DataFrame], kulcs: str) -> pd.DataFrame:
    """Több tábla összefűzése kulcs szerint; azonos kulcsnál a később érkező (frissebb) sor győz."""
    reszek = [r for r in reszek if r is not None and not r.empty]
    if not reszek:
        return pd.DataFrame()
    egyutt = pd.concat(reszek, ignore_index=True)
    return egyutt.drop_duplicates(kulcs, keep="last").sort_values(kulcs).reset_index(drop=True)


def ures(oszlopok: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=oszlopok)


# ---------------------------------------------------------------- Euró-forint árfolyam

def feldolgoz_ekb_csv(szoveg: str) -> tuple[float, str] | None:
    """Az EKB csvdata válaszából az utolsó árfolyam és a hozzá tartozó nap."""
    import csv
    import io
    try:
        sorok = list(csv.DictReader(io.StringIO(szoveg)))
    except csv.Error:
        return None
    for sor in reversed(sorok):
        ertek, nap = szam(sor.get("OBS_VALUE")), (sor.get("TIME_PERIOD") or "").strip()
        if ertek and 200 < ertek < 800 and nap:
            return ertek, nap
    return None


def feldolgoz_frankfurter(adat: dict) -> tuple[float, str] | None:
    try:
        ertek = float(adat["rates"]["HUF"])
    except (KeyError, TypeError, ValueError):
        return None
    return (ertek, str(adat.get("date", ""))) if 200 < ertek < 800 else None


def leker_arfolyam() -> dict:
    """EUR/HUF referenciaárfolyam. Sosem dob hibát: ha minden forrás kiesik, a tartalékkal számol."""
    try:
        valasz = requests.get(B.EKB_ARFOLYAM_URL, headers=B.HTTP_FEJLEC, timeout=15)
        if valasz.status_code == 200:
            eredmeny = feldolgoz_ekb_csv(valasz.text)
            if eredmeny:
                return {"arfolyam": eredmeny[0], "nap": eredmeny[1], "forras": "EKB"}
    except requests.RequestException:
        pass
    try:
        valasz = requests.get(B.FRANKFURTER_URL, headers=B.HTTP_FEJLEC, timeout=15)
        if valasz.status_code == 200:
            eredmeny = feldolgoz_frankfurter(valasz.json())
            if eredmeny:
                return {"arfolyam": eredmeny[0], "nap": eredmeny[1], "forras": "EKB (Frankfurter)"}
    except (requests.RequestException, ValueError):
        pass
    return {"arfolyam": B.EUR_HUF_TARTALEK, "nap": "", "forras": "becsült"}


def ft_kwh(eur_mwh, arfolyam: float) -> float | None:
    """EUR/MWh átváltása Ft/kWh-ra (nettó nagykereskedelmi ár, díjak és adók nélkül)."""
    if eur_mwh is None or pd.isna(eur_mwh):
        return None
    return float(eur_mwh) * arfolyam / 1000


# ---------------------------------------------------------------- Villamosenergia-termelés

TERMELES_OSZLOPOK = ["unix", "ido", "nap", "negyedora", "ora", "perc", "atom", "foldgaz",
                     "egyeb_fosszilis", "egyeb_megujulo", "szel", "napenergia", "fogyasztas",
                     "nettó_import", "megujulo_arany"]

# Az Energy-Charts angol forrásnevei magyar csoportokba sorolva
FORRAS_CSOPORT = {
    "Nuclear": "atom",
    "Fossil gas": "foldgaz",
    "Fossil brown coal / lignite": "egyeb_fosszilis",
    "Fossil hard coal": "egyeb_fosszilis",
    "Fossil oil": "egyeb_fosszilis",
    "Others": "egyeb_fosszilis",
    "Waste": "egyeb_fosszilis",
    "Biomass": "egyeb_megujulo",
    "Hydro Run-of-River": "egyeb_megujulo",
    "Hydro water reservoir": "egyeb_megujulo",
    "Hydro pumped storage": "egyeb_megujulo",
    "Geothermal": "egyeb_megujulo",
    "Other renewables": "egyeb_megujulo",
    "Wind onshore": "szel",
    "Wind offshore": "szel",
    "Solar": "napenergia",
    "Load": "fogyasztas",
    "Cross border electricity trading": "nettó_import",
    "Renewable share of load": "megujulo_arany",
}
TERMELO_CSOPORTOK = ["atom", "foldgaz", "egyeb_fosszilis", "egyeb_megujulo", "szel", "napenergia"]

# A beépített teljesítmény néhány forrást más néven nevez meg, mint a termelési adat
KAPACITAS_CSOPORT = {**FORRAS_CSOPORT, "Solar AC": "napenergia", "Solar gross": None,
                     "Hydro Run-of-River": "egyeb_megujulo"}
KAPACITAS_OSZLOPOK = ["ev", "csoport", "mw"]


def leker_kapacitas() -> pd.DataFrame:
    """Beépített erőművi teljesítmény forrásonként, évenként (Energy-Charts, ENTSO-E alapon)."""
    try:
        valasz = requests.get(B.KAPACITAS_URL, params={"country": "hu", "time_step": "yearly"},
                              headers=B.HTTP_FEJLEC, timeout=B.HTTP_IDOKORLAT)
    except requests.RequestException as e:
        raise ForrasHiba(f"A beépített teljesítmény nem érhető el: {e}") from e
    if valasz.status_code != 200:
        raise ForrasHiba(f"Energy-Charts HTTP {valasz.status_code} (beépített teljesítmény)")
    return feldolgoz_kapacitas(valasz.json())


def feldolgoz_kapacitas(adat: dict) -> pd.DataFrame:
    """A beépített teljesítmény évenként és forráscsoportonként, megawattban.

    A forrás gigawattban adja az értékeket; itt megawattra váltjuk, hogy a termelési
    adatokkal egy mértékegységben legyenek.
    """
    evek = [str(e) for e in (adat.get("time") or [])]
    sorok = []
    for elem in adat.get("production_types") or []:
        csoport = KAPACITAS_CSOPORT.get(elem.get("name"))
        if csoport is None or csoport not in TERMELO_CSOPORTOK:
            continue
        for ev, ertek in zip(evek, elem.get("data") or []):
            if ertek is None:
                continue
            sorok.append({"ev": ev, "csoport": csoport, "mw": float(ertek) * 1000})
    tabla = pd.DataFrame(sorok, columns=KAPACITAS_OSZLOPOK)
    if tabla.empty:
        return tabla
    return (tabla.groupby(["ev", "csoport"], as_index=False)["mw"].sum()
            .sort_values(["ev", "csoport"]).reset_index(drop=True))


def leker_termeles(kezdet: date, veg: date, szakasz_nap: int = 30) -> pd.DataFrame:
    """Magyar villamosenergia-termelés forrásonként, negyedórás bontásban (Energy-Charts)."""
    reszek = []
    aktualis = kezdet
    while aktualis <= veg:
        szakasz_vege = min(aktualis + timedelta(days=szakasz_nap - 1), veg)
        parameterek = {"country": "hu", "start": aktualis.isoformat(), "end": szakasz_vege.isoformat()}
        try:
            valasz = requests.get(B.TERMELES_URL, params=parameterek, headers=B.HTTP_FEJLEC,
                                  timeout=B.HTTP_IDOKORLAT)
        except requests.RequestException as e:
            raise ForrasHiba(f"A termelési adat nem érhető el: {e}") from e
        if valasz.status_code == 404:
            aktualis = szakasz_vege + timedelta(days=1)
            continue
        if valasz.status_code != 200:
            raise ForrasHiba(f"Energy-Charts HTTP {valasz.status_code} (termelés)")
        reszek.append(feldolgoz_termeles(valasz.json()))
        aktualis = szakasz_vege + timedelta(days=1)
    if not reszek:
        return ures(TERMELES_OSZLOPOK)
    tabla = pd.concat(reszek, ignore_index=True).drop_duplicates("unix", keep="last").sort_values("unix")
    return tabla[(tabla["nap"] >= kezdet.isoformat()) & (tabla["nap"] <= veg.isoformat())].reset_index(drop=True)


def feldolgoz_termeles(adat: dict) -> pd.DataFrame:
    """Az API válaszából forráscsoportonkénti teljesítmény (MW) helyi idővel."""
    idok = adat.get("unix_seconds") or []
    if not idok:
        return ures(TERMELES_OSZLOPOK)
    tabla = pd.DataFrame({"unix": pd.Series(idok, dtype="int64")})
    for csoport in TERMELO_CSOPORTOK + ["fogyasztas", "nettó_import", "megujulo_arany"]:
        tabla[csoport] = 0.0 if csoport in TERMELO_CSOPORTOK else None
    for elem in adat.get("production_types") or []:
        csoport = FORRAS_CSOPORT.get(elem.get("name"))
        if csoport is None:
            continue
        ertekek = pd.to_numeric(pd.Series(elem.get("data") or [])[:len(idok)], errors="coerce")
        ertekek = ertekek.reindex(range(len(idok)))
        if csoport in TERMELO_CSOPORTOK:
            tabla[csoport] = tabla[csoport].add(ertekek.fillna(0.0), fill_value=0.0)
        else:
            tabla[csoport] = ertekek

    lepes = tabla["unix"].shift(-1) - tabla["unix"]
    lepes = lepes.fillna(tabla["unix"].diff()).fillna(900)
    tabla["perc"] = (lepes / 60).round().astype(int).clip(upper=60)
    helyi = pd.to_datetime(tabla["unix"], unit="s", utc=True).dt.tz_convert(B.IDOZONA)
    tabla["ido"] = helyi.dt.strftime("%Y-%m-%d %H:%M")
    tabla["nap"] = helyi.dt.strftime("%Y-%m-%d")
    tabla["negyedora"] = helyi.dt.strftime("%H:%M")
    tabla["ora"] = helyi.dt.hour
    # A fogyasztás nélküli sorok (a jövő felé) nem hordoznak információt
    tabla = tabla[tabla["fogyasztas"].notna()]
    return tabla[TERMELES_OSZLOPOK].reset_index(drop=True)
