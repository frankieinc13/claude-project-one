---
name: writing-humanizer
description: Drafts a complete essay meeting assignment criteria (with web research + citations if needed), then humanizes it through GPTInf.com paragraph-by-paragraph and checks it against GPTZero. Trigger when user says "write my essay", "do my assignment", "humanize this", "write a paper on", "answer this writing prompt", or "complete this assignment".
---

# Writing Humanizer

## Trigger

Invoke when the user gives a writing prompt or assignment. Optionally, the user may also provide file paths to attachments (rubrics, source articles, PDFs, screenshots).

---

## Prerequisites (first run only)

```bash
pip install playwright anthropic python-docx
playwright install chromium
```

Fill in `C:/Users/Owner/.cursor/skills/writing-humanizer/credentials.env`:
```
ANTHROPIC_API_KEY=...
GPTINF_EMAIL=...
GPTINF_PASSWORD=...
```

---

## Phase 1 — Claude Code: research + draft (one turn)

1. **Read attachments** if provided — Read tool handles PDF, .docx, images, plain text natively.
2. **Research** if the prompt requires sources — use WebSearch, pull content, format citations (MLA, APA, or per rubric).
3. **Draft the complete essay** — meet all stated criteria: length, format, citation style, argument, grammar.
4. **Split into paragraphs** (double-newline separated) — intro, each body paragraph, conclusion.
5. Call `humanize.py` with the full text:

```bash
python "C:/Users/Owner/.cursor/skills/writing-humanizer/humanize.py" \
  --title "Assignment Title" \
  --prompt-summary "Brief summary of the prompt" \
  --text "FULL ESSAY TEXT HERE"
```

That's it. The script handles everything from this point forward.

---

## Phase 2 — humanize.py (autonomous, no further Claude Code involvement)

The script runs fully on its own:

1. Logs into GPTInf.com (session saved to `session_gptinf.json` for reuse)
2. Humanizes each paragraph via GPTInf Simple mode
3. After each paragraph, calls Claude Sonnet to verify citations/quotes/meaning are intact — makes minimal fixes if not
4. Pastes full humanized essay into GPTZero and scrapes the human score
5. If score < 70%: re-runs flagged paragraphs through GPTInf again, then re-checks GPTZero
6. Saves a Word doc to `output/` with both the original AI draft and the humanized version

**Output:** prints the Word doc path and final GPTZero human score.

---

## Notes

- `--headless` flag runs the browser invisibly (default: visible for debugging)
- Free GPTZero tier: 10,000 character limit per scan; essays over ~1,500 words may need truncation
- GPTInf paid plan: no word limits
- Output files are gitignored (`skills/**/output/`)
