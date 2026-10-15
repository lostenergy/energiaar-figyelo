# Frissítés v19-re

Új adatforrás: a **HUPX Labs**, a magyar áramtőzsde nyilvános adatfelülete. A csomag a korábbi javításokat is tartalmazza, elég ezt az egyet feltölteni.

## Mi az újdonság

**A másnapi ár magától a tőzsdétől jön.** Eddig az Energy-Charts vette át a HUPX árait, és néha csak késő délután. Mostantól a program elsőként a tőzsde saját felületéről kéri le a negyedórás árakat, és csak utána nyúl a másik forráshoz. Ami ebből következik:

- a holnapi ár a közzététel után rögtön megjelenik, nem kell megvárni az átvételt,
- ha az egyik forrás kiesik, a másik viszi tovább; a nyitósáv csak akkor ír „nem elérhető” feliratot, ha mindkettő elérhetetlen,
- a Villamos energia fülön megjelenik a mai tőzsdei forgalom is.

A hosszú, négyszáz napos előzmény továbbra is az Energy-Chartsról jön, mert a tőzsde felülete csak körülbelül két hónapot tart nyilván.

**Új blokk a Termelés fülön: „Mi áll most a hazai erőműparkból?”** A tőzsde közzéteszi a magyar erőművi kieséseket, ezek mostantól itt látszanak:

- három számkártya: mennyi áll nem tervezetten, mennyi tervezetten, és mindez hány bejelentésből,
- táblázat a legnagyobb kiesésekről: melyik egység, kié, tervezett vagy üzemzavar, hány megawatt a beépítettből, és mettől meddig.

A nem tervezett kiesés kerül előre, mert az szokta hirtelen megemelni a másnapi árat. Ez eddig teljesen hiányzott a képből: a Mátra egy blokkjának váratlan leállása például azonnal meglátszik az esti órák árán.

Belépés, kulcs és előfizetés egyikhez sem kell, a felület nyilvános.

## Teendő

1. Csomagold ki az `energiaar-figyelo-v19.zip` fájlt.
2. A tárolóban: **Add file > Upload files**, húzd be a mappa teljes tartalmát, majd **Commit changes**.
3. **Manage app**, három pont, **Reboot app**, utána **Ctrl + F5**. Ugyanez a nézegethető változatnál is, ha telepítetted.

Új fájlok: `hupx.py`, `tests/test_hupx.py`. Változott: `app.py`, `beallitas.py`, `README.md`, `TELEPITES.md`.

## Ellenőrzés

- Az Előzmények fül alján: **v19, 2026-10-15**.
- A Villamos energia fülön a 48 órás görbe alatt ott a mai tőzsdei forgalom.
- A Termelés fülön, a 48 órás ábra alatt megjelenik a kiesések blokkja.
