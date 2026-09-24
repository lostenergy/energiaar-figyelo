# Frissítés v14-re

Ez a csomag a v12 és a v13 teljes tartalmát is hozza, tehát ha azokat még nem töltötted fel, elég ez az egy. Ugyanaz a tároló, ugyanaz a link, a meglévő alkalmazásban nem kell semmit átállítani.

## Mi az újdonság

**Megosztható, nézegethető változat** (`nezo.py`). Eddig a megosztott link a szerkesztői alkalmazásra mutatott, ahol a látogató is frissíthetett, feltölthetett ajánlatot és átírhatta a jegyzéseket. Az új változatban:

- nincs Frissítés gomb, helyette a fejlécben a „Magától frissül” felirat,
- nincs e-mail feltöltés és nincs árbeíró táblázat a Határidős árak fülön,
- hozzáférési kulcs nélkül fut, ezért fizikailag sem tud írni a tárolóba, csak olvasni belőle,
- minden más ugyanaz: élő árak, termelés, lehetőségek, előzmények, Excel letöltés.

**A v13 újdonsága** (ha kimaradt): a Termelés fül a beépített teljesítménnyel, a mai kihasználtsággal és a naperőműpark növekedésével. **A v12 újdonsága:** maga a Termelés fül.

## Teendő

1. Csomagold ki az `energiaar-figyelo-v14.zip` fájlt; a benne lévő mappa neve `energiaar-figyelo-v14`.
2. A tárolóban: **Add file > Upload files**, húzd be a mappa teljes tartalmát (a mappát ne, csak ami benne van), majd **Commit changes**.
3. A meglévő alkalmazásnál: **Manage app**, három pont, **Reboot app**, utána **Ctrl + F5**.

## A nézegethető változat beüzemelése

1. A share.streamlit.io oldalon: **Create app**, majd **Deploy a public app from GitHub**.
2. Ugyanaz a tároló és ág, mint eddig. A **Main file path** mezőbe: `nezo.py`.
3. Az **App URL** mezőben adj neki saját aldomaint, például `cpifm-energia`.
4. Az **Advanced settings > Secrets** mezőbe **csak ennyi** kerüljön, hozzáférési kulcs nélkül:

   ```toml
   [github]
   repo = "a-te-felhasznalod/energiaar-figyelo"
   branch = "main"
   ```

   A tároló nevét másold ki a szerkesztői alkalmazás beállításaiból; a `token` sort itt ne add meg, éppen az a lényeg, hogy ne legyen.

5. **Deploy**. Ezt a címet oszd meg, a szerkesztői cím marad neked.

Ha weblapba is be akarod ágyazni, a cím végére `?embed=true` írandó; a pontos kód a `TELEPITES.md` végén van.

## Ellenőrzés

- A szerkesztői változat alján: **v14, 2026-09-24**.
- A nézegethető változat alján: **v14, 2026-09-24, nézegethető változat**, a fejlécben „Magától frissül”, a Határidős árak fülön pedig a beírás helyett egy rövid megjegyzés.
- Amit a szerkesztői változatban rögzítesz, néhány percen belül a nézegethetőben is megjelenik.

## Amit érdemes szem előtt tartani

A nyilvános telepítést bárki megnyitja, akinek megvan a link. A CEEGEX gázárai és a kereskedői ajánlatok nem tehetők közzé, ezért ezt a címet a cégen belül érdemes tartani. Ha ennél szorosabb védelem kell, privát alkalmazásként is telepíthető, és a Streamlit beállításaiban e-mail címmel sorolható fel, ki nézheti meg.
