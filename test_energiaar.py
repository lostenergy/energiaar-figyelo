"""Tesztek: python -m pytest -q"""

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

GYOKER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GYOKER))

import beallitas as B  # noqa: E402
import forrasok as F  # noqa: E402
import szamitas as S  # noqa: E402

MINTA = Path(__file__).parent / "minta"
BP = ZoneInfo("Europe/Budapest")


def api_valasz(kezdet: str, veg: str, lepes_mp: int = 900, ar=lambda i: 80 + (i % 96) / 4):
    k = int(datetime.fromisoformat(kezdet).replace(tzinfo=BP).timestamp())
    v = int(datetime.fromisoformat(veg).replace(tzinfo=BP).timestamp())
    idok = list(range(k, v, lepes_mp))
    return {"unix_seconds": idok, "price": [ar(i) for i in range(len(idok))], "unit": "EUR / MWh"}


def test_villamos_negyedoras_nap():
    t = F.feldolgoz_villamos(api_valasz("2026-09-11T00:00", "2026-09-12T00:00"))
    assert len(t) == 96
    assert t.iloc[0]["negyedora"] == "00:00" and t.iloc[-1]["negyedora"] == "23:45"
    assert set(t["perc"]) == {15}
    napi = S.napi_osszesites(t)
    assert len(napi) == 1 and napi.iloc[0]["idoszakok"] == 96


def test_oszi_oraatallitas_100_negyedora():
    t = F.feldolgoz_villamos(api_valasz("2026-10-25T00:00", "2026-10-26T00:00", ar=lambda i: 100))
    assert len(t) == 100 and (t["nap"] == "2026-10-25").all()
    napi = S.napi_osszesites(t)
    assert napi.iloc[0]["zsinor"] == 100 and napi.iloc[0]["idoszakok"] == 100


def test_tavaszi_oraatallitas_92_negyedora():
    t = F.feldolgoz_villamos(api_valasz("2026-03-29T00:00", "2026-03-30T00:00"))
    assert len(t) == 92
    assert len(S.napi_osszesites(t)) == 1  # 23 órás nap is teljes


def test_oras_felbontas_es_hianyzo_ar():
    adat = api_valasz("2025-09-01T00:00", "2025-09-02T00:00", lepes_mp=3600, ar=lambda i: 50 if i < 8 else 150)
    adat["price"][3] = None
    t = F.feldolgoz_villamos(adat)
    assert len(t) == 23 and set(t["perc"]) == {60}
    n = S.napi_osszesites(t).iloc[0]
    assert n["csucs"] == 150 and n["csucson_kivul"] == pytest.approx((7 * 50 + 4 * 150) / 11, abs=0.01)


def test_resznap_kimarad_az_osszesitesbol():
    t = F.feldolgoz_villamos(api_valasz("2026-09-12T00:00", "2026-09-12T12:00"))
    assert S.napi_osszesites(t).empty


def test_csucs_sulyozas_es_min_max():
    t = F.feldolgoz_villamos(api_valasz("2026-09-11T00:00", "2026-09-12T00:00",
                                        ar=lambda i: 200 if 32 <= i < 80 else 40))
    n = S.napi_osszesites(t).iloc[0]
    assert n["csucs"] == 200 and n["csucson_kivul"] == 40
    assert n["zsinor"] == pytest.approx((48 * 200 + 48 * 40) / 96)
    assert n["min_ido"] == "00:00" and n["max_ido"] == "08:00"


def test_ceegex_masnapi():
    t = F.feldolgoz_gaz_masnapi((MINTA / "ceegex_masnapi.html").read_text())
    assert len(t) == 10  # a kötés és CEEREP nélküli sorok kimaradnak
    da = t[(t["termek"] == "DA") & (t["kereskedesi_nap"] == "2026-09-10")].iloc[0]
    assert da["atlagar"] == 80.99 and da["mennyiseg_mwh"] == 63984 and da["ceerep_valtozas"] == 2.14
    csak_ceerep = t[(t["termek"] == "Sunday") & (t["kereskedesi_nap"] == "2026-09-04")].iloc[0]
    assert pd.isna(csak_ceerep["atlagar"]) and csak_ceerep["ceerep"] == 69.27
    k = S.gaz_kulcsszamok(t)
    assert k["da"]["atlagar"] == 80.99 and k["da_elozo"]["atlagar"] == 79.07
    assert k["da_het"]["atlagar"] == 71.77 and k["hetvege"]["atlagar"] == 69.27


def test_ceegex_masnapi_szerkezetvaltozas():
    assert F.feldolgoz_gaz_masnapi("<html><body>JavaScript szükséges</body></html>").empty


def test_ceegex_napon_belul_csak_eddigi_orak():
    html = (MINTA / "ceegex_napon_belul.html").read_text()
    most = datetime(2026, 9, 11, 19, 40, tzinfo=BP)  # 14. gázóra (19:00-20:00)
    t = F.feldolgoz_gaz_napon_belul(html, most)
    assert list(t["gazora"]) == [9, 10, 12, 13, 14]
    assert (t["gaznap"] == "2026-09-11").all() and t.iloc[-1]["atlagar"] == 79.44


def test_gaznap_hajnalban_az_elozo_nap():
    assert F.aktualis_gaznap(datetime(2026, 9, 12, 5, 30, tzinfo=BP)) == ("2026-09-11", 24)
    assert F.aktualis_gaznap(datetime(2026, 9, 12, 6, 0, tzinfo=BP)) == ("2026-09-12", 1)


def test_idoszaki_atlagok():
    napok = pd.date_range("2026-06-01", "2026-09-11").strftime("%Y-%m-%d")
    napi = pd.DataFrame({"nap": napok, "zsinor": 100.0, "csucs": 120.0})
    t = S.idoszaki_atlagok(napi, date(2026, 9, 11)).set_index("idoszak")
    assert t.loc["Folyó hét", "napok"] == 5  # hétfőtől péntekig
    assert t.loc["Előző hónap", "napok"] == 31 and t.loc["Folyó negyedév", "napok"] == 73
    assert t.loc["Előző negyedév", "napok"] == 30  # csak júniusi adat van
    assert t.loc["Utolsó 30 nap", "zsinor"] == 100


def test_elozmeny_es_friss_egyesitese():
    elozmeny = F.feldolgoz_villamos(api_valasz("2026-09-08T00:00", "2026-09-11T00:00"))
    friss = F.feldolgoz_villamos(api_valasz("2026-09-10T00:00", "2026-09-13T00:00", ar=lambda i: 55.5))
    egyutt = F.egyesit([elozmeny, friss], "unix")
    assert len(egyutt) == 5 * 96 and egyutt["unix"].is_monotonic_increasing
    assert egyutt["unix"].duplicated().sum() == 0
    # az átfedő napon a frissebb ár marad
    assert (egyutt[egyutt["nap"] == "2026-09-10"]["ar"] == 55.5).all()
    assert (egyutt[egyutt["nap"] == "2026-09-09"]["ar"] != 55.5).any()
    assert list(S.napi_osszesites(egyutt)["nap"]) == ["2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-12"]


def test_egyesites_hianyzo_elozmennyel():
    friss = F.feldolgoz_villamos(api_valasz("2026-09-10T00:00", "2026-09-12T00:00"))
    assert len(F.egyesit([None, friss], "unix")) == 192
    assert F.egyesit([None, None], "unix").empty


def test_leker_villamos_szakaszol_es_szur(monkeypatch):
    hivasok = []

    class Valasz:
        status_code = 200

        def __init__(self, params):
            self.params = params

        def json(self):
            return api_valasz(self.params["start"] + "T00:00", self.params["end"] + "T00:00")

    def hamis_get(url, params=None, headers=None, timeout=None):
        hivasok.append(params)
        return Valasz(params)

    monkeypatch.setattr(F.requests, "get", hamis_get)
    t = F.leker_villamos(date(2026, 1, 1), date(2026, 4, 10), szakasz_nap=30)
    assert len(hivasok) == 4
    assert t["nap"].min() == "2026-01-01" and t["nap"].max() == "2026-04-10"
    assert t["unix"].duplicated().sum() == 0


def test_leker_villamos_hianyzo_idoszak(monkeypatch):
    """Ha egy időszakra még nincs publikált ár (404), a többi adat akkor is megjön."""

    class Valasz:
        def __init__(self, params):
            self.params = params
            self.status_code = 404 if params["start"] >= "2026-09-01" else 200
            self.text = "not found"

        def json(self):
            return api_valasz(self.params["start"] + "T00:00", self.params["end"] + "T00:00")

    monkeypatch.setattr(F.requests, "get", lambda url, params=None, headers=None, timeout=None: Valasz(params))
    t = F.leker_villamos(date(2026, 8, 1), date(2026, 9, 10), szakasz_nap=31)
    assert not t.empty and t["nap"].max() < "2026-09-01"


def test_leker_villamos_hibas_valasz(monkeypatch):
    class Valasz:
        status_code = 500
        text = "belso hiba"

    monkeypatch.setattr(F.requests, "get", lambda *a, **k: Valasz())
    with pytest.raises(F.ForrasHiba, match="500"):
        F.leker_villamos(date(2026, 9, 1), date(2026, 9, 2))

    def halozati_hiba(*a, **k):
        raise F.requests.ConnectionError("időtúllépés")

    monkeypatch.setattr(F.requests, "get", halozati_hiba)
    with pytest.raises(F.ForrasHiba, match="nem érhető el"):
        F.leker_gaz_masnapi()


# --------------------------------------------------------------- határidős árak

import hataridos as H  # noqa: E402


def test_alap_termekek_szeptemberben():
    t = H.alap_termekek(date(2026, 9, 12))
    villamos = t[t["piac"] == "Villamos"]
    gaz = t[t["piac"] == "Gáz"]
    assert set(villamos["tipus"]) == {"Zsinór", "Csúcs"} and set(gaz["tipus"]) == {"Alap"}
    nevek = list(villamos[villamos["tipus"] == "Zsinór"]["termek"])
    assert nevek[:3] == ["2026. 38. hét", "2026. 39. hét", "2026. október"]
    assert "2027. I. negyedév" in nevek and "2027. I. félév" in nevek and "2028. év" in nevek
    assert t["ar"].isna().all()
    # minden szállítási időszak a jegyzés napja után kezdődik, és a vége a kezdet után van
    assert (t["szallitas_kezdete"] > "2026-09-12").all()
    assert (t["szallitas_vege"] > t["szallitas_kezdete"]).all()


def test_termekek_idoszakhatarai():
    assert H.havi_termekek(date(2026, 12, 20), 2) == [
        ("2027. január", date(2027, 1, 1), date(2027, 1, 31)),
        ("2027. február", date(2027, 2, 1), date(2027, 2, 28))]
    assert H.negyedeves_termekek(date(2026, 9, 12), 1) == [
        ("2026. IV. negyedév", date(2026, 10, 1), date(2026, 12, 31))]
    assert H.feleves_termekek(date(2026, 9, 12), 1) == [
        ("2027. I. félév", date(2027, 1, 1), date(2027, 6, 30))]
    assert H.gazev(date(2026, 9, 12)) == [("2026/27. gázév", date(2026, 10, 1), date(2027, 9, 30))]
    assert H.gaz_szezonok(date(2026, 9, 12), 2) == [
        ("2026/27. téli szezon", date(2026, 10, 1), date(2027, 3, 31)),
        ("2027. nyári szezon", date(2027, 4, 1), date(2027, 9, 30))]
    # szökőév és évforduló
    assert H.havi_termekek(date(2028, 1, 15), 1)[0][2] == date(2028, 2, 29)
    assert [n for n, _, _ in H.heti_termekek(date(2025, 12, 24), 1)] == ["2026. 1. hét"]


def test_hataridos_mentes_es_egyesites(tmp_path):
    ma = date(2026, 9, 11)
    elso = H.alap_termekek(ma)
    villamos_ev27 = (elso["termek"] == "2027. év") & (elso["piac"] == "Villamos")
    elso.loc[villamos_ev27 & (elso["tipus"] == "Zsinór"), "ar"] = 92.5
    elso.loc[villamos_ev27 & (elso["tipus"] == "Csúcs"), "ar"] = 118.0
    tarolt = H.egyesit(H.ures(), elso)
    assert len(tarolt) == 2  # az ár nélküli sorok kimaradnak

    fajl = tmp_path / "hataridos.csv"
    fajl.write_bytes(H.csv_bajtok(tarolt))
    assert len(H.olvas(fajl)) == 2

    # másnapi jegyzés: a 2027. év ára módosul, és jön egy új termék
    masnap = H.alap_termekek(date(2026, 9, 12))
    villamos = masnap["piac"] == "Villamos"
    masnap.loc[villamos & (masnap["termek"] == "2027. év") & (masnap["tipus"] == "Zsinór"), "ar"] = 94.0
    masnap.loc[villamos & (masnap["termek"] == "2026. október") & (masnap["tipus"] == "Zsinór"), "ar"] = 130.0
    egyutt = H.egyesit(H.olvas(fajl), masnap)
    assert len(egyutt) == 4 and sorted(egyutt["jegyzes_nap"].unique()) == ["2026-09-11", "2026-09-12"]

    # ugyanarra a napra ismételt rögzítés felülírja a korábbit
    ujra = masnap.copy()
    ujra.loc[villamos & (ujra["termek"] == "2027. év") & (ujra["tipus"] == "Zsinór"), "ar"] = 95.5
    ujra.loc[villamos & (ujra["termek"] == "2026. október") & (ujra["tipus"] == "Zsinór"), "ar"] = 130.0
    vegso = H.egyesit(egyutt, ujra)
    assert len(vegso) == 4
    ev27 = vegso[(vegso["jegyzes_nap"] == "2026-09-12") & (vegso["termek"] == "2027. év")
                 & (vegso["tipus"] == "Zsinór")]
    assert ev27.iloc[0]["ar"] == 95.5


def test_gorbe_es_felar():
    ma = date(2026, 9, 12)
    t = H.alap_termekek(ma)
    t.loc[t["tipus"] == "Zsinór", "ar"] = 100.0  # csak a villamos zsinór termékek
    t = H.egyesit(H.ures(), t)
    g = H.gorbe(t, "Villamos")
    assert not g.empty and g["szallitas_kezdete"].is_monotonic_increasing
    assert H.gorbe(t, "Gáz").empty  # gázárat nem adtunk meg
    assert H.felar(110, 100) == pytest.approx(0.10)
    assert H.felar(90, 100) == pytest.approx(-0.10)
    assert H.felar(110, None) is None and H.felar(110, 0) is None


def test_hibas_hataridos_fajl(tmp_path):
    assert H.olvas(tmp_path / "nincs_ilyen.csv").empty
    rossz = tmp_path / "rossz.csv"
    rossz.write_text("ez nem egy ártáblázat")
    assert H.olvas(rossz).empty
    hianyos = tmp_path / "hianyos.csv"
    hianyos.write_text("piac,termek,ar\nVillamos,2027. év,nem szám\n")
    t = H.olvas(hianyos)
    assert list(t.columns) == H.OSZLOPOK and pd.isna(t.iloc[0]["ar"])
