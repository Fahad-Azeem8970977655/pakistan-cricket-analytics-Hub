"""Plain-English takeaways generated from the currently filtered data."""
import html

import pandas as pd
import streamlit as st

from utils import data as D

TONES = {"up": "#0B8A4B", "down": "#D64545", "info": "#2A7AB9", "warn": "#C9A227"}


def _wp(g):
    n = int(g.result.isin(["Won", "Lost", "Tied"]).sum())
    return (100 * (g.result == "Won").sum() / n if n else None), n


def generate(m, b, w, form_bat=None):
    out = []
    if m.empty: return out
    wp, n = _wp(m)
    if wp is not None and n >= 10:
        out.append(("up" if wp >= 50 else "down", f"Pakistan have won **{wp:.1f}%** of {n} completed matches in this selection."))

    # home vs away
    h = m[m.location_type.str.startswith("Home")]; a = m[m.location_type == "Away"]
    (hw, hn), (aw, an) = _wp(h), _wp(a)
    if hw is not None and aw is not None and hn >= 15 and an >= 15 and abs(hw - aw) >= 8:
        out.append(("warn", f"Venue matters: Pakistan win **{hw:.0f}%** at home but **{aw:.0f}%** away, a gap of {abs(hw - aw):.0f} points."))

    # best / worst opponent
    g = D.grouped_record(m, "opponent")
    g = g[g.Completed >= 10]
    if len(g) >= 3:
        hi, lo = g.loc[g["Win %"].idxmax()], g.loc[g["Win %"].idxmin()]
        out.append(("up", f"Best record against **{hi.opponent}** ({hi['Win %']:.0f}% from {int(hi.Completed)} matches)."))
        out.append(("down", f"Toughest opponent: **{lo.opponent}**, beaten in only {lo['Win %']:.0f}% of {int(lo.Completed)} matches."))

    # best / worst format
    gf = D.grouped_record(m, "format")
    gf = gf[gf.Completed >= 15]
    if len(gf) >= 2:
        hi, lo = gf.loc[gf["Win %"].idxmax()], gf.loc[gf["Win %"].idxmin()]
        if hi["Win %"] - lo["Win %"] >= 8:
            out.append(("info", f"**{hi.format}** is the strongest format ({hi['Win %']:.0f}%), **{lo.format}** the weakest ({lo['Win %']:.0f}%)."))

    # recent trend
    yrs = sorted(m.year.unique())
    if len(yrs) >= 4:
        rec = m[m.year >= yrs[-2]]
        rw, rn = _wp(rec)
        if rw is not None and rn >= 10 and wp is not None and abs(rw - wp) >= 5:
            out.append(("up" if rw > wp else "down", f"Over the last two seasons ({yrs[-2]} to {yrs[-1]}) the win rate is **{rw:.0f}%**, "
                        f"{'up' if rw > wp else 'down'} {abs(rw - wp):.0f} points on the overall figure."))

    # chasing vs defending
    lo_ = m[m.format != "Test"]
    cw, cn = _wp(lo_[lo_.pak_batting_order == "Batting second"]); dw, dn = _wp(lo_[lo_.pak_batting_order == "Batting first"])
    if cw is not None and dw is not None and cn >= 20 and dn >= 20 and abs(cw - dw) >= 8:
        better = "chasing" if cw > dw else "setting a target"
        out.append(("info", f"Pakistan are stronger when **{better}**: {max(cw, dw):.0f}% vs {min(cw, dw):.0f}% (ODI and T20I)."))

    # phases
    if len(lo_) >= 20:
        d = lo_.pak_death_runs.mean() - lo_.opp_death_runs.mean(); p = lo_.pak_powerplay_runs.mean() - lo_.opp_powerplay_runs.mean()
        phase, val = ("death overs", d) if abs(d) >= abs(p) else ("powerplay", p)
        if abs(val) >= 2:
            out.append(("up" if val > 0 else "down", f"Biggest phase gap: in the **{phase}** Pakistan score {abs(val):.1f} runs per innings "
                        f"{'more' if val > 0 else 'fewer'} than the opposition."))

    # toss
    tw = m[m.pak_won_toss == True]; tl = m[m.pak_won_toss == False]
    a1, n1 = _wp(tw); a2, n2 = _wp(tl)
    if a1 is not None and a2 is not None and n1 >= 30 and n2 >= 30 and abs(a1 - a2) >= 8:
        out.append(("info", f"The toss has {'a real' if a1 > a2 else 'a reverse'} effect: {a1:.0f}% wins after winning it vs {a2:.0f}% after losing it."))

    # streak
    s = m.sort_values("date").result.tolist()
    if s:
        cur, k = s[-1], 0
        for r in reversed(s):
            if r == cur: k += 1
            else: break
        if k >= 3 and cur in ("Won", "Lost"):
            out.append(("up" if cur == "Won" else "down", f"Current run: **{k} {'wins' if cur == 'Won' else 'defeats'} in a row**."))

    # players
    if len(b):
        r = b.groupby("player").runs.sum().sort_values(ascending=False)
        if len(r):
            top = r.index[0]
            out.append(("info", f"**{top}** is the leading run-scorer with {int(r.iloc[0]):,} runs"
                        f" and {int(b[b.player == top].is_hundred.sum())} centuries."))
    if len(w):
        k = w.groupby("player").wickets.sum().sort_values(ascending=False)
        if len(k): out.append(("info", f"**{k.index[0]}** leads the wicket-takers with {int(k.iloc[0])} wickets."))
    if form_bat is not None and len(form_bat):
        hot = form_bat[form_bat.Status.str.contains("Hot")].head(2).Player.tolist()
        cold = form_bat[form_bat.Status.str.contains("Cold")].tail(2).Player.tolist()
        if hot: out.append(("up", f"In form with the bat (runs above par, last 5 innings): **{', '.join(hot)}**."))
        if cold: out.append(("down", f"Struggling for runs lately: **{', '.join(cold)}**."))
    return out


def render(items, cols=2):
    if not items:
        st.info("Not enough data for automatic insights with these filters."); return
    c = st.columns(cols)
    for i, (tone, text) in enumerate(items):
        body = html.escape(text).replace("**", "§")
        parts = body.split("§")
        body = "".join(f"<b>{p}</b>" if j % 2 else p for j, p in enumerate(parts))
        c[i % cols].markdown(f'<div class="note" style="border-left:5px solid {TONES[tone]};margin-bottom:8px;color:#1B2A24">{body}</div>', unsafe_allow_html=True)
