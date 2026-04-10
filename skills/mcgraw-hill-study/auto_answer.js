#!/usr/bin/env node
/**
 * auto_answer.js
 * Autonomous SmartBook answerer. Drives the existing playwright-cli "mcgraw" session.
 * Prerequisites: playwright-cli session "mcgraw" must be open and on the SmartBook question page.
 * Usage: node auto_answer.js
 */

const { spawnSync } = require('child_process');
const fs   = require('fs');
const path = require('path');
const Anthropic = require('./node_modules/@anthropic-ai/sdk');

const DIR  = __dirname;
const NODE = 'C:/Program Files/nodejs/node.exe';
const PWJS = 'C:/Users/Owner/AppData/Roaming/npm/node_modules/@playwright/cli/playwright-cli.js';
const GET_Q = fs.readFileSync(path.join(DIR, 'get_question.js'), 'utf8');

// ── Credentials ───────────────────────────────────────────────────────────────
function loadCreds() {
  const creds = {};
  fs.readFileSync(path.join(DIR, 'credentials.env'), 'utf8').split('\n').forEach(line => {
    const eq = line.indexOf('=');
    if (eq > 0) creds[line.slice(0, eq).trim()] = line.slice(eq + 1).trim();
  });
  return creds;
}

// ── playwright-cli eval wrapper ───────────────────────────────────────────────
function pw(jsCode) {
  const r = spawnSync(NODE, [PWJS, '-s=mcgraw', 'eval', jsCode], {
    encoding: 'utf8', timeout: 20000
  });
  const out = r.stdout || '';
  const m = out.match(/### Result\n([\s\S]*?)(?:\n###|$)/);
  if (!m) return null;
  const raw = m[1].trim();
  if (raw.startsWith('"')) {
    try { return JSON.parse(JSON.parse(raw)); } catch(e) {}
  }
  try { return JSON.parse(raw); } catch(e) {}
  return raw;
}

// ── Haiku: returns letter(s) or fill-blank word ───────────────────────────────
async function getAnswer(client, title, qText, options) {
  const isFill   = options.length === 0;
  const isSelect = /Multiple Select/i.test(title);
  const typeLabel = isFill ? 'fill_in_blank' : isSelect ? 'multiple_select' : 'multiple_choice';

  const letters = ['A','B','C','D','E','F'];
  let userMsg = `Type: ${typeLabel}\nQuestion: ${qText}`;
  if (options.length) {
    userMsg += '\nOptions:\n' + options.map((o, i) => `${letters[i]}) ${o}`).join('\n');
  }

  const resp = await client.messages.create({
    model: 'claude-haiku-4-5-20251001',
    max_tokens: 32,
    system:
      'Answer McGraw-Hill SmartBook questions (Strategic Management, Rothaermel ch. 9-10).\n' +
      '- multiple_choice: reply with ONE letter only (A, B, C, or D)\n' +
      '- multiple_select: reply with letters separated by commas only (e.g. "A, C")\n' +
      '- fill_in_blank: reply with the exact word or short phrase only',
    messages: [{ role: 'user', content: userMsg }]
  });
  return resp.content[0].text.trim();
}

// ── Fill-in-blank: execCommand fires React events properly ────────────────────
function submitFillBlank(answer) {
  const val = answer.replace(/'/g, "\\'");
  const r = spawnSync(NODE, [PWJS, '-s=mcgraw', 'eval', `(async function(){
    var inp=document.querySelector('input.fitb-input,input[id*=fitbTesting],[aria-label="Field 1 of 1"]');
    if(!inp) return JSON.stringify({found:false,high:false,advanced:false});
    inp.focus();inp.select();
    document.execCommand('selectAll');
    document.execCommand('insertText',false,'${val}');
    await new Promise(r=>setTimeout(r,600));
    var h=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='High'&&!b.disabled);
    if(h)h.click();
    var next=await new Promise(function(resolve){var t=Date.now();var iv=setInterval(function(){var b=Array.from(document.querySelectorAll('button')).find(b=>/Next Question/i.test(b.textContent));if(b||Date.now()-t>6000){clearInterval(iv);resolve(b||null);}},150);});
    if(next)next.click();
    return JSON.stringify({found:true,high:!!h,advanced:!!next});
  })()`], { encoding: 'utf8', timeout: 15000 });
  const m = r.stdout.match(/### Result\n([\s\S]*?)(?:\n###|$)/);
  if (!m) return null;
  const raw = m[1].trim();
  if (raw.startsWith('"')) { try { return JSON.parse(JSON.parse(raw)); } catch(e){} }
  try { return JSON.parse(raw); } catch(e) {}
  return raw;
}

// ── Submit by index (no text matching — much more reliable) ───────────────────
function buildSubmitEval(answer, options, title) {
  const isFill   = options.length === 0;
  const isSelect = /Multiple Select/i.test(title);
  const LETTERS  = 'ABCDEF';

  if (isFill) {
    return null; // handled separately by submitFillBlank()
  }

  if (isSelect) {
    // answer = "A, C" → indices [0, 2]
    const indices = answer.split(/[,\s]+/)
      .map(l => l.trim().toUpperCase())
      .filter(l => LETTERS.includes(l))
      .map(l => LETTERS.indexOf(l));
    return `(async function(){
      var indices=${JSON.stringify(indices)};
      var boxes=Array.from(document.querySelectorAll('[role=checkbox],input[type=checkbox]'));
      indices.forEach(function(i){if(boxes[i])boxes[i].click();});
      await new Promise(r=>setTimeout(r,300));
      var h=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='High');
      if(h)h.click();
      var next=await new Promise(function(resolve){var t=Date.now();var iv=setInterval(function(){var b=Array.from(document.querySelectorAll('button')).find(b=>/Next Question/i.test(b.textContent));if(b||Date.now()-t>6000){clearInterval(iv);resolve(b||null);}},150);});
      if(next)next.click();
      return JSON.stringify({clicked:indices,high:!!h,advanced:!!next});
    })()`;
  }

  // Single answer — click radio by index
  const idx = LETTERS.indexOf(answer.toUpperCase().charAt(0));
  const safeIdx = idx >= 0 ? idx : 0;
  return `(async function(){
    var radios=Array.from(document.querySelectorAll('[role=radio],input[type=radio]'));
    var el=radios[${safeIdx}];
    if(el)el.click();
    await new Promise(r=>setTimeout(r,300));
    var h=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='High');
    if(h)h.click();
    var next=await new Promise(function(resolve){var t=Date.now();var iv=setInterval(function(){var b=Array.from(document.querySelectorAll('button')).find(b=>/Next Question/i.test(b.textContent));if(b||Date.now()-t>6000){clearInterval(iv);resolve(b||null);}},150);});
    if(next)next.click();
    return JSON.stringify({index:${safeIdx},clicked:!!el,high:!!h,advanced:!!next});
  })()`;
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── Main loop ─────────────────────────────────────────────────────────────────
async function main() {
  const creds = loadCreds();
  if (!creds.ANTHROPIC_API_KEY) { console.error('No ANTHROPIC_API_KEY'); process.exit(1); }
  const client = new Anthropic.default({ apiKey: creds.ANTHROPIC_API_KEY });

  const records = [];
  let lastQ      = '';
  let lastAnswer = null;
  let stuckCount = 0;
  let requeued   = 0;
  let nullCount  = 0;

  console.log('\nAuto-answering SmartBook... (Ctrl+C to stop)\n');

  while (true) {
    const state = pw(GET_Q);

    if (!state) {
      nullCount++;
      console.log(`  Page unreadable (${nullCount}/5), retrying...`);
      if (nullCount >= 5) { console.log('  Giving up.'); break; }
      await sleep(1500);
      continue;
    }
    nullCount = 0;

    const title   = state.title || '';
    const qTexts  = state.questionText || [];
    const qText   = (qTexts[1] || qTexts[0] || '').trim();
    const options = (state.options?.length ? state.options : state.checkboxes || []).filter(Boolean);
    const btns    = state.buttons || [];

    // ── Completion ────────────────────────────────────────────────────────────
    if (/complete|finished|you.ve finished/i.test(title)) {
      console.log('\n  Assignment complete!'); break;
    }
    if (btns.some(b => /^(Finish|Done|Complete Assignment)$/i.test(b))) {
      // Click Complete Assignment if present, then exit
      const compBtn = btns.find(b => /Complete Assignment/i.test(b));
      if (compBtn) pw(`(function(){var b=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Complete Assignment');if(b)b.click();})()`);
      console.log('\n  Assignment complete!'); break;
    }

    // ── Answer Mode (wrong answer shown) ──────────────────────────────────────
    if (/Answer Mode/i.test(title)) {
      console.log('  [Wrong — SmartBook re-queueing] Handling...');
      // SmartBook disables Next Question until you click Read About the Concept
      pw(`(async function(){
        var next=Array.from(document.querySelectorAll('button')).find(b=>/Next Question/i.test(b.textContent)&&!b.disabled);
        if(next){next.click();return;}
        var read=Array.from(document.querySelectorAll('button')).find(b=>/Read About the Concept/i.test(b.textContent));
        if(read){read.click();}
        await new Promise(r=>setTimeout(r,2000));
        var tq=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='To Questions');
        if(tq){tq.click();}
        await new Promise(r=>setTimeout(r,1500));
        var n=await new Promise(function(resolve){var t=Date.now();var iv=setInterval(function(){var b=Array.from(document.querySelectorAll('button')).find(b=>/Next Question/i.test(b.textContent)&&!b.disabled);if(b||Date.now()-t>5000){clearInterval(iv);resolve(b||null);}},200);});
        if(n)n.click();
      })()`);
      requeued++;
      lastQ = ''; // reset so the re-queued question gets answered fresh
      await sleep(2000);
      continue;
    }

    // ── Reading Mode (opened after wrong answer) ───────────────────────────────
    if (/Reading Mode/i.test(title)) {
      console.log('  [Reading Mode] Returning to questions...');
      pw(`(async function(){
        var tq=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='To Questions');
        if(tq)tq.click();
        await new Promise(r=>setTimeout(r,1500));
        var n=Array.from(document.querySelectorAll('button')).find(b=>/Next Question/i.test(b.textContent)&&!b.disabled);
        if(n)n.click();
      })()`);
      await sleep(2000);
      continue;
    }

    // ── Modals / non-question screens ─────────────────────────────────────────
    if (!/Question Mode/i.test(title)) {
      const btn = pw(`(function(){var b=Array.from(document.querySelectorAll('button')).find(b=>/Got it|Start Questions|Continue Questions|Begin/i.test(b.textContent));if(b)b.click();return b?b.textContent.trim():null;})()`);
      if (btn) console.log(`  Dismissed: "${btn}"`);
      await sleep(1000);
      continue;
    }

    // ── Stuck: same question seen again ───────────────────────────────────────
    if (qText && qText === lastQ) {
      stuckCount++;
      console.log(`  Same question (${stuckCount}x) — retrying submit...`);
      if (stuckCount >= 4) {
        console.log('  Stuck 4x, force-advancing...');
        pw(`(function(){var b=Array.from(document.querySelectorAll('button')).find(b=>/Next Question/i.test(b.textContent));if(b)b.click();return !!b;})()`);
        lastQ = '';
        stuckCount = 0;
        await sleep(1000);
        continue;
      }
      // Retry the submit with the last answer
      if (lastAnswer) {
        const result = pw(buildSubmitEval(lastAnswer, options, title));
        console.log(`  Retry submit: ${JSON.stringify(result)}`);
        await sleep(800);
      }
      continue;
    }
    stuckCount = 0;

    // ── New question ──────────────────────────────────────────────────────────
    if (!qText) { await sleep(800); continue; }

    console.log(`\n  [${state.progress || '?'}] ${title.replace('Question Mode: ', '')}`);
    console.log(`  Q: ${qText.slice(0, 120)}`);
    if (options.length) console.log(`  Options: ${options.map((o,i)=>`${' ABCDEF'[i+1]}) ${o}`).join('  |  ')}`);

    // Get answer from Haiku
    let answer;
    try {
      answer = await getAnswer(client, title, qText, options);
    } catch(e) {
      console.log(`  API error: ${e.message} — skipping`);
      pw(`(function(){var b=Array.from(document.querySelectorAll('button')).find(b=>/Next Question/i.test(b.textContent));if(b)b.click();})()`);
      await sleep(800);
      continue;
    }
    console.log(`  Answer: ${answer}`);
    lastAnswer = answer;
    lastQ      = qText;

    const isFillBlank = options.length === 0;
    const result = isFillBlank
      ? submitFillBlank(answer)
      : pw(buildSubmitEval(answer, options, title));
    console.log(`  Submit: ${JSON.stringify(result)}`);

    records.push({ question: qText, type: title.replace('Question Mode: ', ''), answer });
    await sleep(600);
  }

  console.log(`\nDone. ${records.length} questions answered, ${requeued} re-queued by SmartBook.`);
  spawnSync(NODE, [PWJS, '-s=mcgraw', 'state-save', path.join(DIR, 'session.json')]);
  console.log('Session saved.');
}

main().catch(console.error);
