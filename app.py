"""Magyar energiaárak: webes árpult. Az árakat megnyitáskor és a Frissítés gombra kéri le.

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
import forrasok as F
import hataridos as H
import szamitas as S

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
.block-container {{ max-width: 1080px; padding-top: 2.2rem; padding-bottom: 4rem; }}
h2, h3 {{ color: {SZ['tinta']}; font-weight: 600; letter-spacing: -0.01em; }}
.ear-cim {{ font-size: 1.05rem; font-weight: 600; color: {SZ['tinta']}; margin: 0; }}
.ear-frissites {{ font-size: 0.85rem; color: {SZ['acel']}; margin: 0.1rem 0 0 0; }}
.ear-nap {{ font-size: 0.95rem; color: {SZ['acel']}; margin: 1.4rem 0 0.2rem 0; }}
.ear-fo {{
  font-size: clamp(1.4rem, 3.4vw, 2.15rem); font-weight: 500; line-height: 1.22;
  color: {SZ['tinta']}; max-width: 30ch; margin: 0 0 1rem 0; letter-spacing: -0.015em;
  font-variant-numeric: tabular-nums;
}}
.ear-megj {{ font-size: 0.85rem; color: {SZ['acel']}; max-width: 70ch; }}
table.ear-tabla {{ width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; margin: 0.4rem 0 1.6rem 0; }}
table.ear-tabla th {{
  text-align: right; font-weight: 500; font-size: 0.8rem; color: {SZ['acel']};
  padding: 0.35rem 0.5rem; border-bottom: 1px solid {SZ['tinta']};
}}
table.ear-tabla th:first-child, table.ear-tabla td:first-child {{ text-align: left; padding-left: 0; }}
table.ear-tabla td {{
  text-align: right; padding: 0.55rem 0.5rem; border-bottom: 1px solid {SZ['vonal']};
  color: {SZ['tinta']}; font-size: 0.98rem;
}}
table.ear-tabla td.ear-kiemelt {{ font-weight: 600; }}
table.ear-tabla td small {{ color: {SZ['acel']}; font-size: 0.78rem; }}
.ear-fel {{ color: {SZ['emelkedes']}; font-weight: 600; }}
.ear-le {{ color: {SZ['csokkenes']}; font-weight: 600; }}
[data-baseweb="tab-list"] {{ gap: 1.4rem; }}
[data-baseweb="tab"] p {{ font-size: 1rem; }}
@media (max-width: 640px) {{
  .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
  table.ear-tabla td, table.ear-tabla th {{ padding-left: 0.25rem; padding-right: 0.25rem; }}
  table.ear-tabla td {{ font-size: 0.9rem; }}
}}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ formázás

def hu(x, tizedes: int = 2) -> str:
    if x is None or pd.isna(x):
        return "nincs adat"
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


def hu_datum(d, hetnap: bool = True) -> str:
    d = pd.Timestamp(d)
    alap = f"{HONAPOK[d.month - 1]} {d.day}."
    return f"{alap}, {NAPOK[d.weekday()]}" if hetnap else alap


def hu_rovid(d) -> str:
    d = pd.Timestamp(d)
    return f"{HONAPOK[d.month - 1][:3]}. {d.day}."


def tabla_html(fejlec: list[str], sorok: list[str]) -> str:
    th = "".join(f"<th>{escape(h)}</th>" for h in fejlec)
    return f'<table class="ear-tabla"><thead><tr>{th}</tr></thead><tbody>{"".join(sorok)}</tbody></table>'


def abra_alap(fig: go.Figure, magassag: int = 360) -> go.Figure:
    fig.update_layout(
        height=magassag, margin=dict(l=0, r=8, t=8, b=0), separators=", ",
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Archivo, system-ui, sans-serif", color=SZ["tinta"], size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, title=None),
        hovermode="x unified", hoverlabel=dict(bgcolor="white", font_color=SZ["tinta"]),
    )
    fig.update_xaxes(showgrid=False, linecolor=SZ["vonal"], ticks="outside", tickcolor=SZ["vonal"])
    fig.update_yaxes(gridcolor=SZ["kod"], zeroline=True, zerolinecolor=SZ["vonal"], ticksuffix=" ")
    return fig


def mutat(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "locale": "hu"})


# ------------------------------------------------------------------ adatlekérés

@st.cache_data(ttl=B.ELOZMENY_ELTARTHATOSAG, show_spinner=False)
def villamos_elozmeny(vegnap: date) -> pd.DataFrame:
    """Hosszú villamos előzmény. Ritkán változik, ezért órákig megőrizzük."""
    return F.leker_villamos(vegnap - timedelta(days=B.ELOZMENY_NAP), vegnap)


@st.cache_data(ttl=B.FRISS_ELTARTHATOSAG, show_spinner=False)
def villamos_friss(ma: date) -> pd.DataFrame:
    """A legutóbbi napok és a holnapi ár."""
    return F.leker_villamos(ma - timedelta(days=B.FRISS_NAP), ma + timedelta(days=1))


@st.cache_data(ttl=B.FRISS_ELTARTHATOSAG, show_spinner=False)
def gaz_adatok(ma: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    return F.leker_gaz_masnapi(), F.leker_gaz_napon_belul()


def betolt(ma: date) -> dict:
    """Minden forrás lekérése. Ha egy forrás hibázik, a többi adata akkor is megjelenik."""
    ki = {"villamos": F.ures(F.VILLAMOS_OSZLOPOK), "gaz": F.ures(F.GAZ_MASNAPI_OSZLOPOK),
          "gaz_wd": F.ures(F.GAZ_NAPON_BELUL_OSZLOPOK), "hibak": []}
    try:
        friss = villamos_friss(ma)
        try:
            elozmeny = villamos_elozmeny(ma - timedelta(days=B.FRISS_NAP + 1))
        except Exception as e:
            elozmeny = None
            ki["hibak"].append(f"Villamos előzmény: {e}")
        ki["villamos"] = F.egyesit([elozmeny, friss], "unix")
    except Exception as e:
        ki["hibak"].append(f"Energy-Charts: {e}")
    try:
        ki["gaz"], ki["gaz_wd"] = gaz_adatok(ma)
    except Exception as e:
        ki["hibak"].append(f"CEEGEX: {e}")
    return ki


def mindent_ujra() -> None:
    villamos_friss.clear()
    gaz_adatok.clear()


# ------------------------------------------------------------------ fejléc

most = pd.Timestamp.now(tz=B.IDOZONA)
ma, holnap = most.date(), most.date() + timedelta(days=1)

fej_bal, fej_jobb = st.columns([4, 1], vertical_alignment="center")
with fej_bal:
    st.markdown('<p class="ear-cim">Magyar energiaárak</p>', unsafe_allow_html=True)
    hely = st.empty()
with fej_jobb:
    if st.button("Frissítés", width="stretch"):
        mindent_ujra()
        st.rerun()

with st.spinner("Árak lekérése..."):
    adat = betolt(ma)
hely.markdown(f'<p class="ear-frissites">Lekérve {most.strftime("%H:%M")}-kor, budapesti idő szerint</p>',
              unsafe_allow_html=True)

villamos, gaz, gaz_wd = adat["villamos"], adat["gaz"], adat["gaz_wd"]
if adat["hibak"]:
    st.warning("Nem minden forrás válaszolt. Próbáld meg újra a Frissítés gombbal.\n\n"
               + "\n\n".join(adat["hibak"]))

napi = S.napi_osszesites(villamos)
napi_terkep = napi.set_index("nap") if not napi.empty else pd.DataFrame(columns=S.NAPI_OSZLOPOK).set_index("nap")

lap_villamos, lap_gaz, lap_hataridos, lap_elozmeny = st.tabs(
    ["Villamos energia", "Földgáz", "Határidős árak", "Előzmények és letöltés"])


# ------------------------------------------------------------------ villamos

def napi_ertek(nap: date, oszlop: str):
    kulcs = nap.isoformat()
    return napi_terkep.at[kulcs, oszlop] if kulcs in napi_terkep.index else None


with lap_villamos:
    if villamos.empty:
        st.info("Most nem érkezett villamos ár. Próbáld meg újra a Frissítés gombbal.")
    else:
        van_holnap = napi_ertek(holnap, "zsinor") is not None
        fo_nap = holnap if van_holnap else ma
        zs_fo, zs_ma = napi_ertek(fo_nap, "zsinor"), napi_ertek(ma, "zsinor")

        st.markdown(f'<p class="ear-nap">{"Holnap" if van_holnap else "Ma"}, {hu_datum(fo_nap)}</p>',
                    unsafe_allow_html=True)
        if zs_fo is None:
            mondat = "Erre a napra még nincs teljes másnapi ár."
        elif van_holnap and zs_ma is not None:
            v = S.valtozas(zs_fo, zs_ma)
            irany = "drágább" if v > 0.0005 else "olcsóbb" if v < -0.0005 else "ugyanannyi"
            mondat = (f"A zsinórár {hu(zs_fo)} EUR/MWh, {hu_szazalek(v, jel=False)}-kal {irany}, mint ma."
                      if irany != "ugyanannyi" else f"A zsinórár {hu(zs_fo)} EUR/MWh, ugyanannyi, mint ma.")
        else:
            mondat = f"A zsinórár {hu(zs_fo)} EUR/MWh."
        st.markdown(f'<p class="ear-fo">{mondat}</p>', unsafe_allow_html=True)

        # Negyedórás görbe: ma és holnap, csúcsidő sávval
        fig = go.Figure()
        fig.add_vrect(x0=f"2000-01-01 {B.CSUCS_KEZDET:02d}:00", x1=f"2000-01-01 {B.CSUCS_VEGE:02d}:00",
                      fillcolor=SZ["sargarez"], opacity=0.09, line_width=0, layer="below",
                      annotation_text="csúcsidő", annotation_position="top left",
                      annotation_font=dict(color=SZ["sargarez"], size=12))
        for nap, nev, szin, vastag in [(ma, f"Ma, {hu_rovid(ma)}", SZ["acel"], 1.6),
                                       (holnap, f"Holnap, {hu_rovid(holnap)}", SZ["tinta"], 2.4)]:
            resz = villamos[villamos["nap"] == nap.isoformat()]
            if resz.empty:
                continue
            fig.add_scatter(x=pd.to_datetime("2000-01-01 " + resz["negyedora"]), y=resz["ar"], name=nev,
                            mode="lines", line=dict(color=szin, width=vastag, shape="hv"),
                            hovertemplate="%{y:.2f} EUR/MWh<extra>" + nev + "</extra>")
        abra_alap(fig, 380)
        fig.update_xaxes(tickformat="%H:%M", dtick=3 * 3600 * 1000,
                         range=["2000-01-01 00:00", "2000-01-02 00:00"])
        fig.update_yaxes(title=dict(text="EUR/MWh", font=dict(size=12, color=SZ["acel"])))
        mutat(fig)
        if not van_holnap:
            st.markdown('<p class="ear-megj">A holnapi másnapi ár általában 13 óra körül jelenik meg. '
                        'Ha még nem látszik, nézz vissza később, és nyomd meg a Frissítés gombot.</p>',
                        unsafe_allow_html=True)

        # Árlap
        csucs_nev = f"Csúcs, {B.CSUCS_KEZDET} és {B.CSUCS_VEGE} óra között"
        sorok = []
        for nev, oszlop in [("Zsinór", "zsinor"), (csucs_nev, "csucs"), ("Csúcson kívüli", "csucson_kivul")]:
            a, b = napi_ertek(ma, oszlop), napi_ertek(holnap, oszlop)
            kiemelt = ' class="ear-kiemelt"' if oszlop == "zsinor" else ""
            sorok.append(f"<tr><td>{nev}</td><td{kiemelt}>{hu(a)}</td><td{kiemelt}>{hu(b) if b is not None else ''}</td>"
                         f"{valtozas_cella(S.valtozas(b, a))}</tr>")
        for nev, ar_o, ido_o in [("Legolcsóbb negyedóra", "min_ar", "min_ido"),
                                 ("Legdrágább negyedóra", "max_ar", "max_ido")]:
            cellak = []
            for nap in (ma, holnap):
                ar = napi_ertek(nap, ar_o)
                cellak.append(f"<td>{hu(ar)} <small>{napi_ertek(nap, ido_o)}</small></td>" if ar is not None else "<td></td>")
            sorok.append(f"<tr><td>{nev}</td>{''.join(cellak)}<td></td></tr>")
        st.markdown(tabla_html(["EUR/MWh", f"Ma, {hu_rovid(ma)}", f"Holnap, {hu_rovid(holnap)}", "Változás"], sorok),
                    unsafe_allow_html=True)

        # Időszaki átlagok
        st.subheader("Időszaki átlagok")
        atl = S.idoszaki_atlagok(napi, ma)
        sorok = [f"<tr><td>{r.idoszak} <small>{hu_rovid(r.tol)} és {hu_rovid(r.ig)} között</small></td>"
                 f"<td>{hu(r.zsinor)}</td><td>{hu(r.csucs)}</td><td>{r.napok}</td></tr>"
                 for r in atl.itertuples() if r.napok]
        st.markdown(tabla_html(["EUR/MWh", "Zsinór", "Csúcs", "Napok"], sorok), unsafe_allow_html=True)

        # Trend
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
                        line=dict(color=SZ["acel"], width=1.2), hovertemplate="%{y:.2f}")
        fig.add_scatter(x=t["datum"], y=t["het_atlag"], name="7 napos átlag", mode="lines",
                        line=dict(color=SZ["tinta"], width=2.4), hovertemplate="%{y:.2f}")
        fig.add_scatter(x=t["datum"], y=t["csucs"], name="Csúcs", mode="lines", visible="legendonly",
                        line=dict(color=SZ["sargarez"], width=1.4), hovertemplate="%{y:.2f}")
        abra_alap(fig, 320)
        mutat(fig)


# ------------------------------------------------------------------ gáz

with lap_gaz:
    k = S.gaz_kulcsszamok(gaz)
    if k["da"] is None:
        st.info("Most nem érkezett CEEGEX gázár. Próbáld meg újra a Frissítés gombbal.")
    else:
        da = k["da"]
        st.markdown(f'<p class="ear-nap">Másnapi termék, szállítás {hu_datum(da["szallitas_kezdete"][:10])}</p>',
                    unsafe_allow_html=True)
        v = S.valtozas(da["atlagar"], k["da_elozo"]["atlagar"]) if k["da_elozo"] else None
        if v is None:
            mondat = f"A legutóbbi másnapi ár {hu(da['atlagar'])} EUR/MWh."
        else:
            irany = "magasabb" if v > 0.0005 else "alacsonyabb" if v < -0.0005 else None
            mondat = (f"A legutóbbi másnapi ár {hu(da['atlagar'])} EUR/MWh, "
                      + (f"{hu_szazalek(v, jel=False)}-kal {irany}, mint az előző kereskedési napon."
                         if irany else "ugyanannyi, mint az előző kereskedési napon."))
        st.markdown(f'<p class="ear-fo">{mondat}</p>', unsafe_allow_html=True)

        def gaz_sor(nev, r, viszonyitas=None):
            if r is None:
                return ""
            ceerep = hu(r.get("ceerep")) if pd.notna(r.get("ceerep")) else ""
            valt = valtozas_cella(S.valtozas(viszonyitas, r["atlagar"])) if viszonyitas is not None else "<td></td>"
            return (f"<tr><td>{nev} <small>{hu_rovid(r['kereskedesi_nap'])} kereskedés</small></td>"
                    f"<td class='ear-kiemelt'>{hu(r['atlagar'])}</td><td>{ceerep}</td>{valt}</tr>")

        sorok = [gaz_sor("Másnapi, legutóbbi", da),
                 gaz_sor("Másnapi, előző nap", k["da_elozo"], da["atlagar"]),
                 gaz_sor("Másnapi, 5 kereskedési nappal korábban", k["da_het"], da["atlagar"]),
                 gaz_sor("Hétvégi termék", k["hetvege"])]
        if not gaz_wd.empty:
            utolso = gaz_wd.sort_values(["gaznap", "gazora"]).iloc[-1]
            sorok.append(f"<tr><td>Napon belüli, futó átlag <small>{hu_rovid(utolso['gaznap'])} gáznap, "
                         f"{int(utolso['gazora'])}. gázóráig</small></td><td class='ear-kiemelt'>{hu(utolso['atlagar'])}</td>"
                         f"<td></td>{valtozas_cella(S.valtozas(utolso['atlagar'], da['atlagar']))}</tr>")
        st.markdown(tabla_html(["EUR/MWh", "Átlagár", "CEEREP", "Legutóbbihoz képest"], sorok),
                    unsafe_allow_html=True)
        st.markdown('<p class="ear-megj">A napon belüli sor változása a legutóbbi másnapi árhoz viszonyít. '
                    'A gáznap reggel 6 órától másnap reggel 6 óráig tart.</p>', unsafe_allow_html=True)

        st.subheader("Másnapi ár és CEEREP")
        d = gaz[gaz["termek"] == "DA"].copy()
        d["datum"] = pd.to_datetime(d["kereskedesi_nap"])
        fig = go.Figure()
        fig.add_scatter(x=d["datum"], y=d["atlagar"], name="Másnapi átlagár", mode="lines+markers",
                        line=dict(color=SZ["tinta"], width=2.2), marker=dict(size=4), connectgaps=True,
                        hovertemplate="%{y:.2f}")
        fig.add_scatter(x=d["datum"], y=d["ceerep"], name="CEEREP", mode="markers",
                        marker=dict(color=SZ["sargarez"], size=6, symbol="diamond"), hovertemplate="%{y:.2f}")
        abra_alap(fig, 320)
        mutat(fig)
        st.markdown('<p class="ear-megj">A CEEGEX annyi kereskedési napot tesz közzé, amennyi az oldalán '
                    'éppen szerepel, jellemzően néhány hónapot. Hosszabb gázár-előzményhez töltsd le '
                    'rendszeresen az Excelt.</p>', unsafe_allow_html=True)

        if not gaz_wd.empty:
            st.subheader("Napon belüli piac, halmozott átlagár gázóránként")
            fig = go.Figure()
            r = gaz_wd.sort_values("gazora")
            nev = f"{hu_rovid(r.iloc[0]['gaznap'])} gáznap"
            fig.add_scatter(x=r["gazora"], y=r["atlagar"], name=nev, mode="lines+markers",
                            line=dict(color=SZ["tinta"], width=2, shape="hv"), marker=dict(size=5),
                            hovertemplate="%{x}. gázóra: %{y:.2f}<extra>" + nev + "</extra>")
            abra_alap(fig, 280)
            fig.update_layout(hovermode="closest", showlegend=False)
            fig.update_xaxes(range=[0.5, 24.5], dtick=3, title=dict(text="gázóra", font=dict(size=12, color=SZ["acel"])))
            mutat(fig)


# ------------------------------------------------------------------ határidős árak

HATARIDOS_FAJL = "hataridos.csv"


@st.cache_data(show_spinner=False)
def hataridos_mentett(belyeg: float) -> pd.DataFrame:
    return H.olvas(HATARIDOS_FAJL)


def hataridos_belyeg() -> float:
    from pathlib import Path
    f = Path(HATARIDOS_FAJL)
    return f.stat().st_mtime if f.exists() else 0.0


def azonnali_arak() -> dict:
    """Mai azonnali árak és a 30 napos átlag, a határidős árak viszonyítási alapjául."""
    ki = {"Villamos|Zsinór": None, "Villamos|Csúcs": None, "Gáz|Alap": None,
          "Villamos|Zsinór|30": None, "Villamos|Csúcs|30": None, "Gáz|Alap|30": None}
    if not napi.empty:
        mai = napi[napi["nap"] == ma.isoformat()]
        if not mai.empty:
            ki["Villamos|Zsinór"] = mai.iloc[0]["zsinor"]
            ki["Villamos|Csúcs"] = mai.iloc[0]["csucs"]
        utolso30 = napi[napi["nap"] <= ma.isoformat()].tail(30)
        if not utolso30.empty:
            ki["Villamos|Zsinór|30"] = round(utolso30["zsinor"].mean(), 2)
            ki["Villamos|Csúcs|30"] = round(utolso30["csucs"].mean(), 2)
    kulcs = S.gaz_kulcsszamok(gaz)
    if kulcs["da"]:
        ki["Gáz|Alap"] = kulcs["da"]["atlagar"]
    if not gaz.empty:
        da = gaz[(gaz["termek"] == "DA") & gaz["atlagar"].notna()].sort_values("kereskedesi_nap").tail(21)
        if not da.empty:
            ki["Gáz|Alap|30"] = round(da["atlagar"].mean(), 2)
    return ki


with lap_hataridos:
    if "hataridos" not in st.session_state:
        st.session_state.hataridos = H.egyesit(H.ures(), hataridos_mentett(hataridos_belyeg()))
    tarolt = st.session_state.hataridos

    st.markdown('<p class="ear-nap">Határidős árak</p>', unsafe_allow_html=True)
    st.markdown('<p class="ear-fo">Írd be a kereskedőtől kapott jegyzéseket, és lásd, hol állnak '
                'az azonnali árhoz képest.</p>', unsafe_allow_html=True)
    st.markdown('<p class="ear-megj">A magyar határidős jegyzéseket a tőzsdék csak előfizetéssel adják '
                'ki gépi lekérésre, ezért ezeket kézzel kell megadni. A napi árlista a legtöbb '
                'energiakereskedőtől díjmentesen kérhető. Csak azokat a sorokat töltsd ki, amelyekre '
                'kaptál árat; a többi maradhat üresen.</p>', unsafe_allow_html=True)

    with st.expander("Árak megadása és mentése", expanded=tarolt.empty):
        feltoltott = st.file_uploader("Korábban mentett hataridos.csv betöltése", type="csv")
        if feltoltott is not None:
            st.session_state.hataridos = H.egyesit(st.session_state.hataridos, H.olvas(feltoltott))
            tarolt = st.session_state.hataridos
            st.success(f"{len(tarolt)} mentett jegyzés betöltve.")

        jegyzes_nap = st.date_input("Jegyzés napja", value=ma, max_value=ma, format="YYYY.MM.DD",
                                    key="hataridos_nap")
        alap = H.alap_termekek(jegyzes_nap)
        korabbi = tarolt[tarolt["jegyzes_nap"] == jegyzes_nap.isoformat()]
        if not korabbi.empty:
            alap = H.egyesit(alap, korabbi)
            alap = alap[alap["jegyzes_nap"] == jegyzes_nap.isoformat()]
            hiany = H.alap_termekek(jegyzes_nap)
            alap = pd.concat([alap, hiany]).drop_duplicates(["piac", "termek", "tipus"], keep="first")
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
            hide_index=True, width="stretch", height=420, key="hataridos_szerkeszto")

        if st.button("Jegyzések rögzítése", type="primary"):
            uj = alap.copy()
            uj["ar"] = pd.to_numeric(szerkesztett["ar"], errors="coerce").values
            uj["jegyzes_nap"] = jegyzes_nap.isoformat()
            st.session_state.hataridos = H.egyesit(st.session_state.hataridos, uj)
            st.success(f"{int(uj['ar'].notna().sum())} ár rögzítve erre a napra.")
            st.rerun()

        st.markdown('<p class="ear-megj">A böngészőben rögzített árak az oldal bezárásáig élnek. '
                    'Ha meg akarod őrizni őket, töltsd le a fájlt, és tedd fel a GitHub-tárolóba '
                    'hataridos.csv néven; onnan az alkalmazás magától beolvassa.</p>',
                    unsafe_allow_html=True)
        st.download_button("hataridos.csv letöltése", data=H.csv_bajtok(st.session_state.hataridos),
                           file_name=HATARIDOS_FAJL, mime="text/csv", width="content",
                           disabled=st.session_state.hataridos.empty)

    tarolt = st.session_state.hataridos
    if tarolt.empty:
        st.info("Még nincs rögzített határidős ár. Nyisd ki a fenti panelt, és írd be a jegyzéseket.")
    else:
        azonnali = azonnali_arak()
        for piac, egyseg in [("Villamos", "Villamos energia"), ("Gáz", "Földgáz")]:
            g = H.gorbe(tarolt, piac)
            if g.empty:
                continue
            st.subheader(egyseg)
            st.markdown(f'<p class="ear-megj">Jegyzés napja: {hu_datum(g.iloc[0]["jegyzes_nap"])}.</p>',
                        unsafe_allow_html=True)

            sorok = []
            for r in g.itertuples():
                alap_ar = azonnali.get(f"{piac}|{r.tipus}")
                atlag30 = azonnali.get(f"{piac}|{r.tipus}|30")
                sorok.append(
                    f"<tr><td>{r.termek} <small>{r.tipus.lower()}, {hu_rovid(r.szallitas_kezdete)} és "
                    f"{hu_rovid(r.szallitas_vege)} között</small></td>"
                    f"<td class='ear-kiemelt'>{hu(r.ar)}</td>"
                    f"{valtozas_cella(H.felar(r.ar, alap_ar))}"
                    f"{valtozas_cella(H.felar(r.ar, atlag30))}</tr>")
            st.markdown(tabla_html(["EUR/MWh", "Határidős ár", "Azonnali árhoz", "Utóbbi hónaphoz"], sorok),
                        unsafe_allow_html=True)

            fig = go.Figure()
            for tipus, szin in [("Zsinór", SZ["tinta"]), ("Csúcs", SZ["sargarez"]), ("Alap", SZ["tinta"])]:
                resz = g[g["tipus"] == tipus]
                if resz.empty:
                    continue
                fig.add_scatter(x=pd.to_datetime(resz["szallitas_kezdete"]), y=resz["ar"], name=tipus,
                                mode="lines+markers", line=dict(color=szin, width=2.2, shape="hv"),
                                marker=dict(size=7), text=resz["termek"],
                                hovertemplate="%{text}: %{y:.2f} EUR/MWh<extra></extra>")
            mai_ar = azonnali.get(f"{piac}|{'Zsinór' if piac == 'Villamos' else 'Alap'}")
            if mai_ar is not None and pd.notna(mai_ar):
                fig.add_hline(y=float(mai_ar), line=dict(color=SZ["acel"], width=1.2, dash="dot"),
                              annotation_text="mai azonnali ár", annotation_position="top left",
                              annotation_font=dict(color=SZ["acel"], size=12))
            abra_alap(fig, 320)
            fig.update_layout(hovermode="closest")
            fig.update_yaxes(title=dict(text="EUR/MWh", font=dict(size=12, color=SZ["acel"])))
            mutat(fig)

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
                            line=dict(color=SZ["tinta"], width=2.2), marker=dict(size=6),
                            hovertemplate="%{y:.2f} EUR/MWh")
            abra_alap(fig, 280)
            fig.update_layout(showlegend=False, hovermode="closest")
            mutat(fig)


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
        v.drop(columns=["unix"]).rename(columns={"ido": "Időpont", "nap": "Szállítási nap", "negyedora": "Negyedóra",
                                                 "ora": "Óra", "ar": "Ár (EUR/MWh)", "perc": "Időtartam (perc)"}
                                        ).to_excel(iro, sheet_name="Villamos 15 perc", index=False)
        g.drop(columns=["kulcs"]).to_excel(iro, sheet_name="Gáz másnapi", index=False)
        w.drop(columns=["kulcs"]).to_excel(iro, sheet_name="Gáz napon belüli", index=False)
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
        valasztott = st.date_input("Szállítási nap", value=date.fromisoformat(napok_listaja[-1]),
                                   min_value=date.fromisoformat(napok_listaja[0]),
                                   max_value=date.fromisoformat(napok_listaja[-1]), format="YYYY.MM.DD")
        resz = villamos[villamos["nap"] == valasztott.isoformat()]
        if resz.empty:
            st.info(f"{hu_datum(valasztott)}: erre a napra nem érkezett ár.")
        else:
            st.markdown(f'<p class="ear-fo">{hu_datum(valasztott)}: zsinór '
                        f'{hu(napi_ertek(valasztott, "zsinor"))}, csúcs '
                        f'{hu(napi_ertek(valasztott, "csucs"))} EUR/MWh.</p>', unsafe_allow_html=True)
            fig = go.Figure()
            fig.add_scatter(x=pd.to_datetime("2000-01-01 " + resz["negyedora"]), y=resz["ar"], mode="lines",
                            line=dict(color=SZ["tinta"], width=2, shape="hv"), name=hu_rovid(valasztott),
                            hovertemplate="%{y:.2f} EUR/MWh")
            abra_alap(fig, 300)
            fig.update_xaxes(tickformat="%H:%M", dtick=3 * 3600 * 1000)
            fig.update_layout(showlegend=False)
            mutat(fig)
            st.dataframe(resz[["negyedora", "ar", "perc"]].rename(
                columns={"negyedora": "Negyedóra", "ar": "Ár (EUR/MWh)", "perc": "Időtartam (perc)"}),
                hide_index=True, width="stretch", height=300)

    st.subheader("Letöltés")
    st.markdown('<p class="ear-megj">Az Excel a most lekért adatokat tartalmazza: a villamos negyedórás '
                'árakat és napi összesítésüket, a gázárakat, és ha megadtál ilyet, a határidős jegyzéseket.</p>', unsafe_allow_html=True)
    st.download_button("Letöltés Excelben", data=excel(napi, villamos, gaz, gaz_wd, st.session_state.get("hataridos", H.ures())),
                       file_name=f"energiaarak_{ma.isoformat()}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       width="content")

    st.markdown('<p class="ear-megj">Források: Energy-Charts (Fraunhofer ISE, CC BY 4.0) és CEEGEX. '
                'A CEEGEX árai csak belső számításra használhatók, továbbadni vagy közzétenni nem szabad. '
                f'Csúcsidő: {B.CSUCS_KEZDET} és {B.CSUCS_VEGE} óra között, minden nap.</p>',
                unsafe_allow_html=True)
