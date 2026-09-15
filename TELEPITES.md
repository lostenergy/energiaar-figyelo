# Energiaár-figyelő: beüzemelés

Az alkalmazás megnyitáskor kéri le az árakat, és a Frissítés gomb bármikor újra lekéri őket. Nincs benne ütemezett háttérfolyamat, nincs adatbázis.

Két lehetőség van. Az elsővel kapsz egy linket, ami telefonon is működik, és a kollégáknak is megosztható. A második csak a saját gépeden fut.

## A) Webalkalmazás linken, ingyen (kb. 15 perc)

Kétszer kell regisztrálni vagy belépni: a GitHubon tárolod a fájlokat, a Streamlit pedig ebből futtatja az alkalmazást.

**1. Tároló létrehozása**
1. Lépj be a github.com oldalon, vagy regisztrálj ingyenes fiókot.
2. Jobb felül a **+** jelre kattintva válaszd a **New repository** menüt.
3. Név: `energiaar-figyelo`. Láthatóság: **Private**. Kattints a **Create repository** gombra.

**2. Fájlok feltöltése**
1. Csomagold ki a letöltött `energiaar-figyelo.zip` fájlt.
2. A tároló oldalán kattints az **uploading an existing file** hivatkozásra.
3. Nyisd meg a kicsomagolt `energiaar-figyelo` mappát, jelöld ki a **teljes tartalmát**, és húzd a böngészőablakba. Magát a mappát ne húzd be, csak a benne lévő fájlokat és mappákat.
4. Kattints a **Commit changes** gombra.

A `.streamlit` mappa neve ponttal kezdődik, ezért Macen alapból rejtett. Finderben a **Cmd + Shift + pont** megjeleníti. Ha kimaradna, az alkalmazás akkor is működik, csak a színei lesznek mások.

**3. Indítás**
1. Nyisd meg a share.streamlit.io oldalt, és lépj be a GitHub-fiókoddal (**Continue with GitHub**).
2. Engedélyezd, hogy a Streamlit hozzáférjen a privát tárolóidhoz.
3. Kattints a **Create app** gombra, és válaszd a GitHubon lévő meglévő alkalmazás telepítését.
4. Töltsd ki: tároló `felhasznaloneved/energiaar-figyelo`, ág `main`, fő fájl `app.py`. Az App URL mezőben megadhatsz rövid, megjegyezhető címet.
5. Kattints a **Deploy** gombra. Az első indítás 2-3 perc.

**Megosztás:** az alkalmazásban jobb felül **Share**, majd add meg a kollégák e-mail-címét. Meghívót kapnak, és Google-fiókkal vagy e-mailben kapott belépési linkkel nyithatják meg.

**Telefonon, mint egy app:** nyisd meg a linket, Androidon a Chrome menüjében válaszd a **Hozzáadás a kezdőképernyőhöz**, iPhone-on Safariban a **Megosztás > Főképernyőhöz adás** lehetőséget.

A tároló maradjon privát: a CEEGEX árai csak belső használatra valók.

## B) Csak a saját gépeden

Telepítsd a Pythont (python.org, 3.11 vagy újabb), majd a kicsomagolt mappában parancssorból:

```
pip install -r requirements.txt
streamlit run app.py
```

A böngésző magától megnyílik. Ilyenkor nincs link, amit meg lehetne osztani, és minden indításnál futnia kell a parancsnak.

## Adatok megőrzése (ajánlott, egyszeri beállítás)

A Streamlit gépe időnként újraindul, és olyankor törli, amit oda mentettünk. Tartós tároláshoz az alkalmazásnak vissza kell írnia az adatokat a GitHub-tárolóba. Ehhez egy hozzáférési kulcs kell.

**1. Kulcs kiállítása a GitHubon**
1. Nyisd meg: `github.com/settings/personal-access-tokens`
2. **Generate new token** (Fine-grained token).
3. Név: `energiaar-figyelo`. Lejárat: válassz hosszabbat, például egy évet; a lejárat után újat kell kiállítani.
4. *Repository access*: **Only select repositories**, és válaszd ki az `energiaar-figyelo` tárolót.
5. *Permissions* alatt a **Repository permissions > Contents** sort állítsd **Read and write** értékre.
6. **Generate token**, majd másold ki a megjelenő kulcsot. Csak egyszer látod.

**2. Kulcs megadása a Streamlitnek**
1. A Streamlit oldalán nyisd meg az alkalmazást, jobb alul **Manage app**, majd a három pont menüben **Settings > Secrets**.
2. Illeszd be ezt, a kulcsot és a tároló nevét kicserélve:

```toml
[github]
token = "ide_jon_a_kimasolt_kulcs"
repo = "lostenergy/energiaar-figyelo"
branch = "main"
```

3. **Save**. Az alkalmazás újraindul.

Innentől a fejlécben megjelenik, hogy mentve a tárolóba, és a `data` mappában gyűlnek az adatok. A kulcs a Secrets-ben marad, a tárolóba soha nem kerül bele.

**Mit tárol.** A napi villamos összesítést korlátlan ideig, a részletes negyedórás árakat az utolsó 150 napra, a gázárakat teljes egészében, valamint a beírt határidős jegyzéseket. Így az időszaki átlagok évekre visszamenőleg pontosak lesznek, az alkalmazás pedig gyorsabban indul, mert nem kell mindig egy évet újra letöltenie.

Kulcs nélkül minden ugyanúgy működik, csak minden megnyitáskor újra letölti az adatokat, és nem őriz meg semmit.

## Határidős árak megadása

A hosszabb szállítási időszakok (hét, hónap, negyedév, félév, szezon, gázév, naptári év) árait a tőzsdék nem adják ki ingyen, gépi lekérésre alkalmas formában. A HUDEX 2025 októberében megszűnt, az EEX pedig előfizetéshez köti az adatait. A legegyszerűbb, ha a saját energiakereskedődtől kérsz napi árlistát; ügyfeleknek ezt általában díjmentesen küldik.

A **Határidős árak** fülön az alkalmazás felkínálja a piacon szokásos termékek listáját a mai naptól előre, neked csak az árat kell beírni azokhoz, amelyekre kaptál jegyzést. Utána látod az árgörbét, és azt, hogy az egyes termékek mennyivel drágábbak vagy olcsóbbak a mai azonnali árnál és az elmúlt hónap átlagánál.

**Beolvasás e-mailből.** A panelen belül van egy „Ajánlat beolvasása e-mailből" gomb. Ide feltöltheted a kereskedő levelét (msg, eml, txt, html vagy csv), vagy egyszerűen bemásolhatod a szövegét. A beolvasó felismeri a szokásos jelöléseket, megkeresi mellettük az árat, kiolvassa a levélből a jegyzés napját, és megmutatja, melyik sorból mit olvasott ki. Csak akkor kerül a táblázatba, ha az „Átvétel a táblázatba" gombra kattintasz.

Az Outlookból a legegyszerűbb a levelet az asztalra húzni, így msg fájl lesz belőle, és azt feltölteni. Alternatíva: jelöld ki az ártáblázatot a levélben, és másold be a szövegmezőbe.

Felismert jelölések: `M10-2026`, `Q4-2026`, `YR-2027`, `Cal-27`, `Q1/27`, `Okt-26`, `Dec 2026`, `2027. IV. negyedév`, `2026. november`, `W40`, `38. hét`, téli és nyári szezon. A zsinór és a csúcs megkülönböztetése a `BL`, `PL`, `base`, `peak`, `zsinór`, `csúcs` szavakból történik, a gázt a `gas`, `gáz`, `CEGH`, `TTF` szavak jelzik.

**Megőrzés.** A beírt árak az oldal bezárásáig élnek. Ha meg akarod tartani őket:
1. A fülön kattints a **hataridos.csv letöltése** gombra.
2. Töltsd fel a fájlt a GitHub-tárolóba (**Add file > Upload files**), `hataridos.csv` néven, a tároló gyökerébe.
3. Az alkalmazás innentől minden induláskor beolvassa. Legközelebb elég az új napi jegyzéseket beírni, letölteni, és a fájlt felülírni.

Így hetek alatt összegyűlik az árgörbe története is: az alkalmazás megmutatja, hogyan mozgott például a 2027-es éves termék ára az elmúlt jegyzési napokon.

## Napi használat

Nyisd meg az alkalmazást, és nézd meg a számokat. Ha közben új ár jelent meg, nyomd meg a **Frissítés** gombot.

Öt fül van: **Villamos energia** (mai és holnapi nap egy folyamatos, 48 órás görbén, számkártyákkal és időszaki átlagokkal), **Földgáz**, **Határidős árak**, **Piaci kép** (számokban összefoglalt helyzetkép és ingyenes elemzési források), valamint **Előzmények** és letöltés.

- A holnapi villamos ár általában **13 óra körül** jelenik meg. Előtte a mai nap görbéje látszik.
- A CEEGEX másnapi gázára a kereskedési nap folyamán alakul ki, a **CEEREP** index 17:30 után kerül ki.
- Az első betöltés lassabb, mert egyéves villamos előzményt tölt be. Utána gyors.
- Az **Előzmények** fülön letöltheted Excelben a most látott adatokat, a beírt határidős jegyzésekkel együtt.

**Alvó állapot (csak az A változatnál).** Ha 12 órán át senki nem nyitja meg, a Streamlit elaltatja az alkalmazást. Ilyenkor egy felébresztő gomb jelenik meg, és fél-egy perc múlva betölt. Adat nem vész el, mert minden lekérés élőben történik.

**Gázár-előzmény.** A villamos árak egy évre visszamenőleg elérhetők a forrásból. A CEEGEX viszont csak annyi kereskedési napot tesz közzé, amennyi az oldalán éppen szerepel, jellemzően néhány hónapot. Ha hosszabb gázár-sor kell, töltsd le időnként az Excelt.

## Beállítások

A `beallitas.py` fájlban módosítható a csúcsidő (alapból 8 és 20 óra között) és az előzmény hossza (`ELOZMENY_NAP`). GitHubon a fájlra kattintva a ceruza ikonnal szerkeszthető, mentés után az alkalmazás magától újraindul.

**Adathasználat.** Energy-Charts (Fraunhofer ISE, CC BY 4.0 licenc) és CEEGEX. A CEEGEX árai belső számításra szabadon használhatók, továbbadásuk vagy közzétételük külön szerződéshez kötött.

## Informatikusoknak

`forrasok.py` a lekérés és a HTML-feldolgozás, `szamitas.py` az időarányosan súlyozott napi és időszaki átlagok, `app.py` a felület. Állapot nincs, minden lekérés a Streamlit gyorsítótárán keresztül megy: az előzmény 6 óráig, a friss adat 15 percig él, a Frissítés gomb pedig üríti. Tesztek: `python -m pytest -q`, lefedik az óraátállítás napjait, a régi órás és az új negyedórás felbontást, valamint a CEEGEX oldalszerkezetét.
