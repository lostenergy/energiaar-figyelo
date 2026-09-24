"""A termelési adatok feldolgozása és a napenergia árhatása. Futtatás: python -m pytest -q"""

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import forrasok as F  # noqa: E402
import termeles as TE  # noqa: E402

BP = ZoneInfo("Europe/Budapest")
MA = date(2026, 9, 24)


def valasz(kezdet: str, napok: int, nap_csucs: float = 2000.0, szel_szint: float = 150.0):
    """Az Energy-Charts válaszának utánzata: éjjel nincs nap, délben a legtöbb."""
    k = int(datetime.fromisoformat(kezdet).replace(tzinfo=BP).timestamp())
    idok = list(range(k, k + napok * 86400, 900))
    orak = [datetime.fromtimestamp(u, BP).hour + datetime.fromtimestamp(u, BP).minute / 60 for u in idok]
    nap = [round(max(0.0, nap_csucs * (1 - ((o - 12.5) / 6.5) ** 2)), 1) for o in orak]
    szel = [szel_szint] * len(idok)
    atom = [1800.0] * len(idok)
    gaz = [max(300.0, 1800 - n * 0.6) for n in nap]
    fogyasztas = [round(4500 + 900 * (1 if 8 <= o < 20 else 0), 1) for o in orak]
    behozatal = [round(f - (1800 + 150 + n + g + 200 + 250), 1) for f, n, g in zip(fogyasztas, nap, gaz)]
    megujulo = [round((n + s + 250) / f * 100, 1) for n, s, f in zip(nap, szel, fogyasztas)]
    return {"unix_seconds": idok, "deprecated": False, "production_types": [
        {"name": "Cross border electricity trading", "data": behozatal},
        {"name": "Nuclear", "data": atom},
        {"name": "Hydro Run-of-River", "data": [50.0] * len(idok)},
        {"name": "Biomass", "data": [200.0] * len(idok)},
        {"name": "Fossil brown coal / lignite", "data": [150.0] * len(idok)},
        {"name": "Fossil oil", "data": [0.0] * len(idok)},
        {"name": "Fossil gas", "data": gaz},
        {"name": "Geothermal", "data": [0.0] * len(idok)},
        {"name": "Others", "data": [50.0] * len(idok)},
        {"name": "Waste", "data": [0.0] * len(idok)},
        {"name": "Wind onshore", "data": szel},
        {"name": "Solar", "data": nap},
        {"name": "Load", "data": fogyasztas},
        {"name": "Residual load", "data": [f - n for f, n in zip(fogyasztas, nap)]},
        {"name": "Renewable share of load", "data": megujulo},
        {"name": "Renewable share of generation", "data": megujulo},
    ]}


def test_termeles_feldolgozasa_csoportokba():
    t = F.feldolgoz_termeles(valasz("2026-09-22T00:00", 1))
    assert len(t) == 96 and list(t.columns) == F.TERMELES_OSZLOPOK
    elso = t.iloc[0]
    assert elso["atom"] == 1800.0 and elso["szel"] == 150.0 and elso["napenergia"] == 0.0
    # egyéb fosszilis: lignit 150 + olaj 0 + egyéb 50 + hulladék 0
    assert elso["egyeb_fosszilis"] == 200.0
    # egyéb megújuló: vízerőmű 50 + biomassza 200 + geotermikus 0
    assert elso["egyeb_megujulo"] == 250.0
    assert elso["negyedora"] == "00:00" and elso["perc"] == 15
    deli = t[t["negyedora"] == "12:30"].iloc[0]
    assert deli["napenergia"] > 1900


def test_ismeretlen_forras_es_hianyzo_ertek():
    adat = valasz("2026-09-22T00:00", 1)
    adat["production_types"].append({"name": "Marsi energia", "data": [999.0] * len(adat["unix_seconds"])})
    adat["production_types"][1]["data"][5] = None  # hiányzó atomadat
    t = F.feldolgoz_termeles(adat)
    assert t.iloc[5]["atom"] == 0.0  # a hiányzó érték nem rontja el az összeget
    assert 999.0 not in set(t["egyeb_fosszilis"])  # az ismeretlen forrás kimarad


def test_jovobeli_ures_sorok_kimaradnak():
    adat = valasz("2026-09-24T00:00", 1)
    for elem in adat["production_types"]:
        if elem["name"] == "Load":
            elem["data"][-8:] = [None] * 8
    t = F.feldolgoz_termeles(adat)
    assert len(t) == 88


def test_ures_valasz():
    assert F.feldolgoz_termeles({"unix_seconds": [], "production_types": []}).empty


def test_leker_termeles_szakaszol(monkeypatch):
    hivasok = []

    class V:
        status_code = 200

        def __init__(self, p):
            self.p = p

        def json(self):
            napok = (date.fromisoformat(self.p["end"]) - date.fromisoformat(self.p["start"])).days + 1
            return valasz(self.p["start"] + "T00:00", napok)

    def hamis(url, params=None, headers=None, timeout=None):
        hivasok.append(params)
        return V(params)

    monkeypatch.setattr(F.requests, "get", hamis)
    t = F.leker_termeles(date(2026, 6, 1), date(2026, 9, 24), szakasz_nap=30)
    assert len(hivasok) == 4
    assert t["nap"].min() == "2026-06-01" and t["nap"].max() == "2026-09-24"
    assert t["unix"].duplicated().sum() == 0


def test_leker_termeles_hiba(monkeypatch):
    def hiba(*a, **k):
        raise F.requests.ConnectionError("nincs hálózat")

    monkeypatch.setattr(F.requests, "get", hiba)
    with pytest.raises(F.ForrasHiba, match="nem érhető el"):
        F.leker_termeles(date(2026, 9, 1), date(2026, 9, 2))


def test_aktualis_ertekek():
    t = F.feldolgoz_termeles(valasz("2026-09-22T00:00", 1))
    a = TE.aktualis(t.iloc[:51])  # 12:30-ig
    assert a["ido"].endswith("12:30")
    assert a["napenergia"] > 1900 and a["atom"] == 1800
    assert a["termeles"] == pytest.approx(sum(a[k] for k, _, _ in TE.CSOPORTOK))
    assert 0 < a["nap_arany"] < 100
    assert TE.aktualis(F.ures(F.TERMELES_OSZLOPOK)) == {}


def test_napi_osszesites_energiava_valt():
    t = F.feldolgoz_termeles(valasz("2026-09-22T00:00", 3))
    napi = TE.napi_osszesites(t)
    assert len(napi) == 3 and list(napi.columns) == TE.NAPI_OSZLOPOK
    sor = napi.iloc[0]
    assert sor["atom_mwh"] == pytest.approx(1800 * 24, abs=1)  # 1800 MW egész nap
    assert sor["orak"] == 24
    assert sor["termeles_mwh"] + sor["import_mwh"] == pytest.approx(sor["fogyasztas_mwh"], rel=0.01)
    assert 0 < sor["nap_arany"] < 40 and sor["megujulo_arany"] > sor["nap_arany"]


def test_napi_osszesites_reszleges_nap_kimarad():
    t = F.feldolgoz_termeles(valasz("2026-09-24T00:00", 1)).head(40)  # 10 óráig
    assert TE.napi_osszesites(t).empty
    assert TE.napi_osszesites(F.ures(F.TERMELES_OSZLOPOK)).empty


def test_napi_egyesites():
    a = TE.napi_osszesites(F.feldolgoz_termeles(valasz("2026-09-20T00:00", 2)))
    b = TE.napi_osszesites(F.feldolgoz_termeles(valasz("2026-09-21T00:00", 2, nap_csucs=2600)))
    egyutt = TE.egyesit_napi(a, b)
    assert list(egyutt["nap"]) == ["2026-09-20", "2026-09-21", "2026-09-22"]
    # az átfedő napnál a frissebb sor marad
    assert egyutt[egyutt["nap"] == "2026-09-21"].iloc[0]["napenergia_mwh"] > \
        a[a["nap"] == "2026-09-21"].iloc[0]["napenergia_mwh"]
    assert TE.egyesit_napi(None, None).empty


def test_ar_kapcsolat_kimutatja_a_napenergia_hatasat():
    # Minél nagyobb a napenergia részaránya, annál olcsóbb a nap: 2 euró százalékpontonként
    napok = pd.date_range("2026-06-01", "2026-09-24").strftime("%Y-%m-%d")
    arany = [5 + (i % 17) for i in range(len(napok))]
    napi_t = pd.DataFrame({"nap": napok, "nap_arany": arany, "szel_arany": [3.0] * len(napok)})
    napi_ar = pd.DataFrame({"nap": napok, "zsinor": [150 - 2 * a for a in arany]})
    k = TE.ar_kapcsolat(napi_t, napi_ar, MA)
    assert k["pontok"] > 100
    meredekseg, korrelacio = k["nap"]
    assert meredekseg == pytest.approx(-2.0, abs=0.01) and korrelacio < -0.99
    egyben = " ".join(k["mondatok"])
    assert "2,00 euróval alacsonyabb" in egyben and "árleszorító" in egyben
    assert "—" not in egyben


def test_ar_kapcsolat_keves_adattal():
    napi_t = pd.DataFrame({"nap": ["2026-09-20"], "nap_arany": [10.0], "szel_arany": [3.0]})
    napi_ar = pd.DataFrame({"nap": ["2026-09-20"], "zsinor": [100.0]})
    k = TE.ar_kapcsolat(napi_t, napi_ar, MA)
    assert k["pontok"] == 1 and k["nap"] is None and k["mondatok"] == []
    assert TE.ar_kapcsolat(pd.DataFrame(), pd.DataFrame(), MA)["pontok"] == 0


def kapacitas_valasz():
    """A beépített teljesítmény válaszának utánzata (gigawattban, ahogy a forrás adja)."""
    return {"time": ["2023", "2024", "2025"],
            "production_types": [{"name": "Nuclear", "data": [1.92, 1.92, 1.92]},
                                 {"name": "Solar AC", "data": [5.6, 7.4, 8.72]},
                                 {"name": "Solar gross", "data": [6.0, 7.9, 9.3]},
                                 {"name": "Wind onshore", "data": [0.33, 0.33, 0.33]},
                                 {"name": "Biomass", "data": [0.31, 0.31, 0.34]},
                                 {"name": "Fossil gas", "data": [None, 3.5, 3.5]}]}


def test_feldolgoz_kapacitas_megawattban_es_csoportonkent():
    t = F.feldolgoz_kapacitas(kapacitas_valasz())
    nap25 = t[(t["ev"] == "2025") & (t["csoport"] == "napenergia")].iloc[0]
    assert nap25["mw"] == pytest.approx(8720.0)  # gigawattból megawatt
    # a bruttó napelemes sor nem adódik hozzá még egyszer
    assert len(t[(t["ev"] == "2025") & (t["csoport"] == "napenergia")]) == 1
    # a hiányzó érték kimarad, nem lesz belőle nulla
    assert t[(t["ev"] == "2023") & (t["csoport"] == "foldgaz")].empty
    assert F.feldolgoz_kapacitas({}).empty


def test_beepitett_az_utolso_evet_adja():
    b = TE.beepitett(F.feldolgoz_kapacitas(kapacitas_valasz()))
    assert b["_ev"] == "2025" and b["napenergia"] == pytest.approx(8720.0)
    assert b["atom"] == pytest.approx(1920.0)
    assert TE.beepitett(pd.DataFrame()) == {}


def test_kihasznaltsag_a_napi_csucsot_meri_a_beepitetthez():
    kap = F.feldolgoz_kapacitas(kapacitas_valasz())
    t = F.feldolgoz_termeles(valasz("2026-09-24T00:00", 1, nap_csucs=4360.0))
    k = TE.kihasznaltsag(kap, t, "2026-09-24")
    nap = k[k["csoport"] == "napenergia"].iloc[0]
    assert nap["beepitett_mw"] == pytest.approx(8720.0)
    assert nap["arany"] == pytest.approx(50.0, abs=0.5)  # 4360 MW a 8720-ból
    atom = k[k["csoport"] == "atom"].iloc[0]
    assert atom["arany"] == pytest.approx(93.75, abs=0.5)
    assert list(k["arany"]) == sorted(k["arany"], reverse=True)  # a legjobban kihasznált elöl
    assert TE.kihasznaltsag(kap, t, "2026-09-01").empty
    assert TE.kihasznaltsag(pd.DataFrame(), t, "2026-09-24").empty


def test_kapacitas_novekedes_es_mondat():
    kap = F.feldolgoz_kapacitas(kapacitas_valasz())
    n = TE.kapacitas_novekedes(kap)
    assert set(n["csoport"]) == {"napenergia", "szel"} and len(n) == 6
    mondat = TE.kapacitas_mondat(kap)
    assert "5,6 gigawattról" in mondat and "8,7 gigawattra" in mondat and "1,6-szeresére" in mondat
    assert "—" not in mondat
    assert TE.kapacitas_mondat(pd.DataFrame()) is None
