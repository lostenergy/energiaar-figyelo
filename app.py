"""Magyar energiaárak: webes árpult.

Az azonnali árakat megnyitáskor és a Frissítés gombra kéri le. Ha be van állítva GitHub-tároló,
a leszedett adatokat megőrzi, így az előzmény napról napra gyűlik.

Indítás saját gépen: streamlit run app.py
"""

from __future__ import annotations

import io
from datetime import date, timedelta
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import beallitas as B
import elemzes as E
import forrasok as F
import hataridos as H
import szamitas as S
import tarolas as T

SZ = B.SZIN
HONAPOK = ["január", "február", "március", "április", "május", "június", "július",
           "augusztus", "szeptember", "október", "november", "december"]
NAPOK = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]

st.set_page_config(page_title="Energiaárak", page_icon="⚡", layout="wide")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&display=swap');
html, body, .stApp, .stMarkdown, p, h1, h2, h3, li, label, button, td, th, input,
[data-baseweb="tab"], [data-testid="stCaptionContainer"] {{
  font-family: 'Archivo', system-ui, sans-serif;
}}
.block-container {{ max-width: 1180px; padding-top: 1.4rem; padding-bottom: 3rem; }}
h2, h3 {{ color: {SZ['tinta']}; font-weight: 600; letter-spacing: -0.01em; }}
h3 {{ font-size: 1.02rem !important; margin: 1.2rem 0 0.2rem 0 !important; padding: 0 !important; }}
.ear-cim {{ font-size: 1rem; font-weight: 600; color: {SZ['tinta']}; margin: 0; }}
.ear-frissites {{ font-size: 0.78rem; color: {SZ['acel']}; margin: 0.1rem 0 0 0; }}
.ear-vezeto {{
  font-size: 1.02rem; font-weight: 500; color: {SZ['tinta']}; margin: 0.2rem 0 0.7rem 0;
  max-width: 78ch; line-height: 1.45; font-variant-numeric: tabular-nums;
}}
.ear-megj {{ font-size: 0.78rem; color: {SZ['acel']}; max-width: 80ch; margin: 0.2rem 0 0.6rem 0; }}

/* Számkártyák rácsa: sok adat kevés helyen */
.ear-racs {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(128px, 1fr)); gap: 0.4rem; margin: 0.3rem 0 0.9rem 0; }}
.ear-kartya {{ background: {SZ['kod']}; border-radius: 6px; padding: 0.5rem 0.6rem; }}
.ear-kartya .cimke {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em; color: {SZ['acel']}; display: block; }}
.ear-kartya .ertek {{ font-size: 1.22rem; font-weight: 600; color: {SZ['tinta']}; font-variant-numeric: tabular-nums; line-height: 1.25; }}
.ear-kartya .alsó {{ font-size: 0.72rem; color: {SZ['acel']}; font-variant-numeric: tabular-nums; }}

table.ear-tabla {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; margin: 0.2rem 0 1rem 0; }}
table.ear-tabla th {{
  text-align: right; font-weight: 500; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;
  color: {SZ['acel']}; padding: 0.2rem 0.4rem; border-bottom: 1px solid {SZ['tinta']};
}}
table.ear-tabla th:first-child, table.ear-tabla td:first-child {{ text-align: left; padding-left: 0; }}
table.ear-tabla td {{
  text-align: right; padding: 0.3rem 0.4rem; border-bottom: 1px solid {SZ['vonal']};
  color: {SZ['tinta']}; font-size: 0.88rem;
}}
table.ear-tabla tr:hover td {{ background: {SZ['kod']}; }}
table.ear-tabla td.ear-kiemelt {{ font-weight: 600; }}
table.ear-tabla td small, table.ear-tabla td .halvany {{ color: {SZ['acel']}; font-size: 0.74rem; }}
.ear-fel {{ color: {SZ['emelkedes']}; font-weight: 600; }}
.ear-le {{ color: {SZ['csokkenes']}; font-weight: 600; }}
[data-baseweb="tab-list"] {{ gap: 1.1rem; }}
[data-baseweb="tab"] p {{ font-size: 0.92rem; }}
[data-testid="stExpander"] summary p {{ font-size: 0.88rem; }}
div[data-testid="stVerticalBlock"] {{ gap: 0.4rem; }}
@media (max-width: 640px) {{
  .block-container {{ padding-left: 0.8rem; padding-right: 0.8rem; }}
  .ear-racs {{ grid-template-columns: repeat(auto-fit, minmax(104px, 1fr)); }}
  .ear-kartya .ertek {{ font-size: 1.05rem; }}
  table.ear-tabla td {{ font-size: 0.8rem; padding-left: 0.2rem; padding-right: 0.2rem; }}
}}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ formázás

def hu(x, tizedes: int = 2, ha_nincs: str = "nincs adat") -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)) or (not isinstance(x, (int, float, str)) and pd.isna(x)):
        return ha_nincs
    return f"{float(x):,.{tizedes}f}".replace(",", "\u202f").replace(".", ",")


def hu_szazalek(v: float | None, jel: bool = True) -> str:
    if v is None or pd.isna(v):
        return ""
    return (f"{v * 100:+.1f}%" if jel else f"{abs(v) * 100:.1f}%").replace(".", ",")


def valtozas_cella(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "<td></td>"
    osztaly = "ear-fel" if v > 0.0005 else "ear-le" if v < -0.0005 else ""
    return f'<td class="{osztaly}">{hu_szazalek(v)}</td>'


def valtozas_jel(v: float | None) -> str:
    if v is None or pd.isna(v):
        return ""
    osztaly = "ear-fel" if v > 0.0005 else "ear-le" if v < -0.0005 else ""
    return f'<span class="{osztaly}">{hu_szazalek(v)}</span>'


def hu_datum(d, hetnap: bool = True) -> str:
    d = pd.Timestamp(d)
    alap = f"{HONAPOK[d.month - 1]} {d.day}."
    return f"{alap}, {NAPOK[d.weekday()]}" if hetnap else alap


def hu_rovid(d) -> str:
    d = pd.Timestamp(d)
    return f"{HONAPOK[d.month - 1][:3]}. {d.day}."


def kartyak(tetelek: list[tuple[str, str, str]]) -> None:
    """Számkártyák rácsa: (cimke, fő érték, alsó sor)."""
    darabok = "".join(
        f'<div class="ear-kartya"><span class="cimke">{escape(c)}</span>'
        f'<div class="ertek">{e}</div><div class="alsó">{a}</div></div>'
        for c, e, a in tetelek)
    st.markdown(f'<div class="ear-racs">{darabok}</div>', unsafe_allow_html=True)


def tabla_html(fejlec: list[str], sorok: list[str]) -> str:
    th = "".join(f"<th>{escape(h)}</th>" for h in fejlec)
    return f'<table class="ear-tabla"><thead><tr>{th}</tr></thead><tbody>{"".join(sorok)}</tbody></table>'


def abra_alap(fig: go.Figure, magassag: int = 300) -> go.Figure:
    fig.update_layout(
        height=magassag, margin=dict(l=0, r=6, t=6, b=0), separators=", ",
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Archivo, system-ui, sans-serif", color=SZ["tinta"], size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None,
                    font=dict(size=11)),
        hovermode="x unified", hoverlabel=dict(bgcolor="white", font_color=SZ["tinta"]),
    )
    fig.update_xaxes(showgrid=False, linecolor=SZ["vonal"], ticks="outside", tickcolor=SZ["vonal"])
    fig.update_yaxes(gridcolor=SZ["kod"], zeroline=True, zerolinecolor=SZ["vonal"], ticksuffix=" ")
    return fig


def mutat(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "locale": "hu"})


# ------------------------------------------------------------------ tároló

TAROLT = {"napi": "data/villamos_napi.csv", "negyedora": "data/villamos_15perc.csv",
          "gaz": "data/gaz_masnapi.csv", "gaz_wd": "data/gaz_napon_belul.csv",
          "hataridos": "hataridos.csv"}
NEGYEDORA_MEGORZES = 150  # ennyi napnyi negyedórás árat őrzünk meg részletesen


@st.cache_resource(show_spinner=False)
def tarolo() -> T.Tarolo:
    try:
        beallitas = dict(st.secrets.get("github", {}))
    except Exception:
        beallitas = {}
    return T.Tarolo(beallitas)


@st.cache_data(ttl=300, show_spinner=False)
def tarolt_adatok(_tarolo: T.Tarolo, jel: int) -> dict:
    """A tárolóból beolvasott fájlok nyers szövegként (a mentés összehasonlításához is)."""
    ki, hibak = {}, []
    for kulcs, utvonal in TAROLT.items():
        try:
            ki[kulcs] = _tarolo.olvas(utvonal)
        except T.TarolasHiba as e:
            ki[kulcs] = None
            hibak.append(str(e))
    ki["_hibak"] = hibak
    return ki


# ------------------------------------------------------------------ adatlekérés

@st.cache_data(ttl=B.ELOZMENY_ELTARTHATOSAG, show_spinner=False)
def villamos_elozmeny(vegnap: date, napok: int) -> pd.DataFrame:
    return F.leker_villamos(vegnap - timedelta(days=napok), vegnap)


@st.cache_data(ttl=B.FRISS_ELTARTHATOSAG, show_spinner=False)
def villamos_friss(ma: date) -> pd.DataFrame:
    return F.leker_villamos(ma - timedelta(days=B.FRISS_NAP), ma + timedelta(days=2))


@st.cache_data(ttl=B.FRISS_ELTARTHATOSAG, show_spinner=False)
def gaz_adatok(ma: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    return F.leker_gaz_masnapi(), F.leker_gaz_napon_belul()


def betolt(ma: date, mentett: dict) -> dict:
    """Tárolt és élő adatok összefésülése. Egy forrás hibája nem akadályozza a többit."""
    ki = {"hibak": []}
    tarolt_negyedora = T.szoveg_tablava(mentett.get("negyedora"), F.VILLAMOS_OSZLOPOK)
    tarolt_napi = T.szoveg_tablava(mentett.get("napi"), S.NAPI_OSZLOPOK)
    van_elozmeny = not tarolt_napi.empty and tarolt_napi["nap"].max() >= (ma - timedelta(days=5)).isoformat()

    villamos = tarolt_negyedora
    try:
        villamos = F.egyesit([villamos, villamos_friss(ma)], "unix")
        if not van_elozmeny:
            try:
                hosszu = villamos_elozmeny(ma - timedelta(days=B.FRISS_NAP + 1), B.ELOZMENY_NAP)
                villamos = F.egyesit([hosszu, villamos], "unix")
            except Exception as e:
                ki["hibak"].append(f"Villamos előzmény: {e}")
    except Exception as e:
        ki["hibak"].append(f"Energy-Charts: {e}")
    ki["villamos"] = villamos if not villamos.empty else F.ures(F.VILLAMOS_OSZLOPOK)

    szamolt_napi = S.napi_osszesites(ki["villamos"])
    egyutt = pd.concat([t for t in (tarolt_napi, szamolt_napi) if not t.empty], ignore_index=True) \
        if (not tarolt_napi.empty or not szamolt_napi.empty) else pd.DataFrame(columns=S.NAPI_OSZLOPOK)
    if not egyutt.empty:
        egyutt = egyutt.drop_duplicates("nap", keep="last").sort_values("nap").reset_index(drop=True)
        for o in ["zsinor", "csucs", "csucson_kivul", "min_ar", "max_ar", "idoszakok"]:
            egyutt[o] = pd.to_numeric(egyutt[o], errors="coerce")
    ki["napi"] = egyutt

    try:
        gaz, gaz_wd = gaz_adatok(ma)
    except Exception as e:
        ki["hibak"].append(f"CEEGEX: {e}")
        gaz, gaz_wd = None, None
    ki["gaz"] = F.egyesit([T.szoveg_tablava(mentett.get("gaz"), F.GAZ_MASNAPI_OSZLOPOK), gaz], "kulcs")
    ki["gaz_wd"] = F.egyesit([T.szoveg_tablava(mentett.get("gaz_wd"), F.GAZ_NAPON_BELUL_OSZLOPOK),
                              gaz_wd], "kulcs")
    for t, szamok in [(ki["gaz"], ["mennyiseg_mwh", "kotesek", "atlagar", "ceerep", "ceerep_valtozas"]),
                      (ki["gaz_wd"], ["gazora", "mennyiseg_mwh", "atlagar", "valtozas"])]:
        for o in szamok:
            if o in t.columns:
                t[o] = pd.to_numeric(t[o], errors="coerce")
    return ki


def ment_tarolóba(adat: dict, mentett: dict) -> list[str]:
    """A megváltozott táblák visszaírása a GitHub-tárolóba. Visszaadja a mentett fájlok nevét.

    A már elmentett tartalmat a munkamenetben tartjuk számon, így ugyanaz az adat nem íródik
    ki újra és újra, valahányszor a felhasználó kattint egyet.
    """
    t = tarolo()
    if not t.mukodik:
        return []
    utoljara = st.session_state.setdefault("utoljara_mentve", {})
    ma_szoveg = pd.Timestamp.now(tz=B.IDOZONA).strftime("%Y-%m-%d %H:%M")
    hatar = (pd.Timestamp.now(tz=B.IDOZONA).date() - timedelta(days=NEGYEDORA_MEGORZES)).isoformat()
    negyedora = adat["villamos"][adat["villamos"]["nap"] >= hatar] if not adat["villamos"].empty \
        else adat["villamos"]
    tetelek = [("napi", adat["napi"]), ("negyedora", negyedora),
               ("gaz", adat["gaz"]), ("gaz_wd", adat["gaz_wd"])]
    mentve = []
    for kulcs, tabla in tetelek:
        if tabla is None or tabla.empty:
            continue
        szoveg = T.tabla_szovegge(tabla)
        korabbi = utoljara.get(kulcs, mentett.get(kulcs))
        if not T.valtozott(korabbi, szoveg):
            continue
        t.ir(TAROLT[kulcs], szoveg, f"Adatfrissítés {ma_szoveg}")
        utoljara[kulcs] = szoveg
        mentve.append(TAROLT[kulcs])
    return mentve


def mindent_ujra() -> None:
    villamos_friss.clear()
    gaz_adatok.clear()
    tarolt_adatok.clear()


# ------------------------------------------------------------------ fejléc és betöltés

most = pd.Timestamp.now(tz=B.IDOZONA)
ma, holnap = most.date(), most.date() + timedelta(days=1)

fej_bal, fej_jobb = st.columns([5, 1], vertical_alignment="center")
with fej_bal:
    st.markdown('<p class="ear-cim">Magyar energiaárak</p>', unsafe_allow_html=True)
    allapot_hely = st.empty()
with fej_jobb:
    if st.button("Frissítés", width="stretch"):
        mindent_ujra()
        st.rerun()

with st.spinner("Árak lekérése..."):
    mentett = tarolt_adatok(tarolo(), st.session_state.get("tarolo_jel", 0))
    adat = betolt(ma, mentett)

villamos, napi, gaz, gaz_wd = adat["villamos"], adat["napi"], adat["gaz"], adat["gaz_wd"]
hibak = list(dict.fromkeys(list(adat["hibak"]) + list(mentett.get("_hibak", []))))

mentve = []
if tarolo().mukodik and not villamos.empty:
    try:
        mentve = ment_tarolóba(adat, mentett)
    except T.TarolasHiba as e:
        hibak.append(f"Mentés: {e}")

allapot = f"Lekérve {most.strftime('%H:%M')}-kor"
if not napi.empty:
    allapot += f" · {len(napi)} napnyi előzmény"
if mentve:
    allapot += " · mentve a tárolóba"
elif not tarolo().mukodik:
    allapot += " · tároló nincs beállítva"
allapot_hely.markdown(f'<p class="ear-frissites">{allapot}, budapesti idő szerint</p>', unsafe_allow_html=True)

if hibak:
    st.warning("Nem minden lépés sikerült:\n\n" + "\n\n".join(hibak))

napi_terkep = napi.set_index("nap") if not napi.empty else pd.DataFrame(columns=S.NAPI_OSZLOPOK).set_index("nap")


def napi_ertek(nap: date, oszlop: str):
    kulcs = nap.isoformat() if isinstance(nap, date) else str(nap)
    if kulcs in napi_terkep.index and oszlop in napi_terkep.columns:
        ertek = napi_terkep.at[kulcs, oszlop]
        return None if pd.isna(ertek) else ertek
    return None


lap_villamos, lap_gaz, lap_hataridos, lap_piac, lap_elozmeny = st.tabs(
    ["Villamos energia", "Földgáz", "Határidős árak", "Piaci kép", "Előzmények"])


# ------------------------------------------------------------------ villamos

with lap_villamos:
    if villamos.empty:
        st.info("Most nem érkezett villamos ár. Próbáld meg újra a Frissítés gombbal.")
    else:
        van_holnap = napi_ertek(holnap, "zsinor") is not None
        zs_ma, zs_holnap = napi_ertek(ma, "zsinor"), napi_ertek(holnap, "zsinor")
        het = E._atlag(napi, ma, 6)
        honap = E._atlag(napi, ma, 29)

        kartyak([
            ("Ma, zsinór", hu(zs_ma), f"csúcs {hu(napi_ertek(ma, 'csucs'), ha_nincs='')}"),
            ("Holnap, zsinór", hu(zs_holnap, ha_nincs="még nincs"),
             f"ma {valtozas_jel(S.valtozas(zs_holnap, zs_ma))}" if zs_holnap else "13 óra után"),
            ("Holnap, csúcs", hu(napi_ertek(holnap, "csucs"), ha_nincs="-"),
             f"csúcson kívül {hu(napi_ertek(holnap, 'csucson_kivul'), ha_nincs='-')}"),
            ("7 napos átlag", hu(het), f"ma {valtozas_jel(S.valtozas(zs_ma, het))}" if het else ""),
            ("30 napos átlag", hu(honap), f"ma {valtozas_jel(S.valtozas(zs_ma, honap))}" if honap else ""),
            ("Holnap legolcsóbb", hu(napi_ertek(holnap, "min_ar"), ha_nincs="-"),
             str(napi_ertek(holnap, "min_ido") or "")),
            ("Holnap legdrágább", hu(napi_ertek(holnap, "max_ar"), ha_nincs="-"),
             str(napi_ertek(holnap, "max_ido") or "")),
        ])

        # Folyamatos, 48 órás görbe: ma és holnap egy idővonalon, dátumokkal
        ket_nap = villamos[villamos["nap"].isin([ma.isoformat(), holnap.isoformat()])].copy()
        holnapi_negyedorak = int((ket_nap["nap"] == holnap.isoformat()).sum())
        if not ket_nap.empty:
            ket_nap["idopont"] = pd.to_datetime(ket_nap["ido"])
            fig = go.Figure()
            for nap in (ma, holnap):
                fig.add_vrect(x0=f"{nap.isoformat()} {B.CSUCS_KEZDET:02d}:00",
                              x1=f"{nap.isoformat()} {B.CSUCS_VEGE:02d}:00",
                              fillcolor=SZ["sargarez"], opacity=0.08, line_width=0, layer="below")
            for nap, nev, szin in [(ma, "Ma", SZ["acel"]), (holnap, "Holnap", SZ["tinta"])]:
                resz = ket_nap[ket_nap["nap"] == nap.isoformat()]
                if resz.empty:
                    continue
                fig.add_scatter(x=resz["idopont"], y=resz["ar"], name=f"{nev}, {hu_rovid(nap)}",
                                mode="lines", line=dict(color=szin, width=2.2, shape="hv"),
                                hovertemplate="%{x|%m. %d.} %{x|%H:%M} · %{y:.2f} EUR/MWh<extra></extra>")
                # Nap felirata a sáv tetején
                fig.add_annotation(x=pd.Timestamp(f"{nap.isoformat()} 12:00"), y=1.0, yref="paper",
                                   text=f"<b>{hu_datum(nap)}</b>", showarrow=False, yanchor="bottom",
                                   font=dict(size=12, color=szin))
            if honap is not None:
                fig.add_hline(y=float(honap), line=dict(color=SZ["acel"], width=1, dash="dot"),
                              annotation_text="30 napos átlag", annotation_position="bottom left",
                              annotation_font=dict(color=SZ["acel"], size=11))
            if holnapi_negyedorak:
                fig.add_vline(x=pd.Timestamp(f"{holnap.isoformat()} 00:00"),
                              line=dict(color=SZ["vonal"], width=1))
            abra_alap(fig, 350)
            fig.update_layout(margin=dict(l=0, r=6, t=26, b=0))
            fig.update_xaxes(
                tickformat="%H:%M", dtick=3 * 3600 * 1000,
                range=[pd.Timestamp(f"{ma.isoformat()} 00:00"),
                       pd.Timestamp(f"{(holnap + timedelta(days=1)).isoformat()} 00:00")
                       if holnapi_negyedorak else pd.Timestamp(f"{holnap.isoformat()} 00:00")])
            fig.update_yaxes(title=dict(text="EUR/MWh", font=dict(size=11, color=SZ["acel"])))
            mutat(fig)

        if not van_holnap:
            utolso = villamos["ido"].max() if not villamos.empty else ""
            if holnapi_negyedorak:
                st.markdown(f'<p class="ear-megj">A holnapi napra eddig {holnapi_negyedorak} negyedóra '
                            'ára érkezett meg, ezért a napi átlagok még nem készülnek el. A teljes nap '
                            'általában 13 óra után válik elérhetővé; a Frissítés gomb újra lekéri.</p>',
                            unsafe_allow_html=True)
            else:
                st.markdown('<p class="ear-megj">A holnapi ár még nem érhető el a forrásnál. A magyar '
                            'másnapi piac eredménye 13 óra körül születik meg, de az Energy-Charts '
                            'néha csak késő délután veszi át. A legfrissebb ár, amit most kaptunk: '
                            f'{utolso}. Nyomd meg a Frissítés gombot később.</p>', unsafe_allow_html=True)

        bal, jobb = st.columns(2)
        with bal:
            st.subheader("Ma és holnap")
            sorok = []
            for nev, oszlop in [("Zsinór", "zsinor"), (f"Csúcs {B.CSUCS_KEZDET}-{B.CSUCS_VEGE}", "csucs"),
                                ("Csúcson kívüli", "csucson_kivul"), ("Minimum", "min_ar"),
                                ("Maximum", "max_ar")]:
                a, b = napi_ertek(ma, oszlop), napi_ertek(holnap, oszlop)
                kiemelt = ' class="ear-kiemelt"' if oszlop == "zsinor" else ""
                sorok.append(f"<tr><td>{nev}</td><td{kiemelt}>{hu(a, ha_nincs='')}</td>"
                             f"<td{kiemelt}>{hu(b, ha_nincs='')}</td>"
                             f"{valtozas_cella(S.valtozas(b, a))}</tr>")
            st.markdown(tabla_html(["EUR/MWh", hu_rovid(ma), hu_rovid(holnap), "Változás"], sorok),
                        unsafe_allow_html=True)
        with jobb:
            st.subheader("Időszaki átlagok")
            atl = S.idoszaki_atlagok(napi, ma)
            sorok = [f"<tr><td>{r.idoszak}<br><span class='halvany'>{hu_rovid(r.tol)} és "
                     f"{hu_rovid(r.ig)} között</span></td><td>{hu(r.zsinor, ha_nincs='')}</td>"
                     f"<td>{hu(r.csucs, ha_nincs='')}</td><td>{r.napok}</td></tr>"
                     for r in atl.itertuples() if r.napok]
            st.markdown(tabla_html(["EUR/MWh", "Zsinór", "Csúcs", "Nap"], sorok), unsafe_allow_html=True)

        st.subheader("Napi zsinórár alakulása")
        tav = st.segmented_control("Időtáv", ["30 nap", "90 nap", "1 év", "Teljes"], default="90 nap",
                                   required=True, label_visibility="collapsed") or "90 nap"
        napok_szama = {"30 nap": 30, "90 nap": 90, "1 év": 365, "Teljes": 100000}[tav]
        t = napi.copy()
        t["datum"] = pd.to_datetime(t["nap"])
        t["het_atlag"] = t["zsinor"].rolling(7, min_periods=4).mean()
        t = t[t["datum"] >= pd.Timestamp(ma) - pd.Timedelta(days=napok_szama)]
        fig = go.Figure()
        fig.add_scatter(x=t["datum"], y=t["zsinor"], name="Napi zsinór", mode="lines",
                        line=dict(color=SZ["acel"], width=1.1), hovertemplate="%{y:.2f}")
        fig.add_scatter(x=t["datum"], y=t["het_atlag"], name="7 napos átlag", mode="lines",
                        line=dict(color=SZ["tinta"], width=2.2), hovertemplate="%{y:.2f}")
        fig.add_scatter(x=t["datum"], y=t["csucs"], name="Csúcs", mode="lines", visible="legendonly",
                        line=dict(color=SZ["sargarez"], width=1.2), hovertemplate="%{y:.2f}")
        abra_alap(fig, 280)
        mutat(fig)


# ------------------------------------------------------------------ gáz

with lap_gaz:
    kulcsok = S.gaz_kulcsszamok(gaz)
    if kulcsok["da"] is None:
        st.info("Most nem érkezett CEEGEX gázár. Próbáld meg újra a Frissítés gombbal.")
    else:
        da = kulcsok["da"]
        gk = E.gaz_kep(gaz)
        elozo = kulcsok["da_elozo"]["atlagar"] if kulcsok["da_elozo"] else None
        het = kulcsok["da_het"]["atlagar"] if kulcsok["da_het"] else None
        wd_utolso = gaz_wd.sort_values(["gaznap", "gazora"]).iloc[-1] if not gaz_wd.empty else None

        kartyak([
            ("Másnapi ár", hu(da["atlagar"]), f"szállítás {hu_rovid(da['szallitas_kezdete'][:10])}"),
            ("Előző naphoz", valtozas_jel(S.valtozas(da["atlagar"], elozo)) or "-", hu(elozo, ha_nincs="")),
            ("Öt nappal korábbihoz", valtozas_jel(S.valtozas(da["atlagar"], het)) or "-", hu(het, ha_nincs="")),
            ("CEEREP", hu(da.get("ceerep"), ha_nincs="17:30 után"), "elszámolási index"),
            ("30 napos átlag", hu(gk["honap"]), valtozas_jel(gk["honap_valtozas"]) or ""),
            ("Hétvégi termék", hu(kulcsok["hetvege"]["atlagar"] if kulcsok["hetvege"] else None, ha_nincs="-"),
             hu_rovid(kulcsok["hetvege"]["kereskedesi_nap"]) + " kereskedés" if kulcsok["hetvege"] else ""),
            ("Napon belüli", hu(wd_utolso["atlagar"] if wd_utolso is not None else None, ha_nincs="-"),
             f"{int(wd_utolso['gazora'])}. gázóráig" if wd_utolso is not None else ""),
        ])

        bal, jobb = st.columns([3, 2])
        with bal:
            st.subheader("Másnapi ár és CEEREP")
            d = gaz[gaz["termek"] == "DA"].copy()
            d["datum"] = pd.to_datetime(d["kereskedesi_nap"])
            fig = go.Figure()
            fig.add_scatter(x=d["datum"], y=d["atlagar"], name="Másnapi átlagár", mode="lines+markers",
                            line=dict(color=SZ["tinta"], width=2), marker=dict(size=3), connectgaps=True,
                            hovertemplate="%{y:.2f}")
            fig.add_scatter(x=d["datum"], y=d["ceerep"], name="CEEREP", mode="markers",
                            marker=dict(color=SZ["sargarez"], size=5, symbol="diamond"),
                            hovertemplate="%{y:.2f}")
            abra_alap(fig, 280)
            mutat(fig)
        with jobb:
            st.subheader("Napon belüli piac")
            if gaz_wd.empty:
                st.markdown('<p class="ear-megj">Erre a gáznapra még nincs napon belüli kötés.</p>',
                            unsafe_allow_html=True)
            else:
                r = gaz_wd.sort_values("gazora")
                fig = go.Figure()
                fig.add_scatter(x=r["gazora"], y=r["atlagar"], mode="lines+markers",
                                line=dict(color=SZ["tinta"], width=2, shape="hv"), marker=dict(size=4),
                                hovertemplate="%{x}. gázóra: %{y:.2f}<extra></extra>")
                fig.add_hline(y=float(da["atlagar"]), line=dict(color=SZ["acel"], width=1, dash="dot"),
                              annotation_text="másnapi ár", annotation_position="top left",
                              annotation_font=dict(color=SZ["acel"], size=11))
                abra_alap(fig, 280)
                fig.update_layout(hovermode="closest", showlegend=False)
                fig.update_xaxes(range=[0.5, 24.5], dtick=4,
                                 title=dict(text="gázóra", font=dict(size=11, color=SZ["acel"])))
                mutat(fig)
        st.markdown('<p class="ear-megj">A gáznap reggel 6 órától másnap reggel 6 óráig tart. '
                    f'A tárolóban {gk["napok"]} kereskedési nap gyűlt össze, a legalacsonyabb ár '
                    f'{hu(gk["legkisebb"])}, a legmagasabb {hu(gk["legnagyobb"])} EUR/MWh.</p>',
                    unsafe_allow_html=True)


# ------------------------------------------------------------------ határidős árak

def azonnali_arak() -> dict:
    ki = {}
    ki["Villamos|Zsinór"] = napi_ertek(ma, "zsinor")
    ki["Villamos|Csúcs"] = napi_ertek(ma, "csucs")
    ki["Villamos|Zsinór|30"] = E._atlag(napi, ma, 29, oszlop="zsinor")
    ki["Villamos|Csúcs|30"] = E._atlag(napi, ma, 29, oszlop="csucs")
    gk = E.gaz_kep(gaz)
    ki["Gáz|Alap"] = gk["mai"]
    ki["Gáz|Alap|30"] = gk["honap"]
    return ki


with lap_hataridos:
    if "hataridos" not in st.session_state:
        st.session_state.hataridos = H.egyesit(
            H.ures(), T.szoveg_tablava(mentett.get("hataridos"), H.OSZLOPOK))
    tarolt = st.session_state.hataridos

    st.markdown('<p class="ear-vezeto">A heti, havi, negyedéves, féléves és éves jegyzéseket kézzel kell '
                'megadni: a tőzsdék ezeket csak előfizetéssel adják ki gépi lekérésre. A napi árlistát '
                'a legtöbb energiakereskedő díjmentesen küldi az ügyfeleinek.</p>', unsafe_allow_html=True)

    with st.expander("Árak megadása és mentése", expanded=tarolt.empty):
        feltoltott = st.file_uploader("Korábban mentett hataridos.csv betöltése", type="csv")
        if feltoltott is not None:
            st.session_state.hataridos = H.egyesit(st.session_state.hataridos, H.olvas(feltoltott))
            tarolt = st.session_state.hataridos
            st.success(f"{len(tarolt)} jegyzés betöltve.")

        jegyzes_nap = st.date_input("Jegyzés napja", value=ma, max_value=ma, format="YYYY.MM.DD",
                                    key="hataridos_nap")
        alap = H.alap_termekek(jegyzes_nap)
        korabbi = tarolt[tarolt["jegyzes_nap"] == jegyzes_nap.isoformat()]
        if not korabbi.empty:
            alap = pd.concat([korabbi, alap]).drop_duplicates(["piac", "termek", "tipus"], keep="first")
            alap = alap.sort_values(["piac", "szallitas_kezdete", "tipus"]).reset_index(drop=True)

        szerkesztett = st.data_editor(
            alap[["piac", "termek", "tipus", "ar"]],
            column_config={
                "piac": st.column_config.TextColumn("Piac", disabled=True),
                "termek": st.column_config.TextColumn("Termék", disabled=True, width="medium"),
                "tipus": st.column_config.TextColumn("Típus", disabled=True),
                "ar": st.column_config.NumberColumn("Ár (EUR/MWh)", min_value=-500.0, max_value=2000.0,
                                                    step=0.01, format="%.2f"),
            },
            hide_index=True, width="stretch", height=360, key="hataridos_szerkeszto")

        gomb_bal, gomb_jobb = st.columns([1, 3])
        with gomb_bal:
            rogzit = st.button("Rögzítés", type="primary", width="stretch")
        if rogzit:
            uj = alap.copy()
            uj["ar"] = pd.to_numeric(szerkesztett["ar"], errors="coerce").values
            uj["jegyzes_nap"] = jegyzes_nap.isoformat()
            st.session_state.hataridos = H.egyesit(st.session_state.hataridos, uj)
            szoveg = T.tabla_szovegge(st.session_state.hataridos)
            uzenet = f"{int(uj['ar'].notna().sum())} ár rögzítve."
            if tarolo().mukodik:
                try:
                    tarolo().ir(TAROLT["hataridos"], szoveg, f"Határidős jegyzések {jegyzes_nap.isoformat()}")
                    st.session_state.setdefault("utoljara_mentve", {})["hataridos"] = szoveg
                    uzenet += " Mentve a tárolóba."
                except T.TarolasHiba as e:
                    uzenet += f" A mentés nem sikerült: {e}"
            st.success(uzenet)

        with gomb_jobb:
            st.download_button("hataridos.csv letöltése", data=H.csv_bajtok(st.session_state.hataridos),
                               file_name="hataridos.csv", mime="text/csv", width="content",
                               disabled=st.session_state.hataridos.empty)

    tarolt = st.session_state.hataridos
    if tarolt.empty:
        st.info("Még nincs rögzített határidős ár. Nyisd ki a fenti panelt, és írd be a jegyzéseket.")
    else:
        azonnali = azonnali_arak()
        for piac, cim in [("Villamos", "Villamos energia"), ("Gáz", "Földgáz")]:
            g = H.gorbe(tarolt, piac)
            if g.empty:
                continue
            st.subheader(f"{cim} · jegyzés {hu_datum(g.iloc[0]['jegyzes_nap'], hetnap=False)}")
            bal, jobb = st.columns([3, 2])
            with bal:
                fig = go.Figure()
                for tipus, szin in [("Zsinór", SZ["tinta"]), ("Alap", SZ["tinta"]), ("Csúcs", SZ["sargarez"])]:
                    resz = g[g["tipus"] == tipus]
                    if resz.empty:
                        continue
                    fig.add_scatter(x=pd.to_datetime(resz["szallitas_kezdete"]), y=resz["ar"], name=tipus,
                                    mode="lines+markers", line=dict(color=szin, width=2, shape="hv"),
                                    marker=dict(size=6), text=resz["termek"],
                                    hovertemplate="%{text}: %{y:.2f} EUR/MWh<extra></extra>")
                mai_ar = azonnali.get(f"{piac}|{'Zsinór' if piac == 'Villamos' else 'Alap'}")
                if mai_ar is not None and pd.notna(mai_ar):
                    fig.add_hline(y=float(mai_ar), line=dict(color=SZ["acel"], width=1, dash="dot"),
                                  annotation_text="mai azonnali ár", annotation_position="top left",
                                  annotation_font=dict(color=SZ["acel"], size=11))
                abra_alap(fig, 280)
                fig.update_layout(hovermode="closest")
                mutat(fig)
            with jobb:
                sorok = []
                for r in g.itertuples():
                    sorok.append(
                        f"<tr><td>{r.termek}<br><span class='halvany'>{r.tipus.lower()}</span></td>"
                        f"<td class='ear-kiemelt'>{hu(r.ar)}</td>"
                        f"{valtozas_cella(H.felar(r.ar, azonnali.get(f'{piac}|{r.tipus}')))}"
                        f"{valtozas_cella(H.felar(r.ar, azonnali.get(f'{piac}|{r.tipus}|30')))}</tr>")
                st.markdown(tabla_html(["EUR/MWh", "Ár", "Azonnalihoz", "Havihoz"], sorok),
                            unsafe_allow_html=True)

        napok = sorted(tarolt["jegyzes_nap"].unique())
        if len(napok) > 1:
            st.subheader("Egy termék árának alakulása")
            valaszthato = (tarolt[["piac", "termek", "tipus"]].drop_duplicates()
                           .apply(lambda r: f"{r['piac']}: {r['termek']} ({r['tipus'].lower()})", axis=1).tolist())
            valasztott = st.selectbox("Termék", valaszthato, label_visibility="collapsed")
            piac_v, maradek = valasztott.split(": ", 1)
            termek_v, tipus_v = maradek.rsplit(" (", 1)
            t = tarolt[(tarolt["piac"] == piac_v) & (tarolt["termek"] == termek_v)
                       & (tarolt["tipus"].str.lower() == tipus_v.rstrip(")"))].sort_values("jegyzes_nap")
            fig = go.Figure()
            fig.add_scatter(x=pd.to_datetime(t["jegyzes_nap"]), y=t["ar"], mode="lines+markers",
                            line=dict(color=SZ["tinta"], width=2), marker=dict(size=5),
                            hovertemplate="%{y:.2f} EUR/MWh")
            abra_alap(fig, 240)
            fig.update_layout(showlegend=False, hovermode="closest")
            mutat(fig)


# ------------------------------------------------------------------ piaci kép

with lap_piac:
    vk, gk = E.villamos_kep(napi, ma), E.gaz_kep(gaz)
    viszony = E.arany(vk["honap"], gk["honap"])

    mondatok = E.helyzet_szoveg(vk, gk, viszony)
    if mondatok:
        st.markdown(f'<p class="ear-vezeto">{" ".join(mondatok)}</p>', unsafe_allow_html=True)

    kartyak([
        ("Villamos, 7 nap", hu(E._atlag(napi, ma, 6)), ""),
        ("Villamos, 30 nap", hu(vk["honap"]), valtozas_jel(vk["honap_valtozas"]) or "előző 30 naphoz"),
        ("Villamos, 90 nap", hu(vk["negyedev"]), ""),
        ("Egy éve, 30 nap", hu(vk["egy_eve"]), valtozas_jel(vk["ev_valtozas"]) or "nincs előzmény"),
        ("Gáz, másnapi", hu(gk["mai"]), valtozas_jel(gk["het_valtozas"]) or "öt napja"),
        ("Gáz, 30 nap", hu(gk["honap"]), valtozas_jel(gk["honap_valtozas"]) or ""),
        ("Áram/gáz arány", hu(viszony), "30 napos átlagokból"),
        ("Csúcsprémium", hu_szazalek(vk["csucs_premium"], jel=False) or "-", "csúcson kívülihez"),
    ])

    st.markdown('<p class="ear-megj">A számok a fenti füleken látott adatokból készülnek, tehát csak a '
                'megtörtént árakat tükrözik, nem előrejelzést. Az áram/gáz arány azt mutatja, hányszorosa '
                'az áram ára a gázénak: minél közelebb van kettőhöz, annál inkább a gáztüzelésű erőművek '
                'szabják meg az áramárat.</p>', unsafe_allow_html=True)

    st.subheader("Rövid és hosszú távú elemzések")
    st.markdown('<p class="ear-megj">Ingyenesen elérhető, rendszeresen frissülő források. A rövid távúak '
                'a napi és heti döntésekhez, a hosszabbak az éves szerződéskötéshez adnak támpontot.</p>',
                unsafe_allow_html=True)
    sorok = [f"<tr><td><a href='{f['cim']}' target='_blank'>{escape(f['nev'])}</a><br>"
             f"<span class='halvany'>{escape(f['leiras'])}</span></td>"
             f"<td>{escape(f['tav'])} táv</td></tr>" for f in E.FORRASOK]
    st.markdown(tabla_html(["Forrás", "Időtáv"], sorok), unsafe_allow_html=True)


# ------------------------------------------------------------------ előzmények

@st.cache_data(show_spinner=False)
def excel(napi_t: pd.DataFrame, v: pd.DataFrame, g: pd.DataFrame, w: pd.DataFrame,
          h: pd.DataFrame) -> bytes:
    puffer = io.BytesIO()
    with pd.ExcelWriter(puffer, engine="openpyxl") as iro:
        napi_t.rename(columns={"nap": "Szállítási nap", "zsinor": "Zsinór", "csucs": "Csúcs",
                               "csucson_kivul": "Csúcson kívüli", "min_ar": "Minimum", "min_ido": "Min. időpont",
                               "max_ar": "Maximum", "max_ido": "Max. időpont", "idoszakok": "Időszakok"}
                      ).to_excel(iro, sheet_name="Villamos napi", index=False)
        v.drop(columns=["unix"], errors="ignore").rename(
            columns={"ido": "Időpont", "nap": "Szállítási nap", "negyedora": "Negyedóra", "ora": "Óra",
                     "ar": "Ár (EUR/MWh)", "perc": "Időtartam (perc)"}
        ).to_excel(iro, sheet_name="Villamos 15 perc", index=False)
        g.drop(columns=["kulcs"], errors="ignore").to_excel(iro, sheet_name="Gáz másnapi", index=False)
        w.drop(columns=["kulcs"], errors="ignore").to_excel(iro, sheet_name="Gáz napon belüli", index=False)
        if not h.empty:
            h.rename(columns={"jegyzes_nap": "Jegyzés napja", "piac": "Piac", "termek": "Termék",
                              "tipus": "Típus", "szallitas_kezdete": "Szállítás kezdete",
                              "szallitas_vege": "Szállítás vége", "ar": "Ár (EUR/MWh)"}
                     ).to_excel(iro, sheet_name="Határidős", index=False)
        for lap in iro.sheets.values():
            for oszlop in lap.columns:
                lap.column_dimensions[oszlop[0].column_letter].width = 18
    return puffer.getvalue()


with lap_elozmeny:
    if villamos.empty:
        st.info("Az előzmények a sikeres lekérés után jelennek meg.")
    else:
        napok_listaja = sorted(villamos["nap"].unique())
        bal, jobb = st.columns([1, 3])
        with bal:
            valasztott = st.date_input("Szállítási nap", value=date.fromisoformat(napok_listaja[-1]),
                                       min_value=date.fromisoformat(napok_listaja[0]),
                                       max_value=date.fromisoformat(napok_listaja[-1]), format="YYYY.MM.DD")
        resz = villamos[villamos["nap"] == valasztott.isoformat()]
        if resz.empty:
            st.info(f"{hu_datum(valasztott)}: erre a napra nincs negyedórás ár. "
                    f"A részletes előzmény {NEGYEDORA_MEGORZES} napra visszamenőleg érhető el.")
        else:
            with jobb:
                kartyak([
                    ("Zsinór", hu(napi_ertek(valasztott, "zsinor")), hu_datum(valasztott)),
                    ("Csúcs", hu(napi_ertek(valasztott, "csucs")), ""),
                    ("Minimum", hu(napi_ertek(valasztott, "min_ar")), str(napi_ertek(valasztott, "min_ido") or "")),
                    ("Maximum", hu(napi_ertek(valasztott, "max_ar")), str(napi_ertek(valasztott, "max_ido") or "")),
                ])
            fig = go.Figure()
            fig.add_scatter(x=pd.to_datetime("2000-01-01 " + resz["negyedora"]), y=resz["ar"], mode="lines",
                            line=dict(color=SZ["tinta"], width=2, shape="hv"),
                            hovertemplate="%{y:.2f} EUR/MWh")
            abra_alap(fig, 260)
            fig.update_xaxes(tickformat="%H:%M", dtick=3 * 3600 * 1000)
            fig.update_layout(showlegend=False)
            mutat(fig)
            st.dataframe(resz[["negyedora", "ar", "perc"]].rename(
                columns={"negyedora": "Negyedóra", "ar": "Ár (EUR/MWh)", "perc": "Időtartam (perc)"}),
                hide_index=True, width="stretch", height=240)

    st.subheader("Letöltés")
    st.download_button("Minden adat Excelben",
                       data=excel(napi, villamos, gaz, gaz_wd, st.session_state.get("hataridos", H.ures())),
                       file_name=f"energiaarak_{ma.isoformat()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="content")
    st.markdown('<p class="ear-megj">Források: Energy-Charts (Fraunhofer ISE, CC BY 4.0) és CEEGEX. '
                'A CEEGEX árai csak belső számításra használhatók, továbbadni vagy közzétenni nem szabad.</p>',
                unsafe_allow_html=True)
