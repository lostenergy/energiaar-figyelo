"""Lehetőségek: mit áraz a piac, és milyen szerződés illene egy irodaházi fogyasztáshoz.

Minden függvény tiszta számítás a meglévő adatokból (azonnali árak, beolvasott határidős
jegyzések, megfigyelési napló). A szöveges javaslat döntéstámogatás, nem ajánlat: a számok
a megtörtént árakból és a kereskedők indikatív jegyzéseiből jönnek, előrejelzést nem tartalmaznak.
"""

from __future__ import annotations

import calendar
from datetime import date

import pandas as pd

import beallitas as B

HONAP_NEV = ["január", "február", "március", "április", "május", "június", "július",
             "augusztus", "szeptember", "október", "november", "december"]

# A beszerzési hajlandóság fokozatai: a várható fogyasztás ekkora részét érdemes előre rögzíteni
KOCKAZATI_SZINT = {
    "Óvatos": 0.85,
    "Kiegyensúlyozott": 0.70,
    "Rugalmas": 0.50,
}


def _sz(x, tizedes: int = 1) -> str:
    return f"{float(x):,.{tizedes}f}".replace(",", " ").replace(".", ",")


def _szazalek(x, tizedes: int = 0) -> str:
    return f"{abs(float(x)) * 100:.{tizedes}f}".replace(".", ",") + " százalék"


# ---------------------------------------------------------------- órás profil (tanulás az adatokból)

def orai_profil(villamos: pd.DataFrame, ma: date, napok: int = 60) -> pd.DataFrame:
    """Óránkénti átlagár hétköznap és hétvégén, és az eltérés a napi átlagtól.

    Ez az, amit az alkalmazás a felgyűlt negyedórás árakból megtanul: a nap mely szakaszai
    rendszeresen olcsók vagy drágák.
    """
    oszlopok = ["ora", "hetkoznap", "hetvege", "hetkoznap_rel", "hetvege_rel"]
    if villamos is None or villamos.empty:
        return pd.DataFrame(columns=oszlopok)
    t = villamos.copy()
    t["datum"] = pd.to_datetime(t["nap"])
    t = t[(t["datum"] > pd.Timestamp(ma) - pd.Timedelta(days=napok)) & (t["datum"] <= pd.Timestamp(ma))]
    if t.empty:
        return pd.DataFrame(columns=oszlopok)
    t["ar"] = pd.to_numeric(t["ar"], errors="coerce")
    t["perc"] = pd.to_numeric(t["perc"], errors="coerce").fillna(15)
    t["ora"] = pd.to_numeric(t["ora"], errors="coerce")
    t["hetvege"] = t["datum"].dt.weekday >= 5
    t["suly"] = t["ar"] * t["perc"]

    ki = pd.DataFrame({"ora": range(24)})
    for nev, maszk in (("hetkoznap", ~t["hetvege"]), ("hetvege", t["hetvege"])):
        resz = t[maszk]
        if resz.empty:
            ki[nev], ki[f"{nev}_rel"] = None, None
            continue
        csoport = resz.groupby("ora")[["suly", "perc"]].sum()
        atlag = (csoport["suly"] / csoport["perc"]).reindex(range(24))
        napi_atlag = resz["suly"].sum() / resz["perc"].sum()
        ki[nev] = atlag.values
        ki[f"{nev}_rel"] = (atlag / napi_atlag - 1).values if napi_atlag else None
    return ki[oszlopok]


def olcso_sav(profil: pd.DataFrame, oszlop: str = "hetkoznap_rel", hossz: int = 4) -> tuple[int, float] | None:
    """A nap legolcsóbb, egybefüggő, adott hosszúságú sávja: (kezdő óra, átlagos eltérés)."""
    if profil is None or profil.empty or profil[oszlop].isna().all():
        return None
    ertekek = profil.set_index("ora")[oszlop]
    legjobb = None
    for kezdet in range(0, 24 - hossz + 1):
        atlag = ertekek.loc[kezdet:kezdet + hossz - 1].mean()
        if pd.notna(atlag) and (legjobb is None or atlag < legjobb[1]):
            legjobb = (kezdet, float(atlag))
    return legjobb


def negativ_arany(villamos: pd.DataFrame, ma: date, napok: int = 60) -> float | None:
    """A negyedórák mekkora részében volt nulla vagy negatív az ár."""
    if villamos is None or villamos.empty:
        return None
    t = villamos.copy()
    t["datum"] = pd.to_datetime(t["nap"])
    t = t[(t["datum"] > pd.Timestamp(ma) - pd.Timedelta(days=napok)) & (t["datum"] <= pd.Timestamp(ma))]
    if t.empty:
        return None
    return float((pd.to_numeric(t["ar"], errors="coerce") <= 0).mean())


def ora_kategoriak(villamos: pd.DataFrame, nap: date) -> pd.DataFrame:
    """Egy nap órái harmadokba sorolva: a nyolc legolcsóbb, a nyolc középső és a nyolc legdrágább óra."""
    oszlopok = ["ora", "ar", "kategoria"]
    if villamos is None or villamos.empty:
        return pd.DataFrame(columns=oszlopok)
    t = villamos[villamos["nap"] == nap.isoformat()].copy()
    if t.empty:
        return pd.DataFrame(columns=oszlopok)
    t["ar"] = pd.to_numeric(t["ar"], errors="coerce")
    t["ora"] = pd.to_numeric(t["ora"], errors="coerce")
    orak = t.groupby("ora")["ar"].mean().reset_index()
    if len(orak) < 12:
        return pd.DataFrame(columns=oszlopok)
    rang = orak["ar"].rank(method="first")
    harmad = len(orak) / 3
    orak["kategoria"] = ["olcso" if r <= harmad else "draga" if r > 2 * harmad else "kozepes" for r in rang]
    return orak[oszlopok]


def sav_felirat(kategoriak: pd.DataFrame, kategoria: str = "olcso") -> str:
    """Az adott kategóriájú órák összevont, olvasható felsorolása, például: 10 és 15 óra között."""
    if kategoriak is None or kategoriak.empty:
        return ""
    orak = sorted(int(o) for o in kategoriak.loc[kategoriak["kategoria"] == kategoria, "ora"])
    savok, kezdet, elozo = [], None, None
    for o in orak:
        if kezdet is None:
            kezdet = elozo = o
        elif o == elozo + 1:
            elozo = o
        else:
            savok.append((kezdet, elozo + 1))
            kezdet = elozo = o
    if kezdet is not None:
        savok.append((kezdet, elozo + 1))
    return ", ".join(f"{a} és {b} óra között" for a, b in savok)


# ---------------------------------------------------------------- határidős görbe

def legutobbi_gorbe(hataridos: pd.DataFrame, piac: str) -> pd.DataFrame:
    """A legfrissebb jegyzési nap összes ára az adott piacra."""
    if hataridos is None or hataridos.empty:
        return pd.DataFrame(columns=getattr(hataridos, "columns", []))
    t = hataridos[(hataridos["piac"] == piac) & pd.to_numeric(hataridos["ar"], errors="coerce").notna()].copy()
    if t.empty:
        return t
    t["ar"] = pd.to_numeric(t["ar"], errors="coerce")
    return t[t["jegyzes_nap"] == t["jegyzes_nap"].max()].sort_values("szallitas_kezdete").reset_index(drop=True)


def _termek_ar(g: pd.DataFrame, termek: str, tipus: str):
    sor = g[(g["termek"] == termek) & (g["tipus"] == tipus)]
    return None if sor.empty else float(sor.iloc[0]["ar"])


def eves_termekek(g: pd.DataFrame, tipus: str) -> list[tuple[int, float]]:
    """(év, ár) párok a naptári éves termékekből."""
    if g is None or g.empty:
        return []
    t = g[(g["tipus"] == tipus) & g["termek"].str.endswith(". év")]
    return sorted((int(r.termek[:4]), float(r.ar)) for r in t.itertuples())


def gorbe_irany(g: pd.DataFrame, tipus: str = "Zsinór") -> dict:
    """A görbe iránya az első két naptári év alapján: csökkenő, emelkedő vagy lapos."""
    evek = eves_termekek(g, tipus)
    if len(evek) < 2:
        return {"irany": None, "valtozas": None, "evek": evek}
    (ev1, ar1), (ev2, ar2) = evek[0], evek[1]
    valtozas = (ar2 - ar1) / ar1 if ar1 else None
    if valtozas is None:
        irany = None
    elif valtozas < -0.05:
        irany = "csökkenő"
    elif valtozas > 0.05:
        irany = "emelkedő"
    else:
        irany = "lapos"
    return {"irany": irany, "valtozas": valtozas, "evek": evek}


# ---------------------------------------------------------------- irodai profil a zsinór és csúcs termékekből

def orak_szama(ev: int) -> tuple[int, int]:
    """Az év összes órája és a csúcsórák (hétköznap 8 és 20 óra között) száma."""
    osszes = (366 if calendar.isleap(ev) else 365) * 24
    hetkoznap = sum(1 for h in range(1, 13) for n in range(1, calendar.monthrange(ev, h)[1] + 1)
                    if date(ev, h, n).weekday() < 5)
    return osszes, hetkoznap * 12


def profil_ar(zsinor_ar: float, csucs_ar: float, csucs_arany: float, ev: int, eves_mwh: float = 1.0) -> dict:
    """Egy fogyasztási profil lefedése zsinór és csúcs termék keverékével.

    A zsinór termék minden órában, a csúcs termék csak hétköznap 8 és 20 óra között szállít.
    A csúcson kívüli fogyasztást a zsinór fedi le; a csúcsidőszakban hiányzó részt csúcs termék pótolja.
    """
    osszes, csucs = orak_szama(ev)
    kivul = osszes - csucs
    zsinor_mw = (1 - csucs_arany) * eves_mwh / kivul
    csucs_mw = max(csucs_arany * eves_mwh / csucs - zsinor_mw, 0.0)
    energia = zsinor_mw * osszes + csucs_mw * csucs
    ar = (zsinor_mw * osszes * zsinor_ar + csucs_mw * csucs * csucs_ar) / energia if energia else None
    return {"zsinor_mw": zsinor_mw, "csucs_mw": csucs_mw, "ar": ar,
            "zsinor_resz": zsinor_mw * osszes / energia if energia else None}


def csucs_szorzo(napi: pd.DataFrame, ma: date, napok: int = 365) -> float | None:
    """A csúcsidőszak és a zsinór árának aránya hétköznapokon, a tényleges árakból.

    Akkor kell, ha a kereskedő csak zsinór terméket jegyzett: ebből becsüljük a csúcs árát.
    """
    if napi is None or napi.empty:
        return None
    t = napi.copy()
    t["datum"] = pd.to_datetime(t["nap"])
    t = t[(t["datum"] > pd.Timestamp(ma) - pd.Timedelta(days=napok)) & (t["datum"] <= pd.Timestamp(ma))
          & (t["datum"].dt.weekday < 5)]
    zs, cs = pd.to_numeric(t["zsinor"], errors="coerce"), pd.to_numeric(t["csucs"], errors="coerce")
    if zs.sum() <= 0 or len(t) < 20:
        return None
    return float(cs.mean() / zs.mean())


def profil_spot(napi: pd.DataFrame, ma: date, csucs_arany: float, napok: int = 365) -> dict:
    """Mennyibe került volna a profil a másnapi piacon: átlag, valamint a legjobb és legrosszabb 30 nap."""
    ki = {"atlag": None, "legjobb": None, "legrosszabb": None, "napok": 0}
    if napi is None or napi.empty:
        return ki
    t = napi.copy()
    t["datum"] = pd.to_datetime(t["nap"])
    t = t[(t["datum"] > pd.Timestamp(ma) - pd.Timedelta(days=napok)) & (t["datum"] <= pd.Timestamp(ma))]
    if t.empty:
        return ki
    for o in ("zsinor", "csucs", "csucson_kivul"):
        t[o] = pd.to_numeric(t[o], errors="coerce")
    hetkoznap = t["datum"].dt.weekday < 5
    t["profil"] = t["zsinor"]
    t.loc[hetkoznap, "profil"] = csucs_arany * t["csucs"] + (1 - csucs_arany) * t["csucson_kivul"]
    t = t.sort_values("datum")
    gordulo = t["profil"].rolling(30, min_periods=20).mean().dropna()
    ki.update(atlag=float(t["profil"].mean()), napok=len(t),
              legjobb=float(gordulo.min()) if not gordulo.empty else None,
              legrosszabb=float(gordulo.max()) if not gordulo.empty else None)
    return ki


# ---------------------------------------------------------------- sávos beszerzés terve

def savos_terv(ma: date, szallitasi_ev: int, fix_arany: float) -> list[dict]:
    """Mikor mennyit érdemes rögzíteni egy szállítási évből, egyenletes részletekben.

    A jövő évet a hátralévő hónapokban havonta, a későbbi éveket negyedévente osztjuk el,
    hogy egyetlen rossz nap ára se döntse el az egész év költségét.
    """
    terv = []
    if szallitasi_ev <= ma.year:
        return terv
    if szallitasi_ev == ma.year + 1:
        honapok = [date(ma.year, h, 1) for h in range(ma.month, 13)]
        if ma.day > 20 and len(honapok) > 1:
            honapok = honapok[1:]
        honapok = honapok[-4:] if len(honapok) > 4 else honapok
    else:
        kezdo = date(ma.year, 3 * ((ma.month - 1) // 3) + 1, 1)
        honapok = []
        aktualis = kezdo
        while aktualis < date(szallitasi_ev, 1, 1) and len(honapok) < 8:
            if aktualis >= date(ma.year, ma.month, 1):
                honapok.append(aktualis)
            ev, ho = divmod(aktualis.month - 1 + 3, 12)
            aktualis = date(aktualis.year + ev, ho + 1, 1)
    if not honapok:
        return terv
    resz = fix_arany / len(honapok)
    osszeg = 0.0
    for h in honapok:
        osszeg += resz
        terv.append({"honap": h, "felirat": f"{h.year}. {HONAP_NEV[h.month - 1]}", "resz": resz, "osszesen": osszeg})
    return terv


# ---------------------------------------------------------------- javaslat villamos energiára

def villamos_javaslat(hataridos: pd.DataFrame, napi: pd.DataFrame, ma: date, eves_mwh: float,
                      csucs_arany: float, fix_arany: float, trend: dict | None = None) -> dict:
    """Az ideális termék, a hozzá legközelebb álló piaci termékek és a költségkép."""
    g = legutobbi_gorbe(hataridos, "Villamos")
    szorzo = csucs_szorzo(napi, ma)
    zsinor_evek = dict(eves_termekek(g, "Zsinór"))
    csucs_evek = dict(eves_termekek(g, "Csúcs"))

    evek = []
    for ev in sorted(zsinor_evek):
        zs = zsinor_evek[ev]
        cs, becsult = csucs_evek.get(ev), False
        if cs is None and szorzo:
            cs, becsult = zs * szorzo, True
        if cs is None:
            evek.append({"ev": ev, "zsinor": zs, "csucs": None, "csucs_becsult": False, "profil": None})
            continue
        p = profil_ar(zs, cs, csucs_arany, ev, eves_mwh)
        evek.append({"ev": ev, "zsinor": zs, "csucs": cs, "csucs_becsult": becsult, "profil": p["ar"],
                     "zsinor_mw": p["zsinor_mw"], "csucs_mw": p["csucs_mw"], "zsinor_resz": p["zsinor_resz"]})

    spot = profil_spot(napi, ma, csucs_arany)
    kovetkezo = next((e for e in evek if e["ev"] == ma.year + 1), evek[0] if evek else None)

    koltseg = None
    if kovetkezo and kovetkezo["profil"] and spot["atlag"] is not None:
        fix_resz = fix_arany * eves_mwh * kovetkezo["profil"]
        lebego = (1 - fix_arany) * eves_mwh
        koltseg = {
            "ev": kovetkezo["ev"],
            "teljes_fix": eves_mwh * kovetkezo["profil"],
            "javasolt": fix_resz + lebego * spot["atlag"],
            "javasolt_legjobb": fix_resz + lebego * (spot["legjobb"] or spot["atlag"]),
            "javasolt_legrosszabb": fix_resz + lebego * (spot["legrosszabb"] or spot["atlag"]),
            "teljes_spot": eves_mwh * spot["atlag"],
            "spot_legjobb": eves_mwh * (spot["legjobb"] or spot["atlag"]),
            "spot_legrosszabb": eves_mwh * (spot["legrosszabb"] or spot["atlag"]),
        }

    terv = savos_terv(ma, kovetkezo["ev"], fix_arany) if kovetkezo else []

    mondatok = []
    if kovetkezo and kovetkezo["profil"]:
        mondatok.append(
            f"A {kovetkezo['ev']}-es évre a legközelebbi piaci megoldás egy zsinór és egy csúcs termék keveréke: "
            f"{_sz(kovetkezo['zsinor_mw'], 3)} MW zsinór és {_sz(kovetkezo['csucs_mw'], 3)} MW csúcs. "
            f"Ez együtt {_sz(kovetkezo['profil'], 2)} EUR/MWh átlagárat ad a megadott fogyasztási mintára.")
        if kovetkezo["csucs_becsult"]:
            mondatok.append("A csúcs termékre nem volt jegyzés, ezért az árát az elmúlt év tényleges hétköznapi "
                            "csúcs- és zsinórárainak arányából becsültem. Kérd be a kereskedőtől a csúcs (peak) árat is.")
    elif kovetkezo:
        mondatok.append(f"A {kovetkezo['ev']}-es évre csak zsinór jegyzés van ({_sz(kovetkezo['zsinor'], 2)} EUR/MWh), "
                        "és a csúcs árának becsléséhez még kevés a tényleges előzmény.")
    if spot["atlag"] is not None and kovetkezo and kovetkezo["profil"]:
        elteres = kovetkezo["profil"] / spot["atlag"] - 1
        irany = "drágább" if elteres > 0 else "olcsóbb"
        mondatok.append(f"A fix ár {_szazalek(elteres)}kal {irany}, mint amennyibe ugyanez a fogyasztás az elmúlt "
                        f"{spot['napok']} napban a másnapi piacon került volna ({_sz(spot['atlag'], 2)} EUR/MWh).")
    if trend and trend.get("valtozas") is not None and trend.get("pontok", 0) >= 3:
        v = trend["valtozas"]
        if v < -0.03:
            mondatok.append(f"A megfigyelt {trend['pontok']} jegyzési nap alatt a jövő évi ár {_szazalek(v, 1)}kal "
                            "csökkent. Csökkenő piacon nem érdemes sietni: a részleteket érdemes egyenletesen, "
                            "a terv szerint elosztani.")
        elif v > 0.03:
            mondatok.append(f"A megfigyelt {trend['pontok']} jegyzési nap alatt a jövő évi ár {_szazalek(v, 1)}kal "
                            "emelkedett. Emelkedő piacon érdemes a terv első részleteit előrébb hozni.")
        else:
            mondatok.append(f"A megfigyelt {trend['pontok']} jegyzési nap alatt a jövő évi ár alig mozdult, "
                            "a terv szerinti egyenletes ütemezés megfelelő.")

    return {"evek": evek, "spot": spot, "koltseg": koltseg, "terv": terv, "mondatok": mondatok,
            "kovetkezo": kovetkezo, "jegyzes_nap": g["jegyzes_nap"].iloc[0] if not g.empty else None,
            "csucs_szorzo": szorzo}


# ---------------------------------------------------------------- javaslat földgázra

def gaz_javaslat(hataridos: pd.DataFrame, gaz: pd.DataFrame, ma: date, eves_mwh: float,
                 sulyok: tuple = B.GAZ_NEGYEDEVES_SULY) -> dict:
    """Fűtési profilú gázbeszerzés: melyik piaci termékkombináció áll hozzá legközelebb."""
    g = legutobbi_gorbe(hataridos, "Gáz")
    spot = None
    if gaz is not None and not gaz.empty:
        da = gaz[(gaz["termek"] == "DA") & pd.to_numeric(gaz["atlagar"], errors="coerce").notna()]
        if not da.empty:
            spot = float(pd.to_numeric(da.sort_values("kereskedesi_nap")["atlagar"]).tail(21).mean())

    megoldas, ar, mondatok = None, None, []
    if not g.empty:
        negyedevek = g[g["termek"].str.contains("negyedév")].copy()
        negyedevek["q"] = negyedevek["termek"].str.extract(r"(I{1,3}V?|IV)\. negyedév")[0].map(
            {"I": 1, "II": 2, "III": 3, "IV": 4})
        negyedevek["ev"] = negyedevek["termek"].str[:4].astype(int)
        # A következő négy egymást követő negyedév, ha mind megvan
        negyedevek = negyedevek.sort_values("szallitas_kezdete").head(4)
        if len(negyedevek) == 4 and negyedevek["q"].nunique() == 4:
            ar = sum(sulyok[int(r.q) - 1] * float(r.ar) for r in negyedevek.itertuples())
            megoldas = "negyedéves termékek, a fűtési idény súlyával"
        else:
            tel = g[g["termek"].str.contains("téli szezon")]
            nyar = g[g["termek"].str.contains("nyári szezon")]
            if not tel.empty and not nyar.empty:
                teli_suly = sulyok[0] + sulyok[3]
                ar = teli_suly * float(tel.iloc[0]["ar"]) + (1 - teli_suly) * float(nyar.iloc[0]["ar"])
                megoldas = "téli és nyári szezon, a fűtési idény súlyával"
            else:
                ev = g[g["termek"].str.endswith(". év")]
                if not ev.empty:
                    ar = float(ev.iloc[0]["ar"])
                    megoldas = "egyenletes éves termék"
                    mondatok.append("Az éves termék egyenletesen szállít egész évben, az iroda viszont télen "
                                    "fogyaszt. Nyáron a fölösleget vissza kell adni, télen hiány lehet; ezért "
                                    "kérj a kereskedőtől negyedéves vagy szezonális árat is.")
    if ar is None:
        mondatok.append("Gázra nincs beolvasott határidős jegyzés. Ilyenkor a legközelebbi elérhető megoldás "
                        "a CEEGEX másnapi árához vagy a CEEREP indexhez kötött (indexált) szerződés, kiegészítve "
                        "a téli negyedévek fix árával, amit a kereskedőtől lehet kérni.")
    if ar is not None and spot:
        elteres = ar / spot - 1
        mondatok.append(f"Ez {_szazalek(elteres)}kal {'drágább' if elteres > 0 else 'olcsóbb'} a CEEGEX "
                        f"másnapi árának utóbbi havi átlagánál ({_sz(spot, 2)} EUR/MWh). A téli ár "
                        "rendszerint a nyári fölött van, ez önmagában nem kedvezőtlen.")
    koltseg = {"fix": eves_mwh * ar, "spot": eves_mwh * spot if spot else None} if ar is not None else None
    return {"ar": ar, "megoldas": megoldas, "spot": spot, "mondatok": mondatok, "koltseg": koltseg,
            "jegyzes_nap": g["jegyzes_nap"].iloc[0] if not g.empty else None}


# ---------------------------------------------------------------- mit tartogat a piac

def piaci_kilatas(hataridos: pd.DataFrame, napi: pd.DataFrame, gaz: pd.DataFrame, villamos: pd.DataFrame,
                  ma: date) -> list[str]:
    """Néhány mondat arról, mit áraz be a piac, és mit mutatnak a tényleges árak."""
    mondatok = []
    g = legutobbi_gorbe(hataridos, "Villamos")
    spot30 = None
    if napi is not None and not napi.empty:
        t = napi[pd.to_datetime(napi["nap"]) > pd.Timestamp(ma) - pd.Timedelta(days=30)]
        t = t[pd.to_datetime(t["nap"]) <= pd.Timestamp(ma)]
        if not t.empty:
            spot30 = float(pd.to_numeric(t["zsinor"], errors="coerce").mean())

    if not g.empty:
        zs = g[g["tipus"] == "Zsinór"]
        honap = zs[zs["termek"].str.contains("|".join(HONAP_NEV))].head(1)
        if not honap.empty and spot30:
            r = honap.iloc[0]
            v = float(r["ar"]) / spot30 - 1
            mondatok.append(f"A piac {r['termek'][6:]} hónapra {_sz(r['ar'], 2)} EUR/MWh zsinórárat vár, ez "
                            f"{_szazalek(v)}kal {'magasabb' if v > 0 else 'alacsonyabb'}, mint az elmúlt 30 nap "
                            f"tényleges átlaga ({_sz(spot30, 2)}).")
        tel = zs[zs["termek"].str.contains("I. negyedév") & ~zs["termek"].str.contains("II")].head(1)
        evek = eves_termekek(g, "Zsinór")
        if not tel.empty and evek:
            ev_ar = dict(evek).get(int(tel.iloc[0]["termek"][:4]))
            if ev_ar:
                v = float(tel.iloc[0]["ar"]) / ev_ar - 1
                mondatok.append(f"A tél ({tel.iloc[0]['termek']}) {_szazalek(v)}kal "
                                f"{'drágább' if v > 0 else 'olcsóbb'}, mint ugyanannak az évnek az átlaga: "
                                "a fűtési idény és a gyengébb napenergia-termelés a téli hónapokat drágítja.")
        irany = gorbe_irany(g)
        if irany["irany"]:
            (e1, a1), (e2, a2) = irany["evek"][0], irany["evek"][1]
            szoveg = {"csökkenő": "a piac olcsóbb jövőt áraz",
                      "emelkedő": "a piac drágulást áraz",
                      "lapos": "a piac nagyjából változatlan szintet áraz"}[irany["irany"]]
            mondatok.append(f"A {e1}-es év {_sz(a1, 2)}, a {e2}-es {_sz(a2, 2)} EUR/MWh: {szoveg}.")
    else:
        mondatok.append("Határidős jegyzés még nincs beolvasva, ezért a kilátásokat csak a tényleges árakból "
                        "tudom leírni. Töltsd fel a kereskedő napi árlistáját a Határidős árak fülön.")

    profil = orai_profil(villamos, ma)
    sav = olcso_sav(profil)
    if sav:
        mondatok.append(f"Az elmúlt 60 nap hétköznapjain {sav[0]} és {sav[0] + 4} óra között volt a legolcsóbb "
                        f"az áram, a napi átlagnál {_szazalek(sav[1])}kal kevesebb. Ez a naperőművek hatása, "
                        "és a következő években erősödni fog.")
    neg = negativ_arany(villamos, ma)
    if neg:
        mondatok.append(f"A negyedórák {_szazalek(neg, 1)}ában nulla vagy negatív volt az ár.")
    return mondatok
