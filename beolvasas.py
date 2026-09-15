"""Árlisták beolvasása e-mailből vagy szövegből.

A kereskedők árlistái nem egységesek, ezért a beolvasó felismeri a szokásos jelöléseket
(Cal-27, Q1/27, Okt-26, 2027. október, 40. hét), és megkeresi mellettük az árat. Az eredményt
mindig a felhasználó hagyja jóvá, mielőtt rögzülne.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from email import policy
from email.parser import BytesParser

import pandas as pd

import hataridos as H

OSZLOPOK = H.OSZLOPOK + ["forras_sor"]

HONAP_ANGOL = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
               "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
HONAP_MAGYAR = {"jan": 1, "feb": 2, "már": 3, "mar": 3, "ápr": 4, "apr": 4, "máj": 5, "maj": 5,
                "jún": 6, "jun": 6, "júl": 7, "jul": 7, "aug": 8, "sze": 9, "okt": 10,
                "nov": 11, "dec": 12}
ROMAI_SZAM = {"i": 1, "ii": 2, "iii": 3, "iv": 4}

CSUCS_SZAVAK = ("peak", "csúcs", "csucs", "pl ", "peakload")
ZSINOR_SZAVAK = ("base", "zsinór", "zsinor", "bl ", "baseload")
GAZ_SZAVAK = ("gáz", "gaz", "gas", "ttf", "cegh", "mgp", "thm", "földgáz", "foldgaz")
VILLAMOS_SZAVAK = ("villamos", "áram", "aram", "power", "hupx", "eex", "hudex", "el.")

# Ár: 92,45 vagy 92.45 vagy 1 234,56; a százalékot és az évszámot kiszűrjük
SZAM_MINTA = re.compile(r"(?<![\w.,])(\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d{1,3})?|\d{1,4}(?:[.,]\d{1,3})?)(?![\w])")


def szoveg_kinyerese(fajlnev: str, tartalom: bytes) -> str:
    """Sima szöveggé alakítja a feltöltött fájlt. Ismeretlen típusnál megpróbálja szövegként olvasni."""
    nev = (fajlnev or "").lower()
    if nev.endswith(".msg"):
        return msg_szoveggé(tartalom)
    if nev.endswith(".eml"):
        uzenet = BytesParser(policy=policy.default).parsebytes(tartalom)
        resz = uzenet.get_body(preferencelist=("plain", "html"))
        szoveg = resz.get_content() if resz else ""
        return html_szoveggé(szoveg) if resz and resz.get_content_type() == "text/html" else szoveg
    dekodolt = _dekodol(tartalom)
    if nev.endswith((".html", ".htm")) or "<table" in dekodolt.lower() or "<td" in dekodolt.lower():
        return html_szoveggé(dekodolt)
    return dekodolt


def msg_szoveggé(tartalom: bytes) -> str:
    """Outlook-levél szövege. A tárgysort is visszaadja, mert abban gyakran ott a dátum."""
    try:
        import extract_msg
    except ImportError as e:
        raise RuntimeError("Az Outlook-levelek olvasásához az extract-msg csomag kell. "
                           "Mentsd a levelet eml formátumban, vagy másold be a szövegét.") from e
    import io
    uzenet = extract_msg.Message(io.BytesIO(tartalom))
    darabok = [uzenet.subject or "", uzenet.body or ""]
    if not (uzenet.body or "").strip() and getattr(uzenet, "htmlBody", None):
        darabok.append(html_szoveggé(_dekodol(uzenet.htmlBody)))
    return "\n".join(darabok)


DATUM_MINTA = [
    (re.compile(r"\b(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})\b"), (1, 2, 3)),
    (re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](20\d{2})\b"), (3, 2, 1)),
]


def datum_felismerese(szoveg: str) -> date | None:
    """A levélben szereplő első értelmes dátum, például a tárgysorból."""
    for minta, (e, h, n) in DATUM_MINTA:
        for talalat in minta.finditer(szoveg[:600]):
            try:
                return date(int(talalat.group(e)), int(talalat.group(h)), int(talalat.group(n)))
            except ValueError:
                continue
    return None


def _dekodol(tartalom: bytes) -> str:
    for kodolas in ("utf-8", "cp1250", "iso-8859-2", "latin-1"):
        try:
            return tartalom.decode(kodolas)
        except UnicodeDecodeError:
            continue
    return tartalom.decode("utf-8", errors="replace")


def html_szoveggé(html: str) -> str:
    """HTML táblázatból soronként tagolt szöveg, hogy a termék és az ára egy sorba kerüljön."""
    szoveg = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    szoveg = re.sub(r"(?i)</t[dh]>", " | ", szoveg)
    szoveg = re.sub(r"(?i)</(tr|p|div|h\d|li|br)>|<br\s*/?>", "\n", szoveg)
    szoveg = re.sub(r"<[^>]+>", " ", szoveg)
    szoveg = szoveg.replace("&nbsp;", " ").replace("&amp;", "&").replace("&eacute;", "é")
    return "\n".join(re.sub(r"[ \t\u00a0]+", " ", s).strip(" |") for s in szoveg.split("\n"))


def _ev(reszlet: str) -> int:
    szam = int(reszlet)
    return szam if szam > 100 else 2000 + szam


def _termekek(ma: date) -> list[tuple[str, date, date]]:
    """Széles terméklista, amihez a felismert időszakokat hozzárendeljük."""
    lista = [(f"{ma.year}. {H.HONAP_NEV[ma.month - 1]}", H._honap_eleje(ma.year, ma.month),
              H._honap_vege(ma.year, ma.month))]  # a folyó hónap is szerepelhet az árlistán
    lista += H.heti_termekek(ma, 8)
    lista += H.havi_termekek(ma, 24)
    lista += H.negyedeves_termekek(ma, 10)
    lista += H.feleves_termekek(ma, 4)
    lista += H.eves_termekek(ma, 6)
    lista += H.gaz_szezonok(ma, 4)
    lista += H.gazev(ma)
    return lista


def idoszak_felismerese(szoveg: str, ma: date):
    """A szállítási időszak és a felismert szövegrész vége, vagy None, ha nincs benne termék.

    A találat helye azért kell, mert az árat mindig a termék megnevezése után keressük; így a
    terméknévben szereplő évszám (Cal-27, Okt-26) nem kerül be árként.
    """
    t = szoveg.lower().replace("\u00a0", " ")

    m = (re.search(r"\b(?:cal|yr|y)[-/ ]?(\d{2,4})\b", t)
         or re.search(r"\b(20\d{2})\.?\s*(?:év|ev|year|cal)\b", t))
    if m:
        ev = _ev(m.group(1))
        if ma.year <= ev <= ma.year + 8:
            return date(ev, 1, 1), date(ev, 12, 31), m.end()

    m = re.search(r"\bq([1-4])[-/ ]?(\d{2,4})\b", t) or re.search(r"\b(\d{4})[-/ ]?q([1-4])\b", t)
    if m:
        a, b = m.group(1), m.group(2)
        negyedev, ev = (int(a), _ev(b)) if len(a) == 1 else (int(b), _ev(a))
        kezdet = date(ev, 3 * (negyedev - 1) + 1, 1)
        return kezdet, H._honap_vege(*H.divmod_honap(kezdet, 2)), m.end()

    m = re.search(r"\b(20\d{2})\.?\s*(i{1,3}|iv)\.?\s*negyed", t)
    if m:
        kezdet = date(int(m.group(1)), 3 * (ROMAI_SZAM[m.group(2)] - 1) + 1, 1)
        return kezdet, H._honap_vege(*H.divmod_honap(kezdet, 2)), m.end()

    m = re.search(r"\bm[-/ ]?(\d{1,2})[-/ ](\d{2,4})\b", t)  # M10-2026 alak
    if m:
        honap, ev = int(m.group(1)), _ev(m.group(2))
        if 1 <= honap <= 12 and ma.year <= ev <= ma.year + 8:
            return date(ev, honap, 1), H._honap_vege(ev, honap), m.end()

    m = re.search(r"\b([a-záéíóöúü]{3,12})[-/ .]{1,2}(\d{2,4})\b", t)
    if m and m.group(1)[:3] in HONAP_ANGOL or (m and m.group(1)[:3] in HONAP_MAGYAR):
        nev, ev_reszlet = m.group(1)[:3], m.group(2)
        honap = HONAP_ANGOL.get(nev) or HONAP_MAGYAR.get(nev)
        if honap and len(ev_reszlet) >= 2:
            ev = _ev(ev_reszlet)
            if ma.year <= ev <= ma.year + 8:
                return date(ev, honap, 1), H._honap_vege(ev, honap), m.end()

    m = re.search(r"\b(20\d{2})\.?\s*([a-záéíóöúü]{3,12})", t)
    if m:
        honap = HONAP_MAGYAR.get(m.group(2)[:3])
        if honap:
            ev = int(m.group(1))
            return date(ev, honap, 1), H._honap_vege(ev, honap), m.end()

    m = re.search(r"\bw[-/ ]?(\d{1,2})[-/ ]?(\d{2,4})?\b", t) or re.search(r"\b(\d{1,2})\.?\s*hét\b", t)
    if m:
        het = int(m.group(1))
        ev = _ev(m.group(2)) if m.lastindex and m.lastindex > 1 and m.group(2) else ma.year
        if 1 <= het <= 53:
            try:
                kezdet = date.fromisocalendar(ev, het, 1)
            except ValueError:
                return None
            if kezdet >= ma - timedelta(days=7):
                return kezdet, kezdet + timedelta(days=6), m.end()

    for kulcsszo, jelzo in (("tél", "téli"), ("winter", "téli"), ("nyár", "nyári"), ("summer", "nyári")):
        hely = t.find(kulcsszo)
        if hely >= 0:
            for nev, k, v in H.gaz_szezonok(ma, 4):
                if jelzo in nev:
                    return k, v, hely + len(kulcsszo)
    return None


def arak_a_sorban(sor: str) -> list[float]:
    """A sorban szereplő, árnak tűnő számok. Az évszámokat és a százalékokat kihagyja."""
    ki = []
    for talalat in SZAM_MINTA.finditer(sor):
        nyers = talalat.group(1)
        utana = sor[talalat.end():talalat.end() + 2]
        if "%" in utana:
            continue
        tisztitott = nyers.replace(" ", "").replace("\u00a0", "")
        if "," in tisztitott and "." in tisztitott:
            tisztitott = tisztitott.replace(".", "").replace(",", ".")
        else:
            tisztitott = tisztitott.replace(",", ".")
        try:
            ertek = float(tisztitott)
        except ValueError:
            continue
        if "." not in tisztitott and (1990 <= ertek <= 2100 or ertek < 10):
            continue  # évszám vagy sorszám
        if 5 <= ertek <= 2000:
            ki.append(round(ertek, 2))
    return ki


def _piac(sor: str, fejlec: str) -> str:
    egyben = (sor + " " + fejlec).lower()
    gaz = any(sz in egyben for sz in GAZ_SZAVAK)
    villamos = any(sz in egyben for sz in VILLAMOS_SZAVAK)
    if gaz and not villamos:
        return "Gáz"
    return "Villamos"


def _tipusok(sor: str, fejlec: str, darab: int, piac: str) -> list[str]:
    """Mely termékfajtákhoz tartoznak a sorban talált árak."""
    alap = "Alap" if piac == "Gáz" else "Zsinór"
    egyben = (sor + " " + fejlec).lower()
    van_csucs = any(sz in egyben for sz in CSUCS_SZAVAK)
    van_zsinor = any(sz in egyben for sz in ZSINOR_SZAVAK)
    if piac == "Gáz":
        return ["Alap"] * darab
    if van_csucs and not van_zsinor:
        return ["Csúcs"] * darab
    if van_csucs and van_zsinor:
        return ["Zsinór", "Csúcs"][:darab] + [alap] * max(0, darab - 2)
    if darab >= 2:
        return ["Zsinór", "Csúcs"] + [alap] * (darab - 2)  # a szokásos sorrend
    return [alap] * darab


def elemez(szoveg: str, ma: date, jegyzes_nap: date | None = None) -> pd.DataFrame:
    """Árlista szövegéből határidős jegyzések. Minden sorhoz megőrzi az eredeti szövegsort."""
    jegyzes_nap = jegyzes_nap or ma
    nevek = {(k, v): nev for nev, k, v in _termekek(ma)}
    sorok, fejlec = [], ""
    for nyers in szoveg.splitlines():
        sor = re.sub(r"[ \t\u00a0]+", " ", nyers).strip()
        if not sor:
            continue
        talalat = idoszak_felismerese(sor, ma)
        if talalat is None:
            if not arak_a_sorban(sor):
                fejlec = sor[:120]  # feliratsor, például "Base | Peak"
            continue
        idoszak = (talalat[0], talalat[1])
        arak = arak_a_sorban(sor[talalat[2]:])
        if idoszak not in nevek or not arak:
            continue
        piac = _piac(sor, fejlec)
        tipusok = _tipusok(sor, fejlec, len(arak), piac)
        for ar, tipus in zip(arak[:2], tipusok[:2]):
            sorok.append({
                "jegyzes_nap": jegyzes_nap.isoformat(), "piac": piac, "termek": nevek[idoszak],
                "tipus": tipus, "szallitas_kezdete": idoszak[0].isoformat(),
                "szallitas_vege": idoszak[1].isoformat(), "ar": ar, "forras_sor": sor[:120],
            })
    tabla = pd.DataFrame(sorok, columns=OSZLOPOK)
    if tabla.empty:
        return tabla
    tabla = tabla.drop_duplicates(["piac", "termek", "tipus"], keep="first")
    return tabla.sort_values(["piac", "szallitas_kezdete", "tipus"]).reset_index(drop=True)
