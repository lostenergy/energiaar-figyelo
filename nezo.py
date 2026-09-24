"""Nézegethető változat: ugyanaz az alkalmazás, szerkesztés és mentés nélkül.

Ez a fájl csak elindítja az app.py-t úgy, hogy az nézegethető módba kapcsoljon. Ilyenkor
nincs Frissítés gomb, nincs e-mail feltöltés, nincs árbeírás, és semmi nem íródik vissza
a tárolóba. Az árak ettől még élők: a program magától lekéri őket, és a tárolóból
beolvassa a korábban összegyűlt előzményt.

Telepítés: a Streamlit oldalán egy második alkalmazást kell létrehozni ugyanabból a
tárolóból, főfájlnak a nezo.py-t megadva. A beállításai (Secrets) között csak ennyi
legyen, hozzáférési kulcs nélkül:

    [github]
    repo = "felhasznalo/energiaar-figyelo"
    branch = "main"

Kulcs nélkül a program fizikailag sem tud írni a tárolóba, csak olvasni belőle.
"""

import os
import runpy
from pathlib import Path

os.environ["EAR_NEZO"] = "1"

runpy.run_path(str(Path(__file__).with_name("app.py")), run_name="__main__")
