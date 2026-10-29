"""Write EVERY DELIVERY of Pakistan's matches to data/pak_deliveries.csv.gz (for the Phase Analysis page).

    python scripts/build_deliveries.py

* Needs the Cricsheet ZIPs that build_pakistan_dataset_v3.py already downloaded (folder cricsheet_data/). If they are missing it downloads them.
* Does NOT touch any other data file, so there is no need to re-run the whole build or the captain / coach scripts.
* Phase uses the same rule as the main build (actual powerplay overs, rain-reduced games handled): PP / Middle / Death. Tests have phase "Test".
* Hand-added matches are skipped here; the 15 Pakistan v Afghanistan (manual_*) delivery rows already in the file are kept (re-create them with scripts/merge_afghanistan_ballbyball.py).
Output size: roughly 250,000 rows, about 5 MB compressed.
"""
import importlib.util
import json
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("builder", ROOT / "scripts" / "build_pakistan_dataset_v3.py")
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)

PHASE_NAMES = {"pp": "Powerplay", "mid": "Middle", "death": "Death"}


def innings_rows(inn, no, fmt, info, people, canon, mid):
    pb = B.phase_bounds(inn, fmt, info)
    pak_bats = inn["team"] == B.TEAM
    rows, legal_n = [], 0
    for over in inn.get("overs", []):
        o = over["over"]
        phase = "Test" if pb is None else PHASE_NAMES["pp" if pb[0][0] <= o <= pb[0][1] else ("death" if o >= pb[1] else "mid")]
        for k, d in enumerate(over["deliveries"], 1):
            ex, r = d.get("extras", {}), d["runs"]
            lg = B.legal(d); legal_n += 1 if lg else 0
            wk = [w for w in d.get("wickets", []) if w["kind"] not in B.NOT_A_WICKET]
            w0 = wk[0] if wk else None
            nm = lambda n: canon.get(people.get(n, ""), n)
            rows.append(dict(
                match_id=mid, innings_no=no, pak_batting=pak_bats, over=o + 1, ball=k, legal_ball_no=legal_n if lg else None,
                batter=nm(d["batter"]), bowler=nm(d["bowler"]), runs_batter=r["batter"], runs_extras=r["extras"], runs_total=r["total"],
                extras_type=",".join(ex) if ex else "", is_legal=lg,
                is_batter_dot=("wides" not in ex) and r["batter"] == 0,
                is_four=r["batter"] == 4 and not r.get("non_boundary"), is_six=r["batter"] == 6 and not r.get("non_boundary"),
                is_wicket=w0 is not None, wicket_kind=w0["kind"] if w0 else "", player_out=nm(w0["player_out"]) if w0 else "",
                bowler_wicket=bool(w0) and w0["kind"] not in B.NOT_BOWLERS_WICKET, phase=phase))
    return rows


def main():
    m = pd.read_csv(ROOT / "data" / "pak_matches.csv"); m["match_id"] = m["match_id"].astype(str)
    if "data_source" in m: m = m[m.data_source != "manual"]
    meta = m.set_index("match_id")[["date", "format", "opponent"]].to_dict("index")
    canon = {}
    ap = ROOT / "data" / "pak_appearances.csv"
    if ap.exists():
        a = pd.read_csv(ap); a = a[a.player_id.notna() & (a.player_id != "")]
        canon = a.groupby("player_id").player.agg(lambda s: s.value_counts().index[0]).to_dict()
    rows, missing = [], set(meta)
    for fmt, url in B.SOURCES.items():
        z = B.get_zip(fmt, url, False); print(f"{fmt}: reading {z}")
        with zipfile.ZipFile(z) as zf:
            for name in zf.namelist():
                mid = Path(name).stem
                if not name.endswith(".json") or mid not in meta: continue
                data = json.loads(zf.read(name)); info = data.get("info", {}); people = info.get("registry", {}).get("people", {})
                inns = [i for i in data.get("innings", []) if not i.get("super_over")]
                for n, inn in enumerate(inns, 1):
                    rows += innings_rows(inn, n, fmt, info, people, canon, mid)
                missing.discard(mid)
    df = pd.DataFrame(rows)
    df.insert(1, "date", df.match_id.map(lambda i: meta[i]["date"])); df.insert(2, "format", df.match_id.map(lambda i: meta[i]["format"]))
    df.insert(3, "opponent", df.match_id.map(lambda i: meta[i]["opponent"]))
    for c in ("is_legal", "is_batter_dot", "is_four", "is_six", "is_wicket", "bowler_wicket", "pak_batting"): df[c] = df[c].astype(int)
    out = ROOT / "data" / "pak_deliveries.csv.gz"
    if out.exists():
        keep = pd.read_csv(out, dtype={"match_id": str}, low_memory=False); keep = keep[keep.match_id.str.startswith("manual_")]
        if len(keep): df = pd.concat([df.assign(match_id=df.match_id.astype(str)), keep[df.columns]], ignore_index=True)
    df.to_csv(out, index=False, compression="gzip")
    print(f"{len(df):,} deliveries from {df.match_id.nunique()} matches -> {out}  ({out.stat().st_size / 1e6:.1f} MB)")
    if missing: print(f"   {len(missing)} matches in pak_matches.csv were not found in the ZIPs (skipped): {sorted(missing)[:8]}")


if __name__ == "__main__":
    main()
