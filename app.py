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
import beolvasas as BE
import elemzes as E
import forrasok as F
import hataridos as H
import lehetosegek as L
import megfigyeles as M
import szamitas as S
import tarolas as T

SZ = B.SZIN
HONAPOK = ["január", "február", "március", "április", "május", "június", "július",
           "augusztus", "szeptember", "október", "november", "december"]
NAPOK = ["hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat", "vasárnap"]

st.set_page_config(page_title="Energiaárak", page_icon="⚡", layout="wide")

BETU = "Calibri, Carlito, 'Segoe UI', system-ui, sans-serif"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Carlito:wght@400;700&display=swap');
html, body, .stApp, .stMarkdown, p, h1, h2, h3, li, label, button, td, th, input, textarea,
[data-baseweb="tab"], [data-testid="stCaptionContainer"] {{ font-family: {BETU}; }}
.block-container {{ max-width: 1180px; padding-top: 3.6rem; padding-bottom: 3rem; }}

/* A Streamlit minden szövegblokk alá -1rem margót tesz, mert a bekezdésektől 1rem-et vár.
   A saját elemeink maguk adják a térközt, ezért ezt kiegyenlítjük: így nem csúsznak egymásra. */
[data-testid="stMarkdownContainer"] {{ margin-bottom: 0 !important; }}
[data-testid="stMarkdownContainer"] > p:last-child {{ margin-bottom: 0.4rem; }}
div[data-testid="stVerticalBlock"] {{ gap: 0.55rem; }}

.ear-alcim {{ font-size: 1.12rem; font-weight: 700; color: {SZ['tinta']}; margin: 1.3rem 0 0.35rem 0;
             line-height: 1.3; }}
.ear-alcim small {{ display: block; font-size: 0.8rem; font-weight: 400; color: {SZ['acel']}; margin-top: 0.1rem; }}
.ear-felirat {{ font-size: 0.7rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
               font-variant: small-caps; color: {SZ['sargarez']}; margin: 0 0 0.25rem 0; }}
[data-testid="stMarkdownContainer"] .ear-vezeto {{ font-size: 1.05rem; color: {SZ['tinta']}; margin: 0.2rem 0 0.8rem 0; max-width: 80ch;
              line-height: 1.5; font-variant-numeric: tabular-nums; }}
[data-testid="stMarkdownContainer"] .ear-megj {{ font-size: 0.8rem; color: {SZ['acel']}; max-width: 82ch; margin: 0.3rem 0 0.7rem 0; line-height: 1.45; }}

/* Sötét nyitósáv */
.st-key-hos {{ background: linear-gradient(160deg, {SZ['tinta']} 0%, {SZ['tinta_mely']} 100%);
              border-radius: 16px; padding: 1.3rem 1.5rem 0 1.5rem; position: relative; overflow: hidden;
              gap: 0.6rem; }}
.st-key-hos [data-testid="stMarkdownContainer"], .st-key-hos p {{ color: #FFFFFF; }}
.st-key-hos button {{ background: {SZ['sargarez']}; color: {SZ['tinta']}; border: none; font-weight: 700; }}
.st-key-hos button:hover {{ background: #D9A452; color: {SZ['tinta']}; }}
.st-key-hos button:focus-visible {{ outline: 2px solid #FFFFFF; outline-offset: 2px; }}
.hos-kerdes {{ font-size: clamp(1.35rem, 2.6vw, 1.9rem); font-weight: 700; line-height: 1.2; margin: 0.1rem 0 0.35rem 0;
              color: #FFFFFF; }}
.hos-allapot {{ font-size: 0.82rem; color: #B9C4CF; line-height: 1.5; }}
.hos-pont {{ width: 8px; height: 8px; border-radius: 50%; background: {SZ['sargarez']}; display: inline-block;
            margin-right: 0.45rem; vertical-align: 1px;
            box-shadow: 0 0 0 0 rgba(200,146,61,0.7); animation: lukteto 2.4s infinite; }}
@keyframes lukteto {{ 0% {{ box-shadow: 0 0 0 0 rgba(200,146,61,0.6); }}
                      70% {{ box-shadow: 0 0 0 8px rgba(200,146,61,0); }}
                      100% {{ box-shadow: 0 0 0 0 rgba(200,146,61,0); }} }}
@media (prefers-reduced-motion: reduce) {{ .hos-pont {{ animation: none; }} }}
.hos-szamok {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 0.2rem 1.4rem;
              margin: 0.4rem 0 0.2rem 0; }}
.hos-szam .cimke {{ font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: {SZ['sargarez']};
                   font-weight: 700; }}
.hos-szam .ertek {{ font-size: clamp(1.7rem, 3.4vw, 2.4rem); font-weight: 700; color: #FFFFFF; line-height: 1.1;
                   font-variant-numeric: tabular-nums; }}
.hos-szam .ertek small {{ font-size: 0.85rem; font-weight: 400; color: #B9C4CF; margin-left: 0.25rem; }}
.hos-szam .also {{ font-size: 0.8rem; color: #B9C4CF; font-variant-numeric: tabular-nums; }}
.hos-szam .also b {{ color: #FFFFFF; }}
.hos-fel {{ color: #E58B7A; font-weight: 700; }}
.hos-le {{ color: #8FC19E; font-weight: 700; }}

/* Órás csík: mikor érdemes áramot használni */
.hos-csik-cim {{ font-size: 0.95rem; font-weight: 700; color: #FFFFFF; margin: 0.9rem 0 0.35rem 0; }}
.hos-csik {{ display: grid; grid-template-columns: repeat(24, 1fr); gap: 3px; }}
.hos-ora {{ height: 30px; border-radius: 4px; position: relative; }}
.hos-ora.olcso {{ background: {SZ['csokkenes']}; }}
.hos-ora.kozepes {{ background: #3B5670; }}
.hos-ora.draga {{ background: {SZ['emelkedes']}; }}
.hos-ora.most {{ outline: 2px solid #FFFFFF; outline-offset: 1px; }}
.hos-ora:hover {{ filter: brightness(1.2); }}
.hos-orak {{ display: grid; grid-template-columns: repeat(24, 1fr); gap: 3px; font-size: 0.66rem; color: #8FA1B3;
            margin-top: 3px; font-variant-numeric: tabular-nums; }}
.hos-jelmagyarazat {{ display: flex; gap: 1rem; flex-wrap: wrap; font-size: 0.78rem; color: #B9C4CF; margin-top: 0.45rem; }}
.hos-jelmagyarazat i {{ display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 0.3rem;
                       vertical-align: -1px; }}
[data-testid="stMarkdownContainer"] .hos-tipp {{ font-size: 0.86rem; color: #DCE3EA; margin: 0.5rem 0 0 0; max-width: 90ch; line-height: 1.45; }}
.hos-hullam {{ display: block; width: calc(100% + 3rem); margin: 0.9rem -1.5rem 0 -1.5rem; height: 34px; }}

/* Számkártyák */
.ear-racs {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(132px, 1fr)); gap: 0.45rem; margin: 0.3rem 0 0.8rem 0; }}
.ear-kartya {{ background: {SZ['kod']}; border-radius: 8px; padding: 0.55rem 0.7rem; }}
.ear-kartya .cimke {{ font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em;
                     color: {SZ['acel']}; display: block; }}
.ear-kartya .ertek {{ font-size: 1.28rem; font-weight: 700; color: {SZ['tinta']}; font-variant-numeric: tabular-nums;
                     line-height: 1.25; }}
.ear-kartya .also {{ font-size: 0.74rem; color: {SZ['acel']}; font-variant-numeric: tabular-nums; }}

/* Javaslatkártyák a Lehetőségek fülön */
.ear-javaslat {{ border: 1px solid {SZ['vonal']}; border-radius: 12px; padding: 1rem 1.1rem; height: 100%; background: #FFFFFF; }}
.ear-javaslat h4 {{ font-size: 1.05rem; margin: 0 0 0.5rem 0; color: {SZ['tinta']}; }}
.ear-javaslat .blokk {{ margin: 0.7rem 0 0 0; }}
.ear-javaslat .blokk-cim {{ font-size: 0.7rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
                           color: {SZ['sargarez']}; margin-bottom: 0.2rem; }}
.ear-javaslat p {{ margin: 0 0 0.35rem 0; font-size: 0.9rem; line-height: 1.45; color: {SZ['tinta']}; }}
.ear-cimke {{ display: inline-block; font-size: 0.72rem; font-weight: 700; padding: 0.1rem 0.5rem; border-radius: 999px;
             margin-left: 0.3rem; vertical-align: 1px; }}
.ear-cimke.nincs {{ background: {SZ['arany_hatter']}; color: #7A5418; }}
.ear-cimke.van {{ background: #E3EFE6; color: #2F5A3C; }}
.ear-lista {{ list-style: none; padding: 0; margin: 0.2rem 0 0 0; }}
.ear-lista li {{ padding-left: 1rem; position: relative; font-size: 0.88rem; margin: 0.15rem 0; color: {SZ['tinta']};
                font-variant-numeric: tabular-nums; }}
.ear-lista li::before {{ content: "■"; color: {SZ['sargarez']}; position: absolute; left: 0; font-size: 0.6rem; top: 0.3rem; }}
.ear-tanulsag {{ background: {SZ['kod']}; border-left: 3px solid {SZ['sargarez']}; border-radius: 0 8px 8px 0;
                padding: 0.7rem 0.9rem; margin: 0.4rem 0 0.8rem 0; }}
.ear-tanulsag p {{ margin: 0.15rem 0; font-size: 0.92rem; color: {SZ['tinta']}; line-height: 1.45; }}

table.ear-tabla {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; margin: 0.2rem 0 1rem 0; }}
table.ear-tabla th {{
  text-align: right; font-weight: 700; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: {SZ['acel']}; padding: 0.25rem 0.4rem; border-bottom: 1px solid {SZ['tinta']};
}}
table.ear-tabla th, table.ear-tabla td {{ border-left: none !important; border-right: none !important; border-top: none !important; }}
table.ear-tabla th:first-child, table.ear-tabla td:first-child {{ text-align: left; padding-left: 0; }}
table.ear-tabla td {{
  text-align: right; padding: 0.32rem 0.4rem; border-bottom: 1px solid {SZ['vonal']};
  color: {SZ['tinta']}; font-size: 0.9rem;
}}
table.ear-tabla tr:hover td {{ background: {SZ['kod']}; }}
table.ear-tabla td.ear-kiemelt {{ font-weight: 700; }}
table.ear-tabla td small, table.ear-tabla td .halvany {{ color: {SZ['acel']}; font-size: 0.76rem; }}
.ear-fel {{ color: {SZ['emelkedes']}; font-weight: 700; }}
.ear-le {{ color: {SZ['csokkenes']}; font-weight: 700; }}
/* Fülek: teljes szélességű, színes gombsor. A régebbi (baseweb) és az újabb Streamlit-szerkezetre is. */
[data-baseweb="tab-list"], [data-testid="stTabs"] [role="tablist"] {{
  display: flex !important; width: 100%; gap: 6px; background: {SZ['kod']}; padding: 6px;
  border-radius: 14px; border: 1px solid {SZ['vonal']}; overflow: visible !important; margin-bottom: 0.4rem;
}}
[data-baseweb="tab"], [data-testid="stTabs"] [role="tab"] {{
  flex: 1 1 0; min-width: 0; justify-content: center; text-align: center; height: auto !important;
  padding: 0.7rem 0.6rem !important; margin: 0 !important; border-radius: 10px; background: #FFFFFF;
  border: 1px solid {SZ['vonal']}; cursor: pointer; transition: background 0.15s, color 0.15s;
}}
[data-baseweb="tab"] p, [data-testid="stTabs"] [role="tab"] p {{
  font-size: 0.98rem !important; font-weight: 700; color: {SZ['tinta']} !important; margin: 0 !important;
  white-space: normal; line-height: 1.2;
}}
[data-baseweb="tab"]:hover, [data-testid="stTabs"] [role="tab"]:hover {{
  background: {SZ['arany_hatter']}; border-color: {SZ['sargarez']};
}}
[data-baseweb="tab"][aria-selected="true"], [data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
  background: {SZ['tinta']}; border-color: {SZ['tinta']}; box-shadow: inset 0 -3px 0 {SZ['sargarez']};
}}
[data-baseweb="tab"][aria-selected="true"] p, [data-testid="stTabs"] [role="tab"][aria-selected="true"] p {{
  color: #FFFFFF !important;
}}
[data-baseweb="tab"]:focus-visible, [data-testid="stTabs"] [role="tab"]:focus-visible {{
  outline: 2px solid {SZ['sargarez']}; outline-offset: 2px;
}}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"],
[data-testid="stTabs"] .react-aria-SelectionIndicator {{ display: none !important; }}

/* Választógombok (például: mennyit rögzítsünk előre): teljes szélesség, színes kijelölés */
[data-testid="stButtonGroup"], .stElementContainer:has(> [data-testid="stButtonGroup"]),
[data-testid="stElementContainer"]:has(> [data-testid="stButtonGroup"]) {{ width: 100% !important; }}
[data-testid="stButtonGroup"] [role="radiogroup"], [data-testid="stButtonGroup"] > div:last-child {{
  display: flex !important; width: 100%; gap: 4px; background: {SZ['kod']}; padding: 4px;
  border-radius: 10px; border: 1px solid {SZ['vonal']}; flex-wrap: nowrap;
}}
[data-testid="stButtonGroup"] button {{
  flex: 1 1 0; min-width: 0; justify-content: center; border-radius: 7px !important; border: none !important;
  background: transparent; color: {SZ['tinta']}; font-weight: 700; margin: 0 !important; padding: 0.4rem 0.3rem;
}}
[data-testid="stButtonGroup"] button p {{ font-weight: 700; white-space: nowrap; overflow: hidden;
                                         text-overflow: ellipsis; }}
[data-testid="stButtonGroup"] button:hover {{ background: {SZ['arany_hatter']}; color: {SZ['tinta']}; }}
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[kind$="Active"] {{
  background: {SZ['tinta']} !important; color: #FFFFFF !important; box-shadow: inset 0 -3px 0 {SZ['sargarez']};
}}
[data-testid="stButtonGroup"] button[aria-checked="true"] p, [data-testid="stButtonGroup"] button[kind$="Active"] p {{
  color: #FFFFFF !important;
}}
[data-testid="stExpander"] summary p {{ font-size: 0.92rem; }}
@media (max-width: 640px) {{
  .block-container {{ padding-left: 0.8rem; padding-right: 0.8rem; padding-top: 3.2rem; }}
  .st-key-hos {{ padding: 1rem 1rem 0 1rem; }}
  .hos-hullam {{ width: calc(100% + 2rem); margin: 0.7rem -1rem 0 -1rem; }}
  .hos-szamok {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.6rem 0.9rem; }}
  .hos-szam .ertek {{ font-size: 1.55rem; }}
  .hos-szam .ertek small {{ display: block; margin-left: 0; font-size: 0.72rem; }}
  .hos-szam .also {{ font-size: 0.74rem; }}
  .hos-ora {{ height: 24px; }}
  .hos-orak span:nth-child(3n+2), .hos-orak span:nth-child(3n+3) {{ visibility: hidden; }}
  .ear-racs {{ grid-template-columns: repeat(auto-fit, minmax(104px, 1fr)); }}
  [data-baseweb="tab-list"], [data-testid="stTabs"] [role="tablist"] {{ gap: 4px; padding: 4px; flex-wrap: wrap; }}
  [data-baseweb="tab"], [data-testid="stTabs"] [role="tab"] {{ flex: 1 1 30%; padding: 0.55rem 0.3rem !important; }}
  [data-baseweb="tab"] p, [data-testid="stTabs"] [role="tab"] p {{ font-size: 0.82rem !important; white-space: nowrap; }}
  .st-key-kockazat [role="radiogroup"], .st-key-kockazat [data-testid="stButtonGroup"] > div:last-child {{
    flex-direction: column; }}
  .st-key-kockazat button {{ flex: 1 1 auto; width: 100%; }}
  .ear-kartya .ertek {{ font-size: 1.08rem; }}
  table.ear-tabla td {{ font-size: 0.82rem; padding-left: 0.2rem; padding-right: 0.2rem; }}
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
        f'<div class="ertek">{e}</div><div class="also">{a}</div></div>'
        for c, e, a in tetelek)
    st.markdown(f'<div class="ear-racs">{darabok}</div>', unsafe_allow_html=True)


def alcim(szoveg: str, alatta: str = "") -> None:
    """Szakaszcím, kérdés formában; alatta opcionális rövid magyarázat."""
    kiegeszites = f"<small>{alatta}</small>" if alatta else ""
    st.markdown(f'<div class="ear-alcim">{szoveg}{kiegeszites}</div>', unsafe_allow_html=True)


def tabla_html(fejlec: list[str], sorok: list[str]) -> str:
    th = "".join(f"<th>{escape(h)}</th>" for h in fejlec)
    return f'<table class="ear-tabla"><thead><tr>{th}</tr></thead><tbody>{"".join(sorok)}</tbody></table>'


def abra_alap(fig: go.Figure, magassag: int = 300) -> go.Figure:
    fig.update_layout(
        height=magassag, margin=dict(l=0, r=6, t=6, b=0), separators=", ",
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family=BETU, color=SZ["tinta"], size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None,
                    font=dict(size=11)),
        hovermode="x unified", hoverlabel=dict(bgcolor="white", font_color=SZ["tinta"]),
    )
    fig.update_xaxes(showgrid=False, linecolor=SZ["vonal"], ticks="outside", tickcolor=SZ["vonal"])
    fig.update_yaxes(gridcolor=SZ["kod"], zeroline=True, zerolinecolor=SZ["vonal"], ticksuffix=" ")
    return fig


def datum_tengely(fig: go.Figure) -> go.Figure:
    """Számokkal írt dátum a tengelyen, rövid időtávon napra, hosszabbon hónapra."""
    fig.update_xaxes(tickformatstops=[
        dict(dtickrange=[None, 86400000 * 40], value="%m. %d."),
        dict(dtickrange=[86400000 * 40, None], value="%Y. %m.")], hoverformat="%Y. %m. %d.")
    return fig


def mutat(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "locale": "hu"})


# ------------------------------------------------------------------ tároló

TAROLT = {"napi": "data/villamos_napi.csv", "negyedora": "data/villamos_15perc.csv",
          "gaz": "data/gaz_masnapi.csv", "gaz_wd": "data/gaz_napon_belul.csv",
          "hataridos": "hataridos.csv", "naplo": "data/megfigyelesek.csv"}
NEGYEDORA_MEGORZES = 70  # ennyi napnyi negyedórás árat őrzünk meg részletesen
MERET_HATAR = 900_000     # a GitHub felülete egy megabájt fölött már nem kezeli jól a fájlokat


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


@st.cache_data(ttl=B.ARFOLYAM_ELTARTHATOSAG, show_spinner=False)
def arfolyam() -> dict:
    return F.leker_arfolyam()


@st.cache_data(ttl=B.FRISS_ELTARTHATOSAG, show_spinner=False)
def gaz_adatok(ma: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    return F.leker_gaz_masnapi(), F.leker_gaz_napon_belul()


def betolt(ma: date, mentett: dict) -> dict:
    """Tárolt és élő adatok összefésülése. Egy forrás hibája nem akadályozza a többit."""
    ki = {"hibak": []}
    tarolt_negyedora = T.szoveg_tablava(mentett.get("negyedora"), F.VILLAMOS_OSZLOPOK)
    tarolt_napi = T.szoveg_tablava(mentett.get("napi"), S.NAPI_OSZLOPOK)
    # Akkor tekintjük teljesnek a tárolt előzményt, ha friss ÉS elég hosszú. Enélkül egy hiányos
    # mentés után az alkalmazás soha nem töltené vissza a hosszú előzményt.
    van_elozmeny = (not tarolt_napi.empty
                    and tarolt_napi["nap"].max() >= (ma - timedelta(days=5)).isoformat()
                    and len(tarolt_napi) >= B.ELOZMENY_NAP * 0.6)

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
               ("gaz", adat["gaz"]), ("gaz_wd", adat["gaz_wd"]),
               ("naplo", st.session_state.get("naplo"))]
    mentve, gondok = [], []
    for kulcs, tabla in tetelek:
        if tabla is None or tabla.empty:
            continue
        szoveg = T.tabla_szovegge(tabla)
        korabbi = utoljara.get(kulcs, mentett.get(kulcs))
        if not T.valtozott(korabbi, szoveg):
            continue
        if len(szoveg.encode("utf-8")) > MERET_HATAR:
            gondok.append(f"{TAROLT[kulcs]}: túl nagy a mentéshez")
            continue
        try:
            t.ir(TAROLT[kulcs], szoveg, f"Adatfrissítés {ma_szoveg}")
            utoljara[kulcs] = szoveg
            mentve.append(TAROLT[kulcs])
        except T.TarolasHiba as e:
            # Egy fájl hibája ne akadályozza meg a többi mentését.
            gondok.append(f"{TAROLT[kulcs]}: {e}")
    st.session_state["mentesi_gondok"] = gondok
    return mentve


def mindent_ujra() -> None:
    villamos_friss.clear()
    gaz_adatok.clear()
    tarolt_adatok.clear()


# ------------------------------------------------------------------ fejléc és betöltés

most = pd.Timestamp.now(tz=B.IDOZONA)
ma, holnap = most.date(), most.date() + timedelta(days=1)

with st.container(key="hos"):
    fej_bal, fej_jobb = st.columns([5, 1], vertical_alignment="top")
    with fej_jobb:
        if st.button("Frissítés", width="stretch", help="Újra lekéri az árakat a forrásokból"):
            mindent_ujra()
            st.rerun()
    fej_hely = fej_bal.empty()
    szam_hely = st.empty()

with st.spinner("Árak lekérése..."):
    mentett = tarolt_adatok(tarolo(), st.session_state.get("tarolo_jel", 0))
    adat = betolt(ma, mentett)
    arf = arfolyam()

villamos, napi, gaz, gaz_wd = adat["villamos"], adat["napi"], adat["gaz"], adat["gaz_wd"]
hibak = list(dict.fromkeys(list(adat["hibak"]) + list(mentett.get("_hibak", []))))
EUR_HUF = arf["arfolyam"]

napi_terkep = napi.set_index("nap") if not napi.empty else pd.DataFrame(columns=S.NAPI_OSZLOPOK).set_index("nap")


def napi_ertek(nap: date, oszlop: str):
    kulcs = nap.isoformat() if isinstance(nap, date) else str(nap)
    if kulcs in napi_terkep.index and oszlop in napi_terkep.columns:
        ertek = napi_terkep.at[kulcs, oszlop]
        return None if pd.isna(ertek) else ertek
    return None


def ft(eur_mwh, tizedes: int = 1) -> str:
    """EUR/MWh forintban, kWh-ra vetítve."""
    ertek = F.ft_kwh(eur_mwh, EUR_HUF)
    return hu(ertek, tizedes, ha_nincs="")


# Határidős jegyzések: a napló és a Lehetőségek fül is használja, ezért itt töltjük be
if "hataridos" not in st.session_state:
    st.session_state.hataridos = H.egyesit(H.ures(), T.szoveg_tablava(mentett.get("hataridos"), H.OSZLOPOK))

# Megfigyelési napló: minden frissítés feljegyzi, mi volt új
if "naplo" not in st.session_state:
    st.session_state.naplo = M.egyesit(M.ures(), T.szoveg_tablava(mentett.get("naplo"), M.OSZLOPOK))
profil60 = L.orai_profil(villamos, ma)
olcso60 = L.olcso_sav(profil60)
gorbe_v = L.legutobbi_gorbe(st.session_state.hataridos, "Villamos")
jovo_ev = dict(L.eves_termekek(gorbe_v, "Zsinór")).get(ma.year + 1)
gk_most = E.gaz_kep(gaz)
aram30 = E._atlag(napi, ma, 29)
mutatok = {
    "aram_30nap": aram30,
    "deli_sav": olcso60[1] if olcso60 else None,
    "negativ_arany": L.negativ_arany(villamos, ma),
    "fwd_jovo_ev": jovo_ev,
    "gorbe_irany": L.gorbe_irany(gorbe_v)["valtozas"],
    "gaz_30nap": gk_most["honap"],
    "aram_gaz_arany": E.arany(aram30, gk_most["honap"]),
}
uj_esemeny = M.uj_esemenyek(st.session_state.naplo, most.to_pydatetime(), napi, gaz,
                            st.session_state.hataridos, mutatok)
if not uj_esemeny.empty:
    st.session_state.naplo = M.egyesit(st.session_state.naplo, uj_esemeny)

mentve = []
if tarolo().mukodik and not villamos.empty:
    try:
        mentve = ment_tarolóba(adat, mentett)
        hibak += [f"Mentés: {g}" for g in st.session_state.get("mentesi_gondok", [])]
    except T.TarolasHiba as e:
        hibak.append(f"Mentés: {e}")

# ---- a nyitósáv tartalma

allapot = [f"élő, lekérve {most.strftime('%H:%M')}-kor"]
if not napi.empty:
    allapot.append(f"{len(napi)} napnyi előzmény")
if mentve:
    allapot.append(f"{len(mentve)} fájl mentve")
elif not tarolo().mukodik:
    allapot.append("tároló nincs beállítva")
allapot.append(f"1 euró = {hu(EUR_HUF, 2)} Ft ({arf['forras']}{', ' + arf['nap'] if arf['nap'] else ''})")
fej_hely.markdown(
    '<div class="ear-felirat">Magyar energiaárak</div>'
    '<div class="hos-kerdes">Mennyibe kerül most az áram és a gáz?</div>'
    f'<div class="hos-allapot"><span class="hos-pont"></span>{" · ".join(allapot)}</div>',
    unsafe_allow_html=True)


def hos_valtozas(v) -> str:
    if v is None or pd.isna(v):
        return ""
    osztaly = "hos-fel" if v > 0.0005 else "hos-le" if v < -0.0005 else ""
    return f'<span class="{osztaly}">{hu_szazalek(v)}</span>'


negyed = most.floor("15min").strftime("%Y-%m-%d %H:%M")
most_sor = villamos[villamos["ido"] == negyed] if not villamos.empty else villamos
most_ar = float(most_sor.iloc[0]["ar"]) if not most_sor.empty else None
zs_ma, zs_holnap = napi_ertek(ma, "zsinor"), napi_ertek(holnap, "zsinor")
gaz_elozo = S.gaz_kulcsszamok(gaz)["da_elozo"]

szamok = [
    ("Most", most_ar, f"{most.floor('15min').strftime('%H:%M')} és "
                      f"{(most.floor('15min') + pd.Timedelta(minutes=15)).strftime('%H:%M')} között"),
    ("Ma átlagosan", zs_ma, "zsinór, egész napra"),
    ("Holnap átlagosan", zs_holnap,
     f"a mához képest {hos_valtozas(S.valtozas(zs_holnap, zs_ma))}" if zs_holnap else "13 óra körül érkezik"),
    ("Gáz, másnapi", gk_most["mai"],
     f"előző naphoz {hos_valtozas(S.valtozas(gk_most['mai'], gaz_elozo['atlagar'] if gaz_elozo else None))}"),
]
szam_html = "".join(
    f'<div class="hos-szam"><div class="cimke">{c}</div>'
    f'<div class="ertek">{hu(e, 1, ha_nincs="nincs még")}<small>{"EUR/MWh" if e is not None else ""}</small></div>'
    f'<div class="also">{"<b>" + ft(e) + " Ft/kWh</b> · " if e is not None else ""}{a}</div></div>'
    for c, e, a in szamok)

# Órás csík: a holnapi nap, ha már teljes; különben a mai
csik_nap = holnap if not L.ora_kategoriak(villamos, holnap).empty else ma
kategoriak = L.ora_kategoriak(villamos, csik_nap)
csik_html = ""
if not kategoriak.empty:
    kat = kategoriak.set_index("ora")
    cellak, feliratok = [], []
    for ora in range(24):
        if ora in kat.index:
            ar = kat.at[ora, "ar"]
            most_e = " most" if csik_nap == ma and ora == most.hour else ""
            cim = f"{ora}:00 és {ora + 1}:00 között: {hu(ar, 1)} EUR/MWh, {ft(ar)} Ft/kWh"
            cellak.append(f'<div class="hos-ora {kat.at[ora, "kategoria"]}{most_e}" title="{cim}"></div>')
        else:
            cellak.append('<div class="hos-ora"></div>')
        feliratok.append(f"<span>{ora if ora % 3 == 0 else ''}</span>")
    melyik = "holnap" if csik_nap == holnap else "ma"
    olcso_szoveg, draga_szoveg = L.sav_felirat(kategoriak, "olcso"), L.sav_felirat(kategoriak, "draga")
    csik_html = (
        f'<div class="hos-csik-cim">Mikor érdemes áramot használni {melyik}, {NAPOK[csik_nap.weekday()]}?</div>'
        f'<div class="hos-csik">{"".join(cellak)}</div><div class="hos-orak">{"".join(feliratok)}</div>'
        f'<div class="hos-jelmagyarazat"><span><i style="background:{SZ["csokkenes"]}"></i>a nap nyolc legolcsóbb órája</span>'
        f'<span><i style="background:#3B5670"></i>középmezőny</span>'
        f'<span><i style="background:{SZ["emelkedes"]}"></i>a nyolc legdrágább óra</span>'
        + ('<span><i style="background:transparent;outline:2px solid #fff"></i>most</span>' if melyik == "ma" else "")
        + '</div>'
        f'<p class="hos-tipp">Olcsó: {olcso_szoveg}. Ide érdemes időzíteni a hőszivattyús előfűtést vagy '
        f'előhűtést, a hőtárolók és a használati melegvíz felfűtését, valamint az elektromos autók töltését. '
        f'Drága: {draga_szoveg}. Az egérrel egy óra fölé állva látod az árát.</p>')

hullam = ('<svg class="hos-hullam" viewBox="0 0 1200 34" preserveAspectRatio="none" aria-hidden="true">'
          f'<path d="M0,20 C200,4 400,4 600,18 C800,32 1000,30 1200,12" fill="none" stroke="{SZ["sargarez"]}" '
          'stroke-width="1.5" opacity="0.7"/>'
          '<path d="M0,26 C200,12 400,12 600,24 C800,36 1000,34 1200,20 L1200,34 L0,34 Z" fill="#FFFFFF"/></svg>')
szam_hely.markdown(f'<div class="hos-szamok">{szam_html}</div>{csik_html}{hullam}', unsafe_allow_html=True)

if hibak:
    st.warning("Nem minden lépés sikerült:\n\n" + "\n\n".join(hibak))

lap_villamos, lap_gaz, lap_lehetoseg, lap_hataridos, lap_elozmeny = st.tabs(
    ["Villamos energia", "Földgáz", "Lehetőségek", "Határidős árak", "Előzmények"])


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
            if not most_sor.empty:
                most_ido = pd.Timestamp(negyed)
                fig.add_vline(x=most_ido, line=dict(color=SZ["sargarez"], width=1.5))
                fig.add_scatter(x=[most_ido], y=[most_ar], mode="markers", showlegend=False,
                                marker=dict(size=10, color=SZ["sargarez"], line=dict(color="white", width=2)),
                                hovertemplate="most: %{y:.2f} EUR/MWh<extra></extra>")
                fig.add_annotation(x=most_ido, y=0, yref="paper", text="most", showarrow=False,
                                   yanchor="bottom", xanchor="left", xshift=4,
                                   font=dict(size=11, color=SZ["sargarez"]))
            abra_alap(fig, 350)
            fig.update_layout(margin=dict(l=0, r=6, t=30, b=0), showlegend=False)
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
            alcim("Ma és holnap, számokban", "EUR/MWh; a változás a holnapi napot veti össze a maival")
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
            alcim("Mennyi volt átlagosan?", "Egyszerű napi átlagok az adott időszakban")
            atl = S.idoszaki_atlagok(napi, ma)
            sorok = [f"<tr><td>{r.idoszak}<br><span class='halvany'>{hu_rovid(r.tol)} és "
                     f"{hu_rovid(r.ig)} között</span></td><td>{hu(r.zsinor, ha_nincs='')}</td>"
                     f"<td>{hu(r.csucs, ha_nincs='')}</td><td>{r.napok}</td></tr>"
                     for r in atl.itertuples() if r.napok]
            st.markdown(tabla_html(["EUR/MWh", "Zsinór", "Csúcs", "Nap"], sorok), unsafe_allow_html=True)

        alcim("Hogyan alakult a napi ár?")
        tav = st.segmented_control("Időtáv", ["30 nap", "90 nap", "1 év", "Teljes"], default="90 nap",
                                   required=True, label_visibility="collapsed", width="stretch") or "90 nap"
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
        datum_tengely(fig)
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
            alcim("Hogyan alakult a gáz ára?", "CEEGEX másnapi átlagár és a CEEREP elszámolási index")
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
            datum_tengely(fig)
            mutat(fig)
        with jobb:
            alcim("Mi történik ma a napon belüli piacon?", "Halmozott átlagár gázóránként")
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

    st.markdown('<p class="ear-vezeto">A heti, havi, negyedéves, féléves és éves jegyzéseket a tőzsdék '
                'csak előfizetéssel adják ki gépi lekérésre, a napi árlistát viszont a legtöbb '
                'energiakereskedő díjmentesen küldi. Töltsd fel a levelet, és az árak maguktól '
                'bekerülnek a táblázatba.</p>', unsafe_allow_html=True)

    with st.expander("Árak megadása és mentése", expanded=tarolt.empty):
        feltoltott = st.file_uploader("Korábban mentett hataridos.csv betöltése", type="csv")
        if feltoltott is not None:
            st.session_state.hataridos = H.egyesit(st.session_state.hataridos, H.olvas(feltoltott))
            tarolt = st.session_state.hataridos
            st.success(f"{len(tarolt)} jegyzés betöltve.")

        with st.popover("Ajánlat beolvasása e-mailből"):
            st.markdown('<p class="ear-megj">Töltsd fel a kereskedő levelét (msg, eml, txt, html vagy csv), '
                        'vagy másold be a szövegét. A beolvasó felismeri a szokásos jelöléseket '
                        '(Cal-27, YR-2027, Q1/27, M10-2026, Okt-26, 2027. október, 38. hét), és megkeresi '
                        'mellettük az árat. Az eredményt ellenőrizheted, mielőtt bekerül a táblázatba.</p>',
                        unsafe_allow_html=True)
            level = st.file_uploader("Levelek vagy árlisták (több is lehet)",
                                     type=["msg", "eml", "txt", "html", "htm", "csv"],
                                     accept_multiple_files=True, key="hataridos_level")
            beillesztett = st.text_area("Vagy másold be ide a levél szövegét", height=120,
                                        key="hataridos_szoveg", label_visibility="collapsed",
                                        placeholder="M10-2026 HU BL  207,00\nYR-2027 HU BL  159,50")
            if st.button("Beolvasás", key="hataridos_beolvas"):
                try:
                    if level:
                        tabla, jelentes = BE.tobb_fajl(level, ma)
                    else:
                        nap = BE.datum_felismerese(beillesztett or "") or st.session_state.get("hataridos_nap") or ma
                        tabla = BE.elemez(beillesztett or "", ma, min(nap, ma))
                        jelentes = []
                    st.session_state.beolvasott = tabla
                    st.session_state.beolvasott_jelentes = jelentes
                    st.session_state.beolvasott_nap = (
                        date.fromisoformat(tabla["jegyzes_nap"].max()) if not tabla.empty else ma)
                except Exception as e:
                    st.session_state.beolvasott = pd.DataFrame(columns=BE.OSZLOPOK)
                    st.session_state.beolvasott_jelentes = []
                    st.error(f"A feldolgozás nem sikerült: {e}")

            talalt = st.session_state.get("beolvasott")
            jelentes = st.session_state.get("beolvasott_jelentes") or []
            if jelentes:
                st.markdown('<p class="ear-megj">' + "<br>".join(escape(j) for j in jelentes) + "</p>",
                            unsafe_allow_html=True)
            if talalt is not None and not talalt.empty:
                napok_szama = talalt["jegyzes_nap"].nunique()
                st.success(f"{len(talalt)} ár felismerve {napok_szama} jegyzési napra. "
                           "Nézd át, és ha jó, vedd át a táblázatba.")
                st.dataframe(talalt.rename(columns={"jegyzes_nap": "Jegyzés napja", "piac": "Piac",
                                                    "termek": "Termék", "tipus": "Típus",
                                                    "ar": "Ár", "forras_sor": "Forrássor"})
                             [["Jegyzés napja", "Piac", "Termék", "Típus", "Ár", "Forrássor"]],
                             hide_index=True, width="stretch", height=260)
                if st.button("Átvétel és mentés", type="primary", key="hataridos_atvesz"):
                    st.session_state.beolvasott_atveendo = talalt.drop(columns=["forras_sor"])
                    st.session_state.hataridos_nap = st.session_state.get("beolvasott_nap", ma)
                    st.session_state.beolvasott = None
                    st.session_state.beolvasott_jelentes = []
                    st.session_state.mentsd_a_jegyzeseket = True
                    st.rerun()
            elif talalt is not None:
                st.warning("Ebben a szövegben nem találtam felismerhető terméket és árat. "
                           "Másold be csak az ártáblázat sorait, vagy írd be kézzel.")

        jegyzes_nap = st.date_input("Jegyzés napja", value=ma, max_value=ma, format="YYYY.MM.DD",
                                    key="hataridos_nap")
        alap = H.alap_termekek(jegyzes_nap)
        atveendo = st.session_state.pop("beolvasott_atveendo", None)
        if atveendo is not None and not atveendo.empty:
            st.session_state.hataridos = H.egyesit(st.session_state.hataridos, atveendo)
            tarolt = st.session_state.hataridos
            if st.session_state.pop("mentsd_a_jegyzeseket", False):
                uzenet = f"{len(atveendo)} ár átvéve."
                if tarolo().mukodik:
                    try:
                        szoveg = T.tabla_szovegge(tarolt)
                        tarolo().ir(TAROLT["hataridos"], szoveg, "Határidős jegyzések beolvasásból")
                        st.session_state.setdefault("utoljara_mentve", {})["hataridos"] = szoveg
                        uzenet += " Mentve a tárolóba."
                    except T.TarolasHiba as e:
                        uzenet += f" A mentés nem sikerült: {e}"
                st.success(uzenet)
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
            alcim(f"{cim}: mit áraz a piac?", f"Jegyzés napja: {hu_datum(g.iloc[0]['jegyzes_nap'])}")
            bal, jobb = st.columns([3, 2])
            with bal:
                fig = go.Figure()
                # Minden termék egy vízszintes szakasz a saját szállítási időszaka fölött,
                # hogy a hónap, a negyedév és az év ne mosódjon össze egy vonallá
                fajtak = [("hét", "Hetek", SZ["acel"], 3), ("szezon", "Szezonok", "#8A6D3B", 5),
                          ("gázév", "Gázév", "#8A6D3B", 5), ("negyedév", "Negyedévek", SZ["sargarez"], 6),
                          ("félév", "Félévek", "#A7B3BF", 5), (". év", "Évek", SZ["tinta"], 7)]
                for tipus_nev, halvany in (("Zsinór", False), ("Alap", False), ("Csúcs", True)):
                    t_resz = g[g["tipus"] == tipus_nev]
                    if t_resz.empty:
                        continue
                    maradek = t_resz.copy()
                    for kulcsszo, nev, szin, vastag in fajtak + [("", "Hónapok", "#3B5670", 4)]:
                        resz = maradek[maradek["termek"].str.contains(kulcsszo, regex=False)] if kulcsszo else maradek
                        maradek = maradek.drop(resz.index)
                        if resz.empty:
                            continue
                        xs, ys, szovegek = [], [], []
                        for r in resz.itertuples():
                            veg = pd.Timestamp(r.szallitas_vege) + pd.Timedelta(days=1)
                            xs += [pd.Timestamp(r.szallitas_kezdete), veg, None]
                            ys += [r.ar, r.ar, None]
                            szoveg = f"{r.termek}, {tipus_nev.lower()}: {hu(r.ar)} EUR/MWh"
                            szovegek += [szoveg, szoveg, None]
                        fig.add_scatter(x=xs, y=ys, mode="lines", name=f"{nev}, {tipus_nev.lower()}",
                                        line=dict(color=szin, width=vastag, dash="dot" if halvany else "solid"),
                                        opacity=0.55 if halvany else 1, text=szovegek,
                                        hovertemplate="%{text}<extra></extra>")
                mai_ar = azonnali.get(f"{piac}|{'Zsinór' if piac == 'Villamos' else 'Alap'}")
                if mai_ar is not None and pd.notna(mai_ar):
                    fig.add_hline(y=float(mai_ar), line=dict(color=SZ["acel"], width=1, dash="dot"),
                                  annotation_text="mai azonnali ár", annotation_position="top left",
                                  annotation_font=dict(color=SZ["acel"], size=11))
                abra_alap(fig, 300)
                datum_tengely(fig)
                fig.update_layout(hovermode="closest", legend=dict(y=1.02, font=dict(size=10)))
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
            alcim("Hogyan mozgott egy termék ára a jegyzési napok között?")
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
            datum_tengely(fig)
            fig.update_layout(showlegend=False, hovermode="closest")
            mutat(fig)


# ------------------------------------------------------------------ lehetőségek

def millio_ft(eur) -> str:
    return hu(eur * EUR_HUF / 1e6, 1, ha_nincs="")


def eur_ezer(eur) -> str:
    return hu(eur / 1000, 0, ha_nincs="")


def javaslat_kartya(cim: str, blokkok: list[tuple[str, str]]) -> str:
    belso = "".join(f'<div class="blokk"><div class="blokk-cim">{c}</div>{t}</div>' for c, t in blokkok if t)
    return f'<div class="ear-javaslat"><h4>{cim}</h4>{belso}</div>'


def lista(elemek: list[str]) -> str:
    return '<ul class="ear-lista">' + "".join(f"<li>{e}</li>" for e in elemek if e) + "</ul>"


with lap_lehetoseg:
    naplo = st.session_state.naplo
    hataridos_most = st.session_state.hataridos

    # ---- mit tartogat a piac
    alcim("Mit tartogat a piac?", "A beolvasott jegyzésekből és a tényleges árakból, minden frissítéskor újraszámolva")
    kilatas = L.piaci_kilatas(hataridos_most, napi, gaz, villamos, ma)
    st.markdown(f'<p class="ear-vezeto">{" ".join(kilatas)}</p>', unsafe_allow_html=True)

    vk = E.villamos_kep(napi, ma)
    viszony = E.arany(vk["honap"], gk_most["honap"])
    kartyak([
        ("Áram, 30 nap", hu(vk["honap"]), valtozas_jel(vk["honap_valtozas"]) or "előző 30 naphoz"),
        ("Áram, 90 nap", hu(vk["negyedev"]), f"{ft(vk['negyedev'])} Ft/kWh" if vk["negyedev"] else ""),
        ("Egy éve, 30 nap", hu(vk["egy_eve"]), valtozas_jel(vk["ev_valtozas"]) or "nincs előzmény"),
        (f"{ma.year + 1}, zsinór", hu(jovo_ev, ha_nincs="nincs jegyzés"),
         f"{ft(jovo_ev)} Ft/kWh" if jovo_ev else "Határidős fül"),
        ("Gáz, 30 nap", hu(gk_most["honap"]), valtozas_jel(gk_most["honap_valtozas"]) or ""),
        ("Áram/gáz arány", hu(viszony), "kettő körül: a gáz szabja az árat"),
        ("Déli kedvezmény", hu_szazalek(olcso60[1], jel=False) if olcso60 else "-",
         f"{olcso60[0]} és {olcso60[0] + 4} óra között" if olcso60 else ""),
    ])

    # ---- milyen szerződés lenne jó
    alcim("Milyen szerződés lenne jó?",
          "Irodaházi fogyasztásra számolva; a mennyiségek és a kockázatvállalás átírhatók")
    b1, b2, b3 = st.columns([1, 1.4, 1])
    with b1:
        eves_aram = st.number_input("Éves áramfogyasztás (MWh)", min_value=10, max_value=500_000,
                                    value=B.ALAP_EVES_ARAM_MWH, step=50, key="eves_aram")
    with b2:
        profil_nev = st.selectbox("Fogyasztási minta", ["Irodaház (hétköznap nappal)", "Egyenletes (0 és 24 óra között)",
                                                        "Egyedi"], key="profil_nev")
        if profil_nev.startswith("Iroda"):
            csucs_arany = B.ALAP_CSUCS_ARANY
        elif profil_nev.startswith("Egyenletes"):
            osszes_ora, csucs_ora = L.orak_szama(ma.year + 1)
            csucs_arany = csucs_ora / osszes_ora
        else:
            csucs_arany = st.slider("Csúcsidőbe eső rész", 0.2, 0.9, B.ALAP_CSUCS_ARANY, 0.01,
                                    help="Az éves fogyasztás mekkora része esik hétköznap 8 és 20 óra közé",
                                    key="csucs_arany")
    with b3:
        eves_gaz = st.number_input("Éves gázfogyasztás (MWh)", min_value=10, max_value=500_000,
                                   value=B.ALAP_EVES_GAZ_MWH, step=50, key="eves_gaz")
    szint_nevek = {n: f"{n}: {round(v * 100)} százalék fix" for n, v in L.KOCKAZATI_SZINT.items()}
    szint = st.segmented_control("Mennyit rögzítsünk előre a várható fogyasztásból?", list(L.KOCKAZATI_SZINT),
                                 format_func=lambda n: szint_nevek[n], default="Kiegyensúlyozott",
                                 required=True, key="kockazat", width="stretch") or "Kiegyensúlyozott"
    fix_arany = L.KOCKAZATI_SZINT[szint]

    trend_jovo_ev = M.trend(naplo, "fwd_jovo_ev")
    vj = L.villamos_javaslat(hataridos_most, napi, ma, eves_aram, csucs_arany, fix_arany, trend_jovo_ev)
    gj = L.gaz_javaslat(hataridos_most, gaz, ma, eves_gaz)

    # Villamos energia kártya
    kozeli = []
    for e in vj["evek"]:
        if e["profil"]:
            becsult = " (becsült)" if e["csucs_becsult"] else ""
            kozeli.append(f"{e['ev']}: zsinór {hu(e['zsinor'])}, csúcs {hu(e['csucs'])}{becsult}, a mintára "
                          f"<b>{hu(e['profil'])} EUR/MWh</b> ({ft(e['profil'])} Ft/kWh)")
        else:
            kozeli.append(f"{e['ev']}: zsinór {hu(e['zsinor'])} EUR/MWh, csúcsár nélkül")
    if not kozeli:
        kozeli_html = ("<p>Még nincs beolvasott jegyzés. Addig a legközelebbi elérhető megoldás a HUPX másnapi "
                       "árához kötött (indexált) szerződés. Töltsd fel a kereskedő árlistáját a Határidős árak "
                       "fülön, és itt megjelenik a pontos keverék.</p>")
    else:
        kozeli_html = ('<p>Zsinór (base) és csúcs (peak) termék keveréke, az évek szerint:</p>' + lista(kozeli))
    k = vj["koltseg"]
    koltseg_html = ""
    if k:
        koltseg_html = lista([
            f"Minden fix: <b>{millio_ft(k['teljes_fix'])} millió Ft</b> ({eur_ezer(k['teljes_fix'])} ezer EUR)",
            f"Javasolt, {round(fix_arany * 100)} százalék fix: <b>{millio_ft(k['javasolt'])} millió Ft</b>; "
            f"a lebegő rész miatt {millio_ft(k['javasolt_legjobb'])} és {millio_ft(k['javasolt_legrosszabb'])} között",
            f"Minden másnapi áron: {millio_ft(k['teljes_spot'])} millió Ft; "
            f"{millio_ft(k['spot_legjobb'])} és {millio_ft(k['spot_legrosszabb'])} között",
        ]) + ('<p style="font-size:0.8rem;color:#6B7785">A sávok az elmúlt év legolcsóbb és legdrágább '
              '30 napos időszakát vetítik egy egész évre.</p>')
    terv_html = ""
    if vj["terv"]:
        terv_html = ("<p>A rögzítendő rész elosztva, hogy egyetlen rossz nap ára se döntse el az évet:</p>"
                     + lista([f"{t['felirat']}: {hu(t['resz'] * 100, 1)} százalék "
                              f"(összesen {hu(t['osszesen'] * 100, 1)})" for t in vj["terv"]]))
    villamos_html = javaslat_kartya("Villamos energia", [
        ("Az ideális termék",
         "<p>Fix árú, irodai mintára szabott termék: hétköznap nappal több, éjjel és hétvégén kevesebb "
         "energia, több részletben rögzíthető árral (sávos beszerzés). A déli, olcsó órák kihasználására "
         "a mennyiség egy része maradjon a másnapi árhoz kötve.<span class='ear-cimke nincs'>a tőzsdén "
         "nincs ilyen</span></p>"),
        ("Ami a piacon a legközelebb áll", kozeli_html),
        (f"Mennyibe kerülne {k['ev']}-ben?" if k else "", koltseg_html),
        ("Hogyan érdemes beszerezni?", terv_html),
        ("Mit mutatnak a számok?", "".join(f"<p>{m}</p>" for m in vj["mondatok"])),
    ])

    # Földgáz kártya
    gk_koltseg = ""
    if gj["koltseg"]:
        sorok_g = [f"Fix, a legközelebbi megoldással: <b>{millio_ft(gj['koltseg']['fix'])} millió Ft</b> "
                   f"({eur_ezer(gj['koltseg']['fix'])} ezer EUR)"]
        if gj["koltseg"]["spot"]:
            sorok_g.append(f"A mostani havi másnapi átlagárral: {millio_ft(gj['koltseg']['spot'])} millió Ft")
        gk_koltseg = lista(sorok_g)
    gaz_html = javaslat_kartya("Földgáz", [
        ("Az ideális termék",
         "<p>Fix árú, fűtési mintára szabott termék: télen sok, nyáron kevés gáz, a mennyiség a hőfoknaphoz "
         "igazodva rugalmasan változhat (swing). A negyedéves súlyok: I. "
         f"{round(B.GAZ_NEGYEDEVES_SULY[0] * 100)}, II. {round(B.GAZ_NEGYEDEVES_SULY[1] * 100)}, III. "
         f"{round(B.GAZ_NEGYEDEVES_SULY[2] * 100)}, IV. {round(B.GAZ_NEGYEDEVES_SULY[3] * 100)} százalék."
         "<span class='ear-cimke nincs'>a tőzsdén nincs ilyen</span></p>"),
        ("Ami a piacon a legközelebb áll",
         (f"<p><b>{hu(gj['ar'])} EUR/MWh</b> ({ft(gj['ar'])} Ft/kWh), {gj['megoldas']}."
          "<span class='ear-cimke van'>kereskedőnél kérhető</span></p>") if gj["ar"] is not None else ""),
        ("Mennyibe kerülne egy év?", gk_koltseg),
        ("Mit mutatnak a számok?", "".join(f"<p>{m}</p>" for m in gj["mondatok"])),
    ])
    k1, k2 = st.columns(2)
    k1.markdown(villamos_html, unsafe_allow_html=True)
    k2.markdown(gaz_html, unsafe_allow_html=True)

    if k:
        alcim(f"Három beszerzési mód, egy év villamosenergia-költsége ({k['ev']})",
              "Millió Ft; a vonal a lebegő rész lehetséges szórása az elmúlt év árai alapján")
        nevek = ["Minden fix", f"Javasolt ({round(fix_arany * 100)} százalék fix)", "Minden másnapi áron"]
        ertekek = [k["teljes_fix"], k["javasolt"], k["teljes_spot"]]
        also = [k["teljes_fix"], k["javasolt_legjobb"], k["spot_legjobb"]]
        felso = [k["teljes_fix"], k["javasolt_legrosszabb"], k["spot_legrosszabb"]]
        m = EUR_HUF / 1e6
        fig = go.Figure(go.Bar(
            x=nevek, y=[v * m for v in ertekek], marker_color=[SZ["tinta"], SZ["sargarez"], SZ["acel"]],
            width=0.5, text=[f"{hu(v * m, 1)} millió Ft" for v in ertekek], textposition="inside",
            insidetextanchor="start", textfont=dict(color="white", size=13),
            hovertemplate="%{x}: %{y:.1f} millió Ft<extra></extra>"))
        fig.add_scatter(x=nevek[1:], y=[v * m for v in ertekek[1:]], mode="markers",
                        marker=dict(size=1, color="rgba(0,0,0,0)"), hoverinfo="skip",
                        error_y=dict(type="data", symmetric=False,
                                     array=[(f - v) * m for f, v in zip(felso[1:], ertekek[1:])],
                                     arrayminus=[(v - a) * m for a, v in zip(also[1:], ertekek[1:])],
                                     color=SZ["tinta"], thickness=1.5, width=12))
        abra_alap(fig, 300)
        fig.update_layout(showlegend=False, hovermode="closest")
        fig.update_yaxes(rangemode="tozero")
        mutat(fig)

    st.markdown('<p class="ear-megj">Döntéstámogatás, nem ajánlat. A fix árak a kereskedők indikatív jegyzései, '
                'a másnapi árak a megtörtént piaci árak; előrejelzést egyik sem tartalmaz. Az összegek nettó '
                'energiaárak, rendszerhasználati díjak, adók és a kereskedői árrés nélkül.</p>',
                unsafe_allow_html=True)

    # ---- mit tanultunk eddig
    alcim("Mit tanultunk eddig?", "Minden frissítés feljegyzi, mi volt új; ezek összessége itt látszik")
    st.markdown('<div class="ear-tanulsag">' + "".join(f"<p>{m}</p>" for m in M.tanulsagok(naplo))
                + "</div>", unsafe_allow_html=True)

    t1, t2 = st.columns([3, 2])
    with t1:
        alcim("Mikor olcsó az áram egy átlagos napon?", "Az elmúlt 60 nap, a napi átlagtól való eltérés")
        if not profil60.empty and profil60["hetkoznap_rel"].notna().any():
            fig = go.Figure()
            fig.add_hrect(y0=-2, y1=0, fillcolor=SZ["csokkenes"], opacity=0.06, line_width=0, layer="below")
            fig.add_scatter(x=profil60["ora"], y=profil60["hetkoznap_rel"] * 100, name="Hétköznap",
                            mode="lines+markers", line=dict(color=SZ["tinta"], width=2.4, shape="spline"),
                            marker=dict(size=5), hovertemplate="%{x}:00 · %{y:+.0f} százalék<extra>Hétköznap</extra>")
            fig.add_scatter(x=profil60["ora"], y=profil60["hetvege_rel"] * 100, name="Hétvége",
                            mode="lines", line=dict(color=SZ["sargarez"], width=1.8, dash="dot", shape="spline"),
                            hovertemplate="%{x}:00 · %{y:+.0f} százalék<extra>Hétvége</extra>")
            abra_alap(fig, 280)
            fig.update_layout(hovermode="closest", legend=dict(y=1.08))
            fig.update_xaxes(dtick=3, range=[-0.5, 23.5], title=dict(text="óra", font=dict(size=11, color=SZ["acel"])))
            fig.update_yaxes(ticksuffix=" %", zerolinecolor=SZ["tinta"])
            mutat(fig)
        else:
            st.markdown('<p class="ear-megj">Ehhez még kevés a negyedórás adat.</p>', unsafe_allow_html=True)
    with t2:
        alcim("Hogyan mozdultak a mutatók?", "Napi egy érték, a frissítésekből")
        elerheto = {M.MUTATO_NEVEK[n]: n for n in M.MUTATO_NEVEK if len(M.mutato_idosor(naplo, n)) >= 2}
        if elerheto:
            valasztott_mutato = st.selectbox("Mutató", list(elerheto), label_visibility="collapsed",
                                             key="mutato_valaszto")
            sor = M.mutato_idosor(naplo, elerheto[valasztott_mutato])
            szazalek = elerheto[valasztott_mutato] in ("deli_sav", "negativ_arany", "gorbe_irany")
            fig = go.Figure(go.Scatter(x=pd.to_datetime(sor["nap"]), y=sor["ertek"] * (100 if szazalek else 1),
                                       mode="lines+markers", line=dict(color=SZ["tinta"], width=2),
                                       marker=dict(size=6, color=SZ["sargarez"]),
                                       hovertemplate="%{x|%Y. %m. %d.}: %{y:.2f}<extra></extra>"))
            abra_alap(fig, 230)
            datum_tengely(fig)
            fig.update_layout(showlegend=False, hovermode="closest")
            if szazalek:
                fig.update_yaxes(ticksuffix=" %")
            mutat(fig)
        else:
            st.markdown('<p class="ear-megj">A mutatók napi egy értékkel gyűlnek; a második naptól itt '
                        'látszik, merre mozdultak.</p>', unsafe_allow_html=True)

    with st.expander("A megfigyelési napló"):
        esemenyek = naplo[naplo["tema"] != "mutato"].tail(40).iloc[::-1] if not naplo.empty else naplo
        if esemenyek.empty:
            st.markdown('<p class="ear-megj">Még nincs feljegyzett esemény.</p>', unsafe_allow_html=True)
        else:
            st.dataframe(esemenyek[["idopont", "szoveg"]].rename(columns={"idopont": "Időpont", "szoveg": "Mi történt"}),
                         hide_index=True, width="stretch", height=300)
        if not tarolo().mukodik:
            st.markdown('<p class="ear-megj">A tároló nincs beállítva, ezért a napló az oldal bezárásával elvész.</p>',
                        unsafe_allow_html=True)

    alcim("Hol olvashatsz többet?", "Ingyenes, rendszeresen frissülő elemzések; a rövid távúak a napi, "
                                    "a hosszabbak az éves döntésekhez")
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

    alcim("Letöltés")
    st.download_button("Minden adat Excelben",
                       data=excel(napi, villamos, gaz, gaz_wd, st.session_state.get("hataridos", H.ures())),
                       file_name=f"energiaarak_{ma.isoformat()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="content")
    st.markdown('<p class="ear-megj">Források: Energy-Charts (Fraunhofer ISE, CC BY 4.0) és CEEGEX. '
                'A CEEGEX árai csak belső számításra használhatók, továbbadni vagy közzétenni nem szabad.<br>'
                f'Alkalmazás: {B.VERZIO}, {B.VERZIO_NAPJA}.</p>', unsafe_allow_html=True)
