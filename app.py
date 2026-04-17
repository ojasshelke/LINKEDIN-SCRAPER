import streamlit as st
import pandas as pd
import requests
import time
import io
import html
import os
from datetime import datetime, timedelta, timezone
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTOR_LINKEDIN = "supreme_coder~linkedin-post"
ACTOR_X = "xquik~x-tweet-scraper"
APIFY_BASE = "https://api.apify.com/v2"
API_TOKEN = os.getenv("APIFY_TOKEN", "")
IST = timezone(timedelta(hours=5, minutes=30))

COST_PER_LINKEDIN_POST = 0.005
COST_PER_X_TWEET = 0.00015


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIMESTAMP PARSER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _parse_timestamp(item):
    """Extract a timezone-aware datetime from various API response formats."""
    for key in ("posted_at", "createdAt", "created_at", "postedAtISO", "timeSincePosted"):
        val = item.get(key)
        if val is None:
            continue

        # Dict format: {"timestamp": 171300000, "display_text": "2h"}
        if isinstance(val, dict):
            ts_ms = val.get("timestamp")
            if ts_ms is not None:
                try:
                    ts = int(ts_ms)
                    if ts > 1_000_000_000_000:
                        ts //= 1000
                    return datetime.fromtimestamp(ts, tz=timezone.utc)
                except (ValueError, OSError):
                    pass
            date_str = val.get("date", "")
            if date_str:
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass
            continue

        # Scalar value
        raw = str(val).strip()
        if not raw:
            continue

        # Pure numeric epoch
        if raw.isdigit():
            ts = int(raw)
            if ts > 1_000_000_000_000:
                ts //= 1000
            try:
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except (ValueError, OSError):
                pass
            continue

        # String date formats
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%a %b %d %H:%M:%S %z %Y",   # Twitter: "Wed Apr 15 13:14:14 +0000 2026"
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                dt = datetime.strptime(raw, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                pass

    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TIME FILTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _filter_by_time(posts, time_period, custom_dates):
    """Filter posts list by the chosen time window."""
    if time_period == "today":
        midnight = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
        return [p for p in posts if p["PostedDT"] is None or p["PostedDT"] >= midnight]
    if time_period == "custom" and custom_dates and len(custom_dates) > 0:
        sd = custom_dates[0]
        ed = custom_dates[1] if len(custom_dates) > 1 else custom_dates[0]
        start = datetime(sd.year, sd.month, sd.day, 0, 0, 0, tzinfo=IST)
        end = datetime(ed.year, ed.month, ed.day, 23, 59, 59, tzinfo=IST)
        return [p for p in posts if p["PostedDT"] and start <= p["PostedDT"] <= end]
    return posts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA INGESTION — LINKEDIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _ingest_linkedin(raw_items, keyword, time_period, custom_dates):
    posts = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        # ── Author ──
        af = item.get("author")
        if isinstance(af, dict):
            first = af.get("firstName", "")
            last = af.get("lastName", "")
            full = f"{first} {last}".strip()
            author = af.get("name", "").strip() or full or str(item.get("authorName", "")).strip() or "Unknown"
            headline = af.get("headline", "").strip() or str(item.get("authorHeadline", "")).strip()
            author_img = af.get("picture", "") or af.get("image_url", "") or str(item.get("authorProfilePicture", "")).strip()
        else:
            author = (str(af).strip() if af else str(item.get("authorName", "")).strip()) or "Unknown"
            headline = str(item.get("authorHeadline", "")).strip()
            author_img = str(item.get("authorProfilePicture", "")).strip()

        # ── Reactions ──
        stats = item.get("stats")
        if isinstance(stats, dict):
            likes = int(stats.get("total_reactions", 0))
        else:
            likes = 0
            for k in ("likes", "numLikes", "reactionCount"):
                v = item.get(k)
                if v is not None:
                    try:
                        likes = int(v)
                        break
                    except (ValueError, TypeError):
                        pass

        # ── Post URL ──
        activity_id = str(item.get("activity_id", "")).strip()
        post_url = str(item.get("post_url", "") or "").strip()
        if not post_url:
            for k in ("url", "postUrl", "link", "permalink"):
                if item.get(k):
                    post_url = str(item[k]).strip()
                    break
        if not post_url and activity_id and activity_id.isdigit():
            post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
        if not post_url:
            continue

        # ── Timestamp ──
        posted_dt = _parse_timestamp(item)
        if posted_dt:
            posted_time = posted_dt.astimezone(IST).strftime("%I:%M %p · %d %b IST")
        else:
            pa = item.get("posted_at") or item.get("postedAtISO") or item.get("timeSincePosted")
            if isinstance(pa, dict) and pa.get("display_text"):
                posted_time = pa["display_text"]
            else:
                posted_time = str(pa) if pa else ""

        # ── Text ──
        raw_text = str(item.get("text", "")).strip()
        snippet = raw_text[:200] + ("…" if len(raw_text) > 200 else "")

        posts.append({
            "ActivityID": activity_id,
            "Author": author,
            "Handle": "",
            "Headline": headline,
            "AuthorImg": author_img,
            "Likes": likes,
            "Post Link": post_url,
            "Posted": posted_time,
            "PostedDT": posted_dt,
            "Snippet": snippet,
            "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    # Deduplicate
    seen = set()
    unique = []
    for p in posts:
        aid = p["ActivityID"]
        if aid and aid in seen:
            continue
        if aid:
            seen.add(aid)
        unique.append(p)

    unique = _filter_by_time(unique, time_period, custom_dates)
    unique.sort(key=lambda p: p["PostedDT"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return unique


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA INGESTION — X / TWITTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _ingest_x(raw_items, keyword, time_period, custom_dates):
    posts = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        ai = item.get("author") or item.get("user") or {}
        if not isinstance(ai, dict):
            ai = {}

        author = ai.get("name") or item.get("authorName") or item.get("userName") or "Unknown"
        handle = (
            ai.get("username") or ai.get("userName") or ai.get("screen_name")
            or item.get("userHandle") or ""
        )
        if handle and not handle.startswith("@"):
            handle = f"@{handle}"

        bio = ai.get("description") or ai.get("bio") or item.get("authorBio") or ""
        author_img = (
            ai.get("profilePicture") or ai.get("profile_image_url_https")
            or ai.get("avatar") or item.get("authorAvatar") or ""
        )

        likes = item.get("likes") or item.get("likeCount") or item.get("favorite_count") or 0
        try:
            likes = int(likes)
        except (ValueError, TypeError):
            likes = 0

        url = item.get("url") or item.get("tweetUrl") or ""
        if not url and handle and item.get("id"):
            url = f"https://x.com/{handle.lstrip('@')}/status/{item['id']}"

        text = item.get("text") or item.get("full_text") or item.get("tweetText") or ""
        snippet = text[:200] + ("…" if len(text) > 200 else "")

        posted_dt = _parse_timestamp(item)
        if posted_dt:
            posted_time = posted_dt.astimezone(IST).strftime("%I:%M %p · %d %b IST")
        else:
            posted_time = str(item.get("createdAt") or item.get("created_at") or "")

        tweet_id = str(item.get("id", item.get("tweetId", "")))

        posts.append({
            "ActivityID": tweet_id,
            "Author": author,
            "Handle": handle,
            "Headline": bio,
            "AuthorImg": author_img,
            "Likes": likes,
            "Post Link": url,
            "Posted": posted_time,
            "PostedDT": posted_dt,
            "Snippet": snippet,
            "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    seen = set()
    unique = []
    for p in posts:
        aid = p["ActivityID"]
        if aid and aid in seen:
            continue
        if aid:
            seen.add(aid)
        unique.append(p)

    unique = _filter_by_time(unique, time_period, custom_dates)
    unique.sort(key=lambda p: p["PostedDT"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return unique


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SYNCHRONOUS SCRAPING ENGINE
# Uses st.status() inside the active tab — NO st.rerun(), NO tab redirect.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _run_scrape(platform, keyword, time_period, custom_dates, token, max_posts, debug):
    """Start an Apify actor run and poll synchronously until complete."""
    label = "LinkedIn" if platform == "linkedin" else "X (Twitter)"

    with st.status(f"🔄 Scraping {label}…", expanded=True) as status_ui:
        try:
            # ── Build payload ──
            if platform == "linkedin":
                run_url = f"{APIFY_BASE}/acts/{ACTOR_LINKEDIN}/runs?token={token}"
                kw_enc = urllib.parse.quote(keyword.strip())
                search_url = f"https://www.linkedin.com/search/results/content/?keywords={kw_enc}&sortBy=date_posted"
                if time_period in ("today", "past-24h", "past-week", "past-month"):
                    api_filter = "past-24h" if time_period == "today" else time_period
                    search_url += f'&datePosted="{api_filter}"'
                payload = {
                    "urls": [search_url],
                    "startUrls": [{"url": search_url}],
                    "searchKeywords": keyword.strip(),
                    "maxItems": max_posts,
                }
            else:
                run_url = f"{APIFY_BASE}/acts/{ACTOR_X}/runs?token={token}"
                final_kw = keyword.strip()
                if time_period == "custom" and custom_dates and len(custom_dates) > 0:
                    sd = custom_dates[0]
                    ed = custom_dates[1] if len(custom_dates) > 1 else custom_dates[0]
                    final_kw += f" since:{sd.strftime('%Y-%m-%d')} until:{(ed + timedelta(days=1)).strftime('%Y-%m-%d')}"
                payload = {
                    "searchTerms": [final_kw],
                    "tweetsToScrape": max_posts,
                    "maxItems": max_posts,
                }
                if time_period in ("past-24h", "past-week", "past-month"):
                    payload["timePeriod"] = time_period
                elif time_period == "today":
                    payload["timePeriod"] = "past-24h"

            # ── Start run ──
            st.write("🚀 Starting Apify actor run…")
            if debug:
                st.json(payload)

            resp = requests.post(run_url, json=payload, timeout=30)
            if resp.status_code not in (200, 201):
                st.error(f"❌ API Error {resp.status_code}: {resp.text[:500]}")
                status_ui.update(label="❌ Failed to start", state="error")
                return

            run_data = resp.json().get("data", {})
            run_id = run_data.get("id", "")
            dataset_id = run_data.get("defaultDatasetId", "")

            if not run_id:
                st.error("❌ No run ID returned.")
                status_ui.update(label="❌ Failed", state="error")
                return

            st.write(f"✅ Run started · ID: `{run_id}`")

            # ── Poll loop — max 5 minutes ──
            progress = st.progress(0)
            status_line = st.empty()

            for i in range(150):
                time.sleep(2)
                elapsed = (i + 1) * 2
                progress.progress(min(int((elapsed / 300) * 100), 95))

                try:
                    check = requests.get(f"{APIFY_BASE}/actor-runs/{run_id}?token={token}", timeout=30)
                    info = check.json().get("data", {})
                    run_status = info.get("status", "UNKNOWN")
                    ds_id = info.get("defaultDatasetId") or dataset_id
                except Exception as e:
                    status_line.warning(f"⚠️ Poll error: {e}")
                    continue

                status_line.info(f"⏳ Status: **{run_status}** — {elapsed}s elapsed")

                if run_status == "SUCCEEDED":
                    progress.progress(100)
                    st.write("📦 Fetching results…")

                    items_resp = requests.get(
                        f"{APIFY_BASE}/datasets/{ds_id}/items?token={token}&format=json",
                        timeout=120,
                    )
                    if items_resp.status_code != 200:
                        st.error(f"❌ Dataset fetch failed: {items_resp.status_code}")
                        status_ui.update(label="❌ Dataset error", state="error")
                        return

                    raw_items = items_resp.json()
                    st.write(f"📊 Raw items: **{len(raw_items)}**")
                    if debug and raw_items:
                        st.json(raw_items[0])

                    posts = (
                        _ingest_linkedin(raw_items, keyword, time_period, custom_dates)
                        if platform == "linkedin"
                        else _ingest_x(raw_items, keyword, time_period, custom_dates)
                    )

                    st.session_state[f"posts_{platform}"] = posts
                    st.session_state[f"last_keyword_{platform}"] = keyword.strip()
                    st.session_state[f"last_period_{platform}"] = time_period
                    st.session_state[f"last_dates_{platform}"] = custom_dates
                    st.session_state[f"scraped_at_{platform}"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    status_ui.update(label=f"✅ Found {len(posts)} posts!", state="complete")
                    st.balloons()
                    return

                if run_status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    st.error(f"❌ Run **{run_status}**.")
                    if debug:
                        st.json(info)
                    status_ui.update(label=f"❌ {run_status}", state="error")
                    return

            st.error("⏱ Timed out after 5 minutes. Try fewer posts or a narrower window.")
            status_ui.update(label="⏱ Timed out", state="error")

        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")
            status_ui.update(label="❌ Error", state="error")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RENDER RESULTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _render_results(platform):
    posts = st.session_state.get(f"posts_{platform}", [])
    if not posts:
        return

    kw = st.session_state.get(f"last_keyword_{platform}", "")
    per = st.session_state.get(f"last_period_{platform}", "")
    dates = st.session_state.get(f"last_dates_{platform}")
    scraped_at = st.session_state.get(f"scraped_at_{platform}", "")
    df = pd.DataFrame(posts)

    now_utc = datetime.now(timezone.utc)
    midnight_ist = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)

    cnt_today = sum(1 for p in posts if p.get("PostedDT") and p["PostedDT"] >= midnight_ist)
    cnt_1h = sum(1 for p in posts if p.get("PostedDT") and p["PostedDT"] >= now_utc - timedelta(hours=1))
    total_reactions = sum(p.get("Likes", 0) for p in posts)
    est_impressions = total_reactions * 80

    label = "LinkedIn" if platform == "linkedin" else "X (Twitter)"

    per_str = per
    if per == "custom" and dates and len(dates) > 0:
        if len(dates) == 1 or (len(dates) > 1 and dates[0] == dates[1]):
            per_str = f"Date: {dates[0].strftime('%d %b %Y')}"
        else:
            per_str = f"Range: {dates[0].strftime('%d %b')} – {dates[1].strftime('%d %b')}"

    st.success(
        f'✅ Found **{len(df)}** relevant posts on {label} for **"{kw}"** · '
        f"*{per_str}* — last scraped {scraped_at}"
    )

    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("📋 Total Posts", len(df))
    mc2.metric("📅 Today", cnt_today)
    mc3.metric("🕐 Past 1 Hour", cnt_1h)
    mc4.metric("❤️ Total Reactions", f"{total_reactions:,}")
    mc5.metric("👀 Est. Impressions", f"{est_impressions:,}")
    st.markdown("")

    df_display = df.drop(columns=["PostedDT", "AuthorImg", "ActivityID"], errors="ignore")
    if st.toggle(f"📄 Show raw {label} data table", value=False, key=f"raw_{platform}"):
        st.dataframe(
            df_display, use_container_width=True, hide_index=True,
            column_config={"Post Link": st.column_config.LinkColumn("Post Link")},
        )

    st.markdown(f'<div class="section-title">🏆 Scraped {label} Posts</div>', unsafe_allow_html=True)

    def _esc(s):
        return html.escape(str(s or ""), quote=True)

    for row_start in range(0, len(posts), 3):
        cols = st.columns(3)
        for j in range(3):
            idx = row_start + j
            if idx >= len(posts):
                break
            p = posts[idx]

            author = _esc(p.get("Author", ""))
            handle = _esc(p.get("Handle", ""))
            headline_text = _esc(p.get("Headline", ""))
            snippet = _esc(p.get("Snippet", ""))
            posted = _esc(p.get("Posted", ""))
            post_link = _esc(p.get("Post Link", ""))
            scraped_ts = _esc(p.get("Scraped At", ""))

            # Profile image or gradient initial avatar
            if p.get("AuthorImg"):
                img_html = (
                    f'<img src="{_esc(p["AuthorImg"])}" alt="" '
                    f'style="width:44px;height:44px;border-radius:50%;object-fit:cover;'
                    f'margin-right:10px;flex-shrink:0;border:2px solid rgba(56,189,248,.3);" />'
                )
            else:
                initial = author[0].upper() if author else "?"
                img_html = (
                    f'<div style="width:44px;height:44px;border-radius:50%;'
                    f'background:linear-gradient(135deg,#0A66C2,#38bdf8);display:flex;'
                    f'align-items:center;justify-content:center;font-size:1.2rem;'
                    f'font-weight:700;color:#fff;margin-right:10px;flex-shrink:0;">'
                    f'{initial}</div>'
                )

            auth_display = f'<div class="card-author">{author}'
            if handle:
                auth_display += (
                    f' <span style="font-size:0.85rem;color:#64748b;font-weight:400;">'
                    f'{handle}</span>'
                )
            auth_display += "</div>"

            hl = f'<div class="card-headline">{headline_text}</div>' if headline_text else ""
            snip = f'<div class="card-snippet">{snippet}</div>' if snippet else ""
            date_badge = (
                f'<div class="card-date">🟢 {posted}</div>' if posted
                else '<div class="card-date-empty">📅 No date</div>'
            )

            btn_class = "card-link-x" if platform == "x" else "card-link-linkedin"
            pf_name = "X" if platform == "x" else "LinkedIn"

            with cols[j]:
                st.markdown(
                    f'<div class="glass">'
                    f'<div style="display:flex;align-items:center;margin-bottom:8px;">'
                    f'{img_html}<div>{auth_display}{hl}</div></div>'
                    f'{snip}{date_badge}'
                    f'<div class="badge-likes">❤️ {int(p.get("Likes", 0)):,} Reactions</div>'
                    f'<a href="{post_link}" target="_blank" rel="noopener noreferrer" '
                    f'class="{btn_class}">🔗&nbsp; View Post on {pf_name}</a>'
                    f'<div class="card-ts">🕒 Scraped at {scraped_ts}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Downloads
    st.markdown("---")
    dl1, dl2, _ = st.columns([1, 1, 3])
    dl1.download_button(
        "📥 Download CSV",
        data=df_display.to_csv(index=False).encode("utf-8"),
        file_name=f"{platform}_{kw.replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True,
        key=f"dl_csv_{platform}",
    )
    try:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df_display.to_excel(w, index=False)
        dl2.download_button(
            "📥 Download Excel",
            data=buf.getvalue(),
            file_name=f"{platform}_{kw.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key=f"dl_xls_{platform}",
        )
    except Exception:
        dl2.caption("Install `openpyxl` for Excel export.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE CONFIG + STYLES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="Social Post Finder",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

html, body, .stApp {
    background: #080e1a !important;
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    color: #e2e8f0;
}
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: rgba(10,102,194,.3); border-radius: 99px; }

/* ── Hero ── */
.hero {
    text-align: center;
    padding: 2.5rem 1rem 1.5rem;
    margin-bottom: 0.5rem;
    background: radial-gradient(ellipse at top, rgba(10,102,194,.16) 0%, transparent 60%);
    border-bottom: 1px solid rgba(255,255,255,.04);
}
.hero-title {
    font-size: 3.4rem; font-weight: 900; letter-spacing: -.03em;
    background: linear-gradient(135deg, #0A66C2, #38bdf8 55%, #a78bfa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: .3rem; line-height: 1.15;
}
.hero-sub { color: #94a3b8; font-size: 1.05rem; max-width: 650px; margin: 0 auto; }

/* ── Glass Cards ── */
.glass {
    background: rgba(15,23,42,.55);
    backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255,255,255,.06);
    border-radius: 16px; padding: 22px; margin-bottom: 20px;
    transition: transform .3s cubic-bezier(.4,0,.2,1), box-shadow .3s, border-color .3s;
    box-shadow: 0 4px 24px rgba(0,0,0,.22);
    display: flex; flex-direction: column;
    height: 100%;
}
.glass:hover {
    transform: translateY(-5px);
    box-shadow: 0 14px 36px rgba(0,0,0,.32);
    border-color: rgba(10,102,194,.4);
}
.card-author { font-size: 1.15rem; font-weight: 700; color: #f1f5f9; margin-bottom: 2px; }
.card-headline {
    font-size: .84rem; color: #64748b; margin-bottom: 10px; line-height: 1.4;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.card-snippet {
    font-size: .82rem; color: #94a3b8; margin-bottom: 14px; line-height: 1.45;
    display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;
    border-left: 2px solid rgba(10,102,194,.3); padding-left: 10px;
}
.card-date {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(56,189,248,.08); color: #7dd3fc;
    padding: 4px 12px; border-radius: 999px; font-weight: 600; font-size: .82rem;
    border: 1px solid rgba(56,189,248,.18); margin-bottom: 12px;
    width: fit-content;
}
.card-date-empty {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(100,116,139,.12); color: #94a3b8;
    padding: 4px 12px; border-radius: 999px; font-size: .78rem;
    border: 1px solid rgba(100,116,139,.25); margin-bottom: 12px;
    width: fit-content;
}
.card-ts {
    font-size: .72rem; color: #334155; margin-top: auto;
    padding-top: 8px; border-top: 1px solid rgba(255,255,255,.04);
}
.badge-likes {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(244,63,94,.08); color: #fb7185;
    padding: 4px 12px; border-radius: 999px; font-weight: 600; font-size: .88rem;
    border: 1px solid rgba(244,63,94,.15); margin-bottom: 14px;
}

/* ── Buttons ── */
.card-link-linkedin {
    display: inline-flex; align-items: center; justify-content: center;
    width: 100%; background: linear-gradient(135deg, #0A66C2, #0ea5e9);
    color: #fff !important; padding: 9px 0; border-radius: 9px;
    text-decoration: none; font-weight: 600; font-size: .88rem;
    transition: filter .2s, transform .15s; margin-bottom: 8px;
}
.card-link-linkedin:hover { filter: brightness(1.12); transform: scale(1.02); }

.card-link-x {
    display: inline-flex; align-items: center; justify-content: center;
    width: 100%; background: linear-gradient(135deg, #0f1419, #273340);
    color: #f1f5f9 !important; padding: 9px 0; border-radius: 9px;
    border: 1px solid rgba(255,255,255,.12);
    text-decoration: none; font-weight: 600; font-size: .88rem;
    transition: filter .2s, transform .15s; margin-bottom: 8px;
}
.card-link-x:hover { filter: brightness(1.2); transform: scale(1.02); }

div.stButton > button {
    background: linear-gradient(135deg, #0A66C2, #38bdf8) !important;
    color: #fff !important;
    font-weight: 700 !important; font-size: 1.05rem !important;
    border: none !important; border-radius: 11px !important;
    padding: .85rem 1.2rem !important;
    box-shadow: 0 8px 24px rgba(10,102,194,.25);
    transition: all .3s ease;
}
div.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 12px 32px rgba(10,102,194,.35);
    filter: brightness(1.06);
}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div {
    background: rgba(15,23,42,.6) !important;
    border: 1px solid rgba(255,255,255,.08) !important;
    border-radius: 9px !important;
}
section[data-testid="stSidebar"] {
    background: rgba(8,14,26,.92) !important;
    border-right: 1px solid rgba(255,255,255,.04);
}
.section-title {
    font-size: 1.3rem; font-weight: 700; color: #f1f5f9;
    margin-bottom: .8rem; display: flex; align-items: center; gap: 8px;
}
div.stDownloadButton > button {
    background: rgba(15,23,42,.7) !important;
    border: 1px solid rgba(255,255,255,.1) !important;
    color: #e2e8f0 !important; border-radius: 9px !important; font-weight: 600 !important;
}
div.stDownloadButton > button:hover {
    border-color: #0A66C2 !important;
    background: rgba(10,102,194,.12) !important;
}

/* ── Tab Headers ── */
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    font-size: 1.15rem; font-weight: 600; padding: 10px 20px;
    border-bottom: 2px solid transparent;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #38bdf8 !important; border-bottom-color: #38bdf8 !important;
}
</style>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HERO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.markdown("""
<div class="hero">
    <div class="hero-title">🌍 Social Post Finder</div>
    <div class="hero-sub">Unified dual-platform extraction &bull; Real-time posts, analytics &amp; author details</div>
</div>
""", unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SIDEBAR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
api_token = API_TOKEN

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    st.markdown("---")
    st.success("🔑 Apify API Token linked.")
    st.caption("Single token powers both LinkedIn & X.")
    st.markdown("---")
    debug_mode = st.toggle("🐛 Debug Mode", value=False)
    st.markdown("---")
    st.info(
        "**Dual Platforms Support:**\n"
        "1️⃣ LinkedIn (Premium Professional)\n"
        "2️⃣ X / Twitter (Real-time Hash/Mentions)"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SESSION STATE INIT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
for _key in ("posts_linkedin", "posts_x"):
    if _key not in st.session_state:
        st.session_state[_key] = []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TABS — all scraping + rendering happens INSIDE each tab
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
tab_li, tab_x = st.tabs(["🔗 LinkedIn", "𝕏 X (Twitter)"])

# ━━ TAB 1: LINKEDIN ━━
with tab_li:
    col_kw, col_tf = st.columns([2.5, 1])
    with col_kw:
        keyword_li = st.text_input(
            "Brand / Keyword / School / Company",
            value="Polaris School of Technology",
            key="kw_li",
        )
    with col_tf:
        period_li = st.selectbox(
            "Time Window (LinkedIn)",
            ["today", "past-24h", "past-week", "past-month", "custom"],
            key="pd_li",
        )

    dates_li = None
    if period_li == "custom":
        dates_li = st.date_input(
            "Select Custom Date(s) 🗓️ (Start – End)",
            value=(datetime.today() - timedelta(days=5), datetime.today()),
            key="dates_li",
        )

    col_slider, col_cost = st.columns([2, 1])
    with col_slider:
        max_li = st.slider("Max Posts to Fetch", 10, 999, 30, step=10, key="max_li")
    with col_cost:
        est_cost = max_li * COST_PER_LINKEDIN_POST
        st.metric("💰 Est. Cost", f"${est_cost:.2f}")

    st.markdown("---")
    if st.button("🚀 START SCRAPING (LinkedIn)", use_container_width=True, key="btn_li"):
        if not keyword_li.strip():
            st.error("Please enter a keyword.")
        elif not api_token.strip():
            st.error("Please provide your Apify API Token in the sidebar.")
        else:
            _run_scrape("linkedin", keyword_li, period_li, dates_li, api_token, max_li, debug_mode)

    _render_results("linkedin")


# ━━ TAB 2: X (TWITTER) ━━
with tab_x:
    col_kw, col_tf = st.columns([2.5, 1])
    with col_kw:
        keyword_x = st.text_input(
            "Keyword / #hashtag / @mention",
            value="Polaris School of Technology",
            key="kw_x",
        )
    with col_tf:
        period_x = st.selectbox(
            "Time Window (X/Twitter)",
            ["today", "past-24h", "past-week", "past-month", "custom"],
            key="pd_x",
        )

    dates_x = None
    if period_x == "custom":
        dates_x = st.date_input(
            "Select Custom Date(s) 🗓️ (Start – End)",
            value=(datetime.today() - timedelta(days=5), datetime.today()),
            key="dates_x",
        )

    col_slider, col_cost = st.columns([2, 1])
    with col_slider:
        max_x = st.slider("Max Tweets to Fetch", 10, 999, 50, step=10, key="max_x")
    with col_cost:
        est_cost_x = max_x * COST_PER_X_TWEET
        st.metric("💰 Est. Cost", f"${est_cost_x:.4f}")

    st.markdown("---")
    if st.button("🚀 START SCRAPING (X)", use_container_width=True, key="btn_x"):
        if not keyword_x.strip():
            st.error("Please enter a keyword.")
        elif not api_token.strip():
            st.error("Please provide your Apify API Token in the sidebar.")
        else:
            _run_scrape("x", keyword_x, period_x, dates_x, api_token, max_x, debug_mode)

    _render_results("x")
