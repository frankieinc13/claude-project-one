// Run via: node get_question.js
// Evaluates page state for SmartBook question
const state = {
  title: document.title,
  heading: document.querySelector('h1,h2,[class*=heading]')?.textContent?.trim(),
  questionText: [...document.querySelectorAll('p,span,[class*=question]')]
    .map(e => e.textContent.trim())
    .filter(t => t.length > 20 && t.length < 500)
    .slice(0, 3),
  options: [...document.querySelectorAll('[role=radio],input[type=radio]')]
    .map(e => e.parentElement?.textContent?.trim()?.slice(0, 150)),
  checkboxes: [...document.querySelectorAll('[role=checkbox],input[type=checkbox]')]
    .map(e => e.parentElement?.textContent?.trim()?.slice(0, 150)),
  buttons: [...document.querySelectorAll('button')]
    .map(b => b.textContent.trim()).filter(t => t),
  progress: document.querySelector('[class*=progress],[class*=concept]')?.textContent?.trim()
};
JSON.stringify(state);
