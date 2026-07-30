import calendar
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import streamlit as st
from streamlit_autorefresh import st_autorefresh

socket.setdefaulttimeout(6)

st.set_page_config(page_title="Commodities Market Briefs", page_icon="📈", layout="wide")

BASE_DIR = Path(__file__).parent
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
ET = ZoneInfo("America/New_York")

NEWS_FEEDS = [
    ("Investing.com — Commodities & Futures", "https://www.investing.com/rss/news_11.rss"),
    ("Investing.com — Energy Analysis", "https://www.investing.com/rss/commodities_Energy.rss"),
    ("Investing.com — Metals Analysis", "https://www.investing.com/rss/commodities_Metals.rss"),
    ("Investing.com — Agriculture Analysis", "https://www.investing.com/rss/commodities_Agriculture.rss"),
    ("OilPrice.com", "https://oilprice.com/rss/main"),
    ("Mining.com", "https://www.mining.com/feed/"),
]


def format_time_no_leading_zero(dt, with_seconds=False):
    hour12 = dt.hour % 12 or 12
    suffix = dt.strftime("%M:%S %p") if with_seconds else dt.strftime("%M %p")
    return f"{hour12}:{suffix}"


def list_briefs(folder):
    dir_path = BASE_DIR / "briefs" / folder
    if not dir_path.exists():
        return []
    return sorted(
        (f for f in dir_path.iterdir() if DATE_RE.match(f.name)),
        key=lambda f: f.stem,
        reverse=True,
    )


def render_brief_tab(folder, label):
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


@st.cache_data(ttl=180)
def fetch_breaking_news():
    items = []
    for source, url in NEWS_FEEDS:
        try:
            parsed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        except Exception:
            continue
        for entry in parsed.entries[:15]:
            published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            timestamp = calendar.timegm(published) if published else None
            items.append(
                {
                    "title": entry.get("title", "Untitled"),
                    "link": entry.get("link", ""),
                    "source": source,
                    "timestamp": timestamp,
                }
            )

    items.sort(key=lambda item: item["timestamp"] or 0, reverse=True)

    seen, deduped = set(), []
    for item in items:
        key = item["title"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped[:30]


def render_breaking_news_tab():
    col_caption, col_button = st.columns([5, 1])
    with col_button:
        if st.button("🔄 Refresh now", key="news_refresh"):
            fetch_breaking_news.clear()

    items = fetch_breaking_news()

    with col_caption:
        st.caption(
            f"Last refreshed {format_time_no_leading_zero(datetime.now(tz=ET), with_seconds=True)} ET"
            " · also auto-refreshes every 5 minutes"
        )

    if not items:
        st.info("No headlines available right now — try refreshing in a moment.")
        return

    for item in items:
        if item["timestamp"]:
            when = datetime.fromtimestamp(item["timestamp"], tz=timezone.utc).astimezone(ET)
            when_str = f"{when.strftime('%b %d')}, {format_time_no_leading_zero(when)} ET"
        else:
            when_str = "time unknown"
        st.markdown(f"**[{item['title']}]({item['link']})**  \n*{item['source']} — {when_str}*")
        st.divider()


st_autorefresh(interval=5 * 60 * 1000, key="brief_refresh")

st.title("📈 Commodities Market Briefs")

tab_morning, tab_eod, tab_news = st.tabs(["🌅 Morning Brief", "🌆 End-of-Day Brief", "🚨 Breaking News"])

with tab_morning:
    render_brief_tab("morning", "Morning Brief")

with tab_eod:
    render_brief_tab("eod", "End-of-Day Brief")

with tab_news:
    render_breaking_news_tab()

st.caption(
    "Morning/End-of-Day briefs auto-refresh every 5 minutes and update automatically once the "
    "scheduled routine writes and pushes them to this repo. Breaking News pulls live commodities "
    "headlines directly and can be refreshed on demand."
)
