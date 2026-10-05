# Frissítés v18-ra

Két hibajavítás, a 2026. október 5-én tapasztaltak alapján. A csomag a v12-től idáig mindent tartalmaz, tehát elég ezt az egyet feltölteni.

## 1. A Kitekintő fül hibája (ez vitte el az oldalt)

A hírcsatornák eltérő időzónában adják meg a megjelenés idejét: a magyar lapok +0200-t, az angol
nyelvűek GMT-t. Amikor mindkettőből érkezett hír, a program nem tudott velük számolni, és
hibaüzenettel megállt. Mostantól minden időpontot közös időzónára hoz, mielőtt dolgozik velük.

Emellett a Kitekintő fül hibája többé nem állítja meg az egész oldalt: ha a hírek lekérése nem
sikerül, csak ezen a fülön jelenik meg egy üzenet, a többi fül működik tovább.

## 2. A forráskiesés kezelése (ez volt a v17 tartalma)

- **Újrapróbálkozás.** Átmeneti hiba (5xx) vagy megszakadt kapcsolat esetén a lekérés háromszor
  próbálkozik, másfél, majd négy másodperc szünettel.
- **Érthető felirat.** Ha a forrás nem válaszol, a számok helyén „nem elérhető” áll, alatta
  „a forrás most nem válaszol”. A „nincs még” csak akkor jelenik meg, ha valóban nincs még ár.
- **Olvasható hibaüzenet** a kiszolgáló nyers válasza helyett.
- **Az előzmény védelme.** Ha a tároló olvasása nem sikerül, abban a futásban semmit nem ír
  vissza. Azoknál a fájloknál pedig, ahol az adat csak gyarapodhat (napi árak, gáz, termelés,
  napló), kimarad a mentés, ha az új tábla kevesebb sort tartalmazna a tároltnál.

## Teendő

1. Csomagold ki az `energiaar-figyelo-v18.zip` fájlt.
2. A tárolóban: **Add file > Upload files**, húzd be a mappa teljes tartalmát, majd **Commit changes**.
3. **Manage app**, három pont, **Reboot app**, utána **Ctrl + F5**.

Változott: `app.py`, `hirek.py`, `forrasok.py`, `tarolas.py`, `beallitas.py`, `README.md`, a tesztek.

## Ellenőrzés

- Az Előzmények fül alján: **v18, 2026-10-05**.
- A Kitekintő fülön mindhárom szakasz megjelenik, hibaüzenet nélkül.
- A nyitósávban az árak visszatérnek, amint az Energy-Charts újra válaszol; az előzmény napjainak
  száma néhány frissítés után magától visszaáll négyszáz körülire.
