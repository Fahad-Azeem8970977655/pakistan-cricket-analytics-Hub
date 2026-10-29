"""'Ask the data' with the Groq API.

Flow: question -> Groq writes pandas code -> the code is checked (AST allow/deny rules) and run on COPIES of the data
-> Groq explains the real result. The model never sees the CSV files, only the column list and the final result table.
"""
import ast
import concurrent.futures as cf
import os
import re

import numpy as np
import pandas as pd
import plotly.express as px
import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
MODEL_SUGGESTIONS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
EXEC_TIMEOUT = 25


class GroqError(RuntimeError):
    pass


def get_api_key(session_state=None, secrets=None):
    """Order: key typed in the page -> .streamlit/secrets.toml -> environment variable."""
    if session_state and session_state.get("groq_key"):
        return session_state["groq_key"].strip()
    try:
        if secrets is not None and "GROQ_API_KEY" in secrets:
            return str(secrets["GROQ_API_KEY"]).strip()
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY", "").strip()


def chat(messages, api_key, model=DEFAULT_MODEL, temperature=0.0, max_tokens=1400, timeout=60):
    if not api_key:
        raise GroqError("No Groq API key. Paste it in the box on this page, or put GROQ_API_KEY in .streamlit/secrets.toml.")
    try:
        r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                          json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}, timeout=timeout)
    except requests.RequestException as e:
        raise GroqError(f"Could not reach Groq ({type(e).__name__}). Check your internet connection.") from e
    if r.status_code == 401:
        raise GroqError("Groq rejected the API key (401). Check the key.")
    if r.status_code == 429:
        raise GroqError("Groq rate limit reached (429). Wait a minute and try again.")
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:200])
        except Exception:
            msg = r.text[:200]
        raise GroqError(f"Groq error {r.status_code}: {msg}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        raise GroqError("Unexpected reply from Groq.") from e


# ------------------------------------------------------------------ prompt
HINTS = """DATA NOTES
- result is from Pakistan's point of view: Won, Lost, Tied, Draw, No result. Win % = Won / (Won + Lost + Tied).
- format is Test, ODI or T20I. pak_batting_order is 'Batting first' or 'Batting second'. location_type: Home, Home (UAE), Away, Neutral.
- pak_runs / opp_runs are team totals. In Tests they are the sum of both innings.
- the 15 Pakistan v Afghanistan games (bbb_source == 'ESPN play-by-play', not in Cricsheet) have hand-collected scorecards PLUS ESPN delivery-level data: they are in pak_deliveries / pak_overs and have dot_balls and phase columns, but there are no pak_fielding rows (the source names no fielder). Matches with detail_level == 'result-only' (2, Oct 2026) have no batting / bowling rows at all. Empty means unknown, not zero.
- Pakistan player names are full names (e.g. 'Babar Azam'). Opposition names are Cricsheet style (e.g. 'KS Williamson').
- pak_batting.dismissed_by is the opposition bowler who dismissed the Pakistan batter (empty for run-outs / not out).
- opp_batting.dismissal is text such as 'c Babar Azam b Shaheen Shah Afridi'.
- Use match_id to join tables. Dates are datetime64."""


def schema_prompt(frames):
    parts = []
    for name, df in frames.items():
        cols = []
        for c in df.columns:
            s = df[c]
            if s.dtype == object or str(s.dtype).startswith("str") or str(s.dtype) == "category":
                u = s.dropna().unique()
                ex = f" values: {list(u[:12])}" if 0 < len(u) <= 12 else ""
                cols.append(f"{c} (text){ex}")
            else:
                cols.append(f"{c} ({s.dtype})")
        parts.append(f"DataFrame `{name}` ({len(df)} rows): " + "; ".join(cols))
    return "\n".join(parts)


def system_prompt(frames):
    return ("You are a careful cricket data analyst. Answer the user's question about Pakistan men's international cricket by writing Python (pandas) code.\n"
            "RULES:\n- Output ONE ```python code block and nothing else.\n"
            "- Available names: pd, np, px (plotly.express) and the DataFrames listed below. Do NOT import anything, do NOT read or write files.\n"
            "- Use boolean masks (df[df.col == x]) instead of df.query(). Never modify the original frames; use .copy() if you change one.\n"
            "- Put the final answer in a variable called `result` (a DataFrame, Series, number or short string), at most 40 rows. Round numbers sensibly.\n"
            "- Optionally put a Plotly Express figure in `fig` with titles and axis labels.\n"
            "- If the data cannot answer the question, set result = 'The data cannot answer this because ...'.\n"
            "- Mention sample size (matches / innings) as a column when you compute averages or percentages.\n\n"
            + HINTS + "\n\n" + schema_prompt(frames))


def extract_code(text):
    m = re.search(r"```(?:python|py)?\s*(.*?)```", text, re.S | re.I)
    return (m.group(1) if m else text).strip()


# ------------------------------------------------------------------ safety
BLOCKED_NAMES = {"eval", "exec", "compile", "open", "input", "__import__", "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir", "breakpoint",
                 "exit", "quit", "help", "memoryview", "os", "sys", "subprocess", "builtins", "importlib", "pickle", "print", "type", "object", "super"}
BLOCKED_ATTRS = {"eval", "exec", "to_csv", "to_pickle", "to_excel", "to_json", "to_sql", "to_parquet", "to_feather", "to_hdf", "to_html", "to_latex",
                 "to_clipboard", "to_xml", "to_stata", "to_orc", "style", "format", "format_map", "write_html", "write_image", "write_json", "show",
                 "io", "compat", "testing", "util", "api", "core", "system", "popen", "load", "save", "dump", "loads", "dumps"}
BLOCKED_NODES = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.While, ast.Try, ast.With, ast.AsyncWith,
                 ast.Global, ast.Nonlocal, ast.Await, ast.Yield, ast.YieldFrom, ast.AsyncFor)
SAFE_BUILTINS = {n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
                 for n in ("len", "range", "min", "max", "sum", "sorted", "round", "abs", "enumerate", "zip", "list", "dict", "set", "str", "int", "float",
                           "bool", "any", "all", "map", "filter", "reversed", "tuple", "isinstance", "slice", "divmod", "pow", "True", "False", "None")}


def validate_code(code):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Syntax error: {e.msg} (line {e.lineno})")
    for node in ast.walk(tree):
        if isinstance(node, BLOCKED_NODES):
            raise ValueError(f"Not allowed: {type(node).__name__} (no imports, functions, loops with while, try or with)")
        if isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            raise ValueError(f"Not allowed: name '{node.id}'")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_") or node.attr in BLOCKED_ATTRS or node.attr.startswith("read_"):
                raise ValueError(f"Not allowed: attribute '.{node.attr}'")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value:
            raise ValueError("Not allowed: strings containing '__'")
    return tree


def run_code(code, frames):
    """Validate, then run on COPIES of the frames with a timeout. Returns (result, fig)."""
    tree = validate_code(code)
    env = {"__builtins__": SAFE_BUILTINS, "pd": pd, "np": np, "px": px}
    env.update({k: v.copy() for k, v in frames.items()})

    def _go():
        exec(compile(tree, "<ask-the-data>", "exec"), env)  # noqa: S102  (validated above, no builtins like open/import)
        return env.get("result"), env.get("fig")

    with cf.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_go)
        try:
            res, fig = fut.result(timeout=EXEC_TIMEOUT)
        except cf.TimeoutError:
            raise TimeoutError(f"The code took longer than {EXEC_TIMEOUT}s.")
    if res is None:
        raise ValueError("The code did not set a variable called `result`.")
    return res, (fig if hasattr(fig, "to_plotly_json") else None)


def result_text(res, limit=3500):
    if isinstance(res, pd.Series):
        res = res.to_frame()
    if isinstance(res, pd.DataFrame):
        s = res.head(40).to_string(max_cols=14, max_colwidth=40)
        if len(res) > 40:
            s += f"\n... ({len(res)} rows in total)"
    else:
        s = str(res)
    return s[:limit]


def ask(question, frames, api_key, model=DEFAULT_MODEL, history=None):
    """Returns dict(code, result, fig, answer, error, attempts)."""
    out = dict(code="", result=None, fig=None, answer="", error="", attempts=0)
    msgs = [{"role": "system", "content": system_prompt(frames)}]
    for q, a in (history or [])[-3:]:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": f"(earlier answer) {a[:600]}"}]
    msgs.append({"role": "user", "content": question})
    err = ""
    for attempt in (1, 2):
        out["attempts"] = attempt
        reply = chat(msgs, api_key, model)
        out["code"] = extract_code(reply)
        try:
            out["result"], out["fig"] = run_code(out["code"], frames)
            err = ""
            break
        except Exception as e:  # validation or runtime error: tell the model once and retry
            err = f"{type(e).__name__}: {e}"
            msgs += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": f"That code failed with: {err}\nFix it and return ONLY the corrected ```python block."}]
    if err:
        out["error"] = err
        return out
    expl = [{"role": "system", "content": "You are a cricket analyst. Explain the RESULT TABLE to the user in 2 to 5 short sentences. "
                                          "Use only numbers that appear in the table, mention sample sizes, and warn when a sample is small (under 10 matches). "
                                          "Do not invent facts or players."},
            {"role": "user", "content": f"Question: {question}\n\nRESULT TABLE:\n{result_text(out['result'])}"}]
    out["answer"] = chat(expl, api_key, model, temperature=0.2, max_tokens=500)
    return out
