import calendar
import re
import socket
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import feedparser
import streamlit as st
from streamlit_autorefresh import st_autorefresh

socket.setdefaulttimeout(6)

st.set_page_config(page_title="Commodities Market Intelligence", page_icon="🚨", layout="wide")

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

TAG_KEYWORDS = {
    "US": [r"U\.S\.", r"\bUS\b", r"United States", r"Washington", r"\bFed\b", r"Federal Reserve"],
    "Asia": [r"China", r"\bAsia", r"Japan", r"Korea", r"\bJKM\b", r"Beijing", r"India"],
    "Europe": [r"Europe", r"\bEU\b", r"\bTTF\b", r"Russia", r"Ukraine", r"\bUK\b", r"Britain"],
    "Energy": [r"\boil\b", r"crude", r"\bOPEC\b", r"\bWTI\b", r"\bBrent\b", r"refiner", r"diesel", r"gasoline", r"\bfuel\b"],
    "Natural Gas": [r"\bgas\b", r"\bLNG\b", r"Henry Hub", r"\bTTF\b", r"\bJKM\b"],
    "Metals": [r"\bgold\b", r"\bsilver\b", r"\bcopper\b", r"\bmetal", r"\bmining\b", r"\baluminum\b", r"\bsteel\b"],
    "Ties into FX Markets": [r"\bdollar\b", r"currency", r"\bFX\b", r"\byen\b", r"\beuro\b", r"forex"],
    "Geopolitical Risks": [r"\bIran\b", r"\bwar\b", r"strike", r"sanction", r"conflict", r"military", r"attack", r"tension", r"Hormuz", r"Suez"],
}
TAG_PATTERNS = {tag: re.compile("|".join(patterns), re.IGNORECASE) for tag, patterns in TAG_KEYWORDS.items()}


def tags_for_title(title):
    return [tag for tag, pattern in TAG_PATTERNS.items() if pattern.search(title)]

CUSTOM_CSS = """
<style>
:root {
    --maven-bg: #10201B;
    --maven-ink: #EAF3EF;
    --maven-accent: #57C99D;
    --maven-border: #24443A;
}

[data-testid="stAppViewContainer"] { background-color: var(--maven-bg); }
[data-testid="stHeader"] { background-color: rgba(0,0,0,0); }
.block-container { padding-top: 1.5rem; padding-bottom: 1.5rem; max-width: 720px; text-align: center; }

p, li, span, label, .stMarkdown { color: var(--maven-ink); }

.maven-subtitle {
    font-family: Georgia, 'Times New Roman', serif !important;
    color: var(--maven-accent) !important;
    font-size: clamp(2rem, 4.5vw, 2.8rem) !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    text-align: center !important;
    margin: 0.25rem 0 1.1rem 0 !important;
}

.maven-trending {
    font-family: Georgia, 'Times New Roman', serif !important;
    font-size: clamp(1.15rem, 2.6vw, 1.55rem) !important;
    color: var(--maven-accent) !important;
    text-align: center !important;
    margin: 0.9rem 0 1.4rem 0 !important;
    padding: 0.6rem 1rem !important;
    border-top: 1px solid var(--maven-border);
    border-bottom: 1px solid var(--maven-border);
}

[data-testid="stMetricValue"] { color: var(--maven-ink); font-size: 1.7rem; }
[data-testid="stMetricLabel"] { color: var(--maven-accent); font-size: 1rem; }

.stButton button { margin: 0.4rem auto 0 auto; min-height: 2.9rem; font-size: 1.1rem; }

[data-testid="stWidgetLabel"] { text-align: center !important; width: 100%; }
[data-testid="stWidgetLabel"] label { width: 100%; justify-content: center !important; }

.news-row { padding: 0.85rem 0 !important; border-bottom: 1px solid var(--maven-border); text-align: center !important; }
.news-row a { color: var(--maven-ink) !important; text-decoration: none !important; font-weight: 600 !important; font-size: 1.25rem !important; }
.news-row a:hover { color: var(--maven-accent) !important; }
.news-row .news-meta { color: var(--maven-accent) !important; font-size: 1rem !important; margin-top: 0.25rem !important; }

#maven-splash {
    position: fixed;
    inset: 0;
    z-index: 999999;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(160deg, #0F1E1A 0%, #1E3E32 100%);
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
        st.markdown(f'<div class="maven-trending">🔥 Trending: {", ".join(summary["trending"])}</div>', unsafe_allow_html=True)


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

st.markdown('<p class="maven-subtitle">Commodities Market Intelligence</p>', unsafe_allow_html=True)

render_breaking_news()
