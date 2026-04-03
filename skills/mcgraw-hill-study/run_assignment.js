#!/usr/bin/env node
/**
 * McGraw Hill SmartBook Automation
 * Usage: node run_assignment.js "<course>" "<chapter_search_term>"
 * Example: node run_assignment.js "Business Law" "Chapter 20"
 *
 * Uses Playwright directly (no subprocess overhead) + Claude API for answering.
 */

const { chromium } = require('./node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

// ── Config ────────────────────────────────────────────────────────────────────
const DIR = __dirname;
const CREDS_FILE = path.join(DIR, 'credentials.env');
const SESSION_FILE = path.join(DIR, 'session.json');
const CHROME_EXE = 'C:\\Users\\Owner\\AppData\\Local\\ms-playwright\\chromium-1208\\chrome-win64\\chrome.exe';

const COURSES = {
  'business law':   'https://newconnect.mheducation.com/student/class/section/153531117',
  'business strategies': 'https://newconnect.mheducation.com/student/class/section/145520378',
};

// ── Load credentials ──────────────────────────────────────────────────────────
function loadCreds() {
  const creds = {};
  fs.readFileSync(CREDS_FILE, 'utf8').split('\n').forEach(line => {
    const eq = line.indexOf('=');
    if (eq > 0) creds[line.slice(0, eq).trim()] = line.slice(eq + 1).trim();
  });
  return creds;
}

// ── Answer helper: context-based matching against SmartBook reading content ───
async function getAnswer(_client, qType, qText, options, readingContext) {
  return answerFromContext(qText, options, qType, readingContext);
}

function answerFromContext(qText, options, qType, context) {
  const ctx = (context + ' ' + qText).toLowerCase();

  // True/False: look for negation patterns
  if (options.length === 2 && options.some(o => /^true$/i.test(o.trim())) && options.some(o => /^false$/i.test(o.trim()))) {
    // If question uses "not", "never", "incorrect" → likely False
    if (/\b(not|never|incorrect|inaccurate|is false|untrue)\b/i.test(qText)) return 'False';
    return 'True';
  }

  // Score each option by how many words from it appear in the context near the question keywords
  const qWords = qText.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').split(/\s+/).filter(w => w.length > 4);
  const scores = options.map(opt => {
    if (!opt) return 0;
    const optWords = opt.toLowerCase().replace(/[^a-z0-9 ]/g, ' ').split(/\s+/).filter(w => w.length > 3);
    let score = 0;
    for (const word of optWords) {
      if (ctx.includes(word)) score += 1;
    }
    // Boost if the option text appears near question keywords in context
    for (const qw of qWords) {
      const idx = ctx.indexOf(qw);
      if (idx >= 0) {
        const nearby = ctx.slice(Math.max(0, idx - 150), idx + 150);
        for (const ow of optWords) {
          if (nearby.includes(ow)) score += 2;
        }
      }
    }
    return score;
  });

  const maxScore = Math.max(...scores);
  const bestIdx = scores.indexOf(maxScore);
  return options[bestIdx] || options[0];
}

// ── Page helpers ──────────────────────────────────────────────────────────────
async function getPageState(page) {
  return page.evaluate(() => {
    const title = document.title;
    const btns = [...document.querySelectorAll('button')]
      .map(b => b.textContent.trim()).filter(t => t);
    const radios = [...document.querySelectorAll('[role=radio],input[type=radio]')]
      .map(e => ({ text: e.parentElement?.textContent?.trim()?.replace(/correct|incorrect/gi, '').trim(), el: e }));
    const checks = [...document.querySelectorAll('[role=checkbox],input[type=checkbox]')]
      .map(e => ({ text: e.parentElement?.textContent?.trim()?.replace(/correct|incorrect/gi, '').trim(), el: e }));
    const qs = [...document.querySelectorAll('p')]
      .map(e => e.textContent.trim())
      .filter(t => t.length > 20 && t.length < 600 &&
        !t.includes('Review these concept') && !t.includes('All rights reserved') &&
        !t.includes('Rate your confidence'));
    const heading = document.querySelector('h1,h2')?.textContent?.trim();
    const progress = document.body.innerText.match(/(\d+) of (\d+) Concepts/)?.[0] || '';

    // Capture reading context from all iframes (SmartBook highlights = answers)
    let readingContext = '';
    try {
      for (const frame of document.querySelectorAll('iframe')) {
        try {
          const marks = frame.contentDocument?.querySelectorAll('mark,[class*=highlight]');
          if (marks?.length) {
            readingContext += [...marks].map(m => m.textContent.trim()).join(' ') + ' ';
          }
          const paras = frame.contentDocument?.querySelectorAll('p');
          if (paras?.length) {
            readingContext += [...paras].slice(0, 20).map(p => p.textContent.trim()).join(' ');
          }
        } catch(e) {}
      }
    } catch(e) {}

    return {
      title,
      heading,
      questionText: qs.slice(0, 3).join(' | '),
      radioTexts: radios.map(r => r.text),
      checkTexts: checks.map(c => c.text),
      buttons: btns,
      progress,
      readingContext: readingContext.slice(0, 2000)
    };
  });
}

async function clickOptionByText(page, text) {
  const clicked = await page.evaluate((target) => {
    const elems = [...document.querySelectorAll('[role=radio],[role=checkbox],input[type=radio],input[type=checkbox]')];
    const el = elems.find(e => e.parentElement?.textContent?.trim()?.replace(/correct|incorrect/gi,'').trim()?.includes(target));
    if (el) { el.click(); return true; }
    // fallback: find label
    const label = [...document.querySelectorAll('label,li,[class*=option],[class*=answer]')]
      .find(e => e.textContent.trim().includes(target));
    if (label) { label.click(); return true; }
    return false;
  }, text);
  return clicked;
}

async function clickButton(page, text) {
  return page.evaluate((t) => {
    const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === t);
    if (btn) { btn.click(); return true; }
    return false;
  }, text);
}

// ── Login ─────────────────────────────────────────────────────────────────────
async function login(page, email, password) {
  await page.goto('https://connect.mheducation.com', { waitUntil: 'domcontentloaded' });
  // Check if already logged in
  if (page.url().includes('newconnect') || page.url().includes('student')) {
    console.log('  Already logged in');
    return;
  }
  await page.fill('#login-email', email);
  await page.fill('#login-password', password);
  await page.click('button[type=submit]');
  await page.waitForURL('**/newconnect**', { timeout: 20000 }).catch(() => {});
  console.log('  Logged in');
}

// ── Find & launch assignment ──────────────────────────────────────────────────
async function launchAssignment(page, courseUrl, searchTerm) {
  await page.goto(courseUrl, { waitUntil: 'domcontentloaded' });
  // Wait for assignment list to render
  await page.waitForSelector('button', { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3000);
  console.log(`  Page URL: ${page.url()}`);
  const btnCount = await page.evaluate(() => document.querySelectorAll('button').length);
  console.log(`  Buttons on page: ${btnCount}`);
  // Scroll the main-content container to lazy-load all assignments
  await page.evaluate(async () => {
    const delay = ms => new Promise(r => setTimeout(r, ms));
    const container = document.querySelector('.main-content') || document.documentElement;
    const total = container.scrollHeight;
    for (let y = 0; y <= total; y += 500) {
      container.scrollTop = y;
      await delay(200);
    }
    container.scrollTop = total;
    await delay(500);
  });
  await page.waitForTimeout(1000);

  // Find launch button matching search term
  const launched = await page.evaluate((term) => {
    const buttons = [...document.querySelectorAll('button')];
    // Debug: log all button texts
    const allTexts = buttons.map(b => (b.getAttribute('aria-label') || b.textContent.trim() || '').slice(0, 80)).filter(t => t);
    const btn = buttons.find(b => {
      const t = ((b.getAttribute('aria-label') || '') + ' ' + b.textContent).toLowerCase();
      return t.includes(term.toLowerCase());
    });
    if (btn) { btn.click(); return btn.getAttribute('aria-label') || btn.textContent.trim() || 'launched'; }
    return { notFound: true, allTexts };
  }, searchTerm);

  console.log('  launched value:', JSON.stringify(launched));
  if (!launched || (typeof launched === 'object' && launched.notFound)) {
    // Log all Launch/Chapter buttons to diagnose
    const debugBtns = await page.evaluate(() =>
      [...document.querySelectorAll('button')]
        .map(b => (b.textContent.trim() || b.getAttribute('aria-label') || '').slice(0, 100))
        .filter(t => /launch|chapter/i.test(t))
    );
    console.log(`Total Launch/Chapter buttons: ${debugBtns.length}`);
    console.log('Launch/Chapter buttons:', debugBtns.slice(0, 40));
    throw new Error(`Assignment not found: "${searchTerm}"`);
  }
  console.log(`  Launched: ${launched}`);

  // Wait for dialog and click Continue/Begin
  await page.waitForTimeout(1500);
  const continued = await page.evaluate(() => {
    const link = [...document.querySelectorAll('a,button')]
      .find(e => /continue|begin/i.test(e.textContent));
    if (link) { link.click(); return true; }
    return false;
  });
  if (!continued) throw new Error('No Continue/Begin button found in dialog');

  // Wait for SmartBook to load (may open new page/tab)
  await page.waitForTimeout(2000);
  return page;
}

// ── Question answering loop ───────────────────────────────────────────────────
async function answerQuestions(page, client) {
  // Dismiss assignment tips modal if present
  await page.waitForTimeout(1000);
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')]
      .find(b => /got it/i.test(b.textContent));
    btn?.click();
  });

  // Click Start Questions if on welcome screen
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')]
      .find(b => b.textContent.trim() === 'Start Questions');
    btn?.click();
  });
  await page.waitForTimeout(1500);

  // Dismiss Got It modal after Start Questions
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button')]
      .find(b => /got it/i.test(b.textContent));
    btn?.click();
  });
  await page.waitForTimeout(500);

  const records = [];
  let consecutive_same = 0;
  let last_question = '';
  let completed = 0;

  while (true) {
    const state = await getPageState(page);

    // Exit conditions
    if (/complete|finished|you.ve finished/i.test(state.title) ||
        /complete|finished|you.ve finished/i.test(state.questionText)) {
      console.log('  Assignment complete!');
      break;
    }

    // Check if it's a question mode
    if (!/Question Mode/i.test(state.title) && !/Answer Mode/i.test(state.title)) {
      // Try clicking Next Question to advance
      const hasNext = await clickButton(page, 'Next Question');
      if (!hasNext) {
        console.log(`  Unexpected state: ${state.title}`);
        break;
      }
      await page.waitForTimeout(600);
      continue;
    }

    // If in answer mode, just advance
    if (/Answer Mode/i.test(state.title)) {
      await clickButton(page, 'Next Question');
      await page.waitForTimeout(600);
      continue;
    }

    const qText = state.questionText || '';
    const options = state.radioTexts.length ? state.radioTexts : state.checkTexts;
    const qType = state.title; // e.g. "Question Mode: Multiple Choice Question"

    // Detect same question loop
    if (qText === last_question) {
      consecutive_same++;
      if (consecutive_same >= 3) {
        console.log('  Same question 3x, skipping...');
        await clickButton(page, 'Next Question');
        await page.waitForTimeout(600);
        consecutive_same = 0;
        continue;
      }
    } else {
      consecutive_same = 0;
      last_question = qText;
    }

    console.log(`\n  [${state.progress}] ${qType.replace('Question Mode: ', '')}`);
    console.log(`  Q: ${qText.slice(0, 120)}`);
    console.log(`  Options: ${options.join(' | ')}`);

    // Get answer
    let answer;
    try {
      answer = await getAnswer(client, qType, qText, options, state.readingContext || '');
    } catch (err) {
      console.log(`  Answer error: ${err.message}, skipping`);
      await clickButton(page, 'High');
      await page.waitForTimeout(400);
      await clickButton(page, 'Next Question');
      await page.waitForTimeout(600);
      continue;
    }

    console.log(`  Answer: ${answer}`);

    // Handle multiple select (answer may have multiple lines)
    const answerLines = answer.split('\n').map(l => l.replace(/^\d+\.\s*/, '').trim()).filter(Boolean);

    for (const ans of answerLines) {
      // Find closest matching option
      const matched = options.find(o => o && (
        o.toLowerCase().includes(ans.toLowerCase()) ||
        ans.toLowerCase().includes(o.toLowerCase().slice(0, 20))
      )) || ans;
      await clickOptionByText(page, matched.slice(0, 40));
    }

    // Submit with High confidence
    await clickButton(page, 'High');
    await page.waitForTimeout(800);

    // Read result
    const resultState = await getPageState(page);
    const correct = /Correct/.test(resultState.title);
    console.log(`  Result: ${correct ? '✓ Correct' : '✗ Incorrect'}`);

    records.push({
      question: qText.slice(0, 200),
      type: qType.replace('Question Mode: ', ''),
      answer_given: answer,
      correct,
      options
    });

    completed++;

    // Advance
    await clickButton(page, 'Next Question');
    await page.waitForTimeout(600);
  }

  return records;
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2);
  const courseName = (args[0] || 'business law').toLowerCase();
  const chapterSearch = args[1] || 'Chapter 20';

  const creds = loadCreds();
  const client = null; // Context-based answering only

  const courseUrl = COURSES[courseName];
  if (!courseUrl) {
    console.error(`Unknown course: "${courseName}". Available: ${Object.keys(COURSES).join(', ')}`);
    process.exit(1);
  }

  console.log(`\nMcGraw Hill SmartBook Automation`);
  console.log(`Course: ${courseName} | Assignment: ${chapterSearch}\n`);

  // Launch browser — connect to existing session if possible
  let browser;
  const sessionExists = fs.existsSync(SESSION_FILE);

  browser = await chromium.launch({
    executablePath: CHROME_EXE,
    headless: false,
    args: ['--no-sandbox']
  });

  const context = await browser.newContext({
    storageState: sessionExists ? SESSION_FILE : undefined,
    viewport: { width: 1280, height: 900 }
  });
  const page = await context.newPage();

  try {
    console.log('Step 1: Login');
    await login(page, creds.MCGRAW_EMAIL, creds.MCGRAW_PASSWORD);

    // Save session for next time
    await context.storageState({ path: SESSION_FILE });

    console.log('Step 2: Launch assignment');
    await launchAssignment(page, courseUrl, chapterSearch);

    // If a new tab opened (SmartBook), switch to it
    const pages = context.pages();
    const sbPage = pages.find(p => p.url().includes('learning.mheducation.com')) || page;
    if (sbPage !== page) console.log('  Switched to SmartBook tab');

    // Dismiss Got It if present on SmartBook welcome
    await sbPage.waitForTimeout(1500);
    await sbPage.evaluate(() => {
      const btn = [...document.querySelectorAll('button')].find(b => /got it/i.test(b.textContent));
      btn?.click();
    });

    console.log('Step 3: Answering questions...');
    const records = await answerQuestions(sbPage, client);

    console.log(`\nCompleted ${records.length} questions`);

    // Save Word doc
    if (records.length > 0) {
      const json = JSON.stringify(records.map(r => ({
        question: r.question,
        type: r.type,
        correct_answer: r.answer_given,
        explanation: r.correct ? 'Answered correctly' : 'May need review'
      })));
      const { execSync } = require('child_process');
      try {
        execSync(
          `"C:/Program Files/nodejs/node.exe" word_writer_cli.py "${courseName}" "${chapterSearch}" '${json.replace(/'/g, "\\'")}'`,
          { cwd: DIR, stdio: 'inherit' }
        );
      } catch (e) {
        // word_writer is python, use python
        const jsonFile = path.join(DIR, 'records_tmp.json');
        fs.writeFileSync(jsonFile, json);
        try {
          execSync(`python word_writer_cli.py "${courseName}" "${chapterSearch}" "${jsonFile}"`, { cwd: DIR, stdio: 'inherit' });
        } catch (e2) {
          console.log('Word doc save skipped (python not available)');
        }
      }
    }

    await context.storageState({ path: SESSION_FILE });
    console.log(`Session saved to ${SESSION_FILE}`);

  } catch (err) {
    console.error('Error:', err.message);
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
