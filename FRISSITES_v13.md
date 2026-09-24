# Frissítés v13-ra

Ez a csomag a v12 teljes tartalmát is hozza, tehát ha a v12-t még nem töltötted fel, elég ezt az egyet. Ugyanaz a tároló, ugyanaz a link, új beállítás nem kell.

## Mi az újdonság

**Új fül: Termelés** (ez volt a v12 újdonsága is):

- Számkártyák: mennyi megy most a hálózaton, mennyi a hazai termelés, mennyi a behozatal (mínusz jel = kivitel), az atom, a nap, a szél és a megújuló arány.
- 48 órás rétegzett ábra: miből lett az áram tegnap és ma, negyedóránként, dátummal. A rétegek összege a hazai termelés, a pontozott vonal a fogyasztás; a kettő közötti rés a behozatal.
- **Hogyan hat a napenergia az árra:** minden pont egy nap; az illesztett egyenes alatti mondat megmondja, hány euróval mozdul a napi zsinórár, ha a napenergia részaránya egy százalékponttal nagyobb.
- Megújuló részarány idősora és a napi termelés táblázatban, új munkalapként az Excel letöltésben is.

**A v13 kiegészítése, a beépített teljesítmény:**

- **Mennyit hozott ki a mai nap az erőműparkból?** Forrásonként a mai csúcsteljesítmény a beépített teljesítmény százalékában. Innen látszik, hogy egy derült napon a naperőműpark nagy része megy, borús napon a töredéke.
- **Hogyan nőtt a beépített teljesítmény?** A naperőmű és a szélerőmű beépített teljesítménye évről évre, gigawattban, egy mondattal arról, mit jelent ez a déli órák árára.
- A beépített teljesítmény az utolsó lezárt év adata, ezért az azóta épült erőművek még hiányoznak belőle; emiatt a kihasználtság néha száz százalék fölé megy.

## Teendő

1. Csomagold ki az `energiaar-figyelo-v13.zip` fájlt; a benne lévő mappa neve `energiaar-figyelo-v13`.
2. A tárolóban: **Add file > Upload files**, húzd be a kicsomagolt mappa teljes tartalmát (a mappát ne, csak ami benne van), majd **Commit changes**.
3. A Streamlit oldalán: **Manage app**, három pont, **Reboot app**. Utána a böngészőben **Ctrl + F5**.

Új fájlok a v11-hez képest: `termeles.py`, `tests/test_termeles.py`. Változott: `app.py`, `beallitas.py`, `forrasok.py`, `megfigyeles.py`, `README.md`, `TELEPITES.md`.

## Ellenőrzés

- Az Előzmények fül alján: **v13, 2026-09-24**.
- A fülsorban hatodikként ott a **Termelés**, benne a két új ábra a beépített teljesítményről.
- Az első frissítés után a tárolóban megjelenik a `data/termeles_napi.csv`.

Az első betöltés a Termelés fülön lassabb, mert 120 napnyi előzményt tölt le; utána a tárolóból dolgozik, és csak az új napokat kéri le.
