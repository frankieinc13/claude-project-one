---
name: mcgraw-hill-study
description: Automates McGraw Hill Connect SmartBook assignments using playwright-cli and auto_answer.js. Trigger when user says "do my McGraw Hill", "run SmartBook", "answer Connect assignment", "do my homework", or "complete chapter X".
---

# McGraw Hill Study Agent

## Playwright-CLI Command

Always call node directly (never `cmd /c pwcli.bat` — CMD intercepts reserved keywords):
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw [command]
```

## Credentials

Read `C:/Users/Owner/.cursor/skills/mcgraw-hill-study/credentials.env` (key=value format):
- `MCGRAW_EMAIL`, `MCGRAW_PASSWORD`, `ANTHROPIC_API_KEY`

## Courses

| Course | Section URL |
|--------|-------------|
| Business Law | https://newconnect.mheducation.com/student/class/section/153531117 |
| Business Strategies | https://newconnect.mheducation.com/student/class/section/154228371 |

Ask the user which course if not specified.

---

## Steps

### 1. Open browser and navigate to course

```bash
# Open session
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw open

# Restore saved cookies (before navigation)
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw state-load "C:/Users/Owner/.cursor/skills/mcgraw-hill-study/session.json"

# Navigate to course
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "location.assign('SECTION_URL')"

# Check if login is needed
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "JSON.stringify({onLogin: location.href.includes('login')})"
```

**If `onLogin` is true** — session expired, log in:
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw snapshot
# Use refs from snapshot for email/password/sign-in button
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw fill eXX "EMAIL"
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw fill eXX "PASSWORD"
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw click eXX
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "location.assign('SECTION_URL')"
```

### 2. Find and open assignment

```bash
# List assignments
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "JSON.stringify([...document.querySelectorAll('[data-automation-id*=launch-btn],[aria-label*=Launch]')].map(function(e){return {text:(e.closest('li,article')||e).querySelector('h2,h3,[class*=title]') ? (e.closest('li,article')||e).querySelector('h2,h3,[class*=title]').textContent.trim() : e.textContent.trim(), id:e.getAttribute('data-automation-id')}}).slice(0,30))"

# Click assignment at index N
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "(function(){ var btn = document.querySelectorAll('[data-automation-id*=launch-btn],[aria-label*=Launch]')[N]; if(btn) btn.click(); return JSON.stringify({clicked: !!btn}); })()"

# Click Continue/Begin button
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "(function(){ var b = Array.from(document.querySelectorAll('button')).find(function(b){ return /Continue|Begin/i.test(b.textContent); }); if(b) b.click(); return JSON.stringify({action: b ? b.textContent.trim() : 'none'}); })()"

# Handle new tab if opened
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw tab-list
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw tab-select 1

# Dismiss entry modal if present
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js" -s=mcgraw eval "(function(){ var b = Array.from(document.querySelectorAll('button')).find(function(b){ return /Got it|Start Questions|Continue Questions/i.test(b.textContent); }); if(b) b.click(); return JSON.stringify({dismissed: b ? b.textContent.trim() : 'none'}); })()"
```

### 3. Run auto_answer.js

Once the browser is on the SmartBook question page, run:
```bash
"C:/Program Files/nodejs/node.exe" "C:/Users/Owner/.cursor/skills/mcgraw-hill-study/auto_answer.js"
```

`auto_answer.js` handles everything autonomously via Claude Haiku API (~$0.001/assignment):
- Multiple choice, multiple select, fill-in-blank
- Wrong answers: navigates Read About Concept → To Questions → Next
- Stuck detection, completion detection, session save
