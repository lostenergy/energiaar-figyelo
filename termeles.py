"""Villamosenergia-termelés: napi összesítés és a napenergia hatása az árra.

A termelés magyarázza az árakat: sok napsütés délben lenyomja, kevés szél és hideg idő
felnyomja a másnapi árat. Ez a modul ebből számol napi értékeket és egy egyszerű
összefüggést a napenergia részaránya és a napi zsinórár között.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

# Megjelenítési sorrend alulról fölfelé, magyar névvel és színnel.
# A színek a vizualizációs ellenőrzésen átmentek (színlátási zavarral is megkülönböztethetők).
CSOPORTOK = [
    ("egyeb_fosszilis", "Egyéb fosszilis", "#6B7785"),
    ("atom", "Atom (Paks)", "#4a3aa7"),
    ("foldgaz", "Földgáz", "#eb6834"),
    ("egyeb_megujulo", "Egyéb megújuló", "#1baf7a"),
    ("szel", "Szél", "#2a78d6"),
    ("napenergia", "Nap", "#eda100"),
]
TERMELO = [k for k, _, _ in CSOPORTOK]
NAPI_OSZLOPOK = (["nap"] + [f"{k}_mwh" for k in TERMELO]
                 + ["termeles_mwh", "fogyasztas_mwh", "import_mwh", "nap_arany", "szel_arany",
                    "megujulo_arany", "import_arany", "orak"])


def aktualis(t: pd.DataFrame) -> dict:
    """A legutolsó negyedóra adatai: mennyi megy most, miből."""
    if t is None or t.empty:
        return {}
    sor = t.sort_values("unix").iloc[-1]
    ki = {k: (float(sor[k]) if pd.notna(sor[k]) else None) for k, _, _ in CSOPORTOK}
    ki["termeles"] = sum(v for v in ki.values() if v)
    for mezo in ("fogyasztas", "nettó_import", "megujulo_arany"):
        ertek = sor.get(mezo)
        ki[mezo] = float(ertek) if pd.notna(ertek) else None
    ki["ido"] = sor["ido"]
    ki["nap_arany"] = (ki["napenergia"] / ki["fogyasztas"] * 100
                       if ki.get("napenergia") is not None and ki.get("fogyasztas") else None)
    return ki


def napi_osszesites(t: pd.DataFrame, teljes_nap_ora: int = 23) -> pd.DataFrame:
    """Napi energia forrásonként (MWh), és a részarányok a fogyasztásból. Csak teljes napokra."""
    if t is None or t.empty:
        return pd.DataFrame(columns=NAPI_OSZLOPOK)
    m = t.copy()
    for oszlop in TERMELO + ["fogyasztas", "nettó_import", "perc"]:
        m[oszlop] = pd.to_numeric(m[oszlop], errors="coerce")
    m["ora_resz"] = m["perc"] / 60
    sorok = []
    for nap, csoport in m.groupby("nap", sort=True):
        orak = float(csoport["ora_resz"].sum())
        if orak < teljes_nap_ora:
            continue
        sor = {"nap": nap, "orak": round(orak, 2)}
        termeles = 0.0
        for kulcs in TERMELO:
            mennyiseg = float((csoport[kulcs].fillna(0) * csoport["ora_resz"]).sum())
            sor[f"{kulcs}_mwh"] = round(mennyiseg, 1)
            termeles += mennyiseg
        fogyasztas = float((csoport["fogyasztas"].fillna(0) * csoport["ora_resz"]).sum())
        behozatal = float((csoport["nettó_import"].fillna(0) * csoport["ora_resz"]).sum())
        sor["termeles_mwh"] = round(termeles, 1)
        sor["fogyasztas_mwh"] = round(fogyasztas, 1)
        sor["import_mwh"] = round(behozatal, 1)
        alap = fogyasztas if fogyasztas > 0 else None
        sor["nap_arany"] = round(sor["napenergia_mwh"] / alap * 100, 2) if alap else None
        sor["szel_arany"] = round(sor["szel_mwh"] / alap * 100, 2) if alap else None
        sor["megujulo_arany"] = round(
            (sor["napenergia_mwh"] + sor["szel_mwh"] + sor["egyeb_megujulo_mwh"]) / alap * 100, 2) if alap else None
        sor["import_arany"] = round(behozatal / alap * 100, 2) if alap else None
        sorok.append(sor)
    return pd.DataFrame(sorok, columns=NAPI_OSZLOPOK)


def egyesit_napi(regi: pd.DataFrame, uj: pd.DataFrame) -> pd.DataFrame:
    """Napi termelési sorok összefésülése; azonos napnál a frissebb marad."""
    reszek = [t for t in (regi, uj) if t is not None and not t.empty]
    if not reszek:
        return pd.DataFrame(columns=NAPI_OSZLOPOK)
    egyutt = pd.concat(reszek, ignore_index=True)
    return egyutt.drop_duplicates("nap", keep="last").sort_values("nap").reset_index(drop=True)


def beepitett(kapacitas: pd.DataFrame) -> dict:
    """A legutolsó ismert év beépített teljesítménye forrásonként, megawattban."""
    if kapacitas is None or kapacitas.empty:
        return {}
    utolso_ev = kapacitas["ev"].max()
    resz = kapacitas[kapacitas["ev"] == utolso_ev]
    ki = {sor.csoport: float(sor.mw) for sor in resz.itertuples()}
    ki["_ev"] = utolso_ev
    return ki


def kihasznaltsag(kapacitas: pd.DataFrame, t: pd.DataFrame, nap: str) -> pd.DataFrame:
    """Egy nap csúcsteljesítménye forrásonként, a beépített teljesítmény arányában.

    Ez mutatja meg, mennyit hozott ki a nap az erőműparkból: a naperőműveknél derült déli
    órában a beépített teljesítmény nagy része megy, borús napon a töredéke.
    """
    oszlopok = ["csoport", "nev", "szin", "beepitett_mw", "csucs_mw", "most_mw", "arany"]
    kap = beepitett(kapacitas)
    if t is None or t.empty or not kap:
        return pd.DataFrame(columns=oszlopok)
    napi = t[t["nap"] == nap].sort_values("unix")
    if napi.empty:
        return pd.DataFrame(columns=oszlopok)
    sorok = []
    for kulcs, nev, szin in CSOPORTOK:
        ertekek = pd.to_numeric(napi[kulcs], errors="coerce").dropna()
        keret = kap.get(kulcs)
        if ertekek.empty or not keret:
            continue
        csucs = float(ertekek.max())
        sorok.append({"csoport": kulcs, "nev": nev, "szin": szin, "beepitett_mw": float(keret),
                      "csucs_mw": round(csucs, 1), "most_mw": round(float(ertekek.iloc[-1]), 1),
                      "arany": round(csucs / keret * 100, 1)})
    tabla = pd.DataFrame(sorok, columns=oszlopok)
    return tabla.sort_values("arany", ascending=False).reset_index(drop=True)


def kapacitas_novekedes(kapacitas: pd.DataFrame, csoportok=("napenergia", "szel"), evek: int = 10) -> pd.DataFrame:
    """A beépített teljesítmény alakulása néhány forrásnál, az utolsó évekre."""
    if kapacitas is None or kapacitas.empty:
        return pd.DataFrame(columns=["ev", "csoport", "mw"])
    t = kapacitas[kapacitas["csoport"].isin(csoportok)].copy()
    if t.empty:
        return t
    megtart = sorted(t["ev"].unique())[-evek:]
    return t[t["ev"].isin(megtart)].sort_values(["csoport", "ev"]).reset_index(drop=True)


def kapacitas_mondat(kapacitas: pd.DataFrame) -> str | None:
    """Egy mondat arról, mennyivel nőtt a naperőműpark, és mit jelent ez az árakra."""
    novekedes = kapacitas_novekedes(kapacitas, ("napenergia",))
    if len(novekedes) < 2:
        return None
    elso, utolso = novekedes.iloc[0], novekedes.iloc[-1]
    if not elso["mw"]:
        return None
    szorzo = utolso["mw"] / elso["mw"]
    return (f"A beépített naperőművi teljesítmény {elso['ev']} és {utolso['ev']} között "
            f"{elso['mw'] / 1000:.1f}".replace(".", ",") + " gigawattról "
            f"{utolso['mw'] / 1000:.1f}".replace(".", ",") + " gigawattra nőtt, "
            f"{szorzo:.1f}".replace(".", ",") + "-szeresére. Ez az, ami a déli órák árát évről évre "
            "lejjebb viszi, és egyre nagyobbra nyitja a déli és az esti ár közötti különbséget.")


def _meredekseg(x: pd.Series, y: pd.Series) -> tuple[float, float] | None:
    """Egyszerű egyenes illesztése: (meredekség, korrelációs együttható)."""
    if len(x) < 10 or x.std() == 0 or y.std() == 0:
        return None
    meredekseg = float(((x - x.mean()) * (y - y.mean())).sum() / ((x - x.mean()) ** 2).sum())
    korrelacio = float(x.corr(y))
    return meredekseg, korrelacio


def ar_kapcsolat(napi_termeles: pd.DataFrame, napi_ar: pd.DataFrame, ma: date, napok: int = 120) -> dict:
    """Mennyivel nyomja le a napi árat a napenergia és a szél nagyobb részaránya."""
    ki = {"pontok": 0, "tabla": pd.DataFrame(), "nap": None, "szel": None, "mondatok": []}
    if napi_termeles is None or napi_termeles.empty or napi_ar is None or napi_ar.empty:
        return ki
    t = napi_termeles.merge(napi_ar[["nap", "zsinor"]], on="nap", how="inner")
    t["datum"] = pd.to_datetime(t["nap"])
    t = t[(t["datum"] > pd.Timestamp(ma) - pd.Timedelta(days=napok)) & (t["datum"] <= pd.Timestamp(ma))]
    t = t.dropna(subset=["nap_arany", "zsinor"])
    ki["tabla"], ki["pontok"] = t, len(t)
    if len(t) < 10:
        return ki
    nap_ill = _meredekseg(t["nap_arany"], t["zsinor"])
    szel_ill = _meredekseg(t["szel_arany"], t["zsinor"]) if t["szel_arany"].notna().all() else None
    ki["nap"], ki["szel"] = nap_ill, szel_ill

    def _sz(x, tizedes=1):
        return f"{x:,.{tizedes}f}".replace(",", " ").replace(".", ",")

    if nap_ill:
        meredekseg, korrelacio = nap_ill
        irany = "alacsonyabb" if meredekseg < 0 else "magasabb"
        ki["mondatok"].append(
            f"{len(t)} nap adatából: ha a napenergia részaránya egy százalékponttal nagyobb, a napi "
            f"zsinórár átlagosan {_sz(abs(meredekseg), 2)} euróval {irany} egy megawattórán. "
            f"Az együttmozgás erőssége {_sz(korrelacio, 2)} (mínusz egy és egy között).")
    if szel_ill:
        meredekseg, _ = szel_ill
        irany = "alacsonyabb" if meredekseg < 0 else "magasabb"
        ki["mondatok"].append(
            f"A szél esetében ugyanez {_sz(abs(meredekseg), 2)} euró {irany} megawattóránként.")
    if nap_ill and nap_ill[0] < 0:
        ki["mondatok"].append(
            "Ez a naperőművek saját árleszorító hatása: minél több a napenergia, annál olcsóbb a déli áram, "
            "és annál nagyobb a különbség a déli és az esti órák ára között. Ez a különbség a következő "
            "években tovább nőhet, ezért érdemes a rugalmasan időzíthető fogyasztást a déli órákra tenni.")
    return ki
