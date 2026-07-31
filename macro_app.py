import calendar
import re
import socket
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser
import streamlit as st
from streamlit_autorefresh import st_autorefresh

socket.setdefaulttimeout(6)

st.set_page_config(page_title="Macro & Fixed Income Intelligence", page_icon="📊", layout="wide")

BASE_DIR = Path(__file__).parent
ET = ZoneInfo("America/New_York")
GREETING_NAME = "Charles"
BRIEF_PATH = BASE_DIR / "macro" / "brief.md"

NEWS_FEEDS = [
    ("Hedgeweek", "https://www.hedgeweek.com/feed/", "Fund News"),
    ("HedgeNordic", "https://www.hedgenordic.com/feed/", "Fund News"),
    ("Markets Media", "https://www.marketsmedia.com/feed/", "Fund News"),
    ("Opalesque", "https://www.opalesque.com/rss.xml", "Fund News"),
    ("Institutional Asset Manager", "https://www.institutionalassetmanager.co.uk/feed/", "Fund News"),
    ("Investing.com — Forex News", "https://www.investing.com/rss/news_1.rss", "Rates & FX"),
    ("Investing.com — Forex Opinion & Analysis", "https://www.investing.com/rss/forex.rss", "Rates & FX"),
    ("Investing.com — Bonds Analysis & Opinion", "https://www.investing.com/rss/bonds.rss", "Rates & FX"),
    ("Investing.com — Economic Indicators", "https://www.investing.com/rss/news_95.rss", "Macro & Policy"),
    ("Federal Reserve — Press Releases", "https://www.federalreserve.gov/feeds/press_all.xml", "Macro & Policy"),
    ("ECB — Press Releases", "https://www.ecb.europa.eu/rss/press.xml", "Macro & Policy"),
    ("Bank of England — News", "https://www.bankofengland.co.uk/rss/news", "Macro & Policy"),
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

TAG_KEYWORDS = {
    "Hires & Moves": [r"hire", r"hires", r"joins", r"departs?\b", r"departure", r"steps down", r"appoint", r"names? [A-Z]", r"poach"],
    "Fund Launches & Closures": [r"launch", r"raises?\b", r"\bAUM\b", r"capacity", r"closes?\b", r"closure", r"shuts down", r"winds down"],
    "Multi-Strat": [r"multi-strat", r"multi-manager", r"pod shop", r"platform fund"],
    "Rates & Fixed Income": [r"\brates?\b", r"\byield", r"treasury", r"\bbond", r"\bcurve\b", r"duration", r"\bgilts?\b", r"\bbunds?\b", r"\bSTIR\b"],
    "FX": [r"\bFX\b", r"currency", r"\bdollar\b", r"\beuro\b", r"\byen\b", r"sterling", r"forex"],
    "EM": [r"emerging market", r"\bEM\b", r"\bChina\b", r"\bBrazil\b", r"\bIndia\b", r"\bTurkey\b", r"\bMexico\b"],
    "Regulatory & Policy": [r"\bFed\b", r"\bECB\b", r"Bank of England", r"regulat", r"\bpolicy\b", r"rate decision", r"\bFOMC\b", r"\bhike", r"\bcut\b"],
    "London/Europe": [r"\bLondon\b", r"\bUK\b", r"\bEurope", r"Britain"],
    "US": [r"U\.S\.", r"\bUS\b", r"United States", r"Wall Street", r"New York"],
}
TAG_PATTERNS = {tag: re.compile("|".join(patterns), re.IGNORECASE) for tag, patterns in TAG_KEYWORDS.items()}


def tags_for_title(title):
    return [tag for tag, pattern in TAG_PATTERNS.items() if pattern.search(title)]


CUSTOM_CSS = """
<style>
:root {
    --macro-bg: #0B1A2E;
    --macro-card: #122644;
    --macro-ink: #AFDBFF;
    --macro-accent: #6FC3FF;
    --macro-border: #23405E;
    --macro-button-bg: #1E4266;
}

[data-testid="stAppViewContainer"] { background-color: var(--macro-bg); }
[data-testid="stHeader"] { background-color: rgba(0,0,0,0); }
.block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; max-width: 95%; text-align: center; }

p, li, span, label, .stMarkdown, h1, h2, h3, h4 { color: var(--macro-ink); }

.macro-subtitle {
    font-family: Georgia, 'Times New Roman', serif !important;
    color: var(--macro-accent) !important;
    font-size: clamp(1.9rem, 4.2vw, 2.6rem) !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    text-align: center !important;
    margin: 0.25rem 0 1.1rem 0 !important;
}

.macro-brief-card {
    background-color: var(--macro-card);
    border: 1px solid var(--macro-border);
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    text-align: left;
    margin-bottom: 1.25rem;
}
.macro-brief-card p { margin-bottom: 0.85rem; }

.macro-trending {
    font-family: Georgia, 'Times New Roman', serif !important;
    font-size: clamp(1.1rem, 2.4vw, 1.45rem) !important;
    color: var(--macro-accent) !important;
    text-align: center !important;
    margin: 0.9rem 0 1.4rem 0 !important;
    padding: 0.6rem 1rem !important;
    border-top: 1px solid var(--macro-border);
    border-bottom: 1px solid var(--macro-border);
}

[data-testid="stMetricValue"] { color: var(--macro-ink); font-size: 1.6rem; }
[data-testid="stMetricLabel"] { color: var(--macro-accent); font-size: 0.95rem; }

.stButton button {
    margin: 0.4rem auto 0 auto;
    min-height: 2.9rem;
    font-size: 1.1rem;
    background-color: var(--macro-button-bg) !important;
    color: var(--macro-ink) !important;
    border: 1px solid var(--macro-border) !important;
    font-weight: 600;
}

[data-testid="stWidgetLabel"] { text-align: center !important; width: 100%; }
[data-testid="stWidgetLabel"] label { width: 100%; justify-content: center !important; }

[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background-color: var(--macro-bg) !important;
    border-color: var(--macro-border) !important;
}
[data-testid="stMultiSelect"] span { color: var(--macro-ink) !important; }
[data-baseweb="popover"] { background-color: var(--macro-bg) !important; }
[data-baseweb="popover"] ul { background-color: var(--macro-bg) !important; }
[data-baseweb="popover"] li { background-color: var(--macro-bg) !important; color: var(--macro-ink) !important; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] { background-color: var(--macro-button-bg) !important; }

[data-baseweb="tag"] {
    background-color: #123A63 !important;
    border: 1px solid var(--macro-border) !important;
}
[data-baseweb="tag"] span { color: var(--macro-ink) !important; }
[data-baseweb="tag"] svg { fill: var(--macro-ink) !important; }

.news-row { padding: 0.85rem 0 !important; border-bottom: 1px solid var(--macro-border); text-align: center !important; }
.news-row a { color: var(--macro-ink) !important; text-decoration: none !important; font-weight: 600 !important; font-size: 1.2rem !important; }
.news-row a:hover { color: var(--macro-accent) !important; }
.news-row .news-meta { color: var(--macro-accent) !important; font-size: 1rem !important; margin-top: 0.25rem !important; }

#macro-splash {
    position: fixed;
    inset: 0;
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(160deg, #0A1626 0%, #16324F 100%);
    animation: macro-splash-fade 4.6s ease forwards;
    pointer-events: none;
}
#macro-splash span {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: clamp(1.8rem, 5vw, 3rem);
    color: #AFDBFF;
    letter-spacing: 0.03em;
    opacity: 0;
    animation: macro-text-fade 4.6s ease forwards;
}
@keyframes macro-splash-fade {
    0% { opacity: 1; }
    78% { opacity: 1; }
    100% { opacity: 0; visibility: hidden; }
}
@keyframes macro-text-fade {
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
    st.markdown(f'<div id="macro-splash"><span>{greeting_for_now()}</span></div>', unsafe_allow_html=True)


def format_time_no_leading_zero(dt, with_seconds=False):
    hour12 = dt.hour % 12 or 12
    suffix = dt.strftime("%M:%S %p") if with_seconds else dt.strftime("%M %p")
    return f"{hour12}:{suffix}"


def render_macro_brief():
    if not BRIEF_PATH.exists():
        return
    with st.container():
        st.markdown(f'<div class="macro-brief-card">\n\n{BRIEF_PATH.read_text(encoding="utf-8")}\n\n</div>', unsafe_allow_html=True)


@st.cache_data(ttl=180)
def fetch_breaking_news():
    items = []
    for source, url, category in NEWS_FEEDS:
        try:
            parsed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
        except Exception:
            continue
        for entry in parsed.entries[:20]:
            published = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            timestamp = calendar.timegm(published) if published else None
            title = entry.get("title", "Untitled")
            items.append(
                {
                    "title": title,
                    "link": entry.get("link", ""),
                    "source": source,
                    "category": category,
                    "timestamp": timestamp,
                    "tags": tags_for_title(title),
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

    return deduped[:50]


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
    cols = st.columns(4)
    cols[0].metric("Headlines", summary["total"])
    cols[1].metric("Fund News", summary["by_category"].get("Fund News", 0))
    cols[2].metric("Rates & FX", summary["by_category"].get("Rates & FX", 0))
    cols[3].metric("Macro & Policy", summary["by_category"].get("Macro & Policy", 0))

    if summary["oldest"] and summary["newest"]:
        oldest = datetime.fromtimestamp(summary["oldest"], tz=timezone.utc).astimezone(ET)
        newest = datetime.fromtimestamp(summary["newest"], tz=timezone.utc).astimezone(ET)
        span_hours = max(1, round((summary["newest"] - summary["oldest"]) / 3600))
        st.caption(
            f"Covering the last ~{span_hours}h — {format_time_no_leading_zero(oldest)} ET "
            f"to {format_time_no_leading_zero(newest)} ET"
        )

    if summary["trending"]:
        st.markdown(f'<div class="macro-trending">🔥 Trending: {", ".join(summary["trending"])}</div>', unsafe_allow_html=True)


def render_breaking_news():
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.caption(
            f"Last refreshed {format_time_no_leading_zero(datetime.now(tz=ET), with_seconds=True)} ET"
            " · also auto-refreshes every 5 minutes"
        )
        if st.button("🔄 Refresh now", key="news_refresh", use_container_width=True):
            fetch_breaking_news.clear()

    items = fetch_breaking_news()

    if not items:
        st.info("No headlines available right now — try refreshing in a moment.")
        return

    render_news_summary(summarize_news(items))

    _, col_filter, _ = st.columns([1, 2, 1])
    with col_filter:
        selected_tags = st.multiselect("Filter by topic", list(TAG_KEYWORDS.keys()), key="tag_filter")

    filtered_items = (
        [item for item in items if set(item["tags"]) & set(selected_tags)] if selected_tags else items
    )

    if not filtered_items:
        st.info("No headlines match the selected filters.")
        return

    for item in filtered_items:
        if item["timestamp"]:
            when = datetime.fromtimestamp(item["timestamp"], tz=timezone.utc).astimezone(ET)
            when_str = f"{when.strftime('%b %d')}, {format_time_no_leading_zero(when)} ET"
        else:
            when_str = "time unknown"
        st.markdown(
            f'<div class="news-row"><a href="{item["link"]}" target="_blank">{item["title"]}</a>'
            f'<div class="news-meta">{item["source"]} — {when_str}</div></div>',
            unsafe_allow_html=True,
        )


st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
render_splash_once()
st_autorefresh(interval=5 * 60 * 1000, key="news_refresh_timer")

st.markdown('<p class="macro-subtitle">Macro & Fixed Income Intelligence</p>', unsafe_allow_html=True)

render_macro_brief()
render_breaking_news()
