---
name: shorts-scout
description: Finds 5 profitable YouTube Shorts niches a solo creator could enter. For each niche it picks 2 reference channels that prove profitability — scored by avg views per Short, view-to-subscriber outlier ratio, channel growth trend, recency of top Shorts, evergreen content, and monetizability. Trigger when user says "find youtube shorts niche", "research shorts niche", "what niche should I make shorts in", "find profitable shorts niches", "youtube shorts channel ideas", or "scout shorts niches".
---

# Shorts Niche Scout

Queries the YouTube Data API for recent Shorts outliers, checks channel health for each candidate, then uses Claude to cluster results into 5 profitable niches — each backed by 2 reference channels with data proving they're growing right now.

## Prerequisites (first run only)

```bash
pip install google-api-python-client anthropic python-dotenv numpy
```

Get a free YouTube Data API v3 key from Google Cloud Console, then fill in `credentials.env`:

```
YOUTUBE_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
```

## Two-Pass Workflow

### Pass 1 — Generate seed keywords

```bash
python "C:/Users/Owner/.cursor/skills/shorts-scout/scout.py" --propose-seeds
```

Claude writes ~20 evergreen, monetizable seed keywords to `output/<timestamp>/seeds.txt`. Open the file, remove anything you're not interested in, save.

### Pass 2 — Scrape, score, and cluster

```bash
python "C:/Users/Owner/.cursor/skills/shorts-scout/scout.py" \
  --seeds-file "output/<timestamp>/seeds.txt"
```

Or skip Pass 1 and supply keywords directly:

```bash
python "C:/Users/Owner/.cursor/skills/shorts-scout/scout.py" \
  --keywords "home workouts, budgeting tips, Python tutorials"
```

## Output

Creates `output/<timestamp>/`:
| File | Contents |
|------|----------|
| `seeds.txt` | Claude-proposed seed keywords (Pass 1) |
| `channels.csv` | Every qualifying channel: avg views/Short, trend slope, Shorts count, outlier ratio, composite score |
| `outliers.csv` | Every qualifying Short for transparency |
| `niches.md` | **Main report** — 5 niches ranked by avg views/Short, each with 2 reference channels |

## Ranking Criteria

Channels are scored by:

```
score = 0.5 × normalized_avg_views_per_short
      + 0.3 × outlier_ratio (views / max(subs, 1000))
      + 0.2 × recency_bonus (1.0 = today, 0.0 = 30 days ago)
```

**Channel health check:** For each candidate channel, the script fetches its last ~10 Shorts and computes a linear trend slope. Channels with a **negative slope** (declining views) are dropped before Claude sees the data.

## Filters

| Flag | Default | Meaning |
|------|---------|---------|
| `--days` | 30 | Max age of Shorts to consider |
| `--max-subs` | 100,000 | Ignore channels larger than this |
| `--min-views` | 50,000 | Minimum views on the outlier Short |
| `--min-ratio` | 20 | Minimum views/subscribers ratio |
| `--top-n` | 40 | How many channels Claude sees for clustering |

**Loosen filters if no results:**
```bash
python scout.py --seeds-file seeds.txt --min-ratio 10 --min-views 20000 --days 60
```

## What Claude rejects

The niche-clustering prompt instructs Claude to discard:
- Seasonal or trend/hype-dependent niches
- Content relying on copyrighted material (music, sports clips, celebrity footage)
- Non-monetizable content (shock content, re-uploaders)
- Niches a solo creator with no budget cannot replicate
