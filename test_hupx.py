"""A HUPX Labs forrás: másnapi árak és erőművi kiesések. Futtatás: python -m pytest -q"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import forrasok as F  # noqa: E402
import hupx as HU  # noqa: E402


def ar_sor(nap: str, sorszam: int, ar: float, forgalom: float = 3000.0, regio: str = "HU"):
    """A válasz egy sora, pontosan olyan szerkezettel, ahogy a forrás adja."""
    return {"BaseloadPrice": 252.81, "DeliveryDay": f"{nap}T00:00:00Z", "Price": ar,
            "ProductQH": str(sorszam), "Region": regio, "Status": "final", "Volume": forgalom}


KIESES_SOR = {
    "AffectedAssetUnit": "Unit 5.", "AvailableCapacity": 214,
    "EventStart": "2026-10-15T22:00:00+02:00", "EventStop": "2026-10-18T00:00:00+02:00",
    "EventStatus": "Active", "EventType": "Production unavailability",
    "FuelType": "Fossil Brown coal/Lignite", "InstalledCapacity": 224,
    "MarketParticipant": "MVM Mátra Energia Zártkörűen Működő Részvénytársaság",
    "UnavailabilityReason": "<p>Limit of technology system</p>",
    "UnavailabilityType": "Unplanned", "UnavailableCapacity": 224,
}


def test_arak_feldolgozasa_negyedorakra():
    sorok = [ar_sor("2026-10-15", i, 100 + i) for i in range(1, 97)]
    t = HU.feldolgoz_arak(sorok)
    assert len(t) == 96 and list(t.columns) == HU.ARAK_OSZLOPOK
    elso, utolso = t.iloc[0], t.iloc[-1]
    assert elso["ido"] == "2026-10-15 00:00" and elso["negyedora"] == "00:00" and elso["ora"] == 0
    assert utolso["ido"] == "2026-10-15 23:45" and utolso["ora"] == 23
    assert elso["ar"] == 101 and utolso["ar"] == 196
    assert set(t["perc"]) == {15} and set(t["nap"]) == {"2026-10-15"}
    # az időbélyeg másodpercben, negyedórás lépéssel
    assert int(utolso["unix"]) - int(elso["unix"]) == 95 * 900


def test_arak_ora_atallitaskor():
    """Októberi óraátállításkor 100 negyedóra van, és kétszer van 02:00 és 03:00 között."""
    sorok = [ar_sor("2026-10-25", i, 100 + i) for i in range(1, 101)]
    t = HU.feldolgoz_arak(sorok)
    assert len(t) == 100
    assert t.iloc[0]["ido"] == "2026-10-25 00:00"
    assert t.iloc[-1]["ido"] == "2026-10-25 23:45"
    assert list(t["negyedora"]).count("02:00") == 2  # a megismételt óra
    assert set(t["nap"]) == {"2026-10-25"}


def test_arak_hibas_vagy_hianyos_sorok():
    sorok = [ar_sor("2026-10-15", 1, 100), {"DeliveryDay": "2026-10-15T00:00:00Z"},
             {"ProductQH": "2", "Price": 50}, ar_sor("2026-10-15", 2, None)]
    t = HU.feldolgoz_arak(sorok)
    assert len(t) == 1 and t.iloc[0]["ar"] == 100
    assert HU.feldolgoz_arak([]).empty and list(HU.feldolgoz_arak([]).columns) == HU.ARAK_OSZLOPOK


def test_napi_forgalom():
    sorok = [ar_sor("2026-10-15", i, 100, forgalom=3000.0) for i in range(1, 97)]
    forgalom = HU.napi_forgalom(HU.feldolgoz_arak(sorok))
    assert forgalom["2026-10-15"] == pytest.approx(72000.0)  # 96 negyedóra, 3000 MW
    assert HU.napi_forgalom(pd.DataFrame()) == {}


def test_arak_tabla_osszefeslik_a_masik_forrassal():
    """A két forrás ugyanarra az időpontra ugyanazt a kulcsot adja, és a HUPX nyer."""
    hupx = HU.feldolgoz_arak([ar_sor("2026-10-15", 1, 111.11)])
    masik = pd.DataFrame([{"unix": int(hupx.iloc[0]["unix"]), "ido": "2026-10-15 00:00",
                           "nap": "2026-10-15", "negyedora": "00:00", "ora": 0, "ar": 99.99,
                           "perc": 15}], columns=F.VILLAMOS_OSZLOPOK)
    egyben = F.egyesit([masik, hupx[F.VILLAMOS_OSZLOPOK]], "unix")
    assert len(egyben) == 1 and egyben.iloc[0]["ar"] == 111.11


def test_kiesesek_feldolgozasa():
    tervezett = dict(KIESES_SOR, UnavailabilityType="Planned", UnavailableCapacity=428,
                     AffectedAssetUnit="Gönyű Power Plant", FuelType="Fossil Gas")
    t = HU.feldolgoz_kiesesek([tervezett, KIESES_SOR])
    assert list(t.columns) == HU.KIESES_OSZLOPOK
    # a nem tervezett kerül előre, hiába kisebb
    assert t.iloc[0]["tipus"] == "nem tervezett" and t.iloc[0]["egyseg"] == "Unit 5."
    assert t.iloc[0]["uzemanyag"] == "lignit" and t.iloc[1]["uzemanyag"] == "földgáz"
    assert t.iloc[0]["ok"] == "Limit of technology system"  # a jelölők eltávolítva
    assert t.iloc[0]["kezdet"] == "2026-10-15 22:00" and t.iloc[0]["veg"] == "2026-10-18 00:00"
    assert t.iloc[0]["beepitett_mw"] == 224


def test_kiesesek_osszegzese():
    tervezett = dict(KIESES_SOR, UnavailabilityType="Planned", UnavailableCapacity=428)
    o = HU.kieses_osszegzes(HU.feldolgoz_kiesesek([tervezett, KIESES_SOR]))
    assert o["nem_tervezett_mw"] == 224 and o["tervezett_mw"] == 428
    assert o["osszes_mw"] == 652 and o["darab"] == 2
    assert HU.kieses_osszegzes(pd.DataFrame())["darab"] == 0
    assert HU.feldolgoz_kiesesek([]).empty


def test_leker_arak_a_helyes_szurovel(monkeypatch):
    rogzitett = {}

    class Valasz:
        status_code = 200

        def json(self):
            return {"message": "Success", "data": [ar_sor("2026-10-15", 1, 100)]}

    def keres(cim, parameterek=None, nev=""):
        rogzitett.update(cim=cim, parameterek=parameterek, nev=nev)
        return Valasz()

    monkeypatch.setattr(HU.F, "keres", keres)
    t = HU.leker_arak(date(2026, 10, 14), date(2026, 10, 16))
    assert len(t) == 1
    szuro = rogzitett["parameterek"]["filter"]
    assert "DeliveryDay__gte__2026-10-14" in szuro and "DeliveryDay__lte__2026-10-16" in szuro
    assert "Region__in__HU" in szuro and rogzitett["cim"].endswith("dam_aggregated_trading_data_15min")


def test_leker_hibas_valasz(monkeypatch):
    class Valasz:
        status_code = 500

        def json(self):
            return {}

    monkeypatch.setattr(HU.F, "keres", lambda *a, **k: Valasz())
    with pytest.raises(F.ForrasHiba, match="500"):
        HU.leker_kiesesek(date(2026, 10, 15))
