---
name: mcgraw-hill-study
description: Automates McGraw Hill Connect SmartBook assignments using playwright-cli. Claude reads each question snapshot and reasons through the correct answer directly — no external API used. Trigger when user says "do my McGraw Hill", "run SmartBook", "answer Connect assignment", "do my homework", or "complete chapter X".
---

# McGraw Hill Study Agent

Claude answers questions by reasoning directly from its own knowledge of Business Law and Business Strategies — no external API is used.

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

### 1. Open browser and navigate to course (with lazy login)

Go directly to the section URL. If the session cookie is still valid, MHHE redirects to the course — no login page needed.

```bash
# Restore session if saved (skip if first run)
cmd /c pwcli.bat -s=mcgraw state-load "C:/Users/Owner/.cursor/skills/mcgraw-hill-study/session.json"

# Go straight to the section — bypasses login page entirely when session is valid
cmd /c pwcli.bat -s=mcgraw goto "SECTION_URL"

# Check where we landed
cmd /c pwcli.bat -s=mcgraw eval "JSON.stringify({url: location.href, hasLoginForm: !!document.querySelector('#login-email')})"
```

**If `hasLoginForm` is true** — session expired, log in now:
```bash
cmd /c pwcli.bat -s=mcgraw fill "#login-email" "EMAIL"
cmd /c pwcli.bat -s=mcgraw fill "#login-password" "PASSWORD"
cmd /c pwcli.bat -s=mcgraw click "button[type=submit]"
# Confirm redirect to course (not login page)
cmd /c pwcli.bat -s=mcgraw eval "JSON.stringify({url: location.href})"
```

**If `hasLoginForm` is false** — already on course, continue to step 3.

### 3. Find and open assignment

**3a — Get assignment list + click target in one eval:**
```bash
cmd /c pwcli.bat -s=mcgraw eval "JSON.stringify([...document.querySelectorAll('[data-automation-id*=launch-btn],[aria-label*=Launch]')].map(e=>({text:e.closest('li,article')?.querySelector('h2,h3,[class*=title]')?.textContent?.trim()||e.textContent.trim(),id:e.getAttribute('data-automation-id')})).slice(0,30))"
```

From the returned list, identify the target by index (N). Then click + detect panel in a single eval — no separate click command needed:
```bash
cmd /c pwcli.bat -s=mcgraw eval "
  const btn = document.querySelectorAll('[data-automation-id*=launch-btn],[aria-label*=Launch]')[N];
  btn?.click();
  JSON.stringify({clicked: !!btn, label: btn?.textContent?.trim()})
"
```

**3b — Wait for panel then click Continue/Begin in one eval:**
```bash
cmd /c pwcli.bat -s=mcgraw eval "
  const b = [...document.querySelectorAll('button')].find(b => /Continue|Begin/i.test(b.textContent));
  b?.click();
  JSON.stringify({action: b?.textContent?.trim() || 'none'})
"
```
If `action` is `"none"`, wait 1s and retry once.

**3c — Handle new tab + dismiss modals in one eval:**

First check tab count and page state together:
```bash
cmd /c pwcli.bat -s=mcgraw tab-list
```
If tab index 1 exists, switch: `cmd /c pwcli.bat -s=mcgraw tab-select 1`

Then dismiss any entry modals in a single eval:
```bash
cmd /c pwcli.bat -s=mcgraw eval "
  const dismiss = [...document.querySelectorAll('button')].find(b => /Got it|Start Questions|Continue Questions/i.test(b.textContent));
  dismiss?.click();
  JSON.stringify({dismissed: dismiss?.textContent?.trim() || 'none', url: location.href})
"
```
If `dismissed` is `"none"` and URL contains `learning.mheducation.com`, questions are already visible — proceed to step 4.

### 4. Answer questions — main loop

Maintain a running list of records as you go:
```
records = []
```

Each iteration:

**Step A — Read the question**
```bash
cmd /c pwcli.bat -s=mcgraw eval "$(cat C:/Users/Owner/.cursor/skills/mcgraw-hill-study/get_question.js)"
```

Returns structured JSON like:
```json
{
  "heading": "Multiple Choice Question",
  "questionText": ["What is consideration in contract law?"],
  "options": ["An offer made by one party", "Something of value exchanged between parties", "The acceptance of an offer", "A written agreement"],
  "checkboxes": [],
  "buttons": ["High", "Medium", "Low", "Next"],
  "progress": "Concept 3 of 12"
}
```

Derive:
- **Question type**: heading contains `Multiple Choice` → `multiple_choice`, `Multiple Select` → `multiple_select`, `True/False` → `true_false`
- **Question text**: `questionText[0]`
- **Options**: `options` (radio) or `checkboxes` (multi-select)

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
cmd /c pwcli.bat -s=mcgraw eval "JSON.stringify({correct: !!document.querySelector('[class*=correct-answer],[aria-label*=correct],[class*=feedback-correct]'), incorrectMsg: document.querySelector('[class*=incorrect],[class*=feedback]')?.textContent?.trim()?.slice(0,300), explanation: document.querySelector('[class*=explanation],[class*=rationale]')?.textContent?.trim()?.slice(0,300), buttons: [...document.querySelectorAll('button')].map(b=>b.textContent.trim()).filter(t=>t)})"
```

This returns whether the answer was correct plus any explanation text. Record:
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
- Step A JSON has empty `questionText` and `options` for 3 consecutive calls → done
- Step A JSON `buttons` contains "Finish" or "Done" → done
- Same `questionText[0]` appears 3 times in a row → click Next and continue
- Check for completion page:
  ```bash
  cmd /c pwcli.bat -s=mcgraw eval "JSON.stringify({done: !!document.querySelector('[class*=complete],[class*=finished]'), heading: document.querySelector('h1,h2')?.textContent?.trim()})"
  ```

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
