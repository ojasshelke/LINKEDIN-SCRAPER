import os
import re
import html as html_lib
import io
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTOR_ID   = "benjarapi~linkedin-post-search"
APIFY_BASE = "https://api.apify.com/v2"

st.set_page_config(
    page_title="LinkedIn Post Finder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
.avatar-row { display: flex; align-items: center; gap: 13px; margin-bottom: 13px; }
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
.author-meta { display: flex; flex-direction: column; min-width: 0; }
.card-name {
    font-size: 1.05rem; font-weight: 700; color: #f1f5f9;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.card-hl {
    font-size: .78rem; color: #64748b; line-height: 1.35; margin-top: 2px;
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

div[data-testid="stAlert"] { border-radius: 12px !important; }
</style>
""", unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HEADER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("""
<div class="hero">
    <div class="hero-title">🔍 LinkedIn Post Finder</div>
    <div class="hero-sub">Clean results from Apify</div>
</div>
""", unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SIDEBAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/c/ca/LinkedIn_logo_initials.png", width=48)
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")
    api_token = st.text_input(
        "🔑 Apify API Token", type="password",
        value=os.environ.get("APIFY_TOKEN", ""),
        help="Your secret Apify API token. Optionally set APIFY_TOKEN in your environment.",
    )
    st.caption("Get your token → [Apify Console](https://console.apify.com/settings/integrations)")
    st.markdown("---")
    debug_mode = st.toggle("🐛 Debug Mode", value=False)
    st.markdown("---")
    st.info(
        "**How it works:**\n\n"
        "1️⃣ Enter a keyword or school name\n"
        "2️⃣ Pick a time window\n"
        "3️⃣ Click **START SCRAPING**\n"
        "4️⃣ Apify scrapes LinkedIn live\n"
        "5️⃣ Beautiful cards appear instantly!"
    )
    st.markdown("---")
    st.caption("LinkedIn Post Finder **v3.0**")

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
with col_tf:
    time_period = st.selectbox("Time Window", ["past-24h", "past-week", "past-month"])

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


def parse_posts(raw_items: list) -> list:
    """
    Parse the Apify benjarapi/linkedin-post-search response.

    The actor nests author info under item['author'] (a dict) and
    engagement counts under item['stats'] (a dict).
    Text may contain HTML that must be stripped.
    """
    posts = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        # ── Nested author object ──────────────────────────────────────────────
        author_obj = item.get("author")
        if not isinstance(author_obj, dict):
            author_obj = {}

        # Author name
        author_name = _safe_str(author_obj.get("name"))
        if not author_name:
            first = _safe_str(author_obj.get("first_name"))
            last  = _safe_str(author_obj.get("last_name"))
            author_name = f"{first} {last}".strip()
        # Flat-root fallbacks (some actor versions surface these at root)
        if not author_name:
            author_name = (
                _safe_str(item.get("authorName"))
                or _safe_str(item.get("author_name"))
                or "Unknown"
            )

        # Headline
        headline = (
            _safe_str(author_obj.get("headline"))
            or _safe_str(item.get("authorHeadline"))
            or _safe_str(item.get("headline"))
            or ""
        )

        # Profile photo
        photo_url = (
            _safe_str(author_obj.get("image_url"))
            or _safe_str(author_obj.get("profile_picture"))
            or _safe_str(author_obj.get("imageUrl"))
            or _safe_str(item.get("image_url"))
            or _safe_str(item.get("imageUrl"))
            or ""
        )

        # ── Nested stats object ───────────────────────────────────────────────
        stats_obj = item.get("stats")
        if not isinstance(stats_obj, dict):
            stats_obj = {}

        likes = 0
        for key in ("like", "likes", "total_reactions", "reactions", "numLikes", "total"):
            val = _safe_int(stats_obj.get(key))
            if val > 0:
                likes = val
                break
        # Root-level fallback
        if likes == 0:
            for key in ("likes", "numLikes", "likeCount", "totalReactions",
                        "reactionCount", "reactions"):
                val = _safe_int(item.get(key))
                if val > 0:
                    likes = val
                    break

        # ── Post URL ─────────────────────────────────────────────────────────
        post_url = (
            _safe_str(item.get("url"))
            or _safe_str(item.get("postUrl"))
            or _safe_str(item.get("post_url"))
            or _safe_str(item.get("permalink"))
            or ""
        )
        if not post_url:
            urn = _safe_str(item.get("urn") or item.get("activityUrn"))
            if urn:
                activity_id = urn.split(":")[-1]
                if activity_id.isdigit():
                    post_url = (
                        f"https://www.linkedin.com/feed/update/"
                        f"urn:li:activity:{activity_id}/"
                    )
        if not post_url:
            continue  # skip posts with no link

        # ── Content (full clean text for filtering + snippet for display) ───────
        raw_text = (
            item.get("text")
            or item.get("content")
            or item.get("postText")
            or item.get("commentary")
            or ""
        )
        full_text  = _strip_html(str(raw_text))          # full, untruncated
        snippet    = (full_text[:100] + "…") if len(full_text) > 100 else full_text

        posts.append({
            "Author":     author_name,
            "Headline":   headline,
            "Likes":      likes,
            "Post Link":  post_url,
            "Photo URL":  photo_url,
            "Snippet":    snippet,
            "_full_text": full_text,   # kept for relevance filtering, dropped later
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


def build_card(p: dict) -> str:
    """Return clean HTML for a single post card."""
    # Escape every user-supplied string to prevent HTML injection
    name     = html_lib.escape(p["Author"])
    headline = html_lib.escape(p["Headline"])
    snippet  = html_lib.escape(p["Snippet"])
    post_url = html_lib.escape(p["Post Link"])
    likes    = p["Likes"]

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
  <div class="badge-likes">❤️ {likes:,} Reactions</div>
  <a href="{post_url}" target="_blank" rel="noopener noreferrer" class="btn-li">
    🔗&nbsp; View Post on LinkedIn
  </a>
</div>
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SCRAPE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if st.button("🚀  START SCRAPING", use_container_width=True):
    if not keyword.strip():
        st.error("Please enter a keyword first.")
        st.stop()
    if not api_token.strip():
        st.error("Please enter your Apify API token in the sidebar.")
        st.stop()

    token        = api_token.strip()
    status_msg   = st.empty()
    progress_bar = st.progress(0)
    debug_box    = st.container() if debug_mode else None

    try:
        # ── 1. Start actor ────────────────────────────────────────────────────
        status_msg.info(f"🚀 Starting Apify actor for **{keyword}** …")
        progress_bar.progress(5)

        run_url = f"{APIFY_BASE}/acts/{ACTOR_ID}/runs?token={token}"
        payload = {
            "keywords":   keyword.strip(),
            "datePosted": time_period,
            "maxPosts":   80,
            "sortBy":     "date_posted",
        }

        if debug_mode and debug_box:
            debug_box.markdown("### 🐛 API Request")
            debug_box.code(f"POST {run_url}\n\n{payload}")

        resp = requests.post(run_url, json=payload, timeout=30)

        if resp.status_code not in (200, 201):
            st.error(f"❌ Apify returned {resp.status_code}: {resp.text[:500]}")
            if debug_mode and debug_box:
                debug_box.code(resp.text)
            st.stop()

        run_data   = resp.json().get("data", {})
        run_id     = run_data.get("id", "")
        dataset_id = run_data.get("defaultDatasetId", "")

        if not run_id:
            st.error("❌ Could not start actor run. Verify your API token.")
            if debug_mode and debug_box:
                debug_box.json(resp.json())
            st.stop()

        if debug_mode and debug_box:
            debug_box.markdown("### 🐛 Run Started")
            debug_box.code(f"Run ID: {run_id}\nDataset ID: {dataset_id}")

        # ── 2. Poll until SUCCEEDED ───────────────────────────────────────────
        status_msg.info("⏳ Waiting for Apify to finish scraping LinkedIn …")
        progress_bar.progress(15)

        run_status_url = f"{APIFY_BASE}/actor-runs/{run_id}?token={token}"
        max_wait       = 300
        poll_interval  = 4
        elapsed        = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            try:
                run_info   = requests.get(run_status_url, timeout=15).json().get("data", {})
                run_status = run_info.get("status", "UNKNOWN")
            except Exception:
                continue

            pct = min(15 + int((elapsed / max_wait) * 70), 85)
            progress_bar.progress(pct)
            status_msg.info(f"⏳ Apify status: **{run_status}** ({elapsed}s) …")

            if run_status == "SUCCEEDED":
                dataset_id = run_info.get("defaultDatasetId", dataset_id)
                break
            elif run_status in ("FAILED", "ABORTED", "TIMED-OUT"):
                st.error(f"❌ Actor run ended with status: **{run_status}**.")
                if debug_mode and debug_box:
                    debug_box.json(run_info)
                st.stop()
        else:
            st.error("⏱ Timed out waiting for Apify. Please try again.")
            st.stop()

        progress_bar.progress(90)
        status_msg.info("📦 Downloading results …")

        # ── 3. Fetch results ──────────────────────────────────────────────────
        items_url  = (
            f"{APIFY_BASE}/datasets/{dataset_id}/items"
            f"?token={token}&format=json"
        )
        items_resp = requests.get(items_url, timeout=30)

        if items_resp.status_code != 200:
            st.error(f"❌ Failed to fetch results: HTTP {items_resp.status_code}")
            st.stop()

        raw_items = items_resp.json()
        progress_bar.progress(95)

        if debug_mode and debug_box:
            debug_box.markdown(f"### 🐛 Raw items: **{len(raw_items)}**")
            if raw_items and isinstance(raw_items[0], dict):
                debug_box.markdown("**First item keys:**")
                debug_box.code(str(list(raw_items[0].keys())))
                debug_box.markdown("**First item full:**")
                debug_box.json(raw_items[0])

        # ── 4. Parse ──────────────────────────────────────────────────────────
        posts = parse_posts(raw_items)

        # ── 5. Strict keyword filter ──────────────────────────────────────────
        removed_count = 0
        if strict_filter and posts:
            posts, removed_count = strict_keyword_filter(posts, keyword)

        # Drop internal field before DataFrame/export
        for p in posts:
            p.pop("_full_text", None)

        progress_bar.progress(100)
        status_msg.empty()
        progress_bar.empty()

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # RESULTS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if not posts:
            if removed_count > 0:
                st.warning(
                    f"🎯 **Strict filter removed all {removed_count} results** — none of "
                    f"the posts Apify returned actually contained all words of "
                    f"**\"{keyword}\"**. "
                    f"Try turning off the **Strict Keyword Filter** toggle above to see "
                    f"the raw unfiltered results, or broaden your keyword."
                )
            else:
                st.warning(
                    "😕 **No posts found.** The actor returned data but nothing could be parsed. "
                    "Turn on **Debug Mode** in the sidebar to inspect the raw response."
                )
            if debug_mode and debug_box:
                debug_box.markdown("### 🐛 First 5 raw items:")
                for raw in raw_items[:5]:
                    debug_box.json(raw)
            st.stop()

        df = pd.DataFrame(posts)

        st.balloons()
        st.success(f"✅ Found **{len(df)} relevant posts** for **\"{keyword}\"** · *{time_period}*")

        if removed_count > 0:
            st.info(
                f"🎯 **Strict filter active** — removed **{removed_count} irrelevant posts** "
                f"(e.g. 'Polaris School of Quantum') that didn't contain all words of your keyword. "
                f"Showing only posts that genuinely mention **\"{keyword}\"**."
            )

        st.markdown("")

        # ── 3-column card grid ────────────────────────────────────────────────
        st.markdown('<div class="sec-title">🏆 Scraped Posts</div>', unsafe_allow_html=True)

        for row_start in range(0, len(posts), 3):
            cols = st.columns(3)
            for col_idx in range(3):
                post_idx = row_start + col_idx
                if post_idx >= len(posts):
                    break
                with cols[col_idx]:
                    st.markdown(build_card(posts[post_idx]), unsafe_allow_html=True)

        # ── Optional raw DataFrame ────────────────────────────────────────────
        st.markdown("")
        if st.toggle("📄 Show Raw DataFrame", value=False):
            st.dataframe(
                df.drop(columns=["Photo URL"], errors="ignore"),
                use_container_width=True,
                hide_index=True,
                column_config={"Post Link": st.column_config.LinkColumn("Post Link")},
            )

        # ── Export ────────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div class="sec-title">💾 Export Results</div>', unsafe_allow_html=True)

        export_df = df.drop(columns=["Photo URL"], errors="ignore")
        fname_base = f"linkedin_{keyword.replace(' ', '_')}_{int(time.time())}"

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

    except requests.exceptions.Timeout:
        st.error("⏱ Request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        st.error("🌐 Connection error. Check your internet connection.")
    except Exception as exc:
        st.error(f"❌ Unexpected error: {exc}")
        if debug_mode:
            import traceback
            st.code(traceback.format_exc())
