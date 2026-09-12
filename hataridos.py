"""Határidős (forward) árak: terméklista előállítása, beolvasás, mentés, összevetés az azonnali árral.

Az árakat a felhasználó írja be (a kereskedő vagy bróker napi árlistájából), mert a magyar
határidős jegyzések nyilvánosan, automatikusan lekérhető formában nem érhetők el.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd

OSZLOPOK = ["jegyzes_nap", "piac", "termek", "tipus", "szallitas_kezdete", "szallitas_vege", "ar"]

HONAP_NEV = ["január", "február", "március", "április", "május", "június", "július",
             "augusztus", "szeptember", "október", "november", "december"]
ROMAI = {1: "I", 2: "II", 3: "III", 4: "IV"}


def _nap(x) -> date:
    return pd.Timestamp(x).date()


def _honap_eleje(ev: int, honap: int) -> date:
    ev, honap = ev + (honap - 1) // 12, (honap - 1) % 12 + 1
    return date(ev, honap, 1)


def _honap_vege(ev: int, honap: int) -> date:
    kovetkezo = _honap_eleje(ev, honap + 1)
    return kovetkezo - pd.Timedelta(days=1).to_pytimedelta()


def heti_termekek(ma: date, darab: int) -> list[tuple[str, date, date]]:
    """A következő teljes naptári hetek, hétfőtől vasárnapig."""
    kovetkezo_hetfo = _nap(pd.Timestamp(ma) + pd.Timedelta(days=7 - pd.Timestamp(ma).weekday()))
    ki = []
    for i in range(darab):
        kezdet = _nap(pd.Timestamp(kovetkezo_hetfo) + pd.Timedelta(weeks=i))
        veg = _nap(pd.Timestamp(kezdet) + pd.Timedelta(days=6))
        naptar = pd.Timestamp(kezdet).isocalendar()
        ki.append((f"{naptar.year}. {naptar.week}. hét", kezdet, veg))
    return ki


def havi_termekek(ma: date, darab: int) -> list[tuple[str, date, date]]:
    ki = []
    for i in range(1, darab + 1):
        kezdet = _honap_eleje(ma.year, ma.month + i)
        ki.append((f"{kezdet.year}. {HONAP_NEV[kezdet.month - 1]}", kezdet, _honap_vege(kezdet.year, kezdet.month)))
    return ki


def negyedeves_termekek(ma: date, darab: int) -> list[tuple[str, date, date]]:
    ki = []
    elso = 3 * ((ma.month - 1) // 3) + 4  # a következő negyedév első hónapja
    for i in range(darab):
        kezdet = _honap_eleje(ma.year, elso + 3 * i)
        veg = _honap_vege(*divmod_honap(kezdet, 2))
        ki.append((f"{kezdet.year}. {ROMAI[(kezdet.month - 1) // 3 + 1]}. negyedév", kezdet, veg))
    return ki


def divmod_honap(kezdet: date, tolas: int) -> tuple[int, int]:
    """A kezdettől számított tolás hónappal későbbi (év, hónap) pár."""
    nulla = kezdet.year * 12 + kezdet.month - 1 + tolas
    return nulla // 12, nulla % 12 + 1


def feleves_termekek(ma: date, darab: int) -> list[tuple[str, date, date]]:
    """Naptári félévek: január-június és július-december."""
    ki = []
    elso = 1 if ma.month <= 6 else 7
    for i in range(darab):
        kezdet = _honap_eleje(ma.year, elso + 6 * (i + 1))
        veg = _honap_vege(*divmod_honap(kezdet, 5))
        ki.append((f"{kezdet.year}. {'I' if kezdet.month == 1 else 'II'}. félév", kezdet, veg))
    return ki


def eves_termekek(ma: date, darab: int) -> list[tuple[str, date, date]]:
    return [(f"{ma.year + i}. év", date(ma.year + i, 1, 1), date(ma.year + i, 12, 31))
            for i in range(1, darab + 1)]


def gaz_szezonok(ma: date, darab: int) -> list[tuple[str, date, date]]:
    """Gázszezonok: tél október 1-től március 31-ig, nyár április 1-től szeptember 30-ig."""
    ki = []
    kezdet = _honap_eleje(ma.year, 4) if ma.month < 4 else (
        _honap_eleje(ma.year, 10) if ma.month < 10 else _honap_eleje(ma.year + 1, 4))
    for i in range(darab):
        tel = kezdet.month == 10
        veg = _honap_vege(*divmod_honap(kezdet, 5))
        nev = (f"{kezdet.year}/{str(kezdet.year + 1)[-2:]}. téli szezon" if tel
               else f"{kezdet.year}. nyári szezon")
        ki.append((nev, kezdet, veg))
        kezdet = _honap_eleje(*divmod_honap(kezdet, 6))
    return ki


def gazev(ma: date) -> list[tuple[str, date, date]]:
    """Gázév: október 1-től a következő év szeptember 30-ig."""
    kezdo_ev = ma.year if ma.month < 10 else ma.year + 1
    kezdet = date(kezdo_ev, 10, 1)
    return [(f"{kezdo_ev}/{str(kezdo_ev + 1)[-2:]}. gázév", kezdet, date(kezdo_ev + 1, 9, 30))]


def alap_termekek(ma: date) -> pd.DataFrame:
    """A piacon szokásos határidős termékek üres árral, kitöltésre várva."""
    sorok = []

    def hozzaad(piac, tipusok, lista):
        for nev, kezdet, veg in lista:
            for tipus in tipusok:
                sorok.append({"jegyzes_nap": ma.isoformat(), "piac": piac, "termek": nev, "tipus": tipus,
                              "szallitas_kezdete": kezdet.isoformat(), "szallitas_vege": veg.isoformat(),
                              "ar": None})

    hozzaad("Villamos", ["Zsinór"], heti_termekek(ma, 2))
    hozzaad("Villamos", ["Zsinór", "Csúcs"], havi_termekek(ma, 3))
    hozzaad("Villamos", ["Zsinór", "Csúcs"], negyedeves_termekek(ma, 4))
    hozzaad("Villamos", ["Zsinór"], feleves_termekek(ma, 2))
    hozzaad("Villamos", ["Zsinór", "Csúcs"], eves_termekek(ma, 2))
    hozzaad("Gáz", ["Alap"], havi_termekek(ma, 3))
    hozzaad("Gáz", ["Alap"], negyedeves_termekek(ma, 4))
    hozzaad("Gáz", ["Alap"], gaz_szezonok(ma, 2))
    hozzaad("Gáz", ["Alap"], gazev(ma))
    hozzaad("Gáz", ["Alap"], eves_termekek(ma, 2))
    return pd.DataFrame(sorok, columns=OSZLOPOK)


def ures() -> pd.DataFrame:
    return pd.DataFrame(columns=OSZLOPOK)


def olvas(forras) -> pd.DataFrame:
    """Beolvasás fájlból vagy fájlszerű objektumból; hiányzó vagy hibás fájl esetén üres tábla."""
    try:
        tabla = pd.read_csv(forras, dtype={"jegyzes_nap": str, "piac": str, "termek": str, "tipus": str,
                                           "szallitas_kezdete": str, "szallitas_vege": str})
    except Exception:
        return ures()
    for o in OSZLOPOK:
        if o not in tabla.columns:
            tabla[o] = None
    tabla["ar"] = pd.to_numeric(tabla["ar"], errors="coerce")
    return tabla[OSZLOPOK]


def egyesit(regi: pd.DataFrame, uj: pd.DataFrame) -> pd.DataFrame:
    """Az azonos jegyzési napra és termékre vonatkozó sort az új váltja fel. Ár nélküli sorok kimaradnak."""
    reszek = [r for r in (regi, uj) if r is not None and not r.empty]
    if not reszek:
        return ures()
    egyutt = pd.concat(reszek, ignore_index=True)
    egyutt = egyutt[egyutt["ar"].notna()]
    if egyutt.empty:
        return ures()
    egyutt = egyutt.drop_duplicates(["jegyzes_nap", "piac", "termek", "tipus"], keep="last")
    return egyutt.sort_values(["jegyzes_nap", "piac", "szallitas_kezdete", "tipus"]).reset_index(drop=True)


def csv_bajtok(tabla: pd.DataFrame) -> bytes:
    puffer = io.StringIO()
    tabla.to_csv(puffer, index=False, lineterminator="\n")
    return puffer.getvalue().encode("utf-8")


def gorbe(tabla: pd.DataFrame, piac: str, jegyzes_nap: str | None = None) -> pd.DataFrame:
    """Egy jegyzési nap árgörbéje szállítási kezdet szerint rendezve (alapból a legutóbbi nap)."""
    t = tabla[(tabla["piac"] == piac) & tabla["ar"].notna()]
    if t.empty:
        return ures()
    nap = jegyzes_nap or t["jegyzes_nap"].max()
    g = t[t["jegyzes_nap"] == nap].copy()
    sorrend = {"Zsinór": 0, "Alap": 0, "Csúcs": 1}
    g["_rend"] = g["tipus"].map(sorrend).fillna(2)
    return g.sort_values(["szallitas_kezdete", "_rend"]).drop(columns="_rend").reset_index(drop=True)


def felar(hataridos_ar: float, azonnali_ar: float | None) -> float | None:
    """A határidős ár eltérése az azonnali ártól, arányosan."""
    if azonnali_ar is None or pd.isna(azonnali_ar) or not azonnali_ar:
        return None
    return (float(hataridos_ar) - float(azonnali_ar)) / abs(float(azonnali_ar))
