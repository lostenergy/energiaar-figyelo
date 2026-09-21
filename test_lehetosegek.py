"""A Lehetőségek fül számításai és a megfigyelési napló. Futtatás: python -m pytest -q"""

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import forrasok as F  # noqa: E402
import hataridos as H  # noqa: E402
import lehetosegek as L  # noqa: E402
import megfigyeles as M  # noqa: E402
import szamitas as S  # noqa: E402

BP = ZoneInfo("Europe/Budapest")
MA = date(2026, 9, 20)


def villamos_sor(kezdet: str, napok: int, ar=lambda ido: 100.0):
    k = int(datetime.fromisoformat(kezdet).replace(tzinfo=BP).timestamp())
    idok = list(range(k, k + napok * 86400, 900))
    return F.feldolgoz_villamos({"unix_seconds": idok,
                                 "price": [ar(datetime.fromtimestamp(u, BP)) for u in idok]})


def napos_ar(ido):
    """Déli mélypont, esti csúcs: hasonló a mostani magyar árakhoz."""
    return 100 - (60 if 11 <= ido.hour < 15 else 0) + (50 if 18 <= ido.hour < 21 else 0)


def cez_jegyzesek(nap="2026-09-14"):
    sorok = [("2026. október", 207.0), ("2026. november", 220.5), ("2026. IV. negyedév", 213.25),
             ("2027. I. negyedév", 210.5), ("2027. II. negyedév", 128.7), ("2027. év", 159.5),
             ("2028. év", 119.0), ("2029. év", 104.5)]
    alap = H.alap_termekek(date.fromisoformat(nap))
    alap = alap[(alap["piac"] == "Villamos") & (alap["tipus"] == "Zsinór")]
    for termek, ar in sorok:
        alap.loc[alap["termek"] == termek, "ar"] = ar
    alap["jegyzes_nap"] = nap
    return H.egyesit(H.ures(), alap)


# ---------------------------------------------------------------- órás profil

def test_orai_profil_megtalalja_a_deli_olcso_savot():
    v = villamos_sor("2026-08-01T00:00", 50, napos_ar)
    profil = L.orai_profil(v, MA)
    assert len(profil) == 24
    sav = L.olcso_sav(profil)
    assert sav[0] == 11 and sav[1] < -0.4
    assert profil.loc[19, "hetkoznap_rel"] > 0.3


def test_negativ_arany_es_ures_bemenet():
    v = villamos_sor("2026-09-10T00:00", 10, lambda i: -5.0 if i.hour == 13 else 80.0)
    assert L.negativ_arany(v, MA) == pytest.approx(1 / 24, abs=0.001)
    assert L.negativ_arany(F.ures(F.VILLAMOS_OSZLOPOK), MA) is None
    assert L.orai_profil(F.ures(F.VILLAMOS_OSZLOPOK), MA).empty
    assert L.olcso_sav(pd.DataFrame(columns=["ora", "hetkoznap_rel"])) is None


def test_ora_kategoriak_harmadokba_sorol():
    v = villamos_sor("2026-09-21T00:00", 1, lambda i: float(i.hour))
    k = L.ora_kategoriak(v, date(2026, 9, 21))
    assert list(k["kategoria"].value_counts().sort_index()) == [8, 8, 8]
    assert set(k.loc[k["ora"] < 8, "kategoria"]) == {"olcso"}
    assert set(k.loc[k["ora"] >= 16, "kategoria"]) == {"draga"}
    assert L.sav_felirat(k, "olcso") == "0 és 8 óra között"
    assert L.ora_kategoriak(v, date(2026, 9, 22)).empty


def test_sav_felirat_tobb_savval():
    k = pd.DataFrame({"ora": [1, 2, 3, 12, 13], "ar": [1] * 5, "kategoria": ["olcso"] * 5})
    assert L.sav_felirat(k) == "1 és 4 óra között, 12 és 14 óra között"


# ---------------------------------------------------------------- görbe és profilár

def test_gorbe_irany_a_cez_listabol():
    g = L.legutobbi_gorbe(cez_jegyzesek(), "Villamos")
    ir = L.gorbe_irany(g)
    assert ir["irany"] == "csökkenő" and ir["evek"][:2] == [(2027, 159.5), (2028, 119.0)]
    assert L.gorbe_irany(g.iloc[:0])["irany"] is None


def test_orak_szama():
    osszes, csucs = L.orak_szama(2027)
    assert osszes == 8760 and csucs == 261 * 12
    assert L.orak_szama(2028)[0] == 8784


def test_profil_ar_pontosan_lefedi_a_fogyasztast():
    p = L.profil_ar(100.0, 130.0, 0.62, 2027, eves_mwh=1000)
    osszes, csucs = L.orak_szama(2027)
    csucsban = (p["zsinor_mw"] + p["csucs_mw"]) * csucs
    kivul = p["zsinor_mw"] * (osszes - csucs)
    assert csucsban == pytest.approx(620) and kivul == pytest.approx(380)
    assert 100 < p["ar"] < 130
    # egyenletes fogyasztásnál (a csúcsórák aránya) csak zsinór kell
    egyenletes = L.profil_ar(100.0, 130.0, csucs / osszes, 2027, 1000)
    assert egyenletes["csucs_mw"] == pytest.approx(0, abs=1e-9) and egyenletes["ar"] == pytest.approx(100)


def test_csucs_szorzo_es_profil_spot():
    v = villamos_sor("2025-09-01T00:00", 385, napos_ar)
    napi = S.napi_osszesites(v)
    szorzo = L.csucs_szorzo(napi, MA)
    assert szorzo is not None and 0.8 < szorzo < 1.2
    spot = L.profil_spot(napi, MA, 0.62)
    assert spot["napok"] >= 360 and spot["legjobb"] <= spot["atlag"] <= spot["legrosszabb"]
    assert L.csucs_szorzo(napi.iloc[:5], MA) is None


# ---------------------------------------------------------------- sávos terv

def test_savos_terv_jovo_evre_havonta():
    terv = L.savos_terv(MA, 2027, 0.7)
    assert [t["felirat"] for t in terv] == ["2026. szeptember", "2026. október", "2026. november",
                                            "2026. december"]
    assert terv[-1]["osszesen"] == pytest.approx(0.7)
    # a hónap utolsó tíz napjában már a következő hónaptól indul
    kesei = L.savos_terv(date(2026, 9, 25), 2027, 0.7)
    assert kesei[0]["felirat"] == "2026. október" and len(kesei) == 3
    korai = L.savos_terv(date(2026, 3, 5), 2027, 0.6)
    assert len(korai) == 4 and korai[0]["felirat"] == "2026. szeptember"


def test_savos_terv_kesobbi_evre_negyedevente():
    terv = L.savos_terv(MA, 2028, 0.5)
    assert terv[0]["felirat"] == "2026. október" and len(terv) == 5
    assert all(t["honap"].month in (1, 4, 7, 10) for t in terv)
    assert terv[-1]["osszesen"] == pytest.approx(0.5)
    assert L.savos_terv(MA, 2026, 0.5) == []


# ---------------------------------------------------------------- javaslatok

def test_villamos_javaslat_becsult_csucsarral():
    napi = S.napi_osszesites(villamos_sor("2025-09-01T00:00", 385, napos_ar))
    j = L.villamos_javaslat(cez_jegyzesek(), napi, MA, 1000, 0.62, 0.7)
    k = j["kovetkezo"]
    assert k["ev"] == 2027 and k["csucs_becsult"] and k["profil"] is not None
    assert j["koltseg"]["javasolt_legjobb"] <= j["koltseg"]["javasolt"] <= j["koltseg"]["javasolt_legrosszabb"]
    assert j["koltseg"]["teljes_fix"] == pytest.approx(1000 * k["profil"])
    assert any("becsültem" in m for m in j["mondatok"])
    assert len(j["terv"]) == 4


def test_villamos_javaslat_tanul_a_trendbol():
    napi = S.napi_osszesites(villamos_sor("2025-09-01T00:00", 385, napos_ar))
    eso = L.villamos_javaslat(cez_jegyzesek(), napi, MA, 1000, 0.62, 0.7, {"valtozas": -0.08, "pontok": 5})
    emelkedo = L.villamos_javaslat(cez_jegyzesek(), napi, MA, 1000, 0.62, 0.7, {"valtozas": 0.06, "pontok": 5})
    kevés = L.villamos_javaslat(cez_jegyzesek(), napi, MA, 1000, 0.62, 0.7, {"valtozas": 0.2, "pontok": 2})
    assert any("nem érdemes sietni" in m for m in eso["mondatok"])
    assert any("előrébb hozni" in m for m in emelkedo["mondatok"])
    assert not any("megfigyelt" in m for m in kevés["mondatok"])


def test_villamos_javaslat_jegyzes_nelkul():
    j = L.villamos_javaslat(H.ures(), pd.DataFrame(columns=S.NAPI_OSZLOPOK), MA, 1000, 0.62, 0.7)
    assert j["kovetkezo"] is None and j["koltseg"] is None and j["terv"] == []


def gaz_jegyzesek(termekek):
    alap = H.alap_termekek(date(2026, 9, 14))
    alap = alap[alap["piac"] == "Gáz"].copy()
    for termek, ar in termekek.items():
        alap.loc[alap["termek"] == termek, "ar"] = ar
    alap["jegyzes_nap"] = "2026-09-14"
    return H.egyesit(H.ures(), alap)


def test_gaz_javaslat_negyedevekbol():
    h = gaz_jegyzesek({"2026. IV. negyedév": 90.0, "2027. I. negyedév": 95.0,
                       "2027. II. negyedév": 70.0, "2027. III. negyedév": 65.0})
    j = L.gaz_javaslat(h, None, MA, 800)
    vart = 0.42 * 95 + 0.11 * 70 + 0.04 * 65 + 0.43 * 90
    assert j["ar"] == pytest.approx(vart) and "negyedéves" in j["megoldas"]
    assert j["koltseg"]["fix"] == pytest.approx(800 * vart)


def test_gaz_javaslat_szezonokbol_es_evbol():
    sz = L.gaz_javaslat(gaz_jegyzesek({"2026/27. téli szezon": 92.0, "2027. nyári szezon": 70.0}), None, MA, 800)
    assert sz["ar"] == pytest.approx(0.85 * 92 + 0.15 * 70) and "szezon" in sz["megoldas"]
    ev = L.gaz_javaslat(gaz_jegyzesek({"2027. év": 80.0}), None, MA, 800)
    assert ev["ar"] == 80.0 and any("egyenletesen" in m for m in ev["mondatok"])
    nincs = L.gaz_javaslat(H.ures(), None, MA, 800)
    assert nincs["ar"] is None and any("indexált" in m for m in nincs["mondatok"])


def test_piaci_kilatas_mondatai():
    v = villamos_sor("2026-08-01T00:00", 51, napos_ar)
    napi = S.napi_osszesites(v)
    mondatok = L.piaci_kilatas(cez_jegyzesek(), napi, None, v, MA)
    egyben = " ".join(mondatok)
    assert "október hónapra" in egyben and "olcsóbb jövőt" in egyben
    assert "11 és 15 óra között" in egyben
    assert "\u2014" not in egyben and "\u2013" not in egyben
    ures = L.piaci_kilatas(H.ures(), napi, None, v, MA)
    assert any("még nincs beolvasva" in m for m in ures)


# ---------------------------------------------------------------- megfigyelési napló

def napi_holnappal(holnap_is=True):
    napok = ["2026-09-19", "2026-09-20"] + (["2026-09-21"] if holnap_is else [])
    return pd.DataFrame({"nap": napok, "zsinor": [90.0] * len(napok)})


def test_naplo_holnapi_ar_hianya_majd_erkezese():
    naplo = M.ures()
    for ora, perc, van in ((12, 5, False), (13, 20, False), (13, 50, False), (14, 30, True), (16, 0, True)):
        most = datetime(2026, 9, 20, ora, perc, tzinfo=BP)
        uj = M.uj_esemenyek(naplo, most, napi_holnappal(van), None, None, {})
        naplo = M.egyesit(naplo, uj)
    hiany = naplo[naplo["tema"] == "holnapi_ar_hianyzik"]
    assert len(hiany) == 2  # 12 és 13 óra, óránként egyszer
    megjott = naplo[naplo["tema"] == "holnapi_ar"]
    assert len(megjott) == 1 and megjott.iloc[0]["idopont"] == "2026-09-20 14:30"  # az első észlelés marad
    erk = M.erkezesi_ido(naplo)
    assert erk["napok"] == 1 and erk["median"] == "14:30"
    assert erk["legkesobbi_hiany"] == "13:20"  # a 13:50-es hiány ugyanabba az órába esik, nem jegyezzük újra


def test_naplo_hiany_delelott_nem_szamit():
    uj = M.uj_esemenyek(M.ures(), datetime(2026, 9, 20, 9, 0, tzinfo=BP), napi_holnappal(False), None, None, {})
    assert uj.empty


def test_naplo_mutatok_napi_egy_ertek():
    naplo = M.ures()
    for perc, ertek in ((0, 100.0), (30, 100.0), (45, 101.5)):
        most = datetime(2026, 9, 20, 10, perc, tzinfo=BP)
        naplo = M.egyesit(naplo, M.uj_esemenyek(naplo, most, None, None, None, {"aram_30nap": ertek}))
    sor = M.mutato_idosor(naplo, "aram_30nap")
    assert len(sor) == 1 and sor.iloc[0]["ertek"] == 101.5


def test_naplo_trend_es_tanulsagok():
    naplo = M.ures()
    for nap, ertek in ((15, 100.0), (16, 104.0), (17, 110.0)):
        most = datetime(2026, 9, nap, 10, 0, tzinfo=BP)
        naplo = M.egyesit(naplo, M.uj_esemenyek(naplo, most, None, None, None,
                                                {"fwd_jovo_ev": ertek, "gorbe_irany": -0.2}))
    tr = M.trend(naplo, "fwd_jovo_ev")
    assert tr["pontok"] == 3 and tr["valtozas"] == pytest.approx(0.10)
    egyben = " ".join(M.tanulsagok(naplo))
    assert "10,0 százalékkal emelkedett" in egyben and "3 napból 3 napon" in egyben
    assert "\u2014" not in egyben
    assert "még üres" in M.tanulsagok(M.ures())[0]


def test_naplo_gaz_es_jegyzes_egyszer():
    gaz = F.feldolgoz_gaz_masnapi((Path(__file__).parent / "minta" / "ceegex_masnapi.html").read_text())
    h = cez_jegyzesek()
    most = datetime(2026, 9, 20, 10, 0, tzinfo=BP)
    elso = M.uj_esemenyek(M.ures(), most, None, gaz, h, {})
    assert set(elso["tema"]) == {"gaz_da", "jegyzes"}
    naplo = M.egyesit(M.ures(), elso)
    assert M.uj_esemenyek(naplo, most, None, gaz, h, {}).empty


def test_naplo_merete_korlatos():
    sorok = pd.DataFrame({"idopont": [f"2026-01-01 00:{i % 60:02d}" for i in range(6000)], "tema": "gaz_da",
                          "kulcs": [str(i) for i in range(6000)], "ertek": 1.0, "szoveg": ""})
    assert len(M.egyesit(M.ures(), sorok)) == M.MAX_SOR


# ---------------------------------------------------------------- árfolyam

EKB_MINTA = ("KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
             "EXR.D.HUF.EUR.SP00.A,D,HUF,EUR,SP00,A,2026-09-18,363.91,A\n")


def test_ekb_csv_feldolgozasa():
    assert F.feldolgoz_ekb_csv(EKB_MINTA) == (363.91, "2026-09-18")
    assert F.feldolgoz_ekb_csv("hibás válasz") is None
    assert F.feldolgoz_ekb_csv(EKB_MINTA.replace("363.91", "")) is None


def test_frankfurter_feldolgozasa():
    assert F.feldolgoz_frankfurter({"base": "EUR", "date": "2026-09-18", "rates": {"HUF": 363.9}}) == \
        (363.9, "2026-09-18")
    assert F.feldolgoz_frankfurter({"rates": {}}) is None


def test_arfolyam_tartalek_ha_minden_kiesik(monkeypatch):
    def hiba(*a, **k):
        raise F.requests.ConnectionError("nincs hálózat")
    monkeypatch.setattr(F.requests, "get", hiba)
    ki = F.leker_arfolyam()
    assert ki["forras"] == "becsült" and ki["arfolyam"] == F.B.EUR_HUF_TARTALEK


def test_arfolyam_ekb_bol(monkeypatch):
    class V:
        status_code = 200
        text = EKB_MINTA
    monkeypatch.setattr(F.requests, "get", lambda *a, **k: V())
    assert F.leker_arfolyam() == {"arfolyam": 363.91, "nap": "2026-09-18", "forras": "EKB"}


def test_ft_kwh():
    assert F.ft_kwh(100, 365) == pytest.approx(36.5)
    assert F.ft_kwh(None, 365) is None
