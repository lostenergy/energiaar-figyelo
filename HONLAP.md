# Saját weboldal, jelszavas belépéssel

Ez a leírás arról szól, hogyan lesz a tárolóban lévő két lapból saját doménen futó weboldal,
amelynek a nyitólapja nyilvános, az árak pedig belépés mögött vannak.

## Mi készült el

| Fájl | Mi ez |
| --- | --- |
| `docs/index.html` | Nyilvános nyitólap: fejléc, mit mutat az oldal, mire jó és mire nem, Belépés gomb |
| `docs/adatok/index.html` | A belépés mögötti lap, benne keretben az alkalmazás |
| `docs/adatok/beallitas.js` | Itt kell megadni az alkalmazás címét (egy sor) |
| `docs/stilus.css` | Az arculat, mindkét laphoz |

A beállítófájl szándékosan a védett mappában van, így a belépés nélkül érkező látogató az
alkalmazás címét sem látja.

## Mibe kerül

- **Domén:** magyar `.hu` név körülbelül 4000-6000 forint évente, `.com` vagy `.eu` körülbelül
  15 euró évente. Ha van céges domén, elég egy aldomén (például `energia.cegnev.hu`), az ingyen van.
- **Tárhely:** nulla. A Cloudflare Pages ingyenes csomagja bőven elég egy ilyen oldalhoz.
- **Belépés:** nulla, ötven felhasználóig. A Cloudflare Access ingyenes csomagja ennyit tud.

## 1. Domén

A `.hu` neveket csak magyar regisztrátornál lehet megvenni (például Rackhost, Nethely,
Domain-Regisztráció). A `.com` és `.eu` bárhol megvehető. Ha a cégnek már van doménje, a
leggyorsabb út egy aldomén, amit a cég rendszergazdája állít be; ehhez nem kell új előfizetés.

## 2. A domén bekötése a Cloudflare-hez

1. Regisztrálj a `dash.cloudflare.com` oldalon, majd **Add a domain**, és válaszd az ingyenes
   csomagot.
2. A Cloudflare ad két névszervert. Ezeket kell beírni a regisztrátornál a domén beállításai közé.
   Néhány óra, mire átáll.
3. Aldomén esetén nem kell az egész domént átvinni, de a belépésvédelemhez a domént a
   Cloudflare-nek kell kezelnie, ezért ezt előbb egyeztesd a rendszergazdával.

## 3. Az oldal közzététele (Cloudflare Pages)

1. A Cloudflare felületén: **Workers & Pages**, majd **Create**, azon belül **Pages**, és
   **Connect to Git**.
2. Engedélyezd a GitHub-tárolót, és válaszd ki az `energiaar-figyelo` tárolót.
3. A beállításoknál: **Framework preset** = None, **Build command** = üres,
   **Build output directory** = `docs`.
4. **Save and Deploy**. Egy perc múlva él egy ideiglenes cím.
5. A projekt **Custom domains** fülén add hozzá a saját címedet (például `energia.cegnev.hu`).

Innentől minden, amit a tárolóba feltöltesz, egy percen belül megjelenik az oldalon is.

## 4. A belépés bekapcsolása (Cloudflare Access)

1. A Cloudflare felületén: **Zero Trust**, majd **Access > Applications**, és **Add an application**.
2. Típus: **Self-hosted**.
3. Név: Energiaár-figyelő. A **Domain** mezőbe a saját címed, a **Path** mezőbe: `adatok`.
   Így a nyitólap nyilvános marad, és csak az árak kerülnek védelem alá.
4. A szabálynál (**Policy**): Action = **Allow**, Include = **Emails** és felsorolod, ki léphet be,
   vagy **Emails ending in** és megadod a céges végződést, például `@cpifm.hu`.
5. Belépési mód (**Login methods**): **One-time PIN**. Ilyenkor a belépő beírja az e-mail címét,
   kap egy egyszeri kódot, és azzal jut be. Nem kell jelszavakat kiosztani és cserélgetni.
6. **Save**.

Próbáld ki egy privát böngészőablakban: a nyitólapnak nyílnia kell, a Belépés gomb után pedig a
Cloudflare belépési oldalának kell jönnie.

## 5. Az alkalmazás címének beírása

A tárolóban nyisd meg a `docs/adatok/beallitas.js` fájlt, kattints a ceruza ikonra, és írd át ezt
az egy sort a nézegethető változat címére:

```js
const ALKALMAZAS = "https://open-energia.streamlit.app";
```

**Commit changes**, és egy percen belül megjelenik az alkalmazás a védett lapon.

## Mi marad nyilvános

Maga a Streamlit-alkalmazás a saját címén elérhető marad, és a beágyazáshoz ez kell is. A védett
oldalról ez a cím nem szivárog ki, mert a beállítófájl is a belépés mögött van, de aki más úton
megszerzi, az belépés nélkül is megnyitja.

Ha ez nem elfogadható, két út van:

- **A Streamlit-alkalmazás privát telepítése.** A Streamlit beállításaiban felsorolható, ki nézheti
  meg. Ilyenkor a beágyazás nem működik, a weboldalon csak a "Külön ablakban" gomb marad használható.
- **Minden saját kiszolgálóra.** Egy kis bérelt gépen (körülbelül 4-6 euró havonta) az oldal és az
  alkalmazás is egy címen, egy belépés mögött fut. Ehhez szólj, és összeállítom a csomagot.

## Ha nem Cloudflare-t választasz

Hagyományos tárhelyszolgáltatónál ugyanez megoldható: a domén és a tárhely egy helyen, az `adatok`
mappára pedig a vezérlőpultban bekapcsolható a jelszavas védelem (cPanelben **Directory Privacy**,
máshol `.htaccess`). Ilyenkor egy közös felhasználónév és jelszó van, nem névre szóló belépés.
Költsége körülbelül havi 1500 forint a doménnel együtt.
