---
name: mcgraw-hill-study
description: Automates McGraw Hill Connect SmartBook assignments using playwright-cli. Opens a browser, logs in, navigates to the course, reads each question via accessibility tree snapshot, answers using Claude's own knowledge (no API calls), and saves a Word document answer key. Trigger when user says "do my McGraw Hill", "run SmartBook", "answer Connect assignment", or "do my homework".
---

# McGraw Hill Study Agent

You are an automation agent. Use playwright-cli to control a browser and complete McGraw Hill Connect SmartBook assignments. **You answer questions yourself** by reading the accessibility tree snapshot — no external AI calls needed.

## Running playwright-cli

All commands go through the wrapper:
```bash
cmd /c "C:/Users/Owner/.cursor/skills/mcgraw-hill-study/pwcli.bat" [args]
```

Use session name `mcgraw` for all commands after `open`:
```bash
cmd /c "C:/Users/Owner/.cursor/skills/mcgraw-hill-study/pwcli.bat" -s=mcgraw [command]
```

## Credentials

Read `C:/Users/Owner/.cursor/skills/mcgraw-hill-study/credentials.env` directly (key=value format):
- `MCGRAW_EMAIL`
- `MCGRAW_PASSWORD`

## Courses

| Course | Section URL |
|--------|-------------|
| Business Law | https://newconnect.mheducation.com/student/class/section/153531117 |
| Business Strategies | https://newconnect.mheducation.com/student/class/section/145520378 |

Ask the user which course if not specified.

---

## Execution Steps

### 1. Open browser and log in

```bash
# Open browser on login page
cmd /c pwcli.bat open https://connect.mheducation.com

# Take snapshot to confirm login form is visible
cmd /c pwcli.bat -s=mcgraw snapshot

# Fill credentials (replace with values from credentials.env)
cmd /c pwcli.bat -s=mcgraw fill "#login-email" "EMAIL"
cmd /c pwcli.bat -s=mcgraw fill "#login-password" "PASSWORD"
cmd /c pwcli.bat -s=mcgraw click "button[type=submit]"

# Wait for dashboard — take snapshot to confirm
cmd /c pwcli.bat -s=mcgraw snapshot
```

If already logged in (session cookie exists), the snapshot will show the dashboard — skip the fill/click steps.

### 2. Navigate to course

```bash
cmd /c pwcli.bat -s=mcgraw goto "SECTION_URL"
cmd /c pwcli.bat -s=mcgraw snapshot
```

### 3. Find and open assignment

1. Take a snapshot — the assignments list will show buttons with text like "Launch"
2. Scroll to load all assignments if needed: `cmd /c pwcli.bat -s=mcgraw press End`
3. Find the target assignment (user-specified, or first incomplete SmartBook)
4. Click its launch button. Try clicking by aria-label text first:
   ```bash
   cmd /c pwcli.bat -s=mcgraw click "Launch ASSIGNMENT_NAME"
   ```
   If that fails, use eval to click by data-automation-id:
   ```bash
   cmd /c pwcli.bat -s=mcgraw eval "document.querySelector('[data-automation-id=\"launch-btn-0\"]')?.click()"
   ```
5. Snapshot — a side panel will open with a Continue/Begin button
6. Click Continue or Begin:
   ```bash
   cmd /c pwcli.bat -s=mcgraw click "Continue"
   # or
   cmd /c pwcli.bat -s=mcgraw click "Begin"
   ```
7. If a new tab opens at `learning.mheducation.com`, switch to it:
   ```bash
   cmd /c pwcli.bat -s=mcgraw tab-list
   cmd /c pwcli.bat -s=mcgraw tab-select 1
   ```
8. Click "Start Questions" or "Continue Questions" if visible
9. Dismiss "Got it" tip modal if visible:
   ```bash
   cmd /c pwcli.bat -s=mcgraw click "Got it"
   ```

### 4. Answer questions — main loop

Maintain a running list of records as you go:
```
records = []
```

Each iteration:

**Step A — Read the question**
```bash
cmd /c pwcli.bat -s=mcgraw snapshot
```

The accessibility tree will show something like:
```
- heading "Multiple Choice Question"
- text "What is consideration in contract law?"
- radio "An offer made by one party"
- radio "Something of value exchanged between parties"
- radio "The acceptance of an offer"
- radio "A written agreement"
- button "High"
- button "Medium"
- button "Low"
- button "Next"
```

Extract:
- **Question type** from heading: `multiple_choice`, `multiple_select`, `true_false`, `fill_blank`
- **Question text**: the text node after the heading
- **Options**: all radio/checkbox labels

**Step B — Reason and answer**

Use your knowledge of the subject (Business Law / Business Strategies) to determine the correct answer. Do not guess — reason carefully. SmartBook re-queues wrong answers.

Click the correct option(s) by their label text:
```bash
# Multiple choice — one answer
cmd /c pwcli.bat -s=mcgraw click "Something of value exchanged between parties"

# Multiple select — click each correct option
cmd /c pwcli.bat -s=mcgraw click "Option A"
cmd /c pwcli.bat -s=mcgraw click "Option C"

# True/False
cmd /c pwcli.bat -s=mcgraw click "True"
```

If clicking by text fails, use eval:
```bash
cmd /c pwcli.bat -s=mcgraw eval "
  [...document.querySelectorAll('label')]
    .find(l => l.innerText.includes('OPTION_TEXT'))?.click()
"
```

**Step C — Submit with High confidence**
```bash
cmd /c pwcli.bat -s=mcgraw click "High"
```

**Step D — Read feedback**
```bash
cmd /c pwcli.bat -s=mcgraw snapshot
```

The feedback snapshot will show whether the answer was correct and what the correct answer is. Record:
```json
{
  "question": "...",
  "type": "multiple_choice",
  "correct_answer": "...",
  "explanation": "one sentence why"
}
```

**Step E — Next question**
```bash
cmd /c pwcli.bat -s=mcgraw click "Next"
```

**Exit conditions:**
- Snapshot shows a completion message (e.g., "Assignment complete", "You finished")
- No question text found in 3 consecutive snapshots → done
- Same question text appears 3 times in a row → click Next and continue

### 5. Save session (optional)

```bash
cmd /c pwcli.bat -s=mcgraw state-save "C:/Users/Owner/.cursor/skills/mcgraw-hill-study/session.json"
```

### 6. Save Word document

After collecting all records, serialize them to JSON and call:
```bash
cd C:/Users/Owner/.cursor/skills/mcgraw-hill-study
python word_writer_cli.py "COURSE_NAME" "ASSIGNMENT_NAME" 'JSON_ARRAY'
```

Where `JSON_ARRAY` is the records list, e.g.:
```json
[{"question":"What is consideration?","type":"multiple_choice","correct_answer":"Something of value exchanged","explanation":"Consideration is the bargained-for exchange in a contract."}]
```

The doc is saved to `skills/mcgraw-hill-study/output/`.

### 7. Report to user

Print:
- Course and assignment name
- Number of questions answered
- Path to the saved Word doc
- Any questions skipped or uncertain

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Login form not found | Take screenshot: `cmd /c pwcli.bat -s=mcgraw screenshot` |
| Click by text fails | Use `eval` with `document.querySelector` |
| Stuck on same question | Click Next 3x then skip |
| New tab opened | Run `tab-list` then `tab-select` to switch |
| SmartBook won't load | Check URL in snapshot — try `reload` |
