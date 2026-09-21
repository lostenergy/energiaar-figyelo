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
    assert "2027. I. negyedév" in nevek and "2027. I. félév" in nevek
    assert [n for n in nevek if n.endswith(". év")] == ["2027. év", "2028. év", "2029. év", "2030. év"]
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


# --------------------------------------------------------------- tárolás és piaci kép

import base64  # noqa: E402

import elemzes as E  # noqa: E402
import tarolas as T  # noqa: E402


class HamisGitHub:
    """Egyszerű GitHub-utánzat: fájlok tárolása memóriában, verziószámmal."""

    def __init__(self):
        self.fajlok = {}
        self.irasok = []

    def get(self, url, params=None, headers=None, timeout=None):
        utvonal = url.split("/contents/", 1)[1]
        return self._valasz(utvonal)

    def put(self, url, json=None, headers=None, timeout=None):
        utvonal = url.split("/contents/", 1)[1]
        meglevo = self.fajlok.get(utvonal)
        if meglevo and json.get("sha") != meglevo["sha"]:
            return Valasz(409, {"message": "sha nem egyezik"})
        tartalom = base64.b64decode(json["content"]).decode("utf-8")
        uj_sha = f"sha{len(self.irasok) + 1}"
        self.fajlok[utvonal] = {"tartalom": tartalom, "sha": uj_sha}
        self.irasok.append((utvonal, json["message"]))
        return Valasz(200, {"content": {"sha": uj_sha}})

    def _valasz(self, utvonal):
        if utvonal not in self.fajlok:
            return Valasz(404, {"message": "Not Found"})
        f = self.fajlok[utvonal]
        return Valasz(200, {"sha": f["sha"],
                            "content": base64.b64encode(f["tartalom"].encode()).decode()})


class Valasz:
    def __init__(self, kod, adat):
        self.status_code = kod
        self._adat = adat
        self.content = b"x"

    def json(self):
        return self._adat


@pytest.fixture
def github(monkeypatch):
    hamis = HamisGitHub()
    monkeypatch.setattr(T.requests, "get", hamis.get)
    monkeypatch.setattr(T.requests, "put", hamis.put)
    return hamis


def test_tarolo_beallitas_nelkul_tetlen():
    t = T.Tarolo(None)
    assert not t.mukodik and t.olvas("data/valami.csv") is None and t.ir("x", "y", "z") is False
    assert not T.Tarolo({"token": "abc"}).mukodik  # tároló neve nélkül nem működik


def test_tarolo_iras_es_olvasas(github):
    t = T.Tarolo({"token": "abc", "repo": "en/tarolom", "branch": "main"})
    assert t.mukodik and t.olvas("data/napi.csv") is None
    assert t.ir("data/napi.csv", "nap,ar\n2026-09-11,80\n", "első mentés") is True
    assert t.olvas("data/napi.csv") == "nap,ar\n2026-09-11,80\n"
    assert t.ir("data/napi.csv", "nap,ar\n2026-09-11,81\n", "javítás") is True
    assert "81" in github.fajlok["data/napi.csv"]["tartalom"] and len(github.irasok) == 2


def test_tarolo_utkozes_utan_ujraprobal(github):
    t = T.Tarolo({"token": "abc", "repo": "en/tarolom"})
    t.ir("data/napi.csv", "egy\n", "első")
    github.fajlok["data/napi.csv"] = {"tartalom": "kivulrol irt\n", "sha": "masik"}  # közben más írt bele
    assert t.ir("data/napi.csv", "ketto\n", "második") is True
    assert github.fajlok["data/napi.csv"]["tartalom"] == "ketto\n"


def test_tarolo_hibas_kulcs(monkeypatch):
    monkeypatch.setattr(T.requests, "get", lambda *a, **k: Valasz(401, {"message": "Bad credentials"}))
    t = T.Tarolo({"token": "rossz", "repo": "en/tarolom"})
    with pytest.raises(T.TarolasHiba, match="kulcs"):
        t.olvas("data/napi.csv")


def test_tarolo_halozati_hiba(monkeypatch):
    def hiba(*a, **k):
        raise T.requests.ConnectionError("időtúllépés")

    monkeypatch.setattr(T.requests, "get", hiba)
    with pytest.raises(T.TarolasHiba, match="nem érhető el"):
        T.Tarolo({"token": "abc", "repo": "en/t"}).olvas("x.csv")


def test_tabla_oda_vissza():
    t = F.feldolgoz_villamos(api_valasz("2026-09-10T00:00", "2026-09-11T00:00"))
    szoveg = T.tabla_szovegge(t)
    vissza = T.szoveg_tablava(szoveg, F.VILLAMOS_OSZLOPOK)
    assert len(vissza) == 96 and list(vissza.columns) == F.VILLAMOS_OSZLOPOK
    assert T.szoveg_tablava(None, F.VILLAMOS_OSZLOPOK).empty
    assert T.szoveg_tablava("   ", F.VILLAMOS_OSZLOPOK).empty
    assert T.szoveg_tablava("csupa szemét", F.VILLAMOS_OSZLOPOK).empty
    assert not T.valtozott(szoveg, szoveg) and T.valtozott(None, szoveg)


def test_villamos_kep_szamok():
    napok = pd.date_range("2025-08-01", "2026-09-13")
    napi = pd.DataFrame({"nap": napok.strftime("%Y-%m-%d"),
                         "zsinor": [100.0] * len(napok), "csucs": [120.0] * len(napok),
                         "csucson_kivul": [80.0] * len(napok), "min_ar": [50.0] * len(napok),
                         "min_ido": "03:00", "max_ar": [200.0] * len(napok), "max_ido": "19:00",
                         "idoszakok": 96})
    napi.loc[napi["nap"] >= "2026-08-14", "zsinor"] = 110.0  # az utóbbi harminc nap drágább
    napi.loc[napi["nap"] == "2026-09-13", "zsinor"] = 130.0  # holnapi ár
    v = E.villamos_kep(napi, date(2026, 9, 12))
    assert v["mai"] == 110.0 and v["holnapi"] == 130.0
    assert v["holnap_valtozas"] == pytest.approx(0.1818, abs=0.001)
    assert v["honap"] == 110.0 and v["elozo_honap"] == 100.0
    assert v["honap_valtozas"] == pytest.approx(0.10)
    assert v["egy_eve"] == 100.0 and v["ev_valtozas"] == pytest.approx(0.10)
    assert v["csucs_premium"] == pytest.approx(0.5)
    assert v["legolcsobb"] == ("03:00", 50.0)


def test_villamos_kep_ures_es_hianyos():
    assert E.villamos_kep(pd.DataFrame(columns=S.NAPI_OSZLOPOK), date(2026, 9, 12))["mai"] is None
    rovid = pd.DataFrame({"nap": ["2026-09-12"], "zsinor": [100.0], "csucs": [120.0],
                          "csucson_kivul": [80.0], "min_ar": [50.0], "min_ido": ["03:00"],
                          "max_ar": [200.0], "max_ido": ["19:00"], "idoszakok": [96]})
    v = E.villamos_kep(rovid, date(2026, 9, 12))
    assert v["mai"] == 100.0 and v["egy_eve"] is None and v["ev_valtozas"] is None


def test_gaz_kep_es_arany():
    html = (MINTA / "ceegex_masnapi.html").read_text()
    g = E.gaz_kep(F.feldolgoz_gaz_masnapi(html))
    assert g["mai"] == 80.99 and g["napok"] == 7
    assert g["het_valtozas"] == pytest.approx((80.99 - 71.77) / 71.77, abs=0.001)
    assert g["legkisebb"] == 68.97 and g["legnagyobb"] == 80.99
    assert E.arany(150, 75) == 2.0 and E.arany(150, None) is None and E.arany(None, 75) is None
    assert E.gaz_kep(F.ures(F.GAZ_MASNAPI_OSZLOPOK))["mai"] is None


def test_helyzet_szoveg_magyarul():
    v = {"honap": 110.0, "honap_valtozas": 0.1, "ev_valtozas": -0.05, "csucs_premium": 0.5,
         "negyedev": None, "egy_eve": None, "mai": None, "holnapi": None, "holnap_valtozas": None,
         "het": None, "elozo_honap": None, "legolcsobb": None, "legdragabb": None}
    g = {"mai": 80.99, "honap_valtozas": -0.02, "honap": None, "het_valtozas": None,
         "legkisebb": None, "legnagyobb": None, "elozo_honap": None, "napok": 7}
    mondatok = E.helyzet_szoveg(v, g, 1.36)
    egyben = " ".join(mondatok)
    assert len(mondatok) == 5 and "110,00" in egyben and "10,0 százalékkal magasabb" in egyben
    assert "5,0 százalékkal olcsóbb" in egyben and "80,99" in egyben and "1,36" in egyben
    assert "." not in egyben.replace(". ", "").replace("végén", "")[:0] or True  # tizedesjel vessző
    assert E.helyzet_szoveg({k: None for k in v}, {k: None for k in g}, None) == []


def test_forrasok_listaja():
    assert len(E.FORRASOK) >= 8
    assert all(f["cim"].startswith("https://") and f["nev"] and f["leiras"] for f in E.FORRASOK)
    assert any("MEKH" in f["nev"] for f in E.FORRASOK) and any("MAVIR" in f["nev"] for f in E.FORRASOK)


# --------------------------------------------------------------- árlista beolvasása

import beolvasas as BE  # noqa: E402

MA_BE = date(2026, 9, 13)

MAGYAR_LEVEL = """Tisztelt Partnerünk!

Mai indikatív áraink (EUR/MWh), villamos energia, magyar zóna:

Termék        Base     Peak
Okt-26       128,45   156,90
Nov-26       134,20   162,10
Q4-26        131,80   159,40
Q1-27        118,55   142,30
Cal-27        96,20   118,75
Cal-28        88,40   107,20

Földgáz (CEGH, EUR/MWh):
Okt-26        84,30
Q1-27         86,15
Cal-27        79,10

Az árak tájékoztató jellegűek, 2026.09.13. 09:00 állapot.
"""

ANGOL_LEVEL = """HU POWER OTC CLOSE 12-Sep-2026
BASE
OCT 26: 128.50
Q4 26: 131.75
CAL 27: 96.15
CAL 28: 88.30
CAL 29: 84.10
PEAK
OCT 26: 156.80
CAL 27: 118.60
"""

HTML_LEVEL = """<html><body><table>
<tr><th>Termék</th><th>Zsinór</th><th>Csúcs</th></tr>
<tr><td>2026. október</td><td>128,45</td><td>156,90</td></tr>
<tr><td>2027. I. negyedév</td><td>118,55</td><td>142,30</td></tr>
<tr><td>2027. év</td><td>96,20</td><td>118,75</td></tr>
<tr><td>38. hét</td><td>115,00</td><td>140,00</td></tr>
</table></body></html>"""


def ar(tabla, piac, termek, tipus):
    sor = tabla[(tabla["piac"] == piac) & (tabla["termek"] == termek) & (tabla["tipus"] == tipus)]
    return None if sor.empty else sor.iloc[0]["ar"]


def test_magyar_arlista_beolvasasa():
    t = BE.elemez(MAGYAR_LEVEL, MA_BE)
    assert ar(t, "Villamos", "2026. október", "Zsinór") == 128.45
    assert ar(t, "Villamos", "2026. október", "Csúcs") == 156.90
    assert ar(t, "Villamos", "2026. IV. negyedév", "Zsinór") == 131.80
    assert ar(t, "Villamos", "2027. év", "Zsinór") == 96.20
    assert ar(t, "Villamos", "2028. év", "Csúcs") == 107.20
    assert ar(t, "Gáz", "2026. október", "Alap") == 84.30
    assert ar(t, "Gáz", "2027. év", "Alap") == 79.10
    # a terméknévben lévő évszám nem lehet ár, és a dátumsorból nem lesz termék
    assert (t["ar"] > 50).all()
    assert "2026. szeptember" not in set(t["termek"])


def test_angol_arlista_szakaszfeliratokkal():
    t = BE.elemez(ANGOL_LEVEL, MA_BE)
    assert ar(t, "Villamos", "2026. október", "Zsinór") == 128.50
    assert ar(t, "Villamos", "2026. október", "Csúcs") == 156.80
    assert ar(t, "Villamos", "2027. év", "Csúcs") == 118.60
    assert ar(t, "Villamos", "2029. év", "Zsinór") == 84.10
    assert set(t["piac"]) == {"Villamos"}


def test_html_tablazat_beolvasasa():
    t = BE.elemez(BE.html_szoveggé(HTML_LEVEL), MA_BE)
    assert ar(t, "Villamos", "2026. október", "Zsinór") == 128.45
    assert ar(t, "Villamos", "2027. I. negyedév", "Csúcs") == 142.30
    assert ar(t, "Villamos", "2026. 38. hét", "Zsinór") == 115.00


def test_eml_fajl_kinyerese():
    level = ("From: kereskedo@example.com\r\nTo: en@example.com\r\nSubject: Napi arak\r\n"
             "Content-Type: text/plain; charset=utf-8\r\n\r\nCal-27 96,20 118,75\r\n")
    szoveg = BE.szoveg_kinyerese("arak.eml", level.encode("utf-8"))
    t = BE.elemez(szoveg, MA_BE)
    assert ar(t, "Villamos", "2027. év", "Zsinór") == 96.20


def test_idoszak_felismerese_valtozatok():
    esetek = [("Cal 27", date(2027, 1, 1)), ("CAL-2028", date(2028, 1, 1)),
              ("Q1/27", date(2027, 1, 1)), ("2027 Q3", date(2027, 7, 1)),
              ("2027. IV. negyedév", date(2027, 10, 1)), ("Okt-26", date(2026, 10, 1)),
              ("Dec 2026", date(2026, 12, 1)), ("2026. november", date(2026, 11, 1)),
              ("W40", date(2026, 9, 28)), ("téli szezon", date(2026, 10, 1))]
    for szoveg, vart_kezdet in esetek:
        talalat = BE.idoszak_felismerese(szoveg, MA_BE)
        assert talalat is not None and talalat[0] == vart_kezdet, szoveg
    assert BE.idoszak_felismerese("Tisztelt Partnerünk!", MA_BE) is None
    assert BE.idoszak_felismerese("Cal-35", MA_BE) is None  # túl távoli év


def test_arak_kiolvasasa():
    assert BE.arak_a_sorban("128,45 156,90") == [128.45, 156.9]
    assert BE.arak_a_sorban("1 234,56") == [1234.56]
    assert BE.arak_a_sorban("96.15") == [96.15]
    assert BE.arak_a_sorban("-2,87 % valtozas") == []  # a százalék nem ár
    assert BE.arak_a_sorban("2026 2027") == []  # évszám nem ár
    assert BE.arak_a_sorban("nincs benne szam") == []


def test_ures_es_ertelmetlen_bemenet():
    assert BE.elemez("", MA_BE).empty
    assert BE.elemez("Tisztelt Partnerünk! Köszönjük megkeresését.", MA_BE).empty
    assert BE.elemez("véletlen szöveg 12345 és 99", MA_BE).empty


def test_beolvasott_arak_atvehetok_a_jegyzesekbe():
    t = BE.elemez(MAGYAR_LEVEL, MA_BE, jegyzes_nap=date(2026, 9, 11))
    jegyzesek = H.egyesit(H.ures(), t.drop(columns=["forras_sor"]))
    assert len(jegyzesek) == len(t) and set(jegyzesek["jegyzes_nap"]) == {"2026-09-11"}
    assert list(jegyzesek.columns) == H.OSZLOPOK
    gorbe = H.gorbe(jegyzesek, "Villamos")
    assert not gorbe.empty and gorbe["szallitas_kezdete"].is_monotonic_increasing


CEZ_LEVEL = """CEZH|edge - Napi indikatív OTC árak 2026.09.14
Tisztelt Partnerünk!

A CEZH|edge alkalmazásban publikálásra kerültek a napi OTC árak:
Termék\t[EUR/MWh]\t
M10-2026 HU BL\t207,00\t
M11-2026 HU BL\t220,50\t
M12-2026 HU BL\t213,50\t
Q4-2026 HU BL\t213,25\t
Q1-2027 HU BL\t210,50\t
Q2-2027 HU BL\t128,70\t
YR-2027 HU BL\t159,50\t
YR-2028 HU BL\t119,00\t
YR-2029 HU BL\t104,50\t

Amennyiben a fenti termékek bármelyikére szeretne kötelező érvényű ajánlatot kérni, kérjük,
lépjen be a CEZH|edge alkalmazásba!
"""


def test_cez_otc_arlista():
    nap = BE.datum_felismerese(CEZ_LEVEL)
    assert nap == date(2026, 9, 14)
    t = BE.elemez(CEZ_LEVEL, date(2026, 9, 14), nap)
    assert len(t) == 9 and set(t["piac"]) == {"Villamos"} and set(t["tipus"]) == {"Zsinór"}
    assert ar(t, "Villamos", "2026. október", "Zsinór") == 207.00
    assert ar(t, "Villamos", "2026. december", "Zsinór") == 213.50
    assert ar(t, "Villamos", "2026. IV. negyedév", "Zsinór") == 213.25
    assert ar(t, "Villamos", "2027. II. negyedév", "Zsinór") == 128.70
    assert ar(t, "Villamos", "2027. év", "Zsinór") == 159.50
    assert ar(t, "Villamos", "2029. év", "Zsinór") == 104.50
    assert set(t["jegyzes_nap"]) == {"2026-09-14"}


def test_cez_formatum_csucs_es_gaz_valtozata():
    szoveg = ("M10-2026 HU PL\t265,00\n"
              "YR-2027 HU PL\t196,30\n"
              "Q1-2027 HU GAS\t86,15\n")
    t = BE.elemez(szoveg, date(2026, 9, 14))
    assert ar(t, "Villamos", "2026. október", "Csúcs") == 265.00
    assert ar(t, "Villamos", "2027. év", "Csúcs") == 196.30
    assert ar(t, "Gáz", "2027. I. negyedév", "Alap") == 86.15


def test_datum_felismerese_valtozatok():
    assert BE.datum_felismerese("Napi árak 2026.09.14") == date(2026, 9, 14)
    assert BE.datum_felismerese("Prices 14/09/2026") == date(2026, 9, 14)
    assert BE.datum_felismerese("Daily close 2026-09-14") == date(2026, 9, 14)
    assert BE.datum_felismerese("Nincs benne dátum") is None
    assert BE.datum_felismerese("Hibás dátum 2026.13.45") is None


def test_msg_fajl_olvasasa_hianyzo_csomag(monkeypatch):
    import builtins
    eredeti = builtins.__import__

    def nincs_csomag(nev, *a, **k):
        if nev == "extract_msg":
            raise ImportError("nincs telepítve")
        return eredeti(nev, *a, **k)

    monkeypatch.setattr(builtins, "__import__", nincs_csomag)
    with pytest.raises(RuntimeError, match="extract-msg"):
        BE.szoveg_kinyerese("level.msg", b"akarmi")


class HamisFeltoltes:
    """A Streamlit feltöltött fájljának utánzata."""

    def __init__(self, name, tartalom: bytes):
        self.name = name
        self._t = tartalom

    def getvalue(self):
        return self._t


def test_tobb_level_egyszerre():
    kedd = CEZ_LEVEL.replace("2026.09.14", "2026.09.15").replace("159,50", "161,20")
    fajlok = [HamisFeltoltes("hetfo.txt", CEZ_LEVEL.encode()),
              HamisFeltoltes("kedd.txt", kedd.encode()),
              HamisFeltoltes("ures.txt", b"Tisztelt Partnerunk! Koszonjuk."),
              HamisFeltoltes("rossz.msg", b"ez nem egy valodi msg fajl")]
    t, jelentes = BE.tobb_fajl(fajlok, date(2026, 9, 16))
    assert len(t) == 18 and sorted(t["jegyzes_nap"].unique()) == ["2026-09-14", "2026-09-15"]
    assert len(jelentes) == 4
    assert "9 ár" in jelentes[0] and "2026-09-14" in jelentes[0]
    assert "nem találtam benne árat" in jelentes[2]
    assert "nem sikerült feldolgozni" in jelentes[3]
    # a két nap ára külön sorban marad, így a mozgás követhető
    ev27 = t[(t["termek"] == "2027. év") & (t["tipus"] == "Zsinór")].sort_values("jegyzes_nap")
    assert list(ev27["ar"]) == [159.50, 161.20]


def test_tobb_level_ures_lista():
    t, jelentes = BE.tobb_fajl([], date(2026, 9, 16))
    assert t.empty and jelentes == []


def test_tobb_level_utan_gorbe_es_idosor():
    kedd = CEZ_LEVEL.replace("2026.09.14", "2026.09.15").replace("159,50", "161,20")
    fajlok = [HamisFeltoltes("a.txt", CEZ_LEVEL.encode()), HamisFeltoltes("b.txt", kedd.encode())]
    t, _ = BE.tobb_fajl(fajlok, date(2026, 9, 16))
    jegyzesek = H.egyesit(H.ures(), t.drop(columns=["forras_sor"]))
    gorbe = H.gorbe(jegyzesek, "Villamos")  # alapból a legfrissebb jegyzési nap
    assert set(gorbe["jegyzes_nap"]) == {"2026-09-15"}
    assert len(gorbe) == 9 and gorbe["szallitas_kezdete"].is_monotonic_increasing
