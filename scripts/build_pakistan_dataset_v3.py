#!/usr/bin/env python3
"""
Pakistan men's internationals 2015 -> today  |  Cricsheet  |  VERSION 3 (maximum detail)

    pip install requests pandas            (optional: openpyxl for --excel)
    python build_pakistan_dataset_v3.py                # uses ZIPs already on disk
    python build_pakistan_dataset_v3.py --refresh      # re-download latest Cricsheet data
    python build_pakistan_dataset_v3.py --geo --weather --excel    # all optional extras

Options
    --refresh   re-download the Cricsheet ZIPs and the player register
    --geo       look up unknown venue cities online (Open-Meteo geocoder) to fix home/away
    --weather   add temperature / rain / wind for each match (Open-Meteo archive, free, cached)
    --excel     also write everything into one Excel workbook
    --out DIR   output folder (default: output_v3)

What it fixes compared with v2
    * Home / Away / Neutral from the real venue country (not from series-name guessing)
    * Stage reached (Final / Semi / Quarter / Group) inferred from ALL matches of an event
    * Actual powerplay overs, middle overs, death overs (handles rain-reduced games)
    * Fielding (catches, stumpings, run-outs), partnerships, over-by-over data, super overs
    * One canonical name per Cricsheet player id, Cricinfo id / profile link per player
    * Win % with confidence intervals and small-sample flags
    * Optional captain / coach eras from files you fill in, optional weather
    * extra/missing_matches.csv: add matches Cricsheet lacks (Afghanistan games, abandoned matches)
    * A data_quality_report.md that lists everything that still needs a human look
"""
import argparse
import json
import math
import re
import time
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

TEAM = "Pakistan"
START = "2015-01-01"
END = date.today().isoformat()
try:
    SCRIPT_DIR = Path(__file__).resolve().parent
except NameError:          # running inside Jupyter / Colab notebook
    SCRIPT_DIR = Path.cwd()
DATA_DIR = Path("cricsheet_data")
SOURCES = {
    "Test": "https://cricsheet.org/downloads/tests_json.zip",
    "ODI": "https://cricsheet.org/downloads/odis_json.zip",
    "T20I": "https://cricsheet.org/downloads/t20s_json.zip",
}
PEOPLE_URL = "https://cricsheet.org/register/people.csv"
NOT_BOWLERS_WICKET = {"run out", "retired hurt", "retired out", "retired not out", "obstructing the field"}
NOT_A_WICKET = {"retired hurt", "retired not out"}
MULTI_TYPES_EXCLUDED = ("Bilateral", "Unknown", "Other")

# ----------------------------------------------------------------------------- venue -> country
# Country labels equal the Cricsheet team name where a team exists, so "Away" = venue country == opponent.
COUNTRY_KEYWORDS = {
    "Pakistan": ["karachi", "lahore", "rawalpindi", "multan", "faisalabad", "pindi", "islamabad", "abbottabad",
                 "sialkot", "peshawar", "quetta", "gaddafi", "pakistan"],
    "UAE": ["dubai", "abu dhabi", "sharjah", "zayed", "united arab emirates"],
    "Sri Lanka": ["colombo", "galle", "kandy", "pallekele", "hambantota", "dambulla", "moratuwa", "sri lanka"],
    "Bangladesh": ["dhaka", "mirpur", "chattogram", "chittagong", "sylhet", "khulna", "fatullah", "bangladesh"],
    "India": ["mumbai", "wankhede", "delhi", "kolkata", "eden gardens", "chennai", "chepauk", "bengaluru", "bangalore",
              "chinnaswamy", "ahmedabad", "hyderabad", "lucknow", "dharamsala", "dharamshala", "mohali", "chandigarh",
              "pune", "nagpur", "cuttack", "ranchi", "visakhapatnam", "vizag", "indore", "rajkot", "kanpur", "jaipur",
              "guwahati", "thiruvananthapuram", "india"],
    "England": ["london", "birmingham", "edgbaston", "manchester", "old trafford", "nottingham", "trent bridge",
                "leeds", "headingley", "southampton", "ageas bowl", "rose bowl", "cardiff", "bristol",
                "chester-le-street", "durham", "riverside", "taunton", "worcester", "canterbury", "kennington",
                "lord's", "england"],
    "Scotland": ["edinburgh", "grange", "glasgow", "aberdeen", "scotland"],
    "Ireland": ["dublin", "malahide", "belfast", "bready", "stormont", "ireland"],
    "Australia": ["sydney", "melbourne", "brisbane", "gabba", "adelaide", "perth", "hobart", "canberra", "manuka",
                  "geelong", "launceston", "cairns", "townsville", "australia"],
    "New Zealand": ["auckland", "wellington", "christchurch", "hamilton", "dunedin", "napier", "mount maunganui",
                    "mt maunganui", "nelson", "queenstown", "whangarei", "seddon", "new zealand"],
    "South Africa": ["cape town", "newlands", "johannesburg", "centurion", "supersport", "durban", "kingsmead",
                     "port elizabeth", "gqeberha", "st george's park", "paarl", "boland", "bloemfontein",
                     "east london", "buffalo park", "potchefstroom", "kimberley", "benoni", "south africa"],
    "West Indies": ["kingston", "sabina park", "bridgetown", "kensington", "port of spain", "tarouba", "queen's park oval",
                    "providence", "georgetown", "guyana", "gros islet", "st lucia", "daren sammy", "basseterre",
                    "warner park", "north sound", "sir vivian richards", "antigua", "roseau", "grenada", "trinidad",
                    "jamaica", "barbados", "st kitts", "st vincent", "arnos vale", "kingstown", "dominica", "west indies"],
    "Zimbabwe": ["harare", "bulawayo", "queens sports club", "zimbabwe"],
    "Netherlands": ["amstelveen", "rotterdam", "the hague", "hazelaarweg", "netherlands"],
    "Nepal": ["kirtipur", "kathmandu", "mulpani", "nepal"],
    "Oman": ["muscat", "al amerat", "oman"],
    "USA": ["dallas", "grand prairie", "new york", "nassau county", "eisenhower", "lauderhill", "lauderdale",
            "broward", "florida", "morrisville", "texas"],
    "Malaysia": ["kuala lumpur", "bayuemas", "kinrara", "selangor", "malaysia"],
    "China": ["hangzhou", "zhejiang", "huanglong"],
    "Japan": ["nisshin", "aichi"],
    "Kenya": ["nairobi", "ruaraka", "kenya"],
    "Namibia": ["windhoek", "namibia"],
    "Canada": ["brampton", "toronto", "maple leaf", "canada"],
    "Qatar": ["doha", "west end park", "qatar"],
    "Singapore": ["singapore", "kallang"],
    "Hong Kong": ["hong kong", "mong kok", "kowloon", "kai tak"],
}
TEAM_ALIAS = {"United Arab Emirates": "UAE", "United States of America": "USA"}
WI_COUNTRIES = {"Jamaica", "Barbados", "Trinidad and Tobago", "Guyana", "Saint Lucia", "Saint Kitts and Nevis",
                "Antigua and Barbuda", "Dominica", "Grenada", "Saint Vincent and the Grenadines"}


def venue_country(venue, city):
    text = f"{city or ''} {venue or ''}".lower()
    best, blen = None, 0
    for country, kws in COUNTRY_KEYWORDS.items():
        for k in kws:
            if k in text and len(k) > blen:
                best, blen = country, len(k)
    return best


def parse_host(name):
    m = re.match(r"^(.*?)\s+(?:tour of|in)\s+(.*?)(?:\s+(?:Test|ODI|T20I|T20|Twenty20|One-Day|Series|Trophy)\b.*|\s+\d{4}.*)?$",
                 name or "", flags=re.I)
    return (m.group(1).strip(), m.group(2).strip()) if m else (None, None)


def tournament_type(name):
    n = (name or "").lower().strip()
    if not n:
        return "Unknown"
    if "world cup" in n or "world t20" in n:
        return "ICC T20 World Cup" if ("t20" in n or "twenty20" in n) else "ICC World Cup"
    if "champions trophy" in n: return "ICC Champions Trophy"
    if "asia cup" in n: return "Asia Cup"
    if "asian games" in n: return "Asian Games"
    if any(k in n for k in ["tri-series", "tri series", "tri-nation", "triangular", "quadrangular", "tri nation"]):
        return "Tri/Multi-team Series"
    if "independence cup" in n: return "Bilateral"
    if re.search(r"\btour of\b|\bin\b|\bv\b", n): return "Bilateral"
    return "Other"


def tournament_group(ttype, name, fmt):
    return {"ICC World Cup": "ODI World Cup", "ICC T20 World Cup": "T20 World Cup",
            "ICC Champions Trophy": "Champions Trophy", "Asian Games": "Asian Games",
            "Asia Cup": f"Asia Cup ({'T20' if fmt == 'T20I' else 'ODI'})",
            "Tri/Multi-team Series": name, "Bilateral": "Bilateral series"}.get(ttype, "Other series")


def classify_location(vcountry, opponent, ttype, tname, year):
    """Home / Away / Neutral from the venue country; 'Home (UAE)' when Pakistan hosts at a neutral ground."""
    opp_c = TEAM_ALIAS.get(opponent, opponent)
    if vcountry == "Pakistan": return "Home"
    if vcountry is None: return "Unknown"
    if vcountry == opp_c: return "Away"
    if ttype == "Bilateral":
        # FIX v2.1: Cricsheet names Pakistan's home series played abroad "Pakistan v England ODI Series"
        # (Pakistan listed first = host). parse_host() cannot read that pattern, so those games fell through
        # to "Neutral". Also "Pakistan tour of United Arab Emirates" (Sri Lanka 2017 ODIs) is Pakistan hosting.
        if re.match(r"^Pakistan v ", tname or "", flags=re.I):
            return f"Home ({vcountry})"
        visitor, host = parse_host(tname)
        if (visitor or "").strip() == "Pakistan" and TEAM_ALIAS.get(host or "", host) == vcountry == "UAE":
            return f"Home ({vcountry})"
        vis = (visitor or "")
        if vis.startswith("Pakistan v") or (opponent.lower() in vis.lower()) or (host and "pakistan" in host.lower()):
            return f"Home ({vcountry})"
    return "Neutral"


# ----------------------------------------------------------------------------- innings analysis
def legal(d):
    ex = d.get("extras", {})
    return "wides" not in ex and "noballs" not in ex


def bowler_runs(d):
    ex = d.get("extras", {})
    return d["runs"]["total"] - ex.get("byes", 0) - ex.get("legbyes", 0) - ex.get("penalty", 0)


def overs_str(balls):
    return f"{balls // 6}.{balls % 6}"


def phase_bounds(inn, fmt, info):
    """Actual mandatory powerplay and death start, scaled for reduced-over games."""
    if fmt == "Test":
        return None
    lim = inn.get("target", {}).get("overs") or info.get("overs") or (20 if fmt == "T20I" else 50)
    lim = int(float(lim))
    pps = [p for p in inn.get("powerplays", []) if p.get("type") == "mandatory"]
    if pps:
        pp = (int(float(pps[0]["from"])), int(float(pps[0]["to"])))
    else:
        pp = (0, min(6 if fmt == "T20I" else 10, lim) - 1)
    death_lo = max(pp[1] + 1, lim - (4 if fmt == "T20I" else 10))
    return pp, death_lo


def analyse_innings(inn, fmt, info):
    bats, order, bowl = {}, [], {}
    over_charged, over_legal = defaultdict(int), defaultdict(int)
    t = Counter()
    wk_events, parts, over_rows = [], [], []
    pb = phase_bounds(inn, fmt, info)
    cur = dict(runs=0, balls=0, by=defaultdict(int), names=[])
    cum_runs = cum_wk = 0

    def new_bat():
        return dict(runs=0, balls=0, fours=0, sixes=0, dots=0, out=False, kind="", by="", fielders="")

    for over in inn.get("overs", []):
        o = over["over"]
        o_runs = o_wk = o_legal = 0
        for d in over["deliveries"]:
            ex, r = d.get("extras", {}), d["runs"]
            b, ns, bw = d["batter"], d["non_striker"], d["bowler"]
            for p in (b, ns):
                if p not in bats:
                    bats[p] = new_bat(); order.append(p)
                if p not in cur["names"]:
                    cur["names"].append(p)
            if bw not in bowl:
                bowl[bw] = dict(balls=0, runs=0, wkts=0, dots=0, wides=0, noballs=0, fours=0, sixes=0, maidens=0)
            lg = legal(d)
            bt, bl = bats[b], bowl[bw]
            if "wides" not in ex:
                bt["balls"] += 1
                if r["batter"] == 0:          # batter dot ball: faced (not a wide) and scored nothing off the bat
                    bt["dots"] += 1
            bt["runs"] += r["batter"]
            if r["batter"] in (4, 6) and not r.get("non_boundary"):
                k = "fours" if r["batter"] == 4 else "sixes"
                bt[k] += 1; t[k] += 1; t["boundary_runs"] += r["batter"]; bl[k] += 1
            t["runs"] += r["total"]; t["extras"] += r["extras"]
            for k in ("wides", "noballs", "byes", "legbyes", "penalty"):
                t[k] += ex.get(k, 0)
            o_runs += r["total"]
            if lg:
                t["balls"] += 1; o_legal += 1
                if r["total"] == 0: t["dots"] += 1
            if pb:
                ph = "pp" if pb[0][0] <= o <= pb[0][1] else ("death" if o >= pb[1] else "mid")
                t[f"{ph}_runs"] += r["total"]
            br = bowler_runs(d)
            bl["runs"] += br
            if lg:
                bl["balls"] += 1; over_legal[(o, bw)] += 1
                if r["batter"] == 0 and not ex.get("wides") and not ex.get("noballs"):
                    bl["dots"] += 1
            bl["wides"] += ex.get("wides", 0); bl["noballs"] += ex.get("noballs", 0)
            over_charged[(o, bw)] += br
            cur["runs"] += r["total"]; cur["balls"] += 1 if lg else 0
            cur["by"][b] += r["batter"]
            for w in d.get("wickets", []):
                kind, po = w["kind"], w["player_out"]
                if po not in bats:
                    bats[po] = new_bat(); order.append(po)
                bats[po]["kind"] = kind
                if kind in NOT_A_WICKET:
                    continue
                bats[po]["out"] = True
                t["wkts"] += 1; o_wk += 1
                if pb: t[f"{ph}_wkts"] += 1
                if kind not in NOT_BOWLERS_WICKET:
                    bl["wkts"] += 1; bats[po]["by"] = bw
                fl = w.get("fielders", [])
                bats[po]["fielders"] = ", ".join(f.get("name", "") for f in fl)
                wk_events.append(dict(kind=kind, bowler=bw, victim=po, over=o + 1,
                                      fielders=[(f.get("name", ""), bool(f.get("substitute"))) for f in fl]))
                top = sorted(cur["by"].items(), key=lambda x: -x[1])
                names = [b, ns] if b != ns else [b]
                parts.append(dict(wicket_no=t["wkts"], runs=cur["runs"], balls=cur["balls"], unbroken=False,
                                  batter1=names[0], batter1_runs=cur["by"].get(names[0], 0),
                                  batter2=names[1] if len(names) > 1 else "",
                                  batter2_runs=cur["by"].get(names[1], 0) if len(names) > 1 else 0))
                cur = dict(runs=0, balls=0, by=defaultdict(int), names=[])
        cum_runs += o_runs; cum_wk += o_wk
        over_rows.append(dict(over=o + 1, runs=o_runs, wickets=o_wk, legal_balls=o_legal,
                              cum_runs=cum_runs, cum_wkts=cum_wk))
    if cur["balls"] > 0 and len(cur["names"]) >= 1:
        n = cur["names"][-2:] if len(cur["names"]) > 1 else cur["names"]
        parts.append(dict(wicket_no=t["wkts"] + 1, runs=cur["runs"], balls=cur["balls"], unbroken=True,
                          batter1=n[0], batter1_runs=cur["by"].get(n[0], 0),
                          batter2=n[1] if len(n) > 1 else "", batter2_runs=cur["by"].get(n[1], 0) if len(n) > 1 else 0))
    for (o, bw), n in over_legal.items():
        if n >= 6 and over_charged[(o, bw)] == 0:
            bowl[bw]["maidens"] += 1
    return dict(t=t, bats=[(p, order.index(p) + 1, bats[p]) for p in order], bowl=bowl,
                wk=wk_events, parts=parts, overs=over_rows)


def best_fig(items):
    best = None
    for name, b in items:
        key = (b["wkts"], -b["runs"])
        if best is None or key > best[0]:
            best = (key, name, b)
    return best


def top_bat(lst):
    best = None
    for name, pos, b in lst:
        if best is None or b["runs"] > best[1]["runs"]:
            best = (name, b)
    return best


# ----------------------------------------------------------------------------- one match
QA = defaultdict(list)
EVENTS = defaultdict(list)
TEAMS_SEEN = set()


def parse_match(data, fmt, match_id):
    info = data["info"]
    dates = info["dates"]
    opp = [x for x in info["teams"] if x != TEAM][0]
    year = int(dates[0][:4])
    people = info.get("registry", {}).get("people", {})
    oc = info.get("outcome", {})
    winner, by = oc.get("winner"), oc.get("by", {})
    if winner == TEAM: result = "Won"
    elif winner: result = "Lost"
    elif oc.get("result") == "tie": result = "Tied"
    elif oc.get("result") == "draw": result = "Draw"
    else: result = "No result"
    margin_type, margin_value, margin = "", None, ""
    if "runs" in by and "innings" in by:
        margin_type, margin_value, margin = "innings & runs", by["runs"], f"innings and {by['runs']} runs"
    elif "innings" in by:
        margin_type, margin = "innings", "an innings"
    elif "runs" in by:
        margin_type, margin_value, margin = "runs", by["runs"], f"{by['runs']} runs"
    elif "wickets" in by:
        margin_type, margin_value, margin = "wickets", by["wickets"], f"{by['wickets']} wickets"
    if "eliminator" in oc or "bowl_out" in oc:
        margin_type, margin = "super over", "super over"

    ev = info.get("event", {})
    tname = ev.get("name", "") if isinstance(ev, dict) else str(ev)
    stage = ev.get("stage", "") if isinstance(ev, dict) else ""
    ttype = tournament_type(tname)
    multi = ttype not in MULTI_TYPES_EXCLUDED
    group = tournament_group(ttype, tname, fmt)
    vcountry = venue_country(info.get("venue", ""), info.get("city", ""))
    visitor, host = parse_host(tname)

    all_inns = data.get("innings", [])
    so = [i for i in all_inns if i.get("super_over")]
    inns = [i for i in all_inns if not i.get("super_over")]
    an = []
    for n, inn in enumerate(inns, 1):
        a = analyse_innings(inn, fmt, info)
        a.update(no=n, team=inn["team"], target=inn.get("target", {}).get("runs"))
        an.append(a)
    pak = [a for a in an if a["team"] == TEAM]
    opp_i = [a for a in an if a["team"] != TEAM]
    tot = lambda lst, k: sum(a["t"][k] for a in lst)
    rr = lambda lst: round(tot(lst, "runs") * 6 / tot(lst, "balls"), 2) if tot(lst, "balls") else None
    sc = lambda lst: " & ".join(f"{a['t']['runs']}/{a['t']['wkts']}" for a in lst)
    so_score = lambda team: " ".join(f"{sum(d['runs']['total'] for o in i['overs'] for d in o['deliveries'])}/"
                                    f"{sum(len([w for w in d.get('wickets', []) if w['kind'] not in NOT_A_WICKET]) for o in i['overs'] for d in o['deliveries'])}"
                                    for i in so if i["team"] == team)

    pb_all = [x for a in pak for x in a["bats"]]
    ob_all = [x for a in opp_i for x in a["bats"]]
    pbowl = [(n, b) for a in opp_i for n, b in a["bowl"].items()]
    obowl = [(n, b) for a in pak for n, b in a["bowl"].items()]
    pb, ob = top_bat(pb_all), top_bat(ob_all)
    pbw, obw = best_fig(pbowl), best_fig(obowl)
    first_team = an[0]["team"] if an else ""
    order = ("Batting first" if first_team == TEAM else "Batting second") if an else ""
    toss, off = info.get("toss", {}), info.get("officials", {})
    pom = info.get("player_of_match", [])
    squad = info.get("players", {}).get(TEAM, [])
    phase = fmt != "Test"

    # reconciliation check: batter runs + extras == innings total
    for a in an:
        s = sum(b["runs"] for _, _, b in a["bats"]) + a["t"]["extras"]
        if s != a["t"]["runs"]:
            QA["reconcile"].append(f"{match_id} innings {a['no']}: batters+extras={s} vs total={a['t']['runs']}")

    row = {
        "match_id": match_id, "date": dates[0], "end_date": dates[-1], "days_played": len(dates),
        "year": year, "month": int(dates[0][5:7]), "season": info.get("season", ""),
        "format": fmt, "opponent": opp, "venue": info.get("venue", ""), "city": info.get("city", ""),
        "venue_country": vcountry or "Unknown",
        "location_type": classify_location(vcountry, opp, ttype, tname, year),
        "tournament": tname, "tournament_type": ttype, "tournament_group": group,
        "edition": f"{group} {year}" if multi else "",
        "stage_detail": stage, "match_number": ev.get("match_number", "") if isinstance(ev, dict) else "",
        "toss_winner": toss.get("winner", ""), "toss_decision": toss.get("decision", ""),
        "pak_won_toss": toss.get("winner") == TEAM, "pak_batting_order": order,
        "result": result, "margin": margin, "margin_type": margin_type, "margin_value": margin_value,
        "dls_method": oc.get("method", ""),
        "is_win": result == "Won", "is_loss": result == "Lost",
        "is_completed": result in ("Won", "Lost", "Tied"),
        "win_points": {"Won": 1, "Tied": .5, "Draw": .5}.get(result, 0 if result == "Lost" else None),
        "won_toss_and_match": toss.get("winner") == TEAM and result == "Won",
        "player_of_match": ", ".join(pom), "pak_pom": any(p in squad for p in pom),
        "pak_score": sc(pak), "opp_score": sc(opp_i),
        "pak_runs": tot(pak, "runs"), "pak_wkts_lost": tot(pak, "wkts"), "pak_balls_faced": tot(pak, "balls"),
        "pak_overs": " & ".join(overs_str(a["t"]["balls"]) for a in pak), "pak_run_rate": rr(pak),
        "opp_runs": tot(opp_i, "runs"), "opp_wkts_lost": tot(opp_i, "wkts"), "opp_balls_faced": tot(opp_i, "balls"),
        "opp_overs": " & ".join(overs_str(a["t"]["balls"]) for a in opp_i), "opp_run_rate": rr(opp_i),
        "run_diff": tot(pak, "runs") - tot(opp_i, "runs"),
        "pak_target_chased": next((a["target"] for a in pak if a["target"]), None),
        "opp_target_chased": next((a["target"] for a in opp_i if a["target"]), None),
        "pak_chasing": order == "Batting second",
        "pak_fours": tot(pak, "fours"), "pak_sixes": tot(pak, "sixes"),
        "pak_boundary_pct": round(100 * tot(pak, "boundary_runs") / tot(pak, "runs"), 1) if tot(pak, "runs") else None,
        "pak_dot_ball_pct": round(100 * tot(pak, "dots") / tot(pak, "balls"), 1) if tot(pak, "balls") else None,
        "pak_extras_received": tot(pak, "extras"),
        "pak_powerplay_runs": tot(pak, "pp_runs") if phase else None, "pak_powerplay_wkts_lost": tot(pak, "pp_wkts") if phase else None,
        "pak_middle_runs": tot(pak, "mid_runs") if phase else None, "pak_middle_wkts_lost": tot(pak, "mid_wkts") if phase else None,
        "pak_death_runs": tot(pak, "death_runs") if phase else None, "pak_death_wkts_lost": tot(pak, "death_wkts") if phase else None,
        "pak_top_scorer": pb[0] if pb else "", "pak_top_score": pb[1]["runs"] if pb else None,
        "pak_hundreds": sum(1 for _, _, b in pb_all if b["runs"] >= 100),
        "pak_fifties": sum(1 for _, _, b in pb_all if 50 <= b["runs"] < 100),
        "pak_ducks": sum(1 for _, _, b in pb_all if b["runs"] == 0 and b["out"]),
        "pak_fours_conceded": tot(opp_i, "fours"), "pak_sixes_conceded": tot(opp_i, "sixes"),
        "pak_extras_conceded": tot(opp_i, "extras"), "pak_wides_bowled": tot(opp_i, "wides"),
        "pak_noballs_bowled": tot(opp_i, "noballs"), "pak_dot_balls_bowled": tot(opp_i, "dots"),
        "pak_dot_ball_bowled_pct": round(100 * tot(opp_i, "dots") / tot(opp_i, "balls"), 1) if tot(opp_i, "balls") else None,
        "opp_powerplay_runs": tot(opp_i, "pp_runs") if phase else None, "pak_powerplay_wkts_taken": tot(opp_i, "pp_wkts") if phase else None,
        "opp_middle_runs": tot(opp_i, "mid_runs") if phase else None, "pak_middle_wkts_taken": tot(opp_i, "mid_wkts") if phase else None,
        "opp_death_runs": tot(opp_i, "death_runs") if phase else None, "pak_death_wkts_taken": tot(opp_i, "death_wkts") if phase else None,
        "pak_best_bowler": pbw[1] if pbw else "", "pak_best_bowling": f"{pbw[2]['wkts']}/{pbw[2]['runs']}" if pbw else "",
        "pak_five_wkt_hauls": sum(1 for _, b in pbowl if b["wkts"] >= 5),
        "pak_bowlers_used": len({n for n, _ in pbowl}),
        "opp_top_scorer": ob[0] if ob else "", "opp_top_score": ob[1]["runs"] if ob else None,
        "opp_best_bowler": obw[1] if obw else "", "opp_best_bowling": f"{obw[2]['wkts']}/{obw[2]['runs']}" if obw else "",
        "super_over": bool(so), "super_over_pak": so_score(TEAM), "super_over_opp": so_score(opp),
        "pak_xi": ", ".join(squad), "opp_xi": ", ".join(info.get("players", {}).get(opp, [])),
        "umpires": ", ".join(off.get("umpires", [])), "match_referee": ", ".join(off.get("match_referees", [])),
        "pak_captain": "", "pak_coach": "",
    }
    ctx = dict(match_id=match_id, date=dates[0], year=year, format=fmt, opponent=opp, tournament=tname,
               tournament_type=ttype, edition=row["edition"], location_type=row["location_type"],
               venue=row["venue"], result=result, pak_batting_order=order)

    bat_rows, bowl_rows, field_rows, part_rows, over_rows, app_rows = [], [], [], [], [], []
    for a in pak:
        for name, pos, b in a["bats"]:
            bat_rows.append({**ctx, "innings_no": a["no"], "batting_position": pos, "player": name,
                             "player_id": people.get(name, ""), "runs": b["runs"], "balls": b["balls"],
                             "fours": b["fours"], "sixes": b["sixes"],
                             "dot_balls": b["dots"],
                             "dot_ball_pct": round(100 * b["dots"] / b["balls"], 1) if b["balls"] else None,
                             "strike_rate": round(100 * b["runs"] / b["balls"], 1) if b["balls"] else None,
                             "is_out": b["out"], "dismissal": b["kind"], "dismissed_by": b["by"], "fielders": b["fielders"],
                             "is_fifty": 50 <= b["runs"] < 100, "is_hundred": b["runs"] >= 100,
                             "is_duck": b["runs"] == 0 and b["out"], "team_total": a["t"]["runs"],
                             "team_extras": a["t"]["extras"]})
        for p in a["parts"]:
            part_rows.append({**ctx, "innings_no": a["no"], **p})
    for a in opp_i:
        for name, b in a["bowl"].items():
            bowl_rows.append({**ctx, "innings_no": a["no"], "player": name, "player_id": people.get(name, ""),
                              "balls": b["balls"], "overs": overs_str(b["balls"]), "maidens": b["maidens"],
                              "runs_conceded": b["runs"], "wickets": b["wkts"], "dot_balls": b["dots"],
                              "economy": round(b["runs"] * 6 / b["balls"], 2) if b["balls"] else None,
                              "wides": b["wides"], "noballs": b["noballs"], "fours_conceded": b["fours"],
                              "sixes_conceded": b["sixes"], "is_five_wkts": b["wkts"] >= 5,
                              "opp_innings_total": a["t"]["runs"]})
    f = defaultdict(lambda: Counter())
    for a in opp_i:                                   # Pakistan fielding = wickets in opposition innings
        for w in a["wk"]:
            fl = w["fielders"]
            if w["kind"] == "caught" and fl:
                f[fl[0]]["catches"] += 1
            elif w["kind"] == "caught and bowled":
                f[(w["bowler"], False)]["caught_and_bowled"] += 1
            elif w["kind"] == "stumped" and fl:
                f[fl[0]]["stumpings"] += 1
            elif w["kind"] == "run out" and fl:
                for x in fl:
                    f[x]["runouts_direct" if len(fl) == 1 else "runouts_assisted"] += 1
    for (name, sub), c in f.items():
        field_rows.append({**ctx, "player": name, "player_id": people.get(name, ""), "substitute": sub,
                           "catches": c["catches"], "caught_and_bowled": c["caught_and_bowled"],
                           "stumpings": c["stumpings"], "runouts_direct": c["runouts_direct"],
                           "runouts_assisted": c["runouts_assisted"]})
    for a in an:
        side = "Pakistan" if a["team"] == TEAM else "Opposition"
        for o in a["overs"]:
            over_rows.append({**{k: ctx[k] for k in ("match_id", "date", "year", "format", "opponent")},
                              "innings_no": a["no"], "side": side, **o})
    for p in squad:
        app_rows.append({"match_id": match_id, "date": dates[0], "year": year, "format": fmt, "opponent": opp,
                         "player": p, "player_id": people.get(p, ""), "result": result})
    return dict(m=row, bat=bat_rows, bowl=bowl_rows, field=field_rows, part=part_rows, over=over_rows, app=app_rows)


# ----------------------------------------------------------------------------- stage inference
def norm_stage(s):
    s = (s or "").lower()
    if not s: return None
    if "semi" in s: return "Semi Final"
    if "quarter" in s: return "Quarter Final"
    if "play-off" in s or "3rd" in s or "third" in s: return "Play-off"
    if "final" in s: return "Final"
    if "super" in s: return "Super stage"
    return "Group/League"


def ko_structure(ttype, season):
    if ttype == "ICC World Cup" and str(season).startswith("2014"):   # 2015 World Cup had quarter-finals
        return 4, 2
    if ttype in ("ICC World Cup", "ICC T20 World Cup", "ICC Champions Trophy"):
        return 0, 2
    return 0, 0


def infer_stages():
    lab = {}
    for (fmt, name, season), ms in EVENTS.items():
        ttype = tournament_type(name)
        def k(m):
            mn = m["mn"] if isinstance(m["mn"], (int, float)) else (int(m["mn"]) if str(m["mn"]).isdigit() else 0)
            return (m["date"], mn, int(m["id"]) if str(m["id"]).isdigit() else 0)
        ms = sorted(ms, key=k)
        qf, sf = ko_structure(ttype, season)
        anchor = next((i for i, m in enumerate(ms) if norm_stage(m["stage"]) == "Final"), len(ms) - 1)
        for i, m in enumerate(ms):
            ex = norm_stage(m["stage"])
            if ex:
                lab[(fmt, m["id"])] = (ex, "cricsheet"); continue
            r = anchor - i
            if r == 0 and len(ms) >= 3: L = "Final"
            elif 0 < r <= sf and len(ms) > sf + qf + 2: L = "Semi Final"
            elif sf < r <= sf + qf and len(ms) > sf + qf + 2: L = "Quarter Final"
            else: L = "Group/League"
            lab[(fmt, m["id"])] = (L, "inferred")
    return lab


def stage_reached(g):
    g = g.sort_values("date")
    last = g.iloc[-1]
    s = last.stage_inferred
    if s == "Final":
        return "Champions" if last.result == "Won" else ("Runners-up" if last.result == "Lost" else "Final (no result/tie)")
    return {"Semi Final": "Semi-final", "Quarter Final": "Quarter-final", "Play-off": "Play-off",
            "Super stage": "Super stage"}.get(s, "Group/League stage")


# ----------------------------------------------------------------------------- stats helpers
def wilson(w, n, z=1.96):
    if n == 0: return (None, None)
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h), 1), round(100 * (c + h), 1)


def summary(df, by):
    d = df.assign(W=(df.result == "Won").astype(int), L=(df.result == "Lost").astype(int), T=(df.result == "Tied").astype(int))
    g = d.groupby(by, dropna=False).agg(played=("result", "size"), won=("W", "sum"), lost=("L", "sum"), tied=("T", "sum")).reset_index()
    g["completed"] = g.won + g.lost + g.tied
    g["draw_or_nr"] = g.played - g.completed
    g["win_pct"] = (100 * g.won / g.completed.where(g.completed > 0)).round(1)
    ci = [wilson(w, n) for w, n in zip(g.won, g.completed)]
    g["ci95_low"], g["ci95_high"] = [c[0] for c in ci], [c[1] for c in ci]
    g["small_sample"] = g.completed < 10
    return g


def apply_eras(df, path, col):
    if not path.exists(): return
    e = pd.read_csv(path)
    e = e.dropna(subset=["person"]) if "person" in e else e
    if e.empty: return
    e["from_date"] = pd.to_datetime(e.from_date); e["to_date"] = pd.to_datetime(e.to_date.fillna("2100-01-01"))
    d = pd.to_datetime(df["date"])
    for i, r in df.iterrows():
        k = e[(e.from_date <= d[i]) & (e.to_date >= d[i]) & (e.format.isin(["All", r["format"]]))]
        if len(k): df.at[i, col] = k.sort_values("from_date").iloc[-1].person


# ----------------------------------------------------------------------------- optional online helpers
def jget(url, params, cache, key, delay=0.3):
    if key in cache: return cache[key]
    try:
        time.sleep(delay)
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        cache[key] = r.json()
    except Exception as ex:
        print(f"   ! request failed ({key[:40]}): {ex}")
        cache[key] = None
    return cache[key]


def country_to_label(c):
    if not c: return None
    if c in WI_COUNTRIES: return "West Indies"
    m = {"United Arab Emirates": "UAE", "United States": "USA", "United Kingdom": "England",
         "Republic of Ireland": "Ireland", "Türkiye": "Turkey"}
    return m.get(c, c)


def geo_fix(m, cache):
    for i, r in m[m.venue_country == "Unknown"].iterrows():
        q = r.city if isinstance(r.city, str) and r.city else r.venue
        j = jget("https://geocoding-api.open-meteo.com/v1/search", {"name": q, "count": 1}, cache, f"geo:{q}")
        if j and j.get("results"):
            lab = country_to_label(j["results"][0].get("country"))
            m.at[i, "venue_country"] = lab or "Unknown"
            if lab:
                m.at[i, "location_type"] = classify_location(lab, r.opponent, r.tournament_type, r.tournament, r.year)
    return m


def add_weather(m, cache):
    cols = ["weather_tmax_c", "weather_tmin_c", "rain_mm", "wind_kmh_max"]
    for c in cols: m[c] = None
    for i, r in m.iterrows():
        q = r.city if isinstance(r.city, str) and r.city else r.venue
        g = jget("https://geocoding-api.open-meteo.com/v1/search", {"name": q, "count": 1}, cache, f"geo:{q}", 0.15)
        if not g or not g.get("results"): continue
        lat, lon = g["results"][0]["latitude"], g["results"][0]["longitude"]
        j = jget("https://archive-api.open-meteo.com/v1/archive",
                 {"latitude": lat, "longitude": lon, "start_date": r.date, "end_date": r.date, "timezone": "auto",
                  "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max"},
                 cache, f"wx:{lat:.2f},{lon:.2f},{r.date}")
        if j and j.get("daily") and j["daily"].get("time"):
            d = j["daily"]
            m.at[i, "weather_tmax_c"] = d["temperature_2m_max"][0]; m.at[i, "weather_tmin_c"] = d["temperature_2m_min"][0]
            m.at[i, "rain_mm"] = d["precipitation_sum"][0]; m.at[i, "wind_kmh_max"] = d["wind_speed_10m_max"][0]
    return m



# ----------------------------------------------------------------------------- manual / missing matches
MANUAL_HEADER = ("date,format,opponent,venue,city,tournament,stage,result,margin,pak_score,opp_score,"
                 "toss_winner,toss_decision,player_of_match\n")


def score_totals(s):
    parts = re.findall(r"(\d+)(?:/(\d+))?", str(s)) if isinstance(s, str) else []
    if not parts: return None, None
    return sum(int(a) for a, _ in parts), (sum(int(b) for _, b in parts if b) if any(b for _, b in parts) else None)


def load_manual(path):
    """Matches that Cricsheet does not contain (e.g. Afghanistan games, matches abandoned without a ball)."""
    x = pd.read_csv(path)
    x = x.dropna(subset=["date", "format", "opponent"]) if len(x) else x
    rows = []
    for i, r in enumerate(x.itertuples(index=False)):
        r = r._asdict()
        fmt, opp, tname = r["format"], r["opponent"], str(r.get("tournament") or "")
        ttype = tournament_type(tname)
        group = tournament_group(ttype, tname, fmt)
        yr = int(str(r["date"])[:4])
        vc = venue_country(r.get("venue"), r.get("city"))
        res = r.get("result") or "No result"
        pr, pw = score_totals(r.get("pak_score")); orr, ow = score_totals(r.get("opp_score"))
        stg = r.get("stage") if isinstance(r.get("stage"), str) else ""
        rows.append({
            "match_id": f"manual_{i+1}", "date": str(r["date"])[:10], "end_date": str(r["date"])[:10], "year": yr,
            "month": int(str(r["date"])[5:7]), "format": fmt, "opponent": opp, "venue": r.get("venue"), "city": r.get("city"),
            "venue_country": vc or "Unknown", "location_type": classify_location(vc, opp, ttype, tname, yr),
            "tournament": tname, "tournament_type": ttype, "tournament_group": group,
            "edition": f"{group} {yr}" if ttype not in MULTI_TYPES_EXCLUDED else "", "stage_detail": stg,
            "toss_winner": r.get("toss_winner"), "toss_decision": r.get("toss_decision"),
            "pak_won_toss": r.get("toss_winner") == TEAM if isinstance(r.get("toss_winner"), str) else None,
            "result": res, "margin": r.get("margin"), "is_win": res == "Won", "is_loss": res == "Lost",
            "is_completed": res in ("Won", "Lost", "Tied"),
            "win_points": {"Won": 1, "Tied": .5, "Draw": .5}.get(res, 0 if res == "Lost" else None),
            "player_of_match": r.get("player_of_match"), "pak_score": r.get("pak_score"), "opp_score": r.get("opp_score"),
            "pak_runs": pr, "pak_wkts_lost": pw, "opp_runs": orr, "opp_wkts_lost": ow,
            "run_diff": (pr - orr) if pr is not None and orr is not None else None,
            "stage_inferred": (norm_stage(stg) or "Group/League") if ttype not in MULTI_TYPES_EXCLUDED else "",
            "stage_source": "manual" if ttype not in MULTI_TYPES_EXCLUDED else "", "data_source": "manual"})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- files
def get_zip(fmt, url, refresh):
    DATA_DIR.mkdir(exist_ok=True)
    name = Path(url).name
    for c in (DATA_DIR / name, Path.cwd() / name, SCRIPT_DIR / name):
        if c.exists() and not refresh:
            return c
    print(f"   downloading {url}")
    r = requests.get(url, timeout=300); r.raise_for_status()
    (DATA_DIR / name).write_bytes(r.content)
    return DATA_DIR / name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true"); ap.add_argument("--geo", action="store_true")
    ap.add_argument("--weather", action="store_true"); ap.add_argument("--excel", action="store_true")
    ap.add_argument("--out", default="output_v3")
    a, _ = ap.parse_known_args()   # ignores extra args injected by Jupyter/Colab
    out = Path(a.out); out.mkdir(exist_ok=True)

    parsed = []
    for fmt, url in SOURCES.items():
        z = get_zip(fmt, url, a.refresh)
        print(f"{fmt}: reading {z}")
        n = 0
        with zipfile.ZipFile(z) as zf:
            for name in zf.namelist():
                if not name.endswith(".json"): continue
                data = json.loads(zf.read(name))
                info = data.get("info", {})
                if info.get("gender") != "male" or not info.get("dates"): continue
                d0 = info["dates"][0]
                TEAMS_SEEN.update(info.get("teams", []))
                ev = info.get("event", {}); tname = ev.get("name", "") if isinstance(ev, dict) else str(ev)
                if d0 >= "2014-06-01" and tournament_type(tname) not in MULTI_TYPES_EXCLUDED:
                    oc = info.get("outcome", {})
                    EVENTS[(fmt, tname, str(info.get("season", "")))].append(
                        dict(id=Path(name).stem, date=d0, teams=info.get("teams", []), winner=oc.get("winner"),
                             mn=ev.get("match_number") if isinstance(ev, dict) else None,
                             stage=ev.get("stage", "") if isinstance(ev, dict) else ""))
                if TEAM in info.get("teams", []) and START <= d0 <= END:
                    parsed.append(parse_match(data, fmt, Path(name).stem)); n += 1
        print(f"   {n} Pakistan matches")

    m = pd.DataFrame([p["m"] for p in parsed])
    bat = pd.DataFrame([r for p in parsed for r in p["bat"]])
    bowl = pd.DataFrame([r for p in parsed for r in p["bowl"]])
    field = pd.DataFrame([r for p in parsed for r in p["field"]])
    part = pd.DataFrame([r for p in parsed for r in p["part"]])
    over = pd.DataFrame([r for p in parsed for r in p["over"]])
    app = pd.DataFrame([r for p in parsed for r in p["app"]])

    # --- stages from all matches of each event
    lab = infer_stages()
    m["stage_inferred"] = [lab.get((f, i), ("Bilateral/none", "n/a"))[0] if t not in MULTI_TYPES_EXCLUDED else "" for f, i, t in zip(m.format, m.match_id, m.tournament_type)]
    m["stage_source"] = [lab.get((f, i), ("", ""))[1] if t not in MULTI_TYPES_EXCLUDED else "" for f, i, t in zip(m.format, m.match_id, m.tournament_type)]
    m["data_source"] = "cricsheet"
    Path("extra").mkdir(exist_ok=True)
    mp = Path("extra/missing_matches.csv")
    if not mp.exists():
        mp.write_text(MANUAL_HEADER)
    mm = load_manual(mp)
    if len(mm):
        print(f"   + {len(mm)} manual matches from {mp}")
        m = pd.concat([m, mm], ignore_index=True)
    m["is_knockout"] = m.stage_inferred.isin(["Final", "Semi Final", "Quarter Final", "Play-off"])

    # --- optional online fixes
    cache_path = DATA_DIR / "online_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if a.geo:
        print("Geocoding unknown venues ..."); m = geo_fix(m, cache)
    if a.weather:
        print("Fetching weather (cached, ~1-3 min first time) ..."); m = add_weather(m, cache)
    if a.geo or a.weather:
        cache_path.write_text(json.dumps(cache))
    m = m.sort_values("date").reset_index(drop=True)

    # --- eras (captain / coach) from files the user fills in
    Path("eras").mkdir(exist_ok=True)
    for fn in ("captains.csv", "coaches.csv"):
        p = Path("eras") / fn
        if not p.exists():
            p.write_text("format,person,from_date,to_date\n")   # format = All / Test / ODI / T20I ; dates YYYY-MM-DD
    apply_eras(m, Path("eras/captains.csv"), "pak_captain")
    apply_eras(m, Path("eras/coaches.csv"), "pak_coach")

    # --- canonical player names by Cricsheet id
    allp = pd.concat([bat[["player", "player_id"]], bowl[["player", "player_id"]], app[["player", "player_id"]]])
    allp = allp[allp.player_id != ""]
    canon = allp.groupby("player_id").player.agg(lambda s: s.value_counts().index[0]).to_dict()
    multi_names = allp.groupby("player_id").player.nunique()
    for df in (bat, bowl, field, app):
        if len(df):
            df["player_cricsheet_name"] = df["player"]
            df["player"] = [canon.get(i, p) for i, p in zip(df.player_id, df.player)]

    # --- players dimension (+ Cricinfo ids)
    people = None
    try:
        pp = DATA_DIR / "people.csv"
        if a.refresh or not pp.exists():
            r = requests.get(PEOPLE_URL, timeout=60); r.raise_for_status(); pp.write_bytes(r.content)
        people = pd.read_csv(pp)
    except Exception as ex:
        print(f"   ! could not load Cricsheet people register ({ex}); skipping Cricinfo ids")
    pl = app[app.player_id != ""].groupby(["player_id", "player"]).agg(
        matches=("match_id", "nunique"), first_match=("date", "min"), last_match=("date", "max")).reset_index()
    for f in ("Test", "ODI", "T20I"):
        c = app[app.format == f].groupby("player_id").match_id.nunique()
        pl[f"{f}_matches"] = pl.player_id.map(c).fillna(0).astype(int)
    if people is not None and "key_cricinfo" in people.columns:
        mp = people.set_index("identifier")["key_cricinfo"].to_dict()
        pl["cricinfo_id"] = pl.player_id.map(mp)
        pl["cricinfo_url"] = pl.cricinfo_id.apply(lambda x: f"https://www.espncricinfo.com/cricketers/{int(x)}" if pd.notna(x) else "")
    pl = pl.sort_values("matches", ascending=False)

    # --- editions
    ed = []
    for e, g in m[m.edition != ""].groupby("edition"):
        end = g.date.max()
        ed.append(dict(edition=e, tournament_group=g.tournament_group.iloc[0], year=int(g.year.iloc[0]), format=g.format.iloc[0],
                       start=g.date.min(), end=end, played=len(g), won=int((g.result == "Won").sum()),
                       lost=int((g.result == "Lost").sum()), stage_reached=stage_reached(g),
                       stage_source=g.stage_source.iloc[-1],
                       provisional=end >= (date.today() - timedelta(days=7)).isoformat(),
                       stage_check_needed=(stage_reached(g) == "Group/League stage" and
                                           len(g) > {"T20 World Cup": 5, "Champions Trophy": 3}.get(g.tournament_group.iloc[0], 99))))
    ed = pd.DataFrame(ed).sort_values("start")

    # --- summaries
    s_yf = summary(m, ["year", "format"])
    s_op = summary(m, ["opponent"]).sort_values("played", ascending=False)
    s_loc = summary(m, ["format", "location_type"])

    # --- write
    files = {"pak_matches": m, "pak_batting": bat, "pak_bowling": bowl, "pak_fielding": field,
             "pak_partnerships": part, "pak_overs": over, "pak_appearances": app, "pak_players": pl,
             "pak_editions": ed, "summary_year_format": s_yf, "summary_opponent": s_op, "summary_venue_type": s_loc}
    for k, df in files.items():
        df.to_csv(out / f"{k}.csv", index=False)
    if a.excel:
        try:
            with pd.ExcelWriter(out / "pak_dataset.xlsx") as xw:
                for k, df in files.items():
                    if k != "pak_overs": df.to_excel(xw, sheet_name=k[:31], index=False)
            print("Excel workbook written (pak_overs is CSV only: too large for a sheet-friendly view)")
        except Exception as ex:
            print(f"   ! Excel not written ({ex}); run: pip install openpyxl")

    # --- data quality report
    lastd = m.date.max()
    lag = (date.today() - datetime.strptime(lastd, "%Y-%m-%d").date()).days
    unk = m[m.venue_country == "Unknown"]
    oth = m[m.tournament_type.isin(["Other", "Unknown"])]
    dup = m[m.duplicated(["date", "format", "opponent"], keep=False)]
    L = [f"# Data quality report  ({datetime.now():%Y-%m-%d %H:%M})", "",
         f"- Matches: **{len(m)}**  (Test {int((m.format=='Test').sum())}, ODI {int((m.format=='ODI').sum())}, T20I {int((m.format=='T20I').sum())})",
         f"- Latest match in data: **{lastd}** ({lag} days ago). Compare with Pakistan's most recent fixture; Cricsheet can lag.",
         f"- Batting rows {len(bat)}, bowling rows {len(bowl)}, fielding rows {len(field)}, partnerships {len(part)}, over rows {len(over)}",
         f"- Runs reconciliation (batter runs + extras = innings total): **{len(QA['reconcile'])} mismatches**",
         f"- Players with more than one spelling per Cricsheet id (merged): {int((multi_names > 1).sum())}",
         f"- Duplicate (date, format, opponent) rows: {len(dup)}",
         f"- Stage reached is **inferred** where Cricsheet has no stage: {int((m.stage_source=='inferred').sum())} matches (see pak_editions.csv)",
         f"- Editions flagged provisional (ended within 7 days): {int(ed.provisional.sum()) if len(ed) else 0}",
         f"- Captain filled: {int((m.pak_captain!='').sum())}/{len(m)}   Coach filled: {int((m.pak_coach!='').sum())}/{len(m)}"
         "   (fill eras/captains.csv and eras/coaches.csv, then re-run)", ""]
    L += [f"## Venues with unknown country ({unk[['venue','city']].drop_duplicates().shape[0]})",
          "Add keywords to COUNTRY_KEYWORDS in this script, or run with --geo.", ""]
    L += [f"- {r.venue} | {r.city}" for r in unk[["venue", "city"]].drop_duplicates().itertuples()][:60]
    L += ["", f"## Tournaments typed Other/Unknown ({oth.tournament.fillna('').nunique()})"]
    L += [f"- {t or '(blank event name)'}  ({n} matches)" for t, n in oth.tournament.fillna("").value_counts().items()]
    EXPECTED = ["Afghanistan", "Australia", "Bangladesh", "England", "India", "Ireland", "New Zealand",
                "South Africa", "Sri Lanka", "West Indies", "Zimbabwe"]
    miss = [t for t in EXPECTED if t not in set(m.opponent)]
    L += ["", "## COVERAGE WARNINGS (matches Pakistan has really played but are not in the data)"]
    for t in miss:
        why = "absent from the Cricsheet ZIPs entirely" if t not in TEAMS_SEEN else "in Cricsheet but no Pakistan match found"
        L.append(f"- **{t}**: 0 matches vs Pakistan ({why}). Add them to extra/missing_matches.csv.")
    if not miss: L.append("- none of the main opponents is missing")
    L += ["- Matches abandoned without a ball bowled are never in Cricsheet; add them manually if you want them counted.",
          f"- Manual matches included: {int((m.data_source == 'manual').sum())}",
          "", "## Editions whose stage should be double-checked"]
    L += [f"- {r.edition} (played {r.played}, labelled {r.stage_reached})" for r in ed[ed.stage_check_needed].itertuples()] if len(ed) else []
    L += ["", "## Reconciliation mismatches (first 20)"] + [f"- {x}" for x in QA["reconcile"][:20]]
    L += ["", "## Matches per year and format", "", "```\n" + m.groupby(["year", "format"]).size().unstack(fill_value=0).to_string() + "\n```"]
    L += ["", "## Location types", "", "```\n" + m.location_type.value_counts().to_string() + "\n```"]
    L += ["", "## Not available from Cricsheet (cannot be created by this script)",
          "pitch report, day/night flag, ICC rankings, World Test Championship points, crowd, injuries."]
    (out / "data_quality_report.md").write_text("\n".join(L), encoding="utf-8")

    print(f"\nDone. Files in ./{out}/")
    for k, df in files.items():
        print(f"   {k+'.csv':28} {len(df):>7} rows x {df.shape[1]} cols")
    print(f"Latest match: {lastd}  |  see {out}/data_quality_report.md")


if __name__ == "__main__":
    main()
