"""
Shorts Scout — find 5 profitable YouTube Shorts niches with reference channels.

Two-pass workflow:
  Pass 1: python scout.py --propose-seeds
  Pass 2: python scout.py --seeds-file output/<ts>/seeds.txt [options]
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from googleapiclient.discovery import build
import anthropic

SKILL_DIR = Path(__file__).parent
load_dotenv(SKILL_DIR / "credentials.env")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# YouTube API helpers
# ---------------------------------------------------------------------------

def parse_iso_duration(duration: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not m:
        return 0
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


def search_shorts(youtube, keyword: str, published_after: str, max_results: int = 50) -> list[str]:
    resp = youtube.search().list(
        part="id",
        q=keyword,
        type="video",
        videoDuration="short",
        publishedAfter=published_after,
        order="viewCount",
        maxResults=max_results,
    ).execute()
    return [item["id"]["videoId"] for item in resp.get("items", [])]


def fetch_video_stats(youtube, video_ids: list[str]) -> dict:
    if not video_ids:
        return {}
    resp = youtube.videos().list(
        part="statistics,contentDetails,snippet",
        id=",".join(video_ids),
    ).execute()
    result = {}
    for item in resp.get("items", []):
        vid = item["id"]
        stats = item.get("statistics", {})
        snippet = item.get("snippet", {})
        result[vid] = {
            "title": snippet.get("title", ""),
            "channel_id": snippet.get("channelId", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "description": snippet.get("description", "")[:300],
            "published": snippet.get("publishedAt", ""),
            "views": int(stats.get("viewCount", 0)),
            "duration_s": parse_iso_duration(item["contentDetails"].get("duration", "")),
        }
    return result


def fetch_channel_subs(youtube, channel_ids: list[str], cache: dict) -> dict:
    uncached = [c for c in channel_ids if c not in cache]
    for i in range(0, len(uncached), 50):
        batch = uncached[i:i + 50]
        resp = youtube.channels().list(
            part="statistics",
            id=",".join(batch),
        ).execute()
        for item in resp.get("items", []):
            cid = item["id"]
            subs = int(item["statistics"].get("subscriberCount", 0))
            cache[cid] = subs
    return cache


def fetch_channel_recent_shorts(youtube, channel_id: str, limit: int = 10) -> list[dict]:
    """Return stats for the most recent `limit` Shorts from a channel."""
    resp = youtube.search().list(
        part="id",
        channelId=channel_id,
        type="video",
        videoDuration="short",
        order="date",
        maxResults=limit,
    ).execute()
    video_ids = [item["id"]["videoId"] for item in resp.get("items", [])]
    if not video_ids:
        return []
    stats = fetch_video_stats(youtube, video_ids)
    return list(stats.values())


# ---------------------------------------------------------------------------
# Channel health
# ---------------------------------------------------------------------------

def channel_health(shorts: list[dict]) -> dict:
    """
    Returns avg_views, trend_slope, shorts_count, latest_published.
    trend_slope > 0 means growing; < 0 means declining.
    """
    if not shorts:
        return {"avg_views": 0, "trend_slope": 0.0, "shorts_count": 0, "latest_published": ""}

    # Sort oldest→newest
    sorted_shorts = sorted(shorts, key=lambda v: v["published"])
    views = [v["views"] for v in sorted_shorts]
    avg_views = sum(views) / len(views)

    if len(views) >= 2:
        x = list(range(len(views)))
        slope = float(np.polyfit(x, views, 1)[0])
    else:
        slope = 0.0

    latest = max(v["published"] for v in sorted_shorts)
    return {
        "avg_views": avg_views,
        "trend_slope": slope,
        "shorts_count": len(sorted_shorts),
        "latest_published": latest[:10],
    }


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def recency_bonus(published_iso: str, now: datetime) -> float:
    """0.0–1.0 bonus: 1.0 = today, decays to 0.0 at 30 days."""
    try:
        pub = datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
        age_days = max(0, (now - pub).days)
        return max(0.0, 1.0 - age_days / 30.0)
    except Exception:
        return 0.0


def composite_score(outlier_ratio: float, avg_views: float, top_short_age_bonus: float,
                    max_avg_views: float) -> float:
    norm_avg = avg_views / max_avg_views if max_avg_views else 0.0
    return 0.5 * norm_avg + 0.3 * min(outlier_ratio / 200.0, 1.0) + 0.2 * top_short_age_bonus


# ---------------------------------------------------------------------------
# Pass 1 — seed proposal
# ---------------------------------------------------------------------------

def propose_seeds(client: anthropic.Anthropic, out_dir: Path) -> Path:
    prompt = """Generate exactly 20 YouTube Shorts seed keywords for niche discovery.

Requirements:
- Each keyword is a broad, evergreen niche term (e.g. "home workouts", "budgeting tips", "Python tutorials")
- NO seasonal topics (holiday, elections, sports seasons)
- NO celebrity/news/trending topics
- NO music, reactions, or copyrighted-content niches
- All niches must be monetizable via YouTube Partner Program and brand deals
- Solo creators with no budget should be able to replicate content in these niches
- Prefer niches with proven demand across demographics year-round

Output format: one keyword per line, nothing else."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    seeds_text = resp.content[0].text.strip()
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds_file = out_dir / "seeds.txt"
    seeds_file.write_text(seeds_text, encoding="utf-8")
    return seeds_file


# ---------------------------------------------------------------------------
# Pass 2 — scrape, score, cluster
# ---------------------------------------------------------------------------

def build_channel_rows(youtube, video_stats: dict, channel_cache: dict,
                       args, now: datetime) -> list[dict]:
    """
    Per qualifying Short, fetch channel's recent Shorts health.
    Returns one row per *channel* (best Short per channel).
    """
    channel_best: dict[str, dict] = {}

    for vid, v in video_stats.items():
        if v["duration_s"] > 70:
            continue
        subs = channel_cache.get(v["channel_id"], 0)
        if subs > args.max_subs:
            continue
        if v["views"] < args.min_views:
            continue
        ratio = v["views"] / max(subs, 1000)
        if ratio < args.min_ratio:
            continue

        age_bonus = recency_bonus(v["published"], now)
        cid = v["channel_id"]

        if cid not in channel_best or v["views"] > channel_best[cid]["views"]:
            channel_best[cid] = {
                "video_id": vid,
                "title": v["title"],
                "channel_id": cid,
                "channel_title": v["channel_title"],
                "views": v["views"],
                "subs": subs,
                "outlier_ratio": round(ratio, 1),
                "published": v["published"][:10],
                "age_bonus": age_bonus,
                "url": f"https://www.youtube.com/shorts/{vid}",
                "description": v["description"].replace("\n", " "),
            }

    if not channel_best:
        return []

    print(f"  {len(channel_best)} unique candidate channels. Fetching channel health...")

    rows = []
    for cid, row in channel_best.items():
        recent = fetch_channel_recent_shorts(youtube, cid, limit=10)
        health = channel_health(recent)

        if health["trend_slope"] < 0 and health["shorts_count"] >= 3:
            continue  # declining channel

        row["avg_views_per_short"] = round(health["avg_views"])
        row["trend_slope"] = round(health["trend_slope"])
        row["shorts_count"] = health["shorts_count"]
        row["latest_published"] = health["latest_published"]
        rows.append(row)

    if not rows:
        return []

    max_avg = max(r["avg_views_per_short"] for r in rows)
    for row in rows:
        row["score"] = composite_score(
            row["outlier_ratio"], row["avg_views_per_short"], row["age_bonus"], max_avg
        )

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def cluster_into_niches(rows: list[dict], client: anthropic.Anthropic, top_n: int) -> str:
    lines = []
    for i, r in enumerate(rows[:top_n], 1):
        lines.append(
            f"{i}. Channel: {r['channel_title']} | Subs: {r['subs']:,} | "
            f"Avg views/Short: {r['avg_views_per_short']:,} | Outlier ratio: {r['outlier_ratio']} | "
            f"Trend slope: {r['trend_slope']:+,} | Shorts posted: {r['shorts_count']} | "
            f"Latest Short: {r['latest_published']}\n"
            f"   Top Short: [{r['title']}]({r['url']}) ({r['views']:,} views, {r['published']})\n"
            f"   Description: {r['description'][:120]}"
        )
    channel_list = "\n\n".join(lines)

    prompt = f"""You are a YouTube Shorts niche analyst. Below are {len(rows[:top_n])} channels that dramatically outperformed their subscriber count on YouTube Shorts.

Your task: identify exactly **5 profitable niches** a solo creator could enter.

For EACH niche you must:
1. Name the niche (concise, specific — e.g. "Solo travel tips" not "Travel")
2. Explain in 1 sentence why it is **evergreen** (not hype, seasonal, or trend-dependent)
3. Explain in 1 sentence why it is **monetizable** (YouTube Partner Program, brand deals, digital products, etc.)
4. Give a **content template** — a fill-in-the-blank format any solo creator can follow
5. Pick **exactly 2 reference channels** from the data below that best prove this niche is profitable right now. For each:
   - Channel name
   - Avg views per Short
   - Outlier ratio
   - Latest Short date
   - Top Short URL
   - One sentence on what makes this channel's approach replicable

**Reject any niche that is:**
- Seasonal, news-driven, or tied to a trend/hype cycle
- Reliant on copyrighted material (music, clips, sports highlights)
- Not monetizable under standard YouTube policies (shock content, re-uploaders, etc.)
- Hard for a solo creator with no budget to replicate

Rank the 5 niches by strongest average-views-per-Short across their reference channels. Put the best niche first.

---

CHANNELS:

{channel_list}

---

Respond in clean markdown. One H2 section per niche. Be specific and concrete."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_outputs(rows: list[dict], niches_report: str, outlier_rows: list[dict],
                 out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    # channels.csv
    if rows:
        channel_fields = [
            "channel_title", "channel_id", "subs", "avg_views_per_short",
            "trend_slope", "shorts_count", "latest_published", "outlier_ratio",
            "score", "url", "published",
        ]
        chan_path = out_dir / "channels.csv"
        with open(chan_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=channel_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        print(f"Channels CSV: {chan_path}")

    # outliers.csv
    if outlier_rows:
        out_path = out_dir / "outliers.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=outlier_rows[0].keys(), extrasaction="ignore")
            writer.writeheader()
            writer.writerows(outlier_rows)
        print(f"Outliers CSV: {out_path}")

    # niches.md
    niches_path = out_dir / "niches.md"
    niches_path.write_text(niches_report, encoding="utf-8")
    print(f"Niches report: {niches_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Niche Scout — find 5 profitable Shorts niches.")
    parser.add_argument("--propose-seeds", action="store_true",
                        help="Pass 1: have Claude generate seed keywords and exit.")
    parser.add_argument("--seeds-file", type=Path, default=None,
                        help="Pass 2: path to seeds.txt (one keyword per line).")
    parser.add_argument("--keywords", type=str, default=None,
                        help="Comma-separated keywords (alternative to --seeds-file).")
    parser.add_argument("--days", type=int, default=30,
                        help="Look back N days for Shorts (default 30).")
    parser.add_argument("--max-subs", type=int, default=100_000, dest="max_subs")
    parser.add_argument("--min-views", type=int, default=50_000, dest="min_views")
    parser.add_argument("--min-ratio", type=float, default=20.0, dest="min_ratio")
    parser.add_argument("--top-n", type=int, default=40, dest="top_n")
    args = parser.parse_args()

    if not YOUTUBE_API_KEY:
        sys.exit("Error: YOUTUBE_API_KEY not set in credentials.env")
    if not ANTHROPIC_API_KEY:
        sys.exit("Error: ANTHROPIC_API_KEY not set in credentials.env")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = SKILL_DIR / "output" / timestamp

    # --- Pass 1 ---
    if args.propose_seeds:
        print("Asking Claude to propose evergreen seed keywords...")
        seeds_file = propose_seeds(client, out_dir)
        print(f"\nSeeds written to: {seeds_file}")
        print("Review and edit the file, then run Pass 2:")
        print(f'  python scout.py --seeds-file "{seeds_file}"')
        return

    # --- Pass 2 ---
    if args.seeds_file:
        keywords = [k.strip() for k in args.seeds_file.read_text(encoding="utf-8").splitlines()
                    if k.strip()]
    elif args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    else:
        sys.exit("Error: provide --propose-seeds, --seeds-file, or --keywords.")

    published_after = (datetime.now(timezone.utc) - timedelta(days=args.days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    now = datetime.now(timezone.utc)

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    channel_cache: dict = {}
    all_video_stats: dict = {}

    print(f"Searching {len(keywords)} keyword(s) over last {args.days} days...")
    for kw in keywords:
        print(f"  > {kw}")
        video_ids = search_shorts(youtube, kw, published_after)
        for i in range(0, len(video_ids), 50):
            stats = fetch_video_stats(youtube, video_ids[i:i + 50])
            all_video_stats.update(stats)

    print(f"Fetched {len(all_video_stats)} videos. Fetching subscriber counts...")
    channel_ids = list({v["channel_id"] for v in all_video_stats.values()})
    fetch_channel_subs(youtube, channel_ids, channel_cache)

    print("Filtering outliers and checking channel health...")
    rows = build_channel_rows(youtube, all_video_stats, channel_cache, args, now)

    if not rows:
        print("No qualifying channels found. Try: --min-ratio 10 --min-views 20000 --days 60")
        sys.exit(0)

    print(f"  {len(rows)} qualifying channels after health filter.")

    # flat outlier list for CSV transparency
    outlier_rows = [
        {k: v for k, v in r.items() if k not in ("age_bonus", "score")}
        for r in rows
    ]

    print(f"Sending top {min(args.top_n, len(rows))} channels to Claude for niche clustering...")
    niches_report = cluster_into_niches(rows, client, args.top_n)

    save_outputs(rows, niches_report, outlier_rows, out_dir)

    print("\n--- NICHE REPORT ---")
    print(niches_report)


if __name__ == "__main__":
    main()
