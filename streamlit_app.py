import calendar
import re
import socket
from collections import Counter
from datetime import datetime, timedelta, timezone
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
GREETING_NAME = "Evan"

NEWS_FEEDS = [
    ("Investing.com — Commodities & Futures", "https://www.investing.com/rss/news_11.rss", "General"),
    ("Investing.com — Energy Analysis", "https://www.investing.com/rss/commodities_Energy.rss", "Energy"),
    ("Investing.com — Metals Analysis", "https://www.investing.com/rss/commodities_Metals.rss", "Metals"),
    ("Investing.com — Agriculture Analysis", "https://www.investing.com/rss/commodities_Agriculture.rss", "Ags"),
    ("OilPrice.com", "https://oilprice.com/rss/main", "Energy"),
    ("Mining.com", "https://www.mining.com/feed/", "Metals"),
]

TRENDING_STOPWORDS = {
    "the", "a", "an", "to", "of", "in", "on", "for", "as", "with", "its", "it", "will",
    "from", "and", "is", "are", "has", "have", "this", "that", "at", "by", "be", "after",
    "amid", "over", "into", "than", "up", "down", "could", "may", "says", "said", "set",
    "how", "why", "what", "not", "but", "still", "more", "most", "now", "out", "off",
    "your", "you", "we", "us", "about", "eu", "new", "next", "amidst", "their", "his",
    "her", "them", "these", "those", "can", "here", "there",
}
TRENDING_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']+")

CUSTOM_CSS = """
<style>
:root {
    --maven-bg: #EAF3EF;
    --maven-card: #FFFFFF;
    --maven-ink: #16302A;
    --maven-accent: #2F6D53;
    --maven-border: #D3E6DD;
}

[data-testid="stAppViewContainer"] { background-color: var(--maven-bg); }
[data-testid="stHeader"] { background-color: rgba(0,0,0,0); }
.block-container { padding-top: 1.25rem; padding-bottom: 2rem; max-width: 880px; }

h1, h2, h3 { font-family: Georgia, 'Times New Roman', serif; color: var(--maven-ink) !important; }
p, li, span, label, .stMarkdown { color: var(--maven-ink); }

.maven-subtitle {
    font-family: Georgia, 'Times New Roman', serif;
    color: var(--maven-accent);
    font-size: 0.95rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: -0.5rem 0 1rem 0;
}

[data-testid="stTabs"] button[role="tab"] {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 0.95rem;
    color: var(--maven-ink);
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--maven-accent) !important;
    border-bottom-color: var(--maven-accent) !important;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 10px !important;
    border-color: var(--maven-border) !important;
    background-color: var(--maven-card) !important;
}

[data-testid="stMetricValue"] { color: var(--maven-ink); font-size: 1.4rem; }
[data-testid="stMetricLabel"] { color: var(--maven-accent); }

#maven-splash {
    position: fixed;
    inset: 0;
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(160deg, #16302A 0%, #234C3D 100%);
    animation: maven-splash-fade 4.6s ease forwards;
    pointer-events: none;
}
#maven-splash span {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: clamp(1.8rem, 5vw, 3rem);
    color: #EAF3EF;
    letter-spacing: 0.03em;
    opacity: 0;
    animation: maven-text-fade 4.6s ease forwards;
}
@keyframes maven-splash-fade {
    0% { opacity: 1; }
    78% { opacity: 1; }
    100% { opacity: 0; visibility: hidden; }
}
@keyframes maven-text-fade {
    0% { opacity: 0; transform: translateY(8px); }
    18% { opacity: 1; transform: translateY(0); }
    82% { opacity: 1; }
    100% { opacity: 0; }
}
</style>
"""


def greeting_for_now():
    hour = datetime.now(tz=ET).hour
    if 5 <= hour < 12:
        part_of_day = "Morning"
    elif 12 <= hour < 17:
        part_of_day = "Afternoon"
    else:
        part_of_day = "Evening"
    return f"Good {part_of_day}, {GREETING_NAME}"


def render_splash_once():
    if st.session_state.get("splash_shown"):
        return
    st.session_state["splash_shown"] = True
    st.markdown(f'<div id="maven-splash"><span>{greeting_for_now()}</span></div>', unsafe_allow_html=True)


def format_time_no_leading_zero(dt, with_seconds=False):
    hour12 = dt.hour % 12 or 12
    suffix = dt.strftime("%M:%S %p") if with_seconds else dt.strftime("%M %p")
    return f"{hour12}:{suffix}"


def next_display_line(hour_et):
    now = datetime.now(tz=ET)
    next_run = now.replace(hour=hour_et, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)

    days_ahead = (next_run.date() - now.date()).days
    day_label = {0: "today", 1: "tomorrow"}.get(days_ahead, next_run.strftime("%A"))
    time_label = f"{format_time_no_leading_zero(next_run)} ET"
    return f"Report will display {day_label} at {time_label}."


def list_briefs(folder):
    dir_path = BASE_DIR / "briefs" / folder
    if not dir_path.exists():
        return []
    return sorted(
        (f for f in dir_path.iterdir() if DATE_RE.match(f.name)),
        key=lambda f: f.stem,
        reverse=True,
    )


def render_brief_tab(folder, label, hour_et):
    st.caption(next_display_line(hour_et))

    files = list_briefs(folder)
    if not files:
        st.info(f"No {label.lower()} briefs yet — check back after the next scheduled run.")
        return

    dates = [f.stem for f in files]
    selected = st.selectbox("Date", dates, index=0, key=f"{folder}_select")
    chosen = next(f for f in files if f.stem == selected)

    caption = f"Latest {label.lower()} — {selected}" if selected == dates[0] else f"{label} — {selected}"
    st.caption(caption)
    with st.container(border=True):
        st.markdown(chosen.read_text(encoding="utf-8"))


@st.cache_data(ttl=180)
def fetch_breaking_news():
    items = []
    for source, url, category in NEWS_FEEDS:
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
                    "category": category,
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


def summarize_news(items):
    by_category = Counter(item["category"] for item in items)
    timestamps = [item["timestamp"] for item in items if item["timestamp"]]

    word_counts = {}
    for item in items:
        for match in TRENDING_WORD_RE.findall(item["title"]):
            key = match.lower()
            if key in TRENDING_STOPWORDS or len(key) < 4:
                continue
            display, count = word_counts.get(key, (match, 0))
            word_counts[key] = (display, count + 1)

    trending = [display for display, count in sorted(word_counts.values(), key=lambda pair: pair[1], reverse=True) if count >= 2]

    return {
        "total": len(items),
        "by_category": by_category,
        "oldest": min(timestamps) if timestamps else None,
        "newest": max(timestamps) if timestamps else None,
        "trending": trending[:6],
    }


def render_news_summary(summary):
    with st.container(border=True):
        cols = st.columns(5)
        cols[0].metric("Headlines", summary["total"])
        cols[1].metric("Energy", summary["by_category"].get("Energy", 0))
        cols[2].metric("Metals", summary["by_category"].get("Metals", 0))
        cols[3].metric("Ags", summary["by_category"].get("Ags", 0))
        cols[4].metric("General", summary["by_category"].get("General", 0))

        if summary["oldest"] and summary["newest"]:
            oldest = datetime.fromtimestamp(summary["oldest"], tz=timezone.utc).astimezone(ET)
            newest = datetime.fromtimestamp(summary["newest"], tz=timezone.utc).astimezone(ET)
            span_hours = max(1, round((summary["newest"] - summary["oldest"]) / 3600))
            st.caption(
                f"Covering the last ~{span_hours}h — {format_time_no_leading_zero(oldest)} ET "
                f"to {format_time_no_leading_zero(newest)} ET"
            )

        if summary["trending"]:
            st.markdown(f"**🔥 Trending:** {', '.join(summary['trending'])}")


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

    render_news_summary(summarize_news(items))
    st.write("")

    for item in items:
        if item["timestamp"]:
            when = datetime.fromtimestamp(item["timestamp"], tz=timezone.utc).astimezone(ET)
            when_str = f"{when.strftime('%b %d')}, {format_time_no_leading_zero(when)} ET"
        else:
            when_str = "time unknown"
        with st.container(border=True):
            st.markdown(f"**[{item['title']}]({item['link']})**")
            st.caption(f"{item['source']} — {when_str}")


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
render_splash_once()
st_autorefresh(interval=5 * 60 * 1000, key="brief_refresh")

st.image(str(BASE_DIR / "assets" / "maven-header.png"), use_container_width=True)
st.markdown('<p class="maven-subtitle">Commodities Market Intelligence</p>', unsafe_allow_html=True)

tab_morning, tab_eod, tab_news = st.tabs(["🌅 Morning Brief", "🌆 End-of-Day Brief", "🚨 Breaking News"])

with tab_morning:
    render_brief_tab("morning", "Morning Brief", hour_et=8)

with tab_eod:
    render_brief_tab("eod", "End-of-Day Brief", hour_et=17)

with tab_news:
    render_breaking_news_tab()

st.caption(
    "Morning/End-of-Day briefs auto-refresh every 5 minutes and update automatically once the "
    "scheduled routine writes and pushes them to this repo. Breaking News pulls live commodities "
    "headlines directly and can be refreshed on demand."
)
