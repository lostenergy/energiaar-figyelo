# Frissítés v16-ra

Ez a csomag a v12-től v16-ig minden korábbit tartalmaz, tehát ha valamelyik kimaradt, elég ez az egy. Ugyanaz a tároló, ugyanaz a link.

## Mi az újdonság

**A Kitekintő fül összegzése magától elkészül.** A v15-ben a hírek gyűjtése már önműködő volt, de a 3-6 mondatos összegzést kézzel kellett megírni, vagy fizetős kulcs kellett hozzá. Mostantól ez sem kell: az összegzés a hírcímekből készül el magától, beállítás és költség nélkül, és a hírekkel együtt frissül.

Mit mond el területenként:

- hány hír kapcsolódik az árakhoz, és milyen témák köré rendeződnek (időjárás, készletek, leállások, geopolitika, szabályozás, megújulók, olaj, földgáz, atomenergia, villamos energia),
- melyik a két leginkább árérzékeny hír, forrással és idővel,
- a címek szóhasználata inkább emelkedő vagy inkább mérséklődő árak felé mutat-e,
- és hogy a részletekért érdemes megnyitni a cikkeket.

Szándékosan óvatosan fogalmaz, mert a hírek címéből dolgozik, nem a cikkek szövegéből.

**A saját szöveg továbbra is lehetséges.** A fül alján az Összegzés panelen beírhatsz sajátot; az egy hétig elsőbbséget élvez, utána visszaáll az önműködő változat, hogy ne maradjon kint elavult szöveg. A mezők az önműködő összegzéssel vannak előre kitöltve, tehát elég átírni, ha akarod.

**Nyelvi modell kulcsa nem kötelező,** csak lehetőség bővebb elemzéshez; a beállítás módja a `TELEPITES.md` Kitekintő szakaszában van.

## Teendő

1. Csomagold ki az `energiaar-figyelo-v16.zip` fájlt; a benne lévő mappa neve `energiaar-figyelo-v16`.
2. A tárolóban: **Add file > Upload files**, húzd be a mappa teljes tartalmát (a mappát ne, csak ami benne van), majd **Commit changes**.
3. A szerkesztői alkalmazásnál: **Manage app**, három pont, **Reboot app**, utána **Ctrl + F5**. Ugyanezt a nézegethető változatnál is, ha már telepítetted.

Változott: `app.py`, `osszegzes.py`, `hirek.py`, `beallitas.py`, `TELEPITES.md`, `README.md`, `tests/test_hirek.py`.

## Ellenőrzés

- Az Előzmények fül alján: **v16, 2026-10-05**.
- A Kitekintő fülön mindhárom szakaszban ott az összegzés, alatta a megjegyzés: „Magától készült a hírcímekből, és a hírekkel együtt frissül.”
