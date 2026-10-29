"""Helpers for the 'Ask the Data' page: Groq call + a locked-down pandas evaluator.
Lives at the project root (next to app.py) so `import ask_engine` works from pages/."""
import ast, json, os, re

import numpy as np
import pandas as pd
import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b"]   # offline fallback only
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
_SKIP = ("whisper", "tts", "guard", "embed", "vision-preview", "orpheus", "playai", "distil-whisper", "safeguard")
_PREFER = ("gpt-oss-120b", "llama-3.3-70b", "llama-4", "qwen", "kimi", "llama-3.1-70b", "gpt-oss-20b", "llama-3.1-8b")


def list_models(key, timeout=20):
    """Ask Groq which chat models this key can use right now (models get retired, so never hard-code)."""
    r = requests.get(GROQ_MODELS_URL, headers={"Authorization": f"Bearer {key}"}, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"Groq error {r.status_code}: {r.text[:200]}")
    ids = [m["id"] for m in r.json().get("data", []) if m.get("active", True) and not any(k in m["id"].lower() for k in _SKIP)]
    rank = lambda i: next((n for n, p in enumerate(_PREFER) if p in i.lower()), len(_PREFER))
    return sorted(ids, key=lambda i: (rank(i), i))

_BLOCKED_ATTRS = {"to_csv", "to_json", "to_pickle", "to_excel", "to_parquet", "to_sql", "to_hdf", "to_clipboard", "to_feather",
                  "to_html", "to_latex", "to_markdown", "to_xml", "eval", "system", "popen", "open", "read", "write", "load", "loads",
                  "save", "dump", "mkdir", "remove", "unlink", "rmdir", "rename", "pipe", "apply_async", "style"}
_OK_TO = {"to_dict", "to_list", "to_frame", "to_numpy", "to_period", "to_datetime", "to_numeric", "to_timedelta", "to_string", "to_timestamp"}
_BLOCKED_NAMES = {"eval", "exec", "compile", "open", "input", "getattr", "setattr", "delattr", "globals", "locals", "vars",
                  "dir", "type", "__import__", "breakpoint", "help", "os", "sys", "subprocess", "importlib"}
_SAFE_BUILTINS = {n: __builtins__[n] if isinstance(__builtins__, dict) else getattr(__builtins__, n)
                  for n in ("len", "sum", "min", "max", "round", "sorted", "list", "dict", "set", "tuple", "str", "int", "float",
                            "bool", "abs", "range", "enumerate", "zip", "any", "all", "reversed", "isinstance")}


def get_key(st):
    """Look for the Groq key in: Streamlit secrets, environment variable, then the sidebar box."""
    try:
        k = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        k = ""
    k = k or os.environ.get("GROQ_API_KEY", "")
    return "" if k.startswith("gsk_paste") else k


def schema_text(frames: dict) -> str:
    out = []
    for name, df in frames.items():
        cols = ", ".join(f"{c}({'num' if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]) else 'bool' if pd.api.types.is_bool_dtype(df[c]) else 'date' if pd.api.types.is_datetime64_any_dtype(df[c]) else 'text'})" for c in df.columns)
        out.append(f"{name} [{len(df)} rows]: {cols}")
    return "\n".join(out)


SYSTEM = """You answer questions about Pakistan men's cricket matches (2015 to 2026, Tests, ODIs, T20Is) by writing ONE pandas expression.
Data frames available: {frames}. Libraries: pd, np. No imports, no assignments, no file access.
Schema:
{schema}
Rules:
- Win % = wins / completed matches * 100 (use is_win and is_completed). Draws count as completed.
- Batting average = runs / dismissals (is_out). Strike rate = runs / balls * 100. Bowling average = runs_conceded / wickets.
- pak_captain / pak_coach columns on `matches` hold the captain and coach. A player 'as captain' means batting.player == matches.pak_captain for that match_id (merge on match_id).
- Names are text; use .str.contains(..., case=False) for partial matches. Always return a compact result: use .head(20) for tables.
- The expression must evaluate to a DataFrame, Series or a scalar. One expression only (chain with .pipe or a lambda inside if needed).
Reply ONLY with JSON: {{"code": "<expression>", "note": "<one short sentence on how you computed it>"}}"""


def ask_groq(key, model, system, messages, temperature=0.0, timeout=60):
    r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      json={"model": model, "temperature": temperature, "messages": [{"role": "system", "content": system}] + messages}, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"Groq error {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def parse_reply(txt):
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    try:
        d = json.loads(txt)
    except json.JSONDecodeError:
        mt = re.search(r"\{.*\}", txt, re.S)
        if not mt: raise ValueError("The model did not return JSON.")
        d = json.loads(mt.group(0))
    return d["code"].strip().rstrip(";"), d.get("note", "")


def validate(code, allowed_names):
    """Reject anything that is not a single, read-only pandas expression."""
    tree = ast.parse(code, mode="eval")
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.Await, ast.Yield, ast.NamedExpr)):
            raise ValueError("Not allowed in an expression.")
        if isinstance(n, ast.Attribute) and (n.attr.startswith("_") or n.attr in _BLOCKED_ATTRS or n.attr.startswith("read_")
                                             or (n.attr.startswith("to_") and n.attr not in _OK_TO)):
            raise ValueError(f"Attribute '{n.attr}' is not allowed.")
        if isinstance(n, ast.Name):
            if n.id in _BLOCKED_NAMES or n.id.startswith("__"):
                raise ValueError(f"Name '{n.id}' is not allowed.")
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and ("__" in n.value or n.value.startswith(("/", "~", ".."))):
            raise ValueError("Suspicious string in expression.")
    return tree


def run_code(code, frames):
    validate(code, set(frames))
    env = {"__builtins__": _SAFE_BUILTINS, "pd": pd, "np": np, **{k: v.copy() for k, v in frames.items()}}
    return eval(compile(ast.parse(code, mode="eval"), "<ask>", "eval"), env)


def result_to_text(res, n=40):
    if isinstance(res, pd.DataFrame): return res.head(n).to_string()[:4000]
    if isinstance(res, pd.Series): return res.head(n).to_string()[:4000]
    return str(res)[:2000]