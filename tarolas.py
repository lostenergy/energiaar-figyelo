"""Adatok megőrzése a GitHub-tárolóban.

A Streamlit gépe időnként újraindul, és olyankor törli a helyben mentett fájlokat, ezért az
adatokat vissza kell írni a GitHubra. Ehhez egy hozzáférési kulcs kell a beállításokban:

    [github]
    token = "..."
    repo = "felhasznalo/energiaar-figyelo"
    branch = "main"

Kulcs nélkül az alkalmazás ugyanúgy működik, csak nem őriz meg semmit.
"""

from __future__ import annotations

import base64

import pandas as pd
import requests

API = "https://api.github.com/repos/{repo}/contents/{utvonal}"
# Nyilvános tárolónál a fájlok kulcs nélkül is olvashatók; a nézegethető változat így dolgozik.
NYERS = "https://raw.githubusercontent.com/{repo}/{ag}/{utvonal}"
IDOKORLAT = 20


class TarolasHiba(Exception):
    """A GitHub-tárolóval kapcsolatos hiba, érthető üzenettel."""


class Tarolo:
    """Fájlok olvasása és írása a GitHub-tárolóban. Beállítás nélkül csendben tétlen marad."""

    def __init__(self, beallitasok: dict | None):
        b = beallitasok or {}
        self.token = str(b.get("token") or "").strip()
        self.repo = str(b.get("repo") or "").strip()
        self.ag = str(b.get("branch") or "main").strip()
        # Írni csak kulccsal lehet, olvasni nyilvános tárolóból kulcs nélkül is.
        self.mukodik = bool(self.token and self.repo)
        self.olvashat = bool(self.repo)
        self._sha: dict[str, str] = {}

    @property
    def fejlec(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"}

    def olvas(self, utvonal: str) -> str | None:
        """A fájl tartalma szövegként, vagy None, ha nincs ilyen fájl."""
        if not self.olvashat:
            return None
        if not self.token:
            return self._olvas_nyersen(utvonal)
        cim = API.format(repo=self.repo, utvonal=utvonal)
        try:
            valasz = requests.get(cim, params={"ref": self.ag}, headers=self.fejlec, timeout=IDOKORLAT)
        except requests.RequestException as e:
            raise TarolasHiba(f"A GitHub nem érhető el: {e}") from e
        if valasz.status_code == 404:
            return None
        if valasz.status_code == 401:
            raise TarolasHiba("A GitHub elutasította a hozzáférési kulcsot. Ellenőrizd vagy állíts ki újat.")
        if valasz.status_code != 200:
            raise TarolasHiba(f"GitHub HTTP {valasz.status_code} ({utvonal})")
        adat = valasz.json()
        self._sha[utvonal] = adat.get("sha", "")
        return base64.b64decode(adat.get("content", "")).decode("utf-8")

    def _olvas_nyersen(self, utvonal: str) -> str | None:
        """Olvasás hozzáférési kulcs nélkül, nyilvános tárolóból."""
        cim = NYERS.format(repo=self.repo, ag=self.ag, utvonal=utvonal)
        try:
            valasz = requests.get(cim, timeout=IDOKORLAT)
        except requests.RequestException as e:
            raise TarolasHiba(f"A GitHub nem érhető el: {e}") from e
        if valasz.status_code == 404:
            return None
        if valasz.status_code != 200:
            raise TarolasHiba(f"GitHub HTTP {valasz.status_code} ({utvonal})")
        return valasz.text

    def ir(self, utvonal: str, tartalom: str, uzenet: str) -> bool:
        """Fájl írása vagy felülírása. True, ha történt írás; False, ha nincs beállítva tároló."""
        if not self.mukodik:
            return False
        cim = API.format(repo=self.repo, utvonal=utvonal)
        csomag = {"message": uzenet, "branch": self.ag,
                  "content": base64.b64encode(tartalom.encode("utf-8")).decode("ascii")}
        if self._sha.get(utvonal):
            csomag["sha"] = self._sha[utvonal]
        try:
            valasz = requests.put(cim, json=csomag, headers=self.fejlec, timeout=IDOKORLAT)
        except requests.RequestException as e:
            raise TarolasHiba(f"A GitHub nem érhető el: {e}") from e
        if valasz.status_code in (409, 422) and "sha" in csomag:
            # Közben más is írt a fájlba: újraolvassuk, és egyszer újrapróbáljuk.
            self.olvas(utvonal)
            csomag["sha"] = self._sha.get(utvonal, "")
            valasz = requests.put(cim, json=csomag, headers=self.fejlec, timeout=IDOKORLAT)
        if valasz.status_code not in (200, 201):
            reszlet = valasz.json().get("message", "") if valasz.content else ""
            raise TarolasHiba(f"Mentés nem sikerült ({valasz.status_code}): {reszlet}")
        self._sha[utvonal] = valasz.json().get("content", {}).get("sha", "")
        return True


def tabla_szovegge(tabla: pd.DataFrame) -> str:
    return tabla.to_csv(index=False, lineterminator="\n")


def szoveg_tablava(szoveg: str | None, oszlopok: list[str]) -> pd.DataFrame:
    if not szoveg or not szoveg.strip():
        return pd.DataFrame(columns=oszlopok)
    from io import StringIO
    try:
        tabla = pd.read_csv(StringIO(szoveg))
    except Exception:
        return pd.DataFrame(columns=oszlopok)
    for o in oszlopok:
        if o not in tabla.columns:
            tabla[o] = None
    return tabla[oszlopok]


def valtozott(regi_szoveg: str | None, uj_szoveg: str) -> bool:
    return (regi_szoveg or "") != uj_szoveg
