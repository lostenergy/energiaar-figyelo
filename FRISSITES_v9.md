# Frissítés v9-re

Ugyanaz a tároló, ugyanaz az alkalmazás, ugyanaz a link. Csak fájlokat kell cserélni, új beállítás nem kell.

## Mi változott

- **Nem csúsznak egymásra a feliratok.** A fejléc, az állapotsor és a Frissítés gomb külön sorban van, a 48 órás görbén a jelmagyarázat nem takarja a dátumokat.
- **Sötét nyitósáv** a legfontosabb számokkal: most, ma, holnap, gáz, euróban és forintban (Ft/kWh).
- **Színes órás csík:** mikor érdemes áramot használni holnap, a nap nyolc legolcsóbb és nyolc legdrágább órájával.
- **Új Lehetőségek fül** (a korábbi Piaci kép helyett): mit tartogat a piac, milyen szerződés lenne jó áramra és gázra, és mi áll hozzá a legközelebb a piacon.
- **Megfigyelési napló:** minden frissítés feljegyzi, mi volt új, és a fül alján összegzi, mit tanult.
- **A határidős ábra** termékenként vízszintes szakaszokkal mutatja, melyik időszakra mennyit áraz a piac.
- A dátumok a grafikonokon magyar számformátumban jelennek meg.

## Teendő

1. Csomagold ki az `energiaar-figyelo-v9.zip` fájlt.
2. A tárolóban: **Add file > Upload files**, húzd be a kicsomagolt mappa teljes tartalmát, majd **Commit changes**.
3. A Streamlit oldalán: **Manage app**, három pont, **Reboot app**. Utána a böngészőben **Ctrl + F5**.

Új fájlok, amelyeknek meg kell jelenniük a tárolóban: `lehetosegek.py`, `megfigyeles.py` és a `tests` mappában a `test_lehetosegek.py`. Változott: `app.py`, `beallitas.py`, `forrasok.py`, `README.md`, `TELEPITES.md`.

## Ellenőrzés

- Az Előzmények fül alján: **v9, 2026-09-20**.
- Fent sötét sáv, benne a Frissítés gomb aranyszínű.
- Az első frissítés után a tárolóban megjelenik a `data/megfigyelesek.csv`.

A napló az első napokban még kevés tanulságot ad; a holnapi ár érkezési idejéhez például olyan napok kellenek, amikor 11 óra után, de még az ár megjelenése előtt is megnyitottad az oldalt.
