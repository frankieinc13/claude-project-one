---
name: mcgraw-hill-study
description: Automates McGraw Hill Connect SmartBook assignments using the Playwright MCP. Navigates to the course, opens a SmartBook assignment, answers every question using Claude's reasoning, and saves a Word document answer key. Trigger when user says "do my McGraw Hill", "run SmartBook", or "answer Connect assignment".
---

# McGraw Hill Study Agent

You are an automation agent. Use the Playwright MCP browser tools to complete a McGraw Hill Connect SmartBook assignment, then save an answer key as a Word document.

## Credentials

Load from `skills/mcgraw-hill-study/credentials.env`:
- `MCGRAW_EMAIL` — login email
- `MCGRAW_PASSWORD` — login password

Read the file directly; do not use subprocess or dotenv.

## Step-by-step instructions

### 1. Launch browser
```
browser_navigate: https://connect.mheducation.com
```

### 2. Log in
- Wait for the page to load, take a snapshot
- Fill `#login-email` with the email
- Fill `#login-password` with the password
- Click the submit button
- Wait for dashboard to load (take snapshot to confirm)

### 3. Navigate to course
Go directly to the section URL from config.json:
- Business Law: `https://newconnect.mheducation.com/student/class/section/153531117`
- Business Strategies: `https://newconnect.mheducation.com/student/class/section/145520378`

### 4. Find and open assignment
- Take a snapshot of the assignments list
- Find the target assignment (user will specify, or pick the first incomplete SmartBook)
- Click its launch button (look for `[data-automation-id^="launch-btn"]` elements)
- In the side panel that opens, click "Continue" or "Begin"
- If a new tab opens with `learning.mheducation.com`, switch to it
- Click "Start Questions" or "Continue Questions" if present
- Dismiss any "Got it" tip modals

### 5. Answer questions in a loop

For each question:

1. **Take a snapshot** — read the full page text
2. **Identify question type** from text:
   - "Multiple Select Question" → select all correct options
   - "Multiple Choice Question" → select one option
   - "True or False Question" → True or False
   - "Fill in" / "type the" → fill blank
3. **Read the question text and all option labels**
4. **Reason about the correct answer** using your knowledge of the subject (Business Law or Business Strategies)
5. **Click the correct answer(s)** using label elements
6. **Click "High"** (confidence) to submit
7. **Take a snapshot** to read feedback — note if correct and what the correct answer was
8. **Record**: question text, your answer, correct answer, brief explanation
9. **Click "Next"** to advance
10. **Repeat** until no more question text is visible (assignment complete)

**Loop exit conditions:**
- Page shows completion message
- No question text found after 3 consecutive snapshots
- Same question text seen 3 times in a row (stuck) — click Next and continue

### 6. Save answer key

After collecting all questions and answers, call Python to write the Word doc:

```bash
cd C:/Users/Owner/.cursor/skills/mcgraw-hill-study
python word_writer_cli.py "<subject>" "<assignment_name>" "<json_data>"
```

Where `<json_data>` is a JSON array of objects:
```json
[{"question": "...", "type": "...", "correct_answer": "...", "explanation": "..."}]
```

### 7. Report to user

Print a summary:
- Assignment name
- Number of questions answered
- Path to saved Word doc
- Any questions that were skipped or uncertain

## Notes

- Always take a snapshot before deciding what to click — don't guess selectors
- If a click doesn't work, try clicking the parent element or use a more specific selector from the snapshot
- SmartBook re-queues wrong answers, so reason carefully before selecting
- The confidence buttons are labeled "High", "Medium", "Low" — always click "High"
- If you get stuck on a page, take a screenshot and report the URL to the user
