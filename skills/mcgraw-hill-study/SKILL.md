---
name: mcgraw-hill-study
description: Automates McGraw Hill Connect practice assignments for Business Law and Business Strategies. Answers multiple choice, fill-in-the-blank, and matching questions using Claude, then saves a complete answer key and study guide to Google Docs. Can be run manually or on a schedule via Windows Task Scheduler.
---

# McGraw Hill Study Agent

Automates practice assignments on McGraw Hill Connect and saves answer keys + study guides to Google Docs.

## One-time setup required

### 1. Fill in credentials
Edit `credentials.env` with your real values:
```
MCGRAW_EMAIL=your_email@example.com
MCGRAW_PASSWORD=your_password
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Set up Google OAuth (one-time)
1. Go to https://console.cloud.google.com
2. Create a new project (name it anything)
3. Go to **APIs & Services → Library** → enable:
   - **Google Docs API**
   - **Google Drive API**
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth client ID**
5. Application type: **Desktop app**
6. Download the JSON and save it as `google_credentials.json` in this folder
7. Go to **APIs & Services → OAuth consent screen** → set to **External** → add your Google account as a test user

On the first run, a browser window will open for you to authorize. After that, a `token.pickle` is cached and it never asks again.

## Running manually

```bash
# From this directory:
python agent.py "Business Law"
python agent.py "Business Strategies"
python agent.py "Business Law" --assignment "Chapter 4"
python agent.py "Business Law" --headless   # no visible browser window

# Or double-click run.bat and follow the prompts
```

## Scheduling (Windows Task Scheduler)

Edit `schedule_task.bat` to set your desired course, day, and time, then right-click → **Run as administrator**.

To manage existing tasks:
```bat
schtasks /query /tn "McGrawHillStudyAgent_Business_Law"
schtasks /delete /tn "McGrawHillStudyAgent_Business_Law" /f
```

## Output

Each assignment produces a Google Doc in your Drive root titled:
```
McGraw Hill — Business Law — [Assignment Name]
```

The doc contains:
- **Answer Key** — every question with the correct answer and a brief explanation
- **Study Guide** — key concepts, terms, rules, and common mistakes

## Troubleshooting

- If login fails: check credentials.env
- If no assignments are found: a `debug_assignments.png` screenshot is saved in this folder
- If question selectors break after a Connect update: inspect the page and update the CSS selectors in `mcgraw_connect.py`
