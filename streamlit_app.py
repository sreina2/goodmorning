import re
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Commodities Market Briefs", page_icon="📈", layout="wide")

BASE_DIR = Path(__file__).parent
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")


def list_briefs(folder):
    dir_path = BASE_DIR / "briefs" / folder
    if not dir_path.exists():
        return []
    return sorted(
        (f for f in dir_path.iterdir() if DATE_RE.match(f.name)),
        key=lambda f: f.stem,
        reverse=True,
    )


def render_tab(folder, label):
    files = list_briefs(folder)
    if not files:
        st.info(f"No {label.lower()} briefs yet — check back after the next scheduled run.")
        return

    dates = [f.stem for f in files]
    selected = st.selectbox("Date", dates, index=0, key=f"{folder}_select")
    chosen = next(f for f in files if f.stem == selected)

    caption = f"Latest {label.lower()} — {selected}" if selected == dates[0] else f"{label} — {selected}"
    st.caption(caption)
    st.markdown(chosen.read_text(encoding="utf-8"))


st_autorefresh(interval=5 * 60 * 1000, key="brief_refresh")

st.title("📈 Commodities Market Briefs")

tab_morning, tab_eod = st.tabs(["🌅 Morning Brief", "🌆 End-of-Day Brief"])

with tab_morning:
    render_tab("morning", "Morning Brief")

with tab_eod:
    render_tab("eod", "End-of-Day Brief")

st.caption(
    "Auto-refreshes every 5 minutes. New briefs appear here automatically once the "
    "scheduled routine writes and pushes them to this repo."
)
