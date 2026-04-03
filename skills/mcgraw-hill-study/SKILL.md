---
name: mcgraw-hill-study
description: Automates McGraw Hill Connect SmartBook assignments using playwright-cli. Claude reads each question snapshot and reasons through the correct answer directly — no external API used. Trigger when user says "do my McGraw Hill", "run SmartBook", "answer Connect assignment", "do my homework", or "complete chapter X".
---

# McGraw Hill Study Agent

Claude answers questions by reasoning directly from its own knowledge of Business Law and Business Strategies — no external API is used.

## Running playwright-cli

**IMPORTANT: Never use `cmd /c pwcli.bat` — CMD intercepts `goto`, `type`, and other reserved keywords before they reach node.**

Call node directly every time:
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" [args]
```

Use session name `mcgraw` for all commands after `open`:
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw [command]
```

Define a shell variable to keep commands short:
```bash
PWCLI='"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js"'
# Then use: eval "$PWCLI" -s=mcgraw [command]
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

```bash
# 1a — Open browser (no URL yet)
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw open

# 1b — Restore saved session cookies (must happen BEFORE navigation)
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw state-load "C:/Users/Owner/.cursor/skills/mcgraw-hill-study/session.json"

# 1c — Navigate using eval (NOT goto — CMD intercepts that keyword)
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "location.assign('SECTION_URL')"

# 1d — Check where we landed
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "JSON.stringify({url: location.href, onLogin: location.href.includes('login')})"
```

**If `onLogin` is true** — session expired, log in now:
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw snapshot
# Use the ref for Email Address textbox (e.g. e40), Password textbox (e.g. e43), Sign In button (e.g. e53)
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw fill e40 "EMAIL"
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw fill e43 "PASSWORD"
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw click e53
# After login, navigate to the section
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "location.assign('SECTION_URL')"
```

**If `onLogin` is false** — already on course, continue to step 3.

### 3. Find and open assignment

**3a — Get assignment list:**
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "JSON.stringify([...document.querySelectorAll('[data-automation-id*=launch-btn],[aria-label*=Launch]')].map(function(e){return {text:(e.closest('li,article')||e).querySelector('h2,h3,[class*=title]') ? (e.closest('li,article')||e).querySelector('h2,h3,[class*=title]').textContent.trim() : e.textContent.trim(), id:e.getAttribute('data-automation-id')}}).slice(0,30))"
```

From the returned list, identify the target by index (N). Click it — wrap in IIFE since eval is a single expression:
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "(function(){ var btn = document.querySelectorAll('[data-automation-id*=launch-btn],[aria-label*=Launch]')[N]; if(btn) btn.click(); return JSON.stringify({clicked: !!btn, label: btn ? btn.textContent.trim() : null}); })()"
```

**3b — Wait for panel then click Continue/Begin:**
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "(function(){ var b = Array.from(document.querySelectorAll('button')).find(function(b){ return /Continue|Begin/i.test(b.textContent); }); if(b) b.click(); return JSON.stringify({action: b ? b.textContent.trim() : 'none'}); })()"
```
If `action` is `"none"`, wait 1s and retry once.

**3c — Handle new tab + dismiss modals:**

Check tabs:
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw tab-list
```
If tab index 1 exists, switch:
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw tab-select 1
```

Dismiss entry modals:
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "(function(){ var b = Array.from(document.querySelectorAll('button')).find(function(b){ return /Got it|Start Questions|Continue Questions/i.test(b.textContent); }); if(b) b.click(); return JSON.stringify({dismissed: b ? b.textContent.trim() : 'none', url: location.href}); })()"
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
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "$(cat C:/Users/Owner/.cursor/skills/mcgraw-hill-study/get_question.js)"
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

Use your knowledge of the subject to determine the correct answer. Do not guess — SmartBook re-queues wrong answers.

**Step C — Select answer + submit High + advance to next question (one async eval)**

This single call clicks the answer, clicks High, waits for "Next Question" to appear (polls every 100ms, 4s timeout), clicks it, and returns:

```bash
# Single answer (multiple choice or true/false) — replace ANSWER_TEXT
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "(async function(){ var l = Array.from(document.querySelectorAll('label,[role=radio]')).find(function(l){ return l.innerText && l.innerText.includes('ANSWER_TEXT'); }); if(l) l.click(); await new Promise(function(r){ setTimeout(r,300); }); var h = Array.from(document.querySelectorAll('button')).find(function(b){ return b.textContent.trim()==='High'; }); if(h) h.click(); var next = await new Promise(function(resolve){ var t=Date.now(); var iv=setInterval(function(){ var b=Array.from(document.querySelectorAll('button')).find(function(b){ return /Next Question/i.test(b.textContent); }); if(b||Date.now()-t>4000){ clearInterval(iv); resolve(b||null); } },100); }); if(next) next.click(); return JSON.stringify({answered:!!l,high:!!h,advanced:!!next}); })()"

# Multiple select — replace OPTION_A, OPTION_C with actual answer texts
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "(async function(){ var answers=['OPTION_A','OPTION_C']; answers.forEach(function(txt){ var l=Array.from(document.querySelectorAll('label,[role=checkbox]')).find(function(l){ return l.innerText&&l.innerText.includes(txt); }); if(l) l.click(); }); await new Promise(function(r){ setTimeout(r,300); }); var h=Array.from(document.querySelectorAll('button')).find(function(b){ return b.textContent.trim()==='High'; }); if(h) h.click(); var next=await new Promise(function(resolve){ var t=Date.now(); var iv=setInterval(function(){ var b=Array.from(document.querySelectorAll('button')).find(function(b){ return /Next Question/i.test(b.textContent); }); if(b||Date.now()-t>4000){ clearInterval(iv); resolve(b||null); } },100); }); if(next) next.click(); return JSON.stringify({high:!!h,advanced:!!next}); })()"

# Fill-in-blank — clear field first so React detects change, then fill, then submit
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "(async function(){ var inp=document.getElementById('fitbTesting_response0'); if(inp){ var setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; setter.call(inp,''); inp.dispatchEvent(new Event('input',{bubbles:true})); } return JSON.stringify({cleared:!!inp}); })()" && "C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw fill "Field 1 of" "ANSWER_TEXT" && "C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "(async function(){ var h=Array.from(document.querySelectorAll('button')).find(function(b){ return b.textContent.trim()==='High'&&!b.disabled; }); if(h) h.click(); var next=await new Promise(function(resolve){ var t=Date.now(); var iv=setInterval(function(){ var b=Array.from(document.querySelectorAll('button')).find(function(b){ return /Next Question/i.test(b.textContent); }); if(b||Date.now()-t>4000){ clearInterval(iv); resolve(b||null); } },100); }); if(next) next.click(); return JSON.stringify({high:!!h,advanced:!!next}); })()"
```

If `advanced` is `false`, the Next Question button never appeared — take a snapshot to investigate.

Record each question as you go (no feedback check step needed):
```json
{
  "question": "...",
  "type": "multiple_choice",
  "correct_answer": "...",
  "explanation": "one sentence why"
}
```

**Exit conditions:**
- Step A JSON has empty `questionText` and `options` for 3 consecutive calls → done
- Step A JSON `buttons` contains "Finish" or "Done" → done
- Same `questionText[0]` appears 3 times in a row → click Next and continue
- Check for completion page:
  ```bash
  "C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "JSON.stringify({done: !!document.querySelector('[class*=complete],[class*=finished]'), heading: document.querySelector('h1,h2') ? document.querySelector('h1,h2').textContent.trim() : null})"
  ```

### 5. Save session (optional)

```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw state-save "C:/Users/Owner/.cursor/skills/mcgraw-hill-study/session.json"
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
| Login form not found | Take screenshot: `"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw screenshot` |
| Click by text fails | Use `eval` IIFE with `document.querySelector` |
| Stuck on same question | Click Next 3x then skip |
| New tab opened | Run `tab-list` then `tab-select` to switch |
| SmartBook won't load | Check URL in snapshot — try `reload` |
| eval SyntaxError | Wrap multi-statement code in `(function(){ ... })()` — eval must be a single expression |
