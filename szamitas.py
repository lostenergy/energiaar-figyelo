"""Árszámítások: időarányosan súlyozott napi és időszaki átlagok, gáz kulcsszámok."""

from __future__ import annotations

from datetime import date

import pandas as pd

import beallitas as B

NAPI_OSZLOPOK = ["nap", "zsinor", "csucs", "csucson_kivul", "min_ar", "min_ido", "max_ar", "max_ido", "idoszakok"]


def _sulyozott(tabla: pd.DataFrame) -> float | None:
    suly = tabla["perc"].sum()
    return round(float((tabla["ar"] * tabla["perc"]).sum() / suly), 2) if suly else None


def napi_osszesites(villamos: pd.DataFrame, csucs_kezdet: int = B.CSUCS_KEZDET,
                    csucs_vege: int = B.CSUCS_VEGE) -> pd.DataFrame:
    """Napi zsinór-, csúcs- és csúcson kívüli ár, minimum és maximum. Csak teljes (legalább 23 órás) napok."""
    if villamos.empty:
        return pd.DataFrame(columns=NAPI_OSZLOPOK)
    sorok = []
    for nap, l in villamos.groupby("nap", sort=True):
        if l["perc"].sum() < 23 * 60:
            continue
        csucs = l[(l["ora"] >= csucs_kezdet) & (l["ora"] < csucs_vege)]
        kivul = l[(l["ora"] < csucs_kezdet) | (l["ora"] >= csucs_vege)]
        legkisebb = l.loc[l["ar"].idxmin()]
        legnagyobb = l.loc[l["ar"].idxmax()]
        sorok.append([nap, _sulyozott(l), _sulyozott(csucs), _sulyozott(kivul),
                      float(legkisebb["ar"]), legkisebb["negyedora"],
                      float(legnagyobb["ar"]), legnagyobb["negyedora"], len(l)])
    return pd.DataFrame(sorok, columns=NAPI_OSZLOPOK)


def idoszaki_atlagok(napi: pd.DataFrame, ma: date) -> pd.DataFrame:
    """Folyó hét, hónap, negyedév, félév és év átlagai (a mai napig), valamint az előző időszakok."""
    if napi.empty:
        return pd.DataFrame(columns=["idoszak", "tol", "ig", "zsinor", "csucs", "napok"])
    t = napi.copy()
    t["datum"] = pd.to_datetime(t["nap"])
    ma_ts = pd.Timestamp(ma)
    t = t[t["datum"] <= ma_ts]

    het_eleje = ma_ts - pd.Timedelta(days=ma_ts.weekday())
    honap_eleje = ma_ts.replace(day=1)
    negyedev_eleje = ma_ts.replace(month=3 * ((ma_ts.month - 1) // 3) + 1, day=1)
    felev_eleje = ma_ts.replace(month=1 if ma_ts.month <= 6 else 7, day=1)
    ev_eleje = ma_ts.replace(month=1, day=1)
    elozo_honap_vege = honap_eleje - pd.Timedelta(days=1)
    elozo_negyedev_vege = negyedev_eleje - pd.Timedelta(days=1)

    idoszakok = [
        ("Folyó hét", het_eleje, ma_ts),
        ("Előző hét", het_eleje - pd.Timedelta(days=7), het_eleje - pd.Timedelta(days=1)),
        ("Folyó hónap", honap_eleje, ma_ts),
        ("Előző hónap", elozo_honap_vege.replace(day=1), elozo_honap_vege),
        ("Folyó negyedév", negyedev_eleje, ma_ts),
        ("Előző negyedév", elozo_negyedev_vege.replace(month=3 * ((elozo_negyedev_vege.month - 1) // 3) + 1, day=1),
         elozo_negyedev_vege),
        ("Folyó félév", felev_eleje, ma_ts),
        ("Folyó év", ev_eleje, ma_ts),
        ("Utolsó 30 nap", ma_ts - pd.Timedelta(days=29), ma_ts),
        ("Utolsó 365 nap", ma_ts - pd.Timedelta(days=364), ma_ts),
    ]
    sorok = []
    for nev, tol, ig in idoszakok:
        resz = t[(t["datum"] >= tol) & (t["datum"] <= ig)]
        sorok.append({
            "idoszak": nev, "tol": tol.date(), "ig": ig.date(),
            "zsinor": round(resz["zsinor"].mean(), 2) if not resz.empty else None,
            "csucs": round(resz["csucs"].mean(), 2) if not resz.empty else None,
            "napok": len(resz),
        })
    return pd.DataFrame(sorok)


def valtozas(uj, regi) -> float | None:
    if uj is None or regi is None or pd.isna(uj) or pd.isna(regi) or regi == 0:
        return None
    return (float(uj) - float(regi)) / abs(float(regi))


def gaz_kulcsszamok(gaz: pd.DataFrame) -> dict:
    """A legutóbbi másnapi (DA) ár, az előző és az 5 kereskedési nappal korábbi, valamint a hétvégi termék."""
    ki = {"da": None, "da_elozo": None, "da_het": None, "hetvege": None}
    if gaz.empty:
        return ki
    da = gaz[(gaz["termek"] == "DA") & gaz["atlagar"].notna()].sort_values("kereskedesi_nap")
    if not da.empty:
        ki["da"] = da.iloc[-1].to_dict()
    if len(da) > 1:
        ki["da_elozo"] = da.iloc[-2].to_dict()
    if len(da) > 5:
        ki["da_het"] = da.iloc[-6].to_dict()
    hetvege = gaz[(gaz["termek"] == "W/END") & gaz["atlagar"].notna()].sort_values("kereskedesi_nap")
    if not hetvege.empty:
        ki["hetvege"] = hetvege.iloc[-1].to_dict()
    return ki
