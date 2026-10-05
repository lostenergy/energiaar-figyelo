"""A Kitekintő fül hírgyűjtése és összegzése. Futtatás: python -m pytest -q"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hirek as HI  # noqa: E402
import osszegzes as O  # noqa: E402

MOST = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def rss(tetelek: list[tuple[str, str, str, str]]) -> str:
    """Egyszerű RSS 2.0 csatorna: (cím, leírás, link, dátum) négyesekből."""
    sorok = "".join(
        f"<item><title>{c}</title><description>{le}</description>"
        f"<link>{li}</link><pubDate>{d}</pubDate></item>" for c, le, li, d in tetelek)
    return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>' \
           f"<title>Próba</title>{sorok}</channel></rss>"


def atom(tetelek: list[tuple[str, str, str]]) -> str:
    sorok = "".join(
        f'<entry><title>{c}</title><link href="{li}"/><updated>{d}</updated></entry>'
        for c, li, d in tetelek)
    return f'<?xml version="1.0" encoding="UTF-8"?>' \
           f'<feed xmlns="http://www.w3.org/2005/Atom"><title>Próba</title>{sorok}</feed>'


FORRAS_SZURT = HI.Forras("Próba", "http://p/rss", "magyar", szures=True)
FORRAS_SZAK = HI.Forras("Szakmai", "http://p/rss", "vilag", szures=False, magyar=False)


def test_rss_feldolgozas_alapadatok():
    tartalom = rss([("Emelkedett a gáz ára", "A tőzsdén", "http://a/1", "Sat, 03 Oct 2026 10:00:00 +0200")])
    hirek = HI.feldolgoz_csatorna(tartalom, FORRAS_SZURT)
    assert len(hirek) == 1
    h = hirek[0]
    assert h["cim"] == "Emelkedett a gáz ára" and h["link"] == "http://a/1"
    assert h["forras"] == "Próba" and h["terulet"] == "magyar"
    assert h["ido"].tzinfo is not None and h["ido"].year == 2026


def test_atom_feldolgozas():
    hirek = HI.feldolgoz_csatorna(atom([("Power prices fall", "http://a/2", "2026-10-03T08:00:00Z")]),
                                  FORRAS_SZAK)
    assert len(hirek) == 1 and hirek[0]["link"] == "http://a/2"
    assert hirek[0]["ido"].hour == 8


def test_altalanos_hirfolyambol_csak_az_energia_marad():
    tartalom = rss([
        ("Emelkedett az áram ára a tőzsdén", "", "http://a/1", "Sat, 03 Oct 2026 10:00:00 +0200"),
        ("Új stadion épül a városban", "Sportberuházás", "http://a/2", "Sat, 03 Oct 2026 11:00:00 +0200"),
        ("Döntött a kormány", "A földgáz beszerzéséről tárgyaltak", "http://a/3",
         "Sat, 03 Oct 2026 12:00:00 +0200"),
    ])
    cimek = [h["cim"] for h in HI.feldolgoz_csatorna(tartalom, FORRAS_SZURT)]
    assert "Emelkedett az áram ára a tőzsdén" in cimek
    assert "Döntött a kormány" in cimek  # a leírásban van az energia
    assert "Új stadion épül a városban" not in cimek


def test_szakmai_csatornabol_minden_bekerul():
    tartalom = rss([("Company reshuffles its board", "", "http://a/9", "Sat, 03 Oct 2026 10:00:00 +0000")])
    assert len(HI.feldolgoz_csatorna(tartalom, FORRAS_SZAK)) == 1


def test_fontossag_az_arat_mozgato_szavakat_emeli():
    sok = HI.fontossag("Szankció miatt leállás, emelkedő árak a tőzsdén")
    keves = HI.fontossag("Új munkatársat nevezett ki a vállalat")
    assert sok > keves and keves == 0


def test_hibas_tartalom_nem_dol_el():
    assert HI.feldolgoz_csatorna("ez nem xml", FORRAS_SZURT) == []
    assert HI.feldolgoz_csatorna("", FORRAS_SZURT) == []


def hamis_leker(valaszok: dict):
    def leker(forras, idokorlat=10):
        if forras.nev not in valaszok:
            raise HI.requests.ConnectionError("időtúllépés")
        return HI.feldolgoz_csatorna(valaszok[forras.nev], forras)
    return leker


def test_osszegyujt_teruletenkent_rangsorol(monkeypatch):
    magyar = HI.Forras("M", "http://m", "magyar")
    vilag = HI.Forras("V", "http://v", "vilag", szures=False)
    valaszok = {
        "M": rss([
            ("Régi hír az áramról", "", "http://m/regi", "Mon, 01 Jan 2024 10:00:00 +0000"),
            ("Energiaügyi kinevezés", "", "http://m/1", "Sat, 03 Oct 2026 10:00:00 +0000"),
            ("Szankció miatt emelkedik a gáz ára, leállás a vezetéken", "", "http://m/2",
             "Sat, 03 Oct 2026 09:00:00 +0000"),
        ]),
        "V": rss([("Oil prices surge after outage", "", "http://v/1", "Sat, 03 Oct 2026 08:00:00 +0000")]),
    }
    monkeypatch.setattr(HI, "leker_csatorna", hamis_leker(valaszok))
    ki = HI.osszegyujt([magyar, vilag, HI.Forras("Halott", "http://x", "europa")], most=MOST)
    t = ki["hirek"]
    assert ki["forrasok"] == 2 and any("Halott" in h for h in ki["hibak"])
    magyarok = HI.terulet_hirei(t, "magyar")
    assert list(magyarok["cim"])[0].startswith("Szankció")  # az árat mozgató hír megy előre
    assert "http://m/regi" not in list(magyarok["link"])  # a tíz napnál régebbi kimarad
    assert len(HI.terulet_hirei(t, "vilag")) == 1
    assert HI.terulet_hirei(t, "europa").empty


def test_osszegyujt_kiszuri_az_ismetlodest(monkeypatch):
    f1, f2 = HI.Forras("A", "http://a", "magyar"), HI.Forras("B", "http://b", "magyar")
    azonos = ("Emelkedik az áram ára", "", "http://hir/1", "Sat, 03 Oct 2026 10:00:00 +0000")
    monkeypatch.setattr(HI, "leker_csatorna", hamis_leker({"A": rss([azonos]), "B": rss([azonos])}))
    assert len(HI.osszegyujt([f1, f2], most=MOST)["hirek"]) == 1


def test_hirek_szovegge():
    t = pd.DataFrame([{"terulet": "magyar", "ido": MOST, "cim": "Drágul a gáz",
                       "link": "http://a", "forras": "Próba", "pont": 2}], columns=HI.OSZLOPOK)
    szoveg = HI.hirek_szovegge(t, "magyar")
    assert "Drágul a gáz" in szoveg and "2026-10-04" in szoveg and "Próba" in szoveg
    assert HI.hirek_szovegge(t, "vilag") == ""


# ---------------------------------------------------------------- összegzés

def test_osszegzes_beallit_es_olvas():
    t = O.beallit(None, "magyar", "  Három mondat.  ", "kez", "2026-10-04 12:00")
    t = O.beallit(t, "vilag", "Más szöveg.", "gep", "2026-10-04 12:05")
    t = O.beallit(t, "magyar", "Felülírt szöveg.", "gep", "2026-10-04 12:10")
    assert len(t) == 2  # területenként egy sor marad
    m = O.olvas(t, "magyar")
    assert m["szoveg"] == "Felülírt szöveg." and m["mod"] == "gep" and m["frissitve"] == "2026-10-04 12:10"
    assert O.olvas(t, "europa")["szoveg"] == ""
    assert O.olvas(None, "magyar")["szoveg"] == ""


def test_osszegzes_keszit_valasz_feldolgozasa(monkeypatch):
    class Valasz:
        status_code = 200

        def json(self):
            return {"content": [{"type": "text", "text":
                                 'Íme: {"magyar": "Magyar szöveg.", "europa": "Európai.", '
                                 '"vilag": "Világ."}'}]}

    rogzitett = {}

    def post(url, headers=None, json=None, timeout=None):
        rogzitett.update(url=url, fejlec=headers, csomag=json)
        return Valasz()

    monkeypatch.setattr(O.requests, "post", post)
    ki = O.keszit({"magyar": "- hír egy", "europa": "", "vilag": "- hír ketto"}, "kulcs-123")
    assert ki == {"magyar": "Magyar szöveg.", "europa": "Európai.", "vilag": "Világ."}
    assert rogzitett["fejlec"]["x-api-key"] == "kulcs-123"
    assert "hír egy" in rogzitett["csomag"]["messages"][0]["content"]
    assert "(nincs hír)" in rogzitett["csomag"]["messages"][0]["content"]


def test_osszegzes_keszit_hibak(monkeypatch):
    with pytest.raises(ValueError):
        O.keszit({}, "")

    class Valasz:
        status_code = 401

        def json(self):
            return {"error": {"message": "invalid key"}}

    monkeypatch.setattr(O.requests, "post", lambda *a, **k: Valasz())
    with pytest.raises(RuntimeError, match="kulcsot"):
        O.keszit({"magyar": "x"}, "rossz")


# ---------------------------------------------------------------- önműködő összegzés

def hirtabla(tetelek):
    """(cím, forrás, pont, nap eltolás) négyesekből táblázat."""
    sorok = [{"terulet": "magyar", "ido": MOST - pd.Timedelta(days=d), "cim": c,
              "link": f"http://p/{i}", "forras": f, "pont": p}
             for i, (c, f, p, d) in enumerate(tetelek)]
    return pd.DataFrame(sorok, columns=HI.OSZLOPOK)


def test_magatol_osszegzes_temakat_es_kiemelt_hirt_ad():
    t = hirtabla([
        ("Drágult a földgáz a tőzsdén, a tárolói készletek fogynak", "HVG", 3, 0),
        ("Leállás jön a vezetéken karbantartás miatt", "Világgazdaság", 2, 1),
        ("Aszály miatt esett a vízerőművek termelése", "Economx", 1, 2),
        ("Új naperőmű-beruházás indul", "Portfolio", 0, 3),
    ])
    szoveg = O.magatol(t, "hazai", MOST.date())
    assert szoveg.count(".") >= 3  # legalább három mondat
    assert "A hazai hírek közül 4 kapcsolódik" in szoveg
    assert "„Drágult a földgáz a tőzsdén, a tárolói készletek fogynak”" in szoveg
    assert "HVG" in szoveg and "ma" in szoveg
    assert "részletekért" in szoveg
    assert "—" not in szoveg  # magyar szövegben nincs gondolatjel


def test_magatol_osszegzes_iranyt_jelez():
    fel = O.magatol(hirtabla([("Emelkedik az ár", "A", 1, 0), ("Drágul a gáz", "B", 1, 0),
                              ("Rekordot döntött a tőzsdei ár", "C", 1, 0)]), "világszintű", MOST.date())
    assert "emelkedő árak felé mutat" in fel
    le = O.magatol(hirtabla([("Csökken az ár", "A", 1, 0), ("Olcsóbb lett a gáz", "B", 1, 0),
                             ("Zuhant a tőzsdei ár", "C", 1, 0)]), "világszintű", MOST.date())
    assert "mérséklődő árak felé mutat" in le


def test_magatol_osszegzes_ures_tablara():
    assert O.magatol(pd.DataFrame(columns=HI.OSZLOPOK), "európai", MOST.date()) == ""
    assert O.magatol(None, "európai", MOST.date()) == ""


def test_tema_besorolas():
    assert O._tema("Leállás jön a Barátság vezetéken") == "leállások"
    assert O._tema("Szankciók jönnek az orosz olajra") == "geopolitika"
    assert O._tema("Emelkedik a tőzsdei villamosenergia-ár") == "villamos energia"
    assert O._tema("Teljesen érdektelen cím") is None


def test_valaszt_a_friss_irottat_hasznalja():
    info = {"szoveg": "Kézzel írt szöveg.", "frissitve": "2026-10-02 08:00", "mod": "kez"}
    ki = O.valaszt(info, hirtabla([("Drágul a gáz", "A", 1, 0)]), "hazai", MOST.date())
    assert ki["szoveg"] == "Kézzel írt szöveg." and ki["mod"] == "kez" and ki["regi_irt"] == ""


def test_valaszt_elavult_irottat_lecsereli():
    info = {"szoveg": "Régi szöveg.", "frissitve": "2026-09-01 08:00", "mod": "kez"}
    ki = O.valaszt(info, hirtabla([("Drágul a gáz", "A", 1, 0)]), "hazai", MOST.date())
    assert ki["mod"] == "auto" and "Drágul a gáz" in ki["szoveg"]
    assert ki["regi_irt"] == "2026-09-01 08:00"


def test_valaszt_ures_tarolonal_magatol_keszit():
    ki = O.valaszt({}, hirtabla([("Drágul a gáz", "A", 1, 0)]), "európai", MOST.date())
    assert ki["mod"] == "auto" and ki["szoveg"] and ki["regi_irt"] == ""
