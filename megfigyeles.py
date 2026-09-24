"""Megfigyelési napló: minden frissítés feljegyzi, mi volt új, és ezekből tanulságok lesznek.

A napló a tárolóban gyűlik (data/megfigyelesek.csv). Egy eseményt csak egyszer rögzít, az első
észlelés idejével; a napi mutatókból napi egy érték marad, a legutolsó. Így a napló kicsi marad,
és visszakereshető belőle például, hogy a holnapi áram ára jellemzően hány órakor érkezik meg.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

OSZLOPOK = ["idopont", "tema", "kulcs", "ertek", "szoveg"]
MAX_SOR = 5000

MUTATO_NEVEK = {
    "aram_30nap": "Villamos zsinórár, 30 napos átlag",
    "deli_sav": "A legolcsóbb négyórás sáv eltérése a napi átlagtól",
    "negativ_arany": "Nulla vagy negatív árú negyedórák aránya",
    "fwd_jovo_ev": "Jövő évi zsinór termék ára (legfrissebb jegyzés)",
    "gorbe_irany": "Második év ára az elsőhöz képest",
    "gaz_30nap": "Gáz másnapi ár, havi átlag",
    "nap_arany": "A napenergia részaránya a fogyasztásból",
    "aram_gaz_arany": "Áram és gáz árának aránya",
}


def ures() -> pd.DataFrame:
    return pd.DataFrame(columns=OSZLOPOK)


def _sz(x, tizedes: int = 2) -> str:
    return f"{float(x):.{tizedes}f}".replace(".", ",")


def uj_esemenyek(naplo: pd.DataFrame, most: datetime, napi: pd.DataFrame, gaz: pd.DataFrame,
                 hataridos: pd.DataFrame, mutatok: dict) -> pd.DataFrame:
    """A mostani frissítés újdonságai, a naplóban már szereplők nélkül."""
    idopont = most.strftime("%Y-%m-%d %H:%M")
    ma = most.date()
    holnap = ma + timedelta(days=1)
    meglevo = set(zip(naplo["tema"], naplo["kulcs"])) if naplo is not None and not naplo.empty else set()
    sorok = []

    def felvesz(tema, kulcs, ertek, szoveg):
        if (tema, str(kulcs)) not in meglevo:
            sorok.append({"idopont": idopont, "tema": tema, "kulcs": str(kulcs), "ertek": ertek, "szoveg": szoveg})

    # Megérkezett-e a holnapi áram ára; ha még nincs, óránként egyszer ezt is feljegyezzük
    holnapi = None
    if napi is not None and not napi.empty:
        sor = napi[napi["nap"] == holnap.isoformat()]
        if not sor.empty and pd.notna(sor.iloc[0]["zsinor"]):
            holnapi = float(sor.iloc[0]["zsinor"])
    if holnapi is not None:
        felvesz("holnapi_ar", holnap.isoformat(), holnapi,
                f"Megérkezett a {holnap.isoformat()} napi áramár: zsinór {_sz(holnapi)} EUR/MWh")
    elif most.hour >= 11:
        felvesz("holnapi_ar_hianyzik", f"{holnap.isoformat()}|{most.hour:02d}", None,
                f"{most.strftime('%H:%M')}-kor még nem volt elérhető a holnapi áramár")

    # Új gázár a CEEGEX-en
    if gaz is not None and not gaz.empty:
        da = gaz[(gaz["termek"] == "DA") & pd.to_numeric(gaz["atlagar"], errors="coerce").notna()]
        if not da.empty:
            utolso = da.sort_values("kereskedesi_nap").iloc[-1]
            felvesz("gaz_da", utolso["kereskedesi_nap"], float(utolso["atlagar"]),
                    f"Új CEEGEX másnapi gázár ({utolso['kereskedesi_nap']}): {_sz(utolso['atlagar'])} EUR/MWh")

    # Új határidős jegyzési nap
    if hataridos is not None and not hataridos.empty:
        for nap, csoport in hataridos.groupby("jegyzes_nap"):
            felvesz("jegyzes", nap, len(csoport), f"{len(csoport)} határidős jegyzés érkezett a {nap} napra")

    # Napi mutatók: ezekből napi egy érték marad, a legfrissebb
    for nev, ertek in (mutatok or {}).items():
        if ertek is None or pd.isna(ertek):
            continue
        kulcs = f"{nev}|{ma.isoformat()}"
        regi = None
        if naplo is not None and not naplo.empty:
            talalat = naplo[(naplo["tema"] == "mutato") & (naplo["kulcs"] == kulcs)]
            regi = None if talalat.empty else pd.to_numeric(talalat.iloc[-1]["ertek"], errors="coerce")
        if regi is None or pd.isna(regi) or abs(float(regi) - float(ertek)) > 1e-6:
            sorok.append({"idopont": idopont, "tema": "mutato", "kulcs": kulcs, "ertek": round(float(ertek), 4),
                          "szoveg": MUTATO_NEVEK.get(nev, nev)})
    return pd.DataFrame(sorok, columns=OSZLOPOK)


def egyesit(naplo: pd.DataFrame, uj: pd.DataFrame) -> pd.DataFrame:
    """Eseményeknél az első észlelés marad meg, mutatóknál a legutolsó érték."""
    reszek = [t for t in (naplo, uj) if t is not None and not t.empty]
    if not reszek:
        return ures()
    egyutt = pd.concat(reszek, ignore_index=True)
    mutato = egyutt[egyutt["tema"] == "mutato"].drop_duplicates(["tema", "kulcs"], keep="last")
    esemeny = egyutt[egyutt["tema"] != "mutato"].drop_duplicates(["tema", "kulcs"], keep="first")
    egyutt = pd.concat([esemeny, mutato], ignore_index=True).sort_values("idopont", kind="stable")
    return egyutt.tail(MAX_SOR).reset_index(drop=True)[OSZLOPOK]


def mutato_idosor(naplo: pd.DataFrame, nev: str) -> pd.DataFrame:
    """Egy napi mutató értékei napok szerint."""
    if naplo is None or naplo.empty:
        return pd.DataFrame(columns=["nap", "ertek"])
    t = naplo[(naplo["tema"] == "mutato") & naplo["kulcs"].astype(str).str.startswith(f"{nev}|")].copy()
    if t.empty:
        return pd.DataFrame(columns=["nap", "ertek"])
    t["nap"] = t["kulcs"].str.split("|").str[1]
    t["ertek"] = pd.to_numeric(t["ertek"], errors="coerce")
    return t.dropna(subset=["ertek"]).sort_values("nap")[["nap", "ertek"]].reset_index(drop=True)


def trend(naplo: pd.DataFrame, nev: str) -> dict:
    """Az első és az utolsó megfigyelt érték közti arányos változás."""
    sor = mutato_idosor(naplo, nev)
    if len(sor) < 2 or not sor.iloc[0]["ertek"]:
        return {"valtozas": None, "pontok": len(sor)}
    return {"valtozas": float(sor.iloc[-1]["ertek"] / sor.iloc[0]["ertek"] - 1), "pontok": len(sor),
            "elso": float(sor.iloc[0]["ertek"]), "utolso": float(sor.iloc[-1]["ertek"]),
            "elso_nap": sor.iloc[0]["nap"], "utolso_nap": sor.iloc[-1]["nap"]}


def erkezesi_ido(naplo: pd.DataFrame) -> dict:
    """Mikor válik elérhetővé a holnapi áramár: csak azokat a napokat nézi, amikor előtte
    ugyanaznap már feljegyeztük a hiányát, mert csak ezeknél ismert, mikor jelent meg."""
    ki = {"napok": 0, "median": None, "legkesobbi_hiany": None, "legkorabbi": None}
    if naplo is None or naplo.empty:
        return ki
    megjott = naplo[naplo["tema"] == "holnapi_ar"]
    hiany = naplo[naplo["tema"] == "holnapi_ar_hianyzik"].copy()
    if megjott.empty or hiany.empty:
        return ki
    hiany["szallitas"] = hiany["kulcs"].str.split("|").str[0]
    idok, hianyok = [], []
    for sor in megjott.itertuples():
        erkezett = pd.Timestamp(sor.idopont)
        elotte = hiany[(hiany["szallitas"] == sor.kulcs)
                       & (pd.to_datetime(hiany["idopont"]).dt.date == erkezett.date())
                       & (pd.to_datetime(hiany["idopont"]) < erkezett)]
        if elotte.empty:
            continue
        idok.append(erkezett.hour * 60 + erkezett.minute)
        utolso = pd.Timestamp(elotte["idopont"].max())
        hianyok.append(utolso.hour * 60 + utolso.minute)
    if not idok:
        return ki
    perc = lambda p: f"{int(p) // 60}:{int(p) % 60:02d}"  # noqa: E731
    ki.update(napok=len(idok), median=perc(pd.Series(idok).median()),
              legkorabbi=perc(min(idok)), legkesobbi_hiany=perc(max(hianyok)))
    return ki


def tanulsagok(naplo: pd.DataFrame) -> list[str]:
    """A napló összegzése néhány mondatban."""
    if naplo is None or naplo.empty:
        return ["A megfigyelési napló még üres. Minden frissítés feljegyzi, mi volt új, és a tanulságok "
                "itt gyűlnek össze."]
    mondatok = []
    napok = pd.to_datetime(naplo["idopont"]).dt.date.nunique()
    esemenyek = int((naplo["tema"] != "mutato").sum())
    mondatok.append(f"{napok} napon át {esemenyek} újdonságot jegyeztem fel.")

    erk = erkezesi_ido(naplo)
    if erk["napok"]:
        mondatok.append(f"A holnapi áramár {erk['napok']} megfigyelt napon jellemzően {erk['median']} körül vált "
                        f"elérhetővé, a legkorábban {erk['legkorabbi']}-kor; {erk['legkesobbi_hiany']}-kor még "
                        "előfordult, hogy hiányzott.")

    for nev, cimke, egyseg, arany in (
            ("aram_30nap", "a villamos zsinórár havi átlaga", "EUR/MWh", False),
            ("fwd_jovo_ev", "a jövő évi zsinór termék ára", "EUR/MWh", False),
            ("gaz_30nap", "a gáz havi átlagára", "EUR/MWh", False),
            ("deli_sav", "a déli olcsó sáv kedvezménye", "", True)):
        tr = trend(naplo, nev)
        if tr["valtozas"] is None or tr["pontok"] < 3:
            continue
        if arany:
            mondatok.append(f"Az első megfigyelés ({tr['elso_nap']}) óta {cimke} "
                            f"{_sz(abs(tr['elso']) * 100, 0)} százalékról {_sz(abs(tr['utolso']) * 100, 0)} "
                            "százalékra változott.")
        else:
            irany = "emelkedett" if tr["valtozas"] > 0.005 else "csökkent" if tr["valtozas"] < -0.005 else "nem változott"
            if irany == "nem változott":
                mondatok.append(f"{tr['elso_nap']} óta {cimke} nem változott érdemben ({_sz(tr['utolso'])} {egyseg}).")
            else:
                mondatok.append(f"{tr['elso_nap']} óta {cimke} {_sz(abs(tr['valtozas']) * 100, 1)} százalékkal "
                                f"{irany}: {_sz(tr['elso'])} helyett most {_sz(tr['utolso'])} {egyseg}.")

    irany = mutato_idosor(naplo, "gorbe_irany")
    if len(irany) >= 3:
        csokkeno = int((irany["ertek"] < -0.05).sum())
        mondatok.append(f"A megfigyelt {len(irany)} napból {csokkeno} napon áraztak a jegyzések olcsóbb "
                        "második évet, mint az elsőt.")
    return mondatok
