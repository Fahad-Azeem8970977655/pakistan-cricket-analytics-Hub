"""Look & feel: colours, CSS, KPI cards, Plotly template and chart helper."""
import base64
import html
from functools import lru_cache
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

GREEN, DARK, GOLD = "#0B6B3A", "#073B21", "#C9A227"
INK, MUTED, GRID = "#1B2A24", "#5F6F68", "#E6ECE8"
RES_COLORS = {"Won": "#0B8A4B", "Lost": "#D64545", "Tied": "#E5A100", "Draw": "#8A949C", "No result": "#C3CBD0"}
FMT_COLORS = {"Test": "#B7791F", "ODI": "#2A7AB9", "T20I": "#0B6B3A"}
SIDE_COLORS = {"Pakistan": "#0B6B3A", "Opposition": "#D64545"}
COLORWAY = ["#0B6B3A", "#2A7AB9", "#C9A227", "#D64545", "#7B5EA7", "#2FA39A", "#E07B39", "#6B7A86"]
# Colour scales whose LOW end is still clearly visible on a white card (the built-in Greens / YlOrRd start almost white)
SEQ_GREEN = [[0, "#7CCB9B"], [0.5, "#1E9A5A"], [1, "#073B21"]]
SEQ_RED = [[0, "#F2958B"], [0.5, "#D64545"], [1, "#7A1212"]]
SEQ_ORANGE = [[0, "#F5B66A"], [0.5, "#E07B39"], [1, "#8A3B0A"]]
SEQ_BLUE = [[0, "#8DBFE8"], [0.5, "#2A7AB9"], [1, "#0F3F6B"]]
DIV = [[0, "#C0392B"], [0.5, "#F0B429"], [1, "#0B8A4B"]]      # red -> amber -> green (amber stays visible)
DIV_R = [[0, "#0B8A4B"], [0.5, "#F0B429"], [1, "#C0392B"]]

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FONT = "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

pio.templates["pak"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, size=12, color=INK), colorway=COLORWAY, paper_bgcolor="white", plot_bgcolor="white",
    title=dict(font=dict(size=15, color=DARK), x=0.01, xanchor="left", y=0.96, yref="container"),
    margin=dict(l=60, r=30, t=95, b=55),
    xaxis=dict(gridcolor=GRID, linecolor="#C9D3CE", zeroline=False, title=dict(font=dict(size=12, color=MUTED)), automargin=True),
    yaxis=dict(gridcolor=GRID, linecolor="#C9D3CE", zeroline=False, title=dict(font=dict(size=12, color=MUTED)), automargin=True),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11), title=dict(font=dict(size=11, color=MUTED), side="left")),
    hoverlabel=dict(bgcolor="white", font=dict(family=FONT, size=12), bordercolor="#C9D3CE"),
    coloraxis=dict(colorbar=dict(thickness=12, outlinewidth=0, title=dict(font=dict(size=11, color=MUTED)))),
    bargap=0.25))
pio.templates.default = "pak"

@lru_cache(maxsize=1)
def background():
    """(data-URI, is_user_photo). Put your own picture at assets/background.jpg (or .png/.webp) to replace the built-in stadium art."""
    for ext, mime in (("jpg", "image/jpeg"), ("jpeg", "image/jpeg"), ("png", "image/png"), ("webp", "image/webp")):
        p = ASSETS / f"background.{ext}"
        if p.exists():
            return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode(), True
    p = ASSETS / "hero_default.svg"
    if p.exists():
        return "data:image/svg+xml;base64," + base64.b64encode(p.read_bytes()).decode(), False
    return "", False


def logo_path():
    for name in ("logo_light.svg", "logo.svg"):   # light version is made for the dark sidebar
        p = ASSETS / name
        if p.exists():
            return str(p)
    return None


def _css():
    uri, user = background()
    art = f', url("{uri}")' if uri else ""
    page_overlay = 0.90 if user else 0.94
    return CSS.replace("__ART__", art).replace("__OVERLAY__", str(page_overlay)).replace("__URI__", f'url("{uri}")' if uri else "none")


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp {{ font-family: {FONT}; }}
[data-testid="stAppViewContainer"] {{ background-image: linear-gradient(rgba(240,246,242,__OVERLAY__), rgba(240,246,242,__OVERLAY__)), __URI__;
  background-size: cover; background-position: center bottom; background-attachment: fixed; background-color: #F0F6F2; }}
.stApp {{ background: transparent; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1500px; }}
[data-testid="stHeader"] {{ background: transparent; }}
.hero {{ position: relative; color:#fff; padding: 26px 30px 22px 30px; border-radius: 16px; margin-bottom: 18px; min-height: 132px;
  border-bottom: 5px solid {GOLD}; box-shadow: 0 6px 18px rgba(3,35,19,.25);
  background-image: linear-gradient(95deg, rgba(2,26,15,.97) 0%, rgba(3,44,25,.90) 40%, rgba(6,80,44,.45) 75%, rgba(6,80,44,.12) 100%)__ART__;
  background-size: cover; background-position: center right; background-color: {DARK}; }}
.hero h1 {{ color:#FFFFFF; font-size: 1.85rem; font-weight: 800; margin: 0; padding: 0; letter-spacing: -.01em; text-shadow: 0 2px 8px rgba(0,0,0,.55); }}
.hero p {{ color: #E4F4EA; margin: 6px 0 0 0; font-size: .95rem; max-width: 760px; text-shadow: 0 1px 6px rgba(0,0,0,.6); }}
.chips {{ margin-top: 12px; }}
.chip {{ display:inline-block; background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.55); color:#FFFFFF; font-size:.74rem; font-weight:600;
  padding: 3px 11px; border-radius: 999px; margin-right: 7px; backdrop-filter: blur(2px); }}
.kpi {{ background:#fff; border:1px solid #E1E9E4; border-left:5px solid {GREEN}; border-radius:10px; padding:12px 14px 10px 14px;
  box-shadow: 0 1px 2px rgba(7,59,33,.05); height: 100%; height: 122px; overflow: hidden; }}
.kpi.gold {{ border-left-color:{GOLD}; }} .kpi.red {{ border-left-color:#D64545; }} .kpi.blue {{ border-left-color:#2A7AB9; }} .kpi.grey {{ border-left-color:#8A949C; }}
.kpi .l {{ font-size:.70rem; font-weight:700; letter-spacing:.07em; text-transform:uppercase; color:{MUTED}; }}
.kpi .v {{ font-size:1.65rem; font-weight:800; color:{DARK}; line-height:1.15; margin-top:2px; }}
.kpi .s {{ font-size:.76rem; color:{MUTED}; margin-top:1px; }}
.kpi .s.up {{ color:#0B8A4B; font-weight:600; }} .kpi .s.down {{ color:#D64545; font-weight:600; }}
.sec {{ font-size:1.05rem; font-weight:700; color:{DARK}; margin: 22px 0 6px 0; padding-bottom:4px; border-bottom:2px solid #DCE7E0; }}
.sec small {{ font-weight:500; color:{MUTED}; font-size:.8rem; margin-left:8px; }}
.pill {{ display:inline-block; width:30px; height:30px; line-height:30px; border-radius:50%; text-align:center; color:#fff;
  font-weight:700; font-size:.8rem; margin-right:5px; }}
.note {{ background:#fff; border:1px solid #E1E9E4; border-radius:10px; padding:10px 14px; color:{MUTED}; font-size:.85rem; }}
div[data-testid="stPlotlyChart"] {{ background:#fff; border:1px solid #E1E9E4; border-radius:12px; padding:0; overflow:hidden;
  box-shadow: 0 1px 2px rgba(7,59,33,.04); }}
div[data-testid="stPlotlyChart"] > div, div[data-testid="stPlotlyChart"] .js-plotly-plot {{ width:100% !important; }}
div[data-testid="stDataFrame"] {{ border:1px solid #E1E9E4; border-radius:10px; overflow:hidden; }}
button[data-baseweb="tab"] {{ font-weight:700; font-size:.95rem; }}
div[data-testid="stExpander"] {{ background:#fff; border:1px solid #E1E9E4; border-radius:10px; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color:{GREEN}; }}
div[data-baseweb="tab-highlight"] {{ background-color:{GREEN} !important; }}
/* ---------------- dark navy sidebar ---------------- */
[data-testid="stSidebar"] {{ background: linear-gradient(185deg, #07162A 0%, #0C2742 52%, #11375C 100%); border-right: 1px solid #1D4570; border-top: 5px solid {GOLD};
  box-shadow: 4px 0 16px rgba(5,20,40,.25); }}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ scrollbar-color: #3B6591 transparent; }}
[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{ padding-bottom: 6px; }}
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] span {{ color: #E6EEF7 !important; }}
/* navigation */
[data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"], [data-testid="stSidebarNav"] [data-testid="stNavSectionHeader"] * {{ color: #8FB0D3 !important; font-size: .70rem !important;
  font-weight: 800 !important; letter-spacing: .13em; text-transform: uppercase; }}
a[data-testid="stSidebarNavLink"] {{ border-radius: 9px; margin: 1px 0; border-left: 3px solid transparent; }}
a[data-testid="stSidebarNavLink"], a[data-testid="stSidebarNavLink"] span, a[data-testid="stSidebarNavLink"] p {{ color: #E8F0F8 !important; }}
a[data-testid="stSidebarNavLink"]:hover {{ background: rgba(255,255,255,.09); }}
a[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: linear-gradient(90deg, rgba(227,194,90,.28), rgba(227,194,90,.06)); border-left: 3px solid {GOLD}; }}
a[data-testid="stSidebarNavLink"][aria-current="page"] span, a[data-testid="stSidebarNavLink"][aria-current="page"] p {{ color: #FFFFFF !important; font-weight: 700; }}
[data-testid="stSidebarNavViewButton"], [data-testid="stSidebarNavViewButton"] * {{ color: #E3C25A !important; font-weight: 600; }}
[data-testid="stSidebarNavSeparator"] {{ border-color: rgba(255,255,255,.18) !important; }}
/* filters */
.side-title {{ color: #E3C25A; font-size: .78rem; font-weight: 800; letter-spacing: .16em; margin: 4px 0 6px 0; padding-bottom: 5px; border-bottom: 1px solid rgba(255,255,255,.22); }}
.side-count {{ color: #CFE0F1; font-size: .80rem; line-height: 1.45; background: rgba(255,255,255,.07); border: 1px solid rgba(255,255,255,.16); border-radius: 9px;
  padding: 8px 11px; margin: 10px 0 8px 0; }}
.side-count b {{ color: #FFFFFF; font-size: 1.05rem; }}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"], [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p, [data-testid="stSidebar"] label {{
  color: #DCE9F6 !important; font-weight: 700 !important; font-size: .80rem !important; letter-spacing: .03em; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"], [data-testid="stSidebar"] small {{ color: #A9C1DA !important; }}
/* pills (format / venue) */
[data-testid="stSidebar"] button[data-variant="pills"] {{ background: rgba(255,255,255,.06) !important; border: 1px solid rgba(255,255,255,.30) !important; border-radius: 999px !important;
  min-height: 30px; padding: 2px 11px; }}
[data-testid="stSidebar"] button[data-variant="pills"], [data-testid="stSidebar"] button[data-variant="pills"] * {{ color: #E8F0F8 !important; font-size: .80rem !important; font-weight: 600 !important; }}
[data-testid="stSidebar"] button[data-variant="pills"]:hover {{ border-color: #E3C25A !important; background: rgba(255,255,255,.12) !important; }}
[data-testid="stSidebar"] button[data-variant="pills"][aria-pressed="true"] {{ background: #0B8A4B !important; border-color: #5FD39A !important; }}
[data-testid="stSidebar"] button[data-variant="pills"][aria-pressed="true"], [data-testid="stSidebar"] button[data-variant="pills"][aria-pressed="true"] * {{ color: #FFFFFF !important; font-weight: 700 !important; }}
/* slider */
[data-testid="stSidebar"] [data-testid="stSliderThumbValue"], [data-testid="stSidebar"] [data-testid="stSliderTickBarMin"], [data-testid="stSidebar"] [data-testid="stSliderTickBarMax"] {{ color: #FFFFFF !important; font-weight: 700; }}
/* select boxes inside the sidebar (the visible box is the parent of the tags container) */
[data-testid="stSidebar"] [data-testid="stMultiSelect"] div:has(> [data-testid="stMultiSelectTagsContainer"]),
[data-testid="stSidebar"] [data-testid="stSelectbox"] div:has(> input), [data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div {{
  background: #0A2038 !important; border: 1px solid rgba(255,255,255,.38) !important; border-radius: 9px; }}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] input, [data-testid="stSidebar"] [data-testid="stSelectbox"] input {{ color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF; caret-color: #FFFFFF; }}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] input::placeholder, [data-testid="stSidebar"] [data-testid="stSelectbox"] input::placeholder {{ color: #B9CDE2 !important; -webkit-text-fill-color: #B9CDE2; opacity: 1; }}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] svg, [data-testid="stSidebar"] [data-testid="stSelectbox"] svg {{ fill: #E8F0F8 !important; color: #E8F0F8 !important; }}
[data-testid="stSidebar"] [data-testid="stMultiSelect"] svg path[fill="none"], [data-testid="stSidebar"] [data-testid="stSelectbox"] svg path[fill="none"] {{ fill: none !important; }}
[data-testid="stSidebar"] span[data-baseweb="tag"] {{ background: #0B8A4B !important; color: #FFFFFF !important; border-radius: 6px; }}
[data-testid="stSidebar"] span[data-baseweb="tag"] span, [data-testid="stSidebar"] span[data-baseweb="tag"] svg {{ color: #FFFFFF !important; fill: #FFFFFF !important; }}
/* expander + button */
[data-testid="stSidebar"] [data-testid="stExpander"], [data-testid="stSidebar"] [data-testid="stExpander"] details, [data-testid="stSidebar"] [data-testid="stExpander"] summary {{ background: transparent !important; }}
[data-testid="stSidebar"] [data-testid="stExpander"] {{ background: rgba(255,255,255,.06) !important; border: 1px solid rgba(255,255,255,.26) !important; border-radius: 10px; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary, [data-testid="stSidebar"] [data-testid="stExpander"] summary * {{ color: #E8F0F8 !important; font-weight: 700; font-size: .84rem; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {{ fill: #E8F0F8 !important; }}
[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {{ background: transparent; border: 1px solid #E3C25A; border-radius: 9px; }}
[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"], [data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] * {{ color: #E3C25A !important; font-weight: 700; }}
[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {{ background: rgba(227,194,90,.16); }}
@media print {{ [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] {{ display:none !important; }} .block-container {{ max-width:100% !important; padding:0 !important; }} .stApp {{ background:#fff; }} }}
</style>
"""


def inject():
    st.markdown(_css(), unsafe_allow_html=True)


def hero(title, subtitle="", chips=None):
    c = "".join(f'<span class="chip">{html.escape(str(x))}</span>' for x in (chips or []))
    c = f'<div class="chips">{c}</div>' if c else ""
    st.markdown(f'<div class="hero"><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p>{c}</div>', unsafe_allow_html=True)


def section(title, hint=""):
    h = f"<small>{html.escape(hint)}</small>" if hint else ""
    st.markdown(f'<div class="sec">{html.escape(title)}{h}</div>', unsafe_allow_html=True)


def note(text):
    st.markdown(f'<div class="note">{html.escape(text)}</div>', unsafe_allow_html=True)


def kpi_html(label, value, sub="", tone="green", trend=""):
    t = f" {trend}" if trend in ("up", "down") else ""
    sm = ' style="font-size:1.2rem;padding-top:5px"' if len(str(value)) > 9 else ""
    return (f'<div class="kpi {tone}"><div class="l">{html.escape(str(label))}</div><div class="v"{sm}>{html.escape(str(value))}</div>'
            f'<div class="s{t}">{html.escape(str(sub))}</div></div>')


def kpis(items, per_row=6):
    """items: list of (label, value, sub, tone[, trend]). Renders rows of cards."""
    for i in range(0, len(items), per_row):
        chunk = items[i:i + per_row]
        cols = st.columns(per_row)
        for col, it in zip(cols, chunk):
            col.markdown(kpi_html(*it), unsafe_allow_html=True)
        st.write("")


def form_strip(results):
    """results: list of 'Won'/'Lost'/... newest last."""
    letter = {"Won": "W", "Lost": "L", "Tied": "T", "Draw": "D", "No result": "N"}
    st.markdown("".join(f'<span class="pill" title="{r}" style="background:{RES_COLORS.get(r, "#999")}">{letter.get(r, "?")}</span>'
                        for r in results), unsafe_allow_html=True)


def plot(fig, title=None, x=None, y=None, h=380, legend=None, cbar=None, pct=False, key=None, hline=None, ylim=None):
    """Style a Plotly figure and render it with proper axis titles."""
    if title: fig.update_layout(title_text=title)
    if x is not None: fig.update_xaxes(title_text=x)
    # primary axes only (a secondary y axis keeps its own settings)
    ys = [k for k in fig.layout if k == "yaxis" or (k.startswith("yaxis") and k[5:].isdigit() and not fig.layout[k].overlaying)]
    for k in ys:
        if y is not None: fig.layout[k].title.text = y
        if pct: fig.layout[k].ticksuffix = "%"
        if ylim: fig.layout[k].range = ylim
    if hline is not None:
        fig.add_hline(y=hline, line_dash="dot", line_color="#8A949C")
    if legend is not None: fig.update_layout(legend_title_text=legend)
    if cbar: fig.update_layout(coloraxis_colorbar_title_text=cbar)
    fig.update_traces(selector=dict(type="bar"), cliponaxis=False, textfont_size=10)
    fig.update_traces(selector=dict(type="treemap"), pathbar_visible=False, root_color="white")
    if any(t.type == "pie" for t in fig.data):
        # Pie / donut: put every percentage in the legend (tiny slices cannot hold a label), keep the ring fully inside the card,
        # and reserve a fixed band under the ring for the legend so nothing is cut off.
        for t in fig.data:
            if t.type == "pie" and t.values is not None:
                tot = float(sum(t.values)) or 1.0
                t.labels = [f"{l} · {100 * v / tot:.1f}%" for l, v in zip(t.labels, t.values)]
        fig.update_traces(selector=dict(type="pie"), domain=dict(x=[0.12, 0.88], y=[0.0, 1.0]), textinfo="percent", textposition="inside",
                          insidetextorientation="horizontal", sort=False)
        fig.update_layout(showlegend=True, uniformtext=dict(minsize=11, mode="hide"), margin=dict(l=20, r=20, t=62, b=100),
                          legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.04, yanchor="top", title_text="", font=dict(size=12)))
    st.plotly_chart(fig, width="stretch", key=key)