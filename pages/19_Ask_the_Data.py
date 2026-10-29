"""Ask the Data: type a question in plain English; Groq writes a pandas expression, it is checked and run on your CSVs."""
import pandas as pd
import streamlit as st

import ask_engine as AE
from utils import data as D
from utils import theme as T

D.setup()
m, b, w = D.load()
T.hero("Ask the Data", "Ask a question in plain English. Groq writes the query, the dashboard runs it on your data")

# ---- API key: secrets.toml  ->  environment variable  ->  box below ---------------------------------------------
key = AE.get_key(st)
with st.sidebar:
    st.markdown("**Groq settings**")
    if not key:
        key = st.text_input("Groq API key", type="password", placeholder="gsk_...", help="Free key from console.groq.com. Not saved anywhere.")
    else:
        st.success("API key loaded")
    @st.cache_data(ttl=3600, show_spinner=False)
    def _models(k):
        return AE.list_models(k)
    try:
        _list = _models(key) if key else AE.MODELS
    except Exception as e:
        _list = AE.MODELS; st.warning(f"Could not fetch your model list ({e}). Using defaults.")
    model = st.selectbox("Model", _list or AE.MODELS, help="Live list from your Groq account. The first one is the recommended pick.")
if not key:
    st.info("Add your Groq key to continue. Put `GROQ_API_KEY = \"gsk_...\"` in `.streamlit/secrets.toml` (recommended), "
            "or paste it into the sidebar box. Get a free key at console.groq.com.")
    st.stop()

mm = m.copy(); mm["date"] = pd.to_datetime(mm["date"])
frames = {"matches": mm, "batting": b, "bowling": w}
system = AE.SYSTEM.format(frames=", ".join(frames), schema=AE.schema_text({
    "matches": mm[[c for c in ["match_id", "date", "year", "format", "opponent", "venue", "city", "location_type", "tournament", "stage_detail", "toss_winner",
                                "toss_decision", "pak_won_toss", "pak_batting_order", "result", "margin", "is_win", "is_loss", "is_completed", "player_of_match",
                                "pak_runs", "pak_wkts_lost", "opp_runs", "opp_wkts_lost", "pak_run_rate", "run_diff", "pak_captain", "pak_coach", "is_knockout"] if c in mm]],
    "batting": b, "bowling": w}))

EXAMPLES = ["Babar Azam's batting average and strike rate in each format",
            "Win % by captain in T20Is, minimum 10 matches",
            "Top 10 Pakistan wicket-takers in Tests since 2020",
            "Win % when Pakistan wins the toss vs loses it, by format",
            "How many hundreds has Mohammad Rizwan scored as captain vs not?"]
st.caption("Try one:")
cols = st.columns(len(EXAMPLES))
picked = None
for c, ex in zip(cols, EXAMPLES):
    if c.button(ex, use_container_width=True): picked = ex

st.session_state.setdefault("ask_history", [])
for h in st.session_state.ask_history:
    with st.chat_message("user"): st.write(h["q"])
    with st.chat_message("assistant"):
        st.write(h["answer"])
        with st.expander("How this was computed"):
            st.code(h["code"], language="python"); st.caption(h["note"])
            if h["table"] is not None: st.dataframe(h["table"], width="stretch")

q = st.chat_input("Ask about matches, players, captains, coaches...") or picked
if q:
    with st.chat_message("user"): st.write(q)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                ctx = [{"role": "user", "content": hh["q"]} for hh in st.session_state.ask_history[-2:]] + [{"role": "user", "content": q}]
                tried = [model] + [x for x in (_list or []) if x != model][:4]
                for model_try in tried:                      # skip models Groq has retired / your key cannot use
                    try:
                        raw = AE.ask_groq(key, model_try, system, ctx); model = model_try; break
                    except RuntimeError as e:
                        if "model_not_found" not in str(e) and "404" not in str(e): raise
                else:
                    raise RuntimeError("None of the available Groq models worked. Pick another in the sidebar.")
                code, note = AE.parse_reply(raw)
                res = AE.run_code(code, frames)
                txt = AE.result_to_text(res)
                answer = AE.ask_groq(key, model, "You explain cricket data results. In 2-4 plain sentences answer the question using ONLY the result provided. "
                                     "Do not invent numbers. If the result is empty say so.", [{"role": "user", "content": f"Question: {q}\n\nResult:\n{txt}"}], temperature=0.2)
            st.write(answer)
            tbl = res if isinstance(res, (pd.DataFrame, pd.Series)) else None
            with st.expander("How this was computed"):
                st.code(code, language="python"); st.caption(note)
                if tbl is not None: st.dataframe(tbl, width="stretch")
            st.session_state.ask_history.append({"q": q, "answer": answer, "code": code, "note": note, "table": tbl})
        except Exception as e:
            st.error(f"Could not answer that: {e}")
            st.caption("Try rephrasing, name the format (Test / ODI / T20I) or a player's full name.")
if st.session_state.ask_history and st.button("Clear conversation"):
    st.session_state.ask_history = []; st.rerun()
T.note("Answers come from your CSVs only. Always check the 'How this was computed' box for important numbers. Only read-only pandas expressions are executed.")