from __future__ import annotations

import os
import re
import html as html_lib
import io
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

# Load variables from a local `.env` file (never commit `.env`).
load_dotenv()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTOR_ID   = "supreme_coder~linkedin-post"
APIFY_BASE = "https://api.apify.com/v2"


st.set_page_config(
    page_title="LinkedIn Post Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _default_apify_token() -> str:
    """
    Token resolution order (called AFTER set_page_config so st.secrets is safe):
    1. APIFY_TOKEN / APIFY_API_TOKEN env var  (local .env via dotenv)
    2. st.secrets['APIFY_TOKEN']              (Streamlit Cloud Secrets)
    """
    for key in ("APIFY_TOKEN", "APIFY_API_TOKEN"):
        t = (os.environ.get(key) or "").strip()
        if t:
            return t
    for key in ("APIFY_TOKEN", "APIFY_API_TOKEN"):
        try:
            val = st.secrets.get(key, "")
            if val:
                return str(val).strip()
        except Exception:
            pass
    return ""


# Cache the resolved token once per session.
if "resolved_apify_token" not in st.session_state:
    st.session_state["resolved_apify_token"] = _default_apify_token()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CSS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

html, body, .stApp {
    background: #060d18 !important;
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    color: #e2e8f0;
}
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: rgba(10,102,194,.35); border-radius: 99px; }

/* ── Hero ── */
.hero {
    text-align: center;
    padding: 3rem 1rem 1.8rem;
    margin-bottom: 1.8rem;
    background: radial-gradient(ellipse 80% 40% at 50% 0%, rgba(10,102,194,.18) 0%, transparent 70%);
    border-bottom: 1px solid rgba(255,255,255,.045);
}
.hero-title {
    font-size: 3.4rem; font-weight: 900; letter-spacing: -.04em;
    background: linear-gradient(130deg, #2196f3 0%, #0A66C2 40%, #38bdf8 70%, #818cf8 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: .4rem; line-height: 1.1;
}
.hero-sub { color: #64748b; font-size: 1rem; max-width: 560px; margin: 0 auto; }

/* ── Cards ── */
.card {
    background: rgba(12,20,38,.68);
    backdrop-filter: blur(22px); -webkit-backdrop-filter: blur(22px);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 18px; padding: 22px 20px 18px;
    margin-bottom: 16px;
    transition: transform .28s cubic-bezier(.4,0,.2,1), box-shadow .28s, border-color .28s;
    box-shadow: 0 4px 28px rgba(0,0,0,.3);
    display: flex; flex-direction: column; height: 100%;
}
.card:hover {
    transform: translateY(-6px);
    box-shadow: 0 20px 48px rgba(0,0,0,.42);
    border-color: rgba(10,102,194,.5);
}

/* Avatar row */
.avatar-row { display: flex; align-items: flex-start; gap: 13px; margin-bottom: 13px; }
.avatar-img {
    width: 54px; height: 54px; border-radius: 50%;
    object-fit: cover; flex-shrink: 0;
    border: 2.5px solid rgba(10,102,194,.55);
    background: rgba(10,102,194,.1);
}
.avatar-initials {
    width: 54px; height: 54px; border-radius: 50%; flex-shrink: 0;
    background: linear-gradient(135deg,rgba(10,102,194,.4),rgba(56,189,248,.25));
    border: 2px solid rgba(10,102,194,.3);
    display: flex; align-items: center; justify-content: center;
    font-size: 1.25rem; font-weight: 700; color: #93c5fd;
    letter-spacing: -.02em;
}
.author-meta { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.card-name {
    font-size: 1rem; font-weight: 800; color: #f8fafc;
    white-space: normal;
    word-break: normal;          /* never split mid-character */
    overflow-wrap: break-word;   /* only break long unbreakable strings (URLs etc) */
    line-height: 1.3; letter-spacing: -.01em;
}
.card-hl {
    font-size: .78rem; color: #64748b; line-height: 1.35; margin-top: 3px;
    display: -webkit-box; -webkit-line-clamp: 2;
    -webkit-box-orient: vertical; overflow: hidden;
}

/* Snippet */
.card-snip {
    font-size: .8rem; color: #94a3b8; line-height: 1.52;
    border-left: 2.5px solid rgba(10,102,194,.4); padding-left: 10px;
    margin-bottom: 14px; flex-grow: 1;
    display: -webkit-box; -webkit-line-clamp: 3;
    -webkit-box-orient: vertical; overflow: hidden;
}

/* Date badge */
.badge-date {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(56,189,248,.1); color: #7dd3fc;
    padding: 5px 14px; border-radius: 999px;
    font-weight: 600; font-size: .82rem;
    border: 1px solid rgba(56,189,248,.22);
    margin-bottom: 10px; width: fit-content;
}
.badge-date-none {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(100,116,139,.1); color: #94a3b8;
    padding: 5px 14px; border-radius: 999px;
    font-size: .78rem;
    border: 1px solid rgba(100,116,139,.2);
    margin-bottom: 10px; width: fit-content;
}

/* Reactions badge */
.badge-likes {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(244,63,94,.09); color: #fb7185;
    padding: 5px 14px; border-radius: 999px;
    font-weight: 700; font-size: .84rem;
    border: 1px solid rgba(244,63,94,.2);
    margin-bottom: 13px; width: fit-content;
}

/* LinkedIn CTA */
.btn-li {
    display: inline-flex; align-items: center; justify-content: center; gap: 7px;
    width: 100%;
    background: linear-gradient(135deg, #0A66C2 0%, #1e87e8 100%);
    color: #fff !important; padding: 10px 0; border-radius: 10px;
    text-decoration: none !important; font-weight: 600; font-size: .88rem;
    box-shadow: 0 4px 18px rgba(10,102,194,.3);
    transition: filter .2s, transform .15s, box-shadow .2s;
    margin-top: auto;
}
.btn-li:hover { filter: brightness(1.14); transform: scale(1.02); box-shadow: 0 8px 28px rgba(10,102,194,.46); }

/* Section header */
.sec-title {
    font-size: 1.2rem; font-weight: 700; color: #f1f5f9;
    margin: .5rem 0 1rem; display: flex; align-items: center; gap: 8px;
}

/* Scrape button */
div.stButton > button {
    background: linear-gradient(135deg, #0A66C2 0%, #1a8ae6 100%) !important;
    color: #fff !important; font-weight: 800 !important; font-size: 1.1rem !important;
    letter-spacing: .025em !important; border: none !important;
    border-radius: 12px !important; padding: .9rem 1.2rem !important;
    box-shadow: 0 8px 28px rgba(10,102,194,.35) !important;
    transition: all .3s ease !important;
}
div.stButton > button:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 14px 36px rgba(10,102,194,.5) !important;
    filter: brightness(1.08) !important;
}

/* Inputs */
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div {
    background: rgba(12,20,38,.75) !important;
    border: 1px solid rgba(255,255,255,.09) !important;
    border-radius: 10px !important;
}
div[data-baseweb="input"] > div:focus-within {
    border-color: rgba(10,102,194,.65) !important;
    box-shadow: 0 0 0 3px rgba(10,102,194,.13) !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: rgba(5,11,22,.96) !important;
    border-right: 1px solid rgba(255,255,255,.045);
}

/* Download buttons */
div.stDownloadButton > button {
    background: rgba(12,20,38,.85) !important;
    border: 1px solid rgba(255,255,255,.1) !important;
    color: #e2e8f0 !important; border-radius: 10px !important; font-weight: 600 !important;
}
div.stDownloadButton > button:hover {
    border-color: #0A66C2 !important; background: rgba(10,102,194,.15) !important;
}

/* Progress bar */
.stProgress > div > div > div { background: linear-gradient(90deg,#0A66C2,#38bdf8) !important; }

/* Stats cards */
.stats-row {
    display: flex; gap: 16px; margin: 1.2rem 0 1.5rem;
    flex-wrap: wrap;
}
.stat-card {
    flex: 1; min-width: 180px;
    background: rgba(12,20,38,.72);
    backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 16px; padding: 20px 22px;
    text-align: center;
    transition: transform .25s, box-shadow .25s, border-color .25s;
    box-shadow: 0 4px 20px rgba(0,0,0,.25);
}
.stat-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 36px rgba(0,0,0,.35);
    border-color: rgba(10,102,194,.45);
}
.stat-value {
    font-size: 2.2rem; font-weight: 900; letter-spacing: -.03em;
    line-height: 1.1; margin-bottom: 4px;
}
.stat-value.blue  { color: #38bdf8; }
.stat-value.pink  { color: #fb7185; }
.stat-value.green { color: #4ade80; }
.stat-label {
    font-size: .82rem; color: #64748b; font-weight: 600;
    text-transform: uppercase; letter-spacing: .06em;
}

div[data-testid="stAlert"] { border-radius: 12px !important; }
</style>
""", unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HEADER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("""
<div class="hero">
    <div class="hero-title">🔍 LinkedIn Post Finder</div>
    <div class="hero-sub">AGGRESSIVE MODE &bull; Powered by Apify &bull; Scrape every last post</div>
</div>
""", unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SIDEBAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/c/ca/LinkedIn_logo_initials.png", width=48)
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")

    # Token is loaded silently from .env — not exposed in the UI.
    api_token = st.session_state["resolved_apify_token"]

    # Show a small green indicator if token is present, red if missing.
    if api_token:
        st.markdown(
            '<span style="color:#4ade80;font-size:.85rem;font-weight:600;">'
            '✅ Apify token loaded</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span style="color:#f87171;font-size:.85rem;font-weight:600;">'
            '❌ No token found — add APIFY_TOKEN to your .env file</span>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    debug_mode = st.toggle("🐛 Debug Mode", value=False)
    st.markdown("---")
    st.warning(
        "⚠️ **Higher aggressiveness = more posts but higher Apify cost.** "
        "300 posts ≈ $0.25 per run. 500 posts ≈ $0.40+."
    )
    st.markdown("---")
    st.info(
        "**How it works:**\n\n"
        "1️⃣ Enter a keyword\n"
        "2️⃣ Pick time window + aggressiveness\n"
        "3️⃣ Click **START AGGRESSIVE SCRAPING**\n"
        "4️⃣ Apify scrapes every possible post\n"
        "5️⃣ Clean cards appear instantly!"
    )
    st.markdown("---")
    st.caption("LinkedIn Post Finder **v4.0 — AGGRESSIVE**")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INPUTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
col_kw, col_tf = st.columns([2.5, 1])
with col_kw:
    keyword = st.text_input(
        "Brand / Keyword / School / Company",
        value="Polaris School of Technology",
        placeholder="e.g. Polaris School of Technology, openai, #buildinpublic",
    )
# Display label → (LinkedIn URL datePosted value, client-side hour cutoff or None)
TIME_OPTIONS = {
    "Past 1 Hour":   ("past-24h", 1),
    "Past 2 Hours":  ("past-24h", 2),
    "Past 3 Hours":  ("past-24h", 3),
    "Past 24 Hours": ("past-24h", None),
    "Past Week":     ("past-week", None),
    "Past Month":    ("past-month", None),
}

with col_tf:
    time_label  = st.selectbox("Time Window", list(TIME_OPTIONS.keys()), index=3)
    apify_date_param, hour_cutoff = TIME_OPTIONS[time_label]

# Aggressiveness slider
max_posts = st.slider(
    "🔥 Aggressiveness Level — Maximum posts to scrape",
    min_value=50, max_value=500, value=300, step=50,
    help=(
        "Higher = more posts scraped = less chance of missing anything. "
        "**300+** recommended for thorough coverage. "
        "Apify cost scales with this value."
    ),
)

# Strict filter toggle (inline, below inputs)
strict_filter = st.toggle(
    "🎯 Strict Keyword Filter — show ONLY posts that contain ALL words of your keyword",
    value=True,
    help=(
        "When ON, posts that don't actually mention every significant word of your "
        "keyword (e.g. 'Technology') are removed after fetching. "
        "Turn OFF to see all raw results Apify returned."
    ),
)

st.markdown("")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA PARSING HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_HTML_TAG = re.compile(r"<[^>]+>")
_MULTI_SP = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    """Remove all HTML tags and collapse whitespace."""
    if not text:
        return ""
    text = _HTML_TAG.sub(" ", str(text))
    return _MULTI_SP.sub(" ", text).strip()


def _safe_str(obj) -> str:
    """Return a clean string only if obj is a plain string/number, not a dict/list."""
    if obj is None:
        return ""
    if isinstance(obj, (dict, list)):
        return ""          # never stringify raw objects
    return str(obj).strip()


def _safe_int(obj) -> int:
    """Safely convert a value to int."""
    if obj is None:
        return 0
    if isinstance(obj, (dict, list)):
        return 0
    try:
        return int(obj)
    except (TypeError, ValueError):
        return 0


def _fix_name(name: str) -> str:
    """
    Fix names where Apify returns every character separated by a space:
        'K a v i s h a M .'  →  'Kavisha M.'
        'V i v e k  R a j a n'  →  'Vivek Rajan'

    Strategy: if ≥60 % of space-separated tokens are single characters,
    the name has been character-spaced. Merge consecutive single-char
    tokens into words; multi-char tokens (initials like 'Dr', 'MBA') stay.
    """
    if not name:
        return name
    tokens = name.split()
    if len(tokens) < 3:
        return name  # Short names like "Harsh Saini" are fine as-is

    single = sum(1 for t in tokens if len(t) == 1)
    if single / len(tokens) < 0.6:
        return name  # Looks normal — leave it alone

    # Merge consecutive single-char tokens into one chunk
    chunks, buf = [], []
    for t in tokens:
        if len(t) == 1:
            buf.append(t)
        else:
            if buf:
                chunks.append("".join(buf))
                buf = []
            chunks.append(t)
    if buf:
        chunks.append("".join(buf))
    return " ".join(chunks)


def parse_posts(raw_items: list) -> list:
    """
    Parse the supreme_coder/linkedin-post actor response.

    This actor returns FLAT fields (no nested stats/author dicts):
      authorName, authorHeadline, authorProfilePicture,
      numLikes, url, text (already clean), postedAtTimestamp (Unix ms), postedAtISO
    """
    posts = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        # ── Author ────────────────────────────────────────────────────────────
        author_name = _safe_str(item.get("authorName"))
        if not author_name:
            # fallback: build from nested author dict
            author_obj = item.get("author") or {}
            if isinstance(author_obj, dict):
                first = _safe_str(author_obj.get("firstName") or author_obj.get("first_name"))
                last  = _safe_str(author_obj.get("lastName")  or author_obj.get("last_name"))
                author_name = f"{first} {last}".strip()
        author_name = _fix_name(author_name) if author_name else "Unknown"

        headline = (
            _safe_str(item.get("authorHeadline"))
            or _safe_str(item.get("headline"))
            or ""
        )

        photo_url = (
            _safe_str(item.get("authorProfilePicture"))
            or _safe_str(item.get("authorImage"))
            or ""
        )

        # ── Likes — numLikes is a direct int ─────────────────────────────────
        likes = _safe_int(item.get("numLikes"))

        # ── Post URL ─────────────────────────────────────────────────────────
        post_url = _safe_str(item.get("url")) or _safe_str(item.get("post_url")) or ""
        if not post_url:
            urn = _safe_str(item.get("urn"))
            if urn:
                activity_id = urn.split(":")[-1]
                if activity_id.isdigit():
                    post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
        if not post_url:
            continue

        # ── Text — already plain text, no HTML stripping needed ───────────────
        raw_text  = item.get("text") or item.get("content") or ""
        full_text = _strip_html(str(raw_text))
        snippet   = (full_text[:100] + "…") if len(full_text) > 100 else full_text

        # ── Timestamp — postedAtTimestamp is Unix ms (int) ───────────────────
        ts_ms = item.get("postedAtTimestamp")
        if ts_ms is not None:
            posted_at_raw = str(int(ts_ms))
        else:
            posted_at_raw = str(item.get("postedAtISO") or item.get("timeSincePosted") or "")

        parsed_dt = _parse_timestamp(posted_at_raw)
        if parsed_dt:
            import datetime as _dt
            ist_dt = parsed_dt + _dt.timedelta(hours=5, minutes=30)
            posted_display = ist_dt.strftime("%-I:%M %p · %d %b")
        elif posted_at_raw:
            posted_display = posted_at_raw
        else:
            posted_display = ""

        posts.append({
            "Author":     author_name,
            "Headline":   headline,
            "Likes":      likes,
            "Post Link":  post_url,
            "Photo URL":  photo_url,
            "Snippet":    snippet,
            "Posted":     posted_display,
            "_full_text": full_text,
            "_posted_at": posted_at_raw,
        })

    return posts


# Common English stop-words we skip when building the "must-match" set
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "it", "its", "be",
    "as", "are", "was", "were", "this", "that", "these", "those",
    "i", "we", "you", "he", "she", "they", "my", "our", "your",
    "his", "her", "their", "about", "into", "than", "then", "s",
}


def _significant_words(keyword: str) -> list[str]:
    """
    Return the list of lowercase significant words from the keyword,
    stripping punctuation and ignoring stop-words.
    Words of length ≤ 2 are also skipped.
    """
    tokens = re.findall(r"[a-zA-Z0-9]+", keyword.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 2]


def strict_keyword_filter(posts: list, keyword: str) -> tuple[list, int]:
    """
    Keep only posts where EVERY significant word of `keyword` appears
    (case-insensitive) in either the full post text OR the author headline.

    Returns (filtered_posts, removed_count).
    """
    sig_words = _significant_words(keyword)
    if not sig_words:
        return posts, 0

    kept, removed = [], 0
    for p in posts:
        haystack = (p.get("_full_text", "") + " " + p.get("Headline", "")).lower()
        if all(w in haystack for w in sig_words):
            kept.append(p)
        else:
            removed += 1

    return kept, removed


# Matches relative timestamps like "6h", "6h ago", "6 hours ago",
# "2d", "2 days ago", "1w", "30m", "30 minutes ago"
_REL_TIME_RE = re.compile(
    r"(\d+)\s*(s(?:ec(?:ond)?s?)?|m(?:in(?:ute)?s?)?|h(?:our)?s?|d(?:ay)?s?|w(?:eek)?s?)",
    re.IGNORECASE,
)
_REL_UNIT_SECONDS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
    "w": 604800, "week": 604800, "weeks": 604800,
}


def _parse_timestamp(raw: str) -> datetime | None:
    """
    Parse a timestamp string into a UTC-naive datetime.

    Handles:
    - Unix epoch ms/s as a digit string  e.g. "1713234000000"
    - Relative strings                   e.g. "6h", "6h ago", "6 hours ago", "2d"
    - ISO-8601                           e.g. "2026-04-16T01:50:00Z"
    """
    if not raw:
        return None

    raw = raw.strip()

    # ── Unix epoch (all digits) ───────────────────────────────────────────────
    if raw.isdigit():
        ms = int(raw)
        try:
            return datetime.utcfromtimestamp(ms / 1000 if ms > 1e10 else ms)
        except (OSError, OverflowError, ValueError):
            return None

    # ── Relative time string ("6h", "6 hours ago", "2d", "30m") ─────────────
    m = _REL_TIME_RE.search(raw)
    if m:
        n    = int(m.group(1))
        unit = m.group(2).lower().rstrip("s")   # normalise plural
        # map to canonical key
        seconds = None
        for key, val in _REL_UNIT_SECONDS.items():
            if unit == key or unit == key.rstrip("s"):
                seconds = val
                break
        if seconds is None:
            # fallback: try full token
            seconds = _REL_UNIT_SECONDS.get(unit)
        if seconds is not None:
            import datetime as _dt
            return datetime.utcnow() - _dt.timedelta(seconds=n * seconds)

    # ── ISO-8601 ──────────────────────────────────────────────────────────────
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw[: len(fmt) + 6], fmt)
        except ValueError:
            continue

    return None  # truly unparseable


def hour_filter(posts: list, max_hours: int) -> tuple[list, int]:
    """
    Keep only posts posted within the last `max_hours` hours.

    - Posts WITH a parseable timestamp that is older than the cutoff → REMOVED.
    - Posts with NO parseable timestamp → also REMOVED when a strict hour
      filter is active (we can't confirm they're recent).

    Returns (filtered_posts, removed_count).
    """
    import datetime as _dt
    cutoff = datetime.utcnow() - _dt.timedelta(hours=max_hours)
    kept, removed = [], 0
    for p in posts:
        ts = _parse_timestamp(p.get("_posted_at", ""))
        if ts is not None and ts >= cutoff:
            kept.append(p)
        else:
            # ts is None (unparseable) OR ts < cutoff (too old) → drop
            removed += 1
    return kept, removed


def today_filter(posts: list) -> tuple[list, int]:
    """
    Keep only posts posted today (from midnight 00:00 UTC to now).

    Returns (filtered_posts, removed_count).
    """
    midnight = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    kept, removed = [], 0
    for p in posts:
        ts = _parse_timestamp(p.get("_posted_at", ""))
        if ts is not None and ts >= midnight:
            kept.append(p)
        else:
            removed += 1
    return kept, removed


def build_card(p: dict) -> str:
    """Return clean HTML for a single post card."""
    # Escape every user-supplied string to prevent HTML injection
    name     = html_lib.escape(p["Author"])
    headline = html_lib.escape(p["Headline"])
    snippet  = html_lib.escape(p["Snippet"])
    post_url = html_lib.escape(p["Post Link"])
    likes    = p["Likes"]
    posted   = html_lib.escape(p.get("Posted", ""))

    # Avatar
    if p["Photo URL"]:
        photo = html_lib.escape(p["Photo URL"])
        avatar = (
            f'<img src="{photo}" class="avatar-img" '
            f'alt="{name}" onerror="this.parentNode.innerHTML='
            f"'<div class=\\'avatar-initials\\'>"
            + "".join(w[0].upper() for w in p["Author"].split()[:2] if w)
            + f"</div>'"
            f">"
        )
    else:
        initials = "".join(w[0].upper() for w in p["Author"].split()[:2] if w) or "?"
        avatar = f'<div class="avatar-initials">{initials}</div>'

    hl_block  = f'<div class="card-hl">{headline}</div>'  if headline else ""
    snip_block = f'<div class="card-snip">"{snippet}"</div>' if snippet else ""

    # Date badge
    if posted:
        date_block = f'<div class="badge-date">🕐 {posted} IST</div>'
    else:
        date_block = ''

    return f"""
<div class="card">
  <div class="avatar-row">
    {avatar}
    <div class="author-meta">
      <div class="card-name">{name}</div>
      {hl_block}
    </div>
  </div>
  {snip_block}
  {date_block}
  <div class="badge-likes">❤️ {likes:,} Reactions</div>
  <a href="{post_url}" target="_blank" rel="noopener noreferrer" class="btn-li">
    🔗&nbsp; View Post on LinkedIn
  </a>
</div>
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCRAPE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCRAPE  (session-state driven so st.rerun() polling never freezes the UI)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _reset_run() -> None:
    for k in ("run_id", "dataset_id", "run_started", "raw_items",
              "scrape_keyword", "scrape_time_label", "scrape_hour_cutoff",
              "scrape_strict", "scrape_max_posts", "scrape_date_param"):
        st.session_state.pop(k, None)


# ── START button ────────────────────────────────────────────────────────────
if st.button("🚀  START AGGRESSIVE SCRAPING", use_container_width=True):
    if not keyword.strip():
        st.error("Please enter a keyword first.")
        st.stop()
    if not api_token.strip():
        st.error("❌ No Apify token found. Add APIFY_TOKEN to Streamlit Secrets or your .env file.")
        st.stop()

    _reset_run()

    token = api_token.strip()
    try:
        import urllib.parse
        kw_encoded = urllib.parse.quote(keyword.strip())
        search_url = (
            f"https://www.linkedin.com/search/results/content/"
            f"?keywords={kw_encoded}"
            f"&datePosted=%22{apify_date_param}%22"
            f"&sortBy=date_posted"
        )
        run_url = f"{APIFY_BASE}/acts/{ACTOR_ID}/runs?token={token}&maxItems={max_posts}"
        payload = {"urls": [search_url]}
        resp = requests.post(run_url, json=payload, timeout=30)
        if resp.status_code not in (200, 201):
            st.error(f"❌ Apify returned {resp.status_code}: {resp.text[:400]}")
            st.stop()
        data = resp.json().get("data", {})
        run_id = data.get("id", "")
        if not run_id:
            st.error("❌ Could not start actor run. Check your Apify token.")
            st.stop()
        # Persist run state across reruns
        st.session_state["run_id"]             = run_id
        st.session_state["dataset_id"]         = data.get("defaultDatasetId", "")
        st.session_state["run_started"]        = time.time()
        st.session_state["raw_items"]          = None
        st.session_state["scrape_keyword"]     = keyword.strip()
        st.session_state["scrape_time_label"]  = time_label
        st.session_state["scrape_hour_cutoff"] = hour_cutoff
        st.session_state["scrape_strict"]      = strict_filter
        st.session_state["scrape_max_posts"]   = max_posts
        st.session_state["scrape_date_param"]  = apify_date_param
    except Exception as exc:
        st.error(f"❌ Failed to start run: {exc}")
        st.stop()

    st.rerun()


# ── POLLING LOOP (runs on every rerun while a job is in flight) ─────────────
if "run_id" in st.session_state and st.session_state.get("raw_items") is None:

    token      = api_token.strip()
    run_id     = st.session_state["run_id"]
    dataset_id = st.session_state["dataset_id"]
    started    = st.session_state["run_started"]
    elapsed    = int(time.time() - started)
    max_wait   = max(300, 300 + (st.session_state.get("scrape_max_posts", 300) - 100) * 2)

    status_ph = st.empty()
    prog_ph   = st.progress(min(10 + int(elapsed / max_wait * 80), 88))

    # Check if timed out
    if elapsed > max_wait:
        status_ph.error("⏱ Timed out waiting for Apify. Try fewer posts or try again.")
        _reset_run()
        st.stop()

    # Poll run status (each call is ≤2s — safe for Streamlit Cloud)
    try:
        run_info   = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}?token={token}", timeout=10
        ).json().get("data", {})
        run_status = run_info.get("status", "UNKNOWN")
        dataset_id = run_info.get("defaultDatasetId", dataset_id)
        st.session_state["dataset_id"] = dataset_id
    except Exception:
        run_status = "UNKNOWN"

    if run_status == "SUCCEEDED":
        status_ph.info("📦 Downloading results …")
        prog_ph.progress(92)
        try:
            items_resp = requests.get(
                f"{APIFY_BASE}/datasets/{dataset_id}/items?token={token}&format=json",
                timeout=60,
            )
            if items_resp.status_code != 200:
                st.error(f"❌ Failed to fetch results: HTTP {items_resp.status_code}")
                _reset_run()
                st.stop()
            st.session_state["raw_items"] = items_resp.json()
        except Exception as exc:
            st.error(f"❌ Error fetching results: {exc}")
            _reset_run()
            st.stop()
        prog_ph.progress(100)
        status_ph.empty()
        st.rerun()

    elif run_status in ("FAILED", "ABORTED", "TIMED-OUT"):
        status_ph.error(f"❌ Actor run ended with status: **{run_status}**.")
        _reset_run()
        st.stop()

    else:
        # Still running — show live status and rerun after 3s
        status_ph.info(f"⏳ Apify status: **{run_status}** — {elapsed}s elapsed … scraping LinkedIn")
        time.sleep(3)
        st.rerun()


# ── RESULTS (rendered once raw_items is ready in session state) ──────────────
if st.session_state.get("raw_items") is not None:

    raw_items   = st.session_state["raw_items"]
    kw          = st.session_state.get("scrape_keyword", keyword)
    tl          = st.session_state.get("scrape_time_label", time_label)
    hc          = st.session_state.get("scrape_hour_cutoff", hour_cutoff)
    sf          = st.session_state.get("scrape_strict", strict_filter)

    if debug_mode:
        st.markdown(f"### 🐛 Raw items: **{len(raw_items)}**")
        if raw_items and isinstance(raw_items[0], dict):
            first = raw_items[0]
            st.markdown("**First item keys:**")
            st.code(str(list(first.keys())))
            ts_fields = {k: first[k] for k in (
                "postedAt", "posted_at", "publishedAt", "createdAt",
                "postedDate", "timestamp", "date", "time",
                "relativeTime", "relative_time",
            ) if k in first}
            st.markdown("**Timestamp fields:**")
            st.json(ts_fields if ts_fields else {"note": "none found"})
            st.markdown("**First item:**")
            st.json(first)

    posts = parse_posts(raw_items)

    hour_removed = 0
    if hc and posts:
        if hc == "today":
            posts, hour_removed = today_filter(posts)
        else:
            posts, hour_removed = hour_filter(posts, hc)

    removed_count = 0
    if sf and posts:
        posts, removed_count = strict_keyword_filter(posts, kw)

    for p in posts:
        p.pop("_full_text", None)
        p.pop("_posted_at", None)

    if not posts:
        if hour_removed > 0 and removed_count == 0:
            st.warning(
                f"⏱ **No posts within {tl.lower()}.** "
                f"{hour_removed} post(s) were older than {hc}h. "
                f"Try **Past 24 Hours** or a wider window."
            )
        elif removed_count > 0:
            st.warning(
                f"🎯 **Strict filter removed all {removed_count} results.** "
                f"None contained all words of **\"{kw}\"**. "
                f"Turn off the Strict Keyword Filter to see raw results."
            )
        else:
            st.warning("😕 No posts found. Enable Debug Mode to inspect the raw response.")
        if st.button("🔄 Try Again"):
            _reset_run()
            st.rerun()
        st.stop()

    df = pd.DataFrame(posts)

    st.balloons()
    st.success(f"✅ Found **{len(df)} relevant posts** for **\"{kw}\"** · *{tl}*")
    if removed_count > 0:
        st.info(
            f"🎯 Strict filter removed **{removed_count} irrelevant posts** — "
            f"showing only posts that mention **\"{kw}\"**."
        )



    st.markdown("")

    # ── Stats summary bar ─────────────────────────────────────────────────
    total_reactions  = sum(p.get("Likes", 0) for p in posts)
    est_impressions  = total_reactions * 80
    total_posts      = len(posts)

    st.markdown(f"""
<div class="stats-row">
  <div class="stat-card">
    <div class="stat-value blue">{total_posts}</div>
    <div class="stat-label">📝 Total Posts</div>
  </div>
  <div class="stat-card">
    <div class="stat-value pink">{total_reactions:,}</div>
    <div class="stat-label">❤️ Total Reactions</div>
  </div>
  <div class="stat-card">
    <div class="stat-value green">{est_impressions:,}</div>
    <div class="stat-label">👁️ Est. Impressions</div>
  </div>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="sec-title">🏆 Scraped Posts</div>', unsafe_allow_html=True)

    for row_start in range(0, len(posts), 3):
        cols = st.columns(3)
        for col_idx in range(3):
            post_idx = row_start + col_idx
            if post_idx >= len(posts):
                break
            with cols[col_idx]:
                st.markdown(build_card(posts[post_idx]), unsafe_allow_html=True)

    st.markdown("")
    if st.toggle("📄 Show Raw DataFrame", value=False):
        st.dataframe(
            df.drop(columns=["Photo URL"], errors="ignore"),
            use_container_width=True,
            hide_index=True,
            column_config={"Post Link": st.column_config.LinkColumn("Post Link")},
        )

    st.markdown("---")
    st.markdown('<div class="sec-title">💾 Export Results</div>', unsafe_allow_html=True)
    export_df  = df.drop(columns=["Photo URL"], errors="ignore")
    fname_base = f"linkedin_{kw.replace(' ', '_')}_{int(time.time())}"
    dl1, dl2, _ = st.columns([1, 1, 2])
    dl1.download_button(
        "📥 Download CSV",
        data=export_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{fname_base}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            export_df.to_excel(w, index=False)
        dl2.download_button(
            "📥 Download Excel",
            data=buf.getvalue(),
            file_name=f"{fname_base}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception:
        dl2.caption("Install `openpyxl` for Excel export.")
