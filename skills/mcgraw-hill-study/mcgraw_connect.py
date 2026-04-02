"""
McGraw Hill Connect browser automation using Playwright.
Handles login, navigation, question extraction, and answer submission.
"""

import time
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout


class McGrawHillConnect:
    BASE_URL = "https://connect.mheducation.com"

    def __init__(self, headless=False):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.page = None

    def start(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=300  # slight delay so the page can keep up
        )
        context = self.browser.new_context(viewport={"width": 1280, "height": 900})
        self.page = context.new_page()

    def stop(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def login(self, email: str, password: str):
        self.page.goto(f"{self.BASE_URL}/connect/login")
        self._wait()

        self.page.locator("input[type='email'], input[name='email'], #email").first.fill(email)
        self.page.locator("input[type='password']").first.fill(password)
        self.page.locator("button[type='submit'], input[type='submit']").first.click()
        self._wait(3)

    # ------------------------------------------------------------------
    # Course navigation
    # ------------------------------------------------------------------

    def navigate_to_course(self, course_keyword: str):
        """
        From the dashboard, click the first course whose text contains course_keyword.
        Falls back to searching the page for any link containing the keyword.
        """
        self.page.goto(f"{self.BASE_URL}/connect/dashboard")
        self._wait(2)

        try:
            # Try role-based link first
            self.page.get_by_role("link", name=course_keyword, exact=False).first.click()
        except Exception:
            # Fall back to any element containing that text
            self.page.get_by_text(course_keyword, exact=False).first.click()

        self._wait(3)

    # ------------------------------------------------------------------
    # Assignment listing
    # ------------------------------------------------------------------

    def get_practice_assignments(self) -> list[dict]:
        """
        Return a list of {text, locator} dicts for visible assignment items.
        Tries multiple selector strategies to be resilient to DOM changes.
        """
        candidates = []

        selectors = [
            "[class*='assignment-item']",
            "[class*='AssignmentItem']",
            "[data-type='assignment']",
            "li[class*='item']",
            "a[href*='assignment']",
        ]

        for sel in selectors:
            elements = self.page.locator(sel).all()
            if elements:
                for el in elements:
                    try:
                        text = el.inner_text(timeout=1000).strip()
                        if text and len(text) > 3:
                            candidates.append({"text": text, "locator": el})
                    except Exception:
                        pass
                if candidates:
                    break

        return candidates

    def open_assignment(self, locator):
        locator.click()
        self._wait(4)

    # ------------------------------------------------------------------
    # Question extraction
    # ------------------------------------------------------------------

    def get_current_question(self) -> dict:
        """
        Inspect the current page and return a normalized question dict:
        {
            type: 'multiple_choice' | 'fill_blank' | 'matching' | None,
            text: str,
            options: [str],        # MC only
            num_blanks: int,       # fill_blank only
            left_items: [str],     # matching only
            right_items: [str],    # matching only
        }
        """
        q = {
            "type": None,
            "text": "",
            "options": [],
            "num_blanks": 0,
            "left_items": [],
            "right_items": [],
        }

        # --- Question text ---
        for sel in [
            "[class*='question-text']",
            "[class*='questionText']",
            "[class*='stem']",
            "[class*='prompt']",
            ".question p",
            ".question",
        ]:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=500):
                    q["text"] = el.inner_text(timeout=1000).strip()
                    break
            except Exception:
                pass

        # --- Detect type ---

        # Multiple choice: radio inputs present
        radios = self.page.locator("input[type='radio']").all()
        if radios:
            q["type"] = "multiple_choice"
            for sel in [
                "label.answer-choice",
                "[class*='answer-option']",
                "[class*='choice-label']",
                "label",
            ]:
                labels = self.page.locator(sel).all()
                texts = []
                for lbl in labels:
                    try:
                        t = lbl.inner_text(timeout=500).strip()
                        if t:
                            texts.append(t)
                    except Exception:
                        pass
                if texts:
                    q["options"] = texts
                    break
            return q

        # Matching: select dropdowns present
        selects = self.page.locator("select").all()
        if selects:
            q["type"] = "matching"
            # Left items are usually labels or list items next to the selects
            left_labels = self.page.locator("[class*='match-term'], [class*='matchTerm'], td:first-child").all()
            q["left_items"] = [el.inner_text(timeout=500).strip() for el in left_labels if el.inner_text(timeout=500).strip()]
            # Right items are the select options (excluding placeholder)
            for sel_el in selects[:1]:
                options = sel_el.locator("option").all()
                q["right_items"] = [
                    opt.inner_text(timeout=500).strip()
                    for opt in options
                    if opt.get_attribute("value") not in ("", None)
                ]
            return q

        # Fill in the blank: text inputs present
        text_inputs = self.page.locator("input[type='text'], input[class*='blank']").all()
        if text_inputs:
            q["type"] = "fill_blank"
            q["num_blanks"] = len(text_inputs)
            return q

        return q

    # ------------------------------------------------------------------
    # Answering
    # ------------------------------------------------------------------

    def select_multiple_choice(self, answer_text: str) -> bool:
        """Click the label or radio that matches answer_text."""
        # Try clicking the label that contains the text
        labels = self.page.locator("label").all()
        for label in labels:
            try:
                if answer_text.strip().lower() in label.inner_text(timeout=500).lower():
                    label.click()
                    time.sleep(0.4)
                    return True
            except Exception:
                pass

        # Try clicking the radio button directly by its associated value
        try:
            self.page.get_by_text(answer_text, exact=False).first.click()
            return True
        except Exception:
            pass

        return False

    def fill_blanks(self, answers: list[str]):
        inputs = self.page.locator("input[type='text'], input[class*='blank']").all()
        for i, ans in enumerate(answers):
            if i < len(inputs):
                inputs[i].fill(ans)
                time.sleep(0.2)

    def select_matching(self, matches: dict):
        """
        matches: {"Term A": "Definition X", ...}
        For each select element, pick the option whose text matches the right-side value.
        """
        selects = self.page.locator("select").all()
        left_labels = self.page.locator(
            "[class*='match-term'], [class*='matchTerm'], td:first-child"
        ).all()

        for i, sel_el in enumerate(selects):
            if i < len(left_labels):
                term = left_labels[i].inner_text(timeout=500).strip()
                target = matches.get(term, "")
                if target:
                    sel_el.select_option(label=target)
                    time.sleep(0.3)

    # ------------------------------------------------------------------
    # Submit & feedback
    # ------------------------------------------------------------------

    def submit_current(self):
        for sel in [
            "button:has-text('Submit')",
            "button:has-text('Check')",
            "input[type='submit']",
            "button[class*='submit']",
        ]:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=500):
                    btn.click()
                    self._wait(2)
                    return
            except Exception:
                pass

    def get_feedback(self) -> dict:
        """
        After submission, extract whether the answer was correct and what the
        correct answer was according to Connect.
        """
        feedback = {"correct": False, "correct_answer": ""}

        # Correct/incorrect banner
        try:
            if self.page.locator("[class*='correct']:not([class*='in'])").first.is_visible(timeout=1000):
                feedback["correct"] = True
        except Exception:
            pass

        # Shown correct answer
        for sel in [
            "[class*='correct-answer']",
            "[class*='correctAnswer']",
            "[class*='solution']",
            "[class*='feedback']",
        ]:
            try:
                el = self.page.locator(sel).first
                if el.is_visible(timeout=500):
                    feedback["correct_answer"] = el.inner_text(timeout=500).strip()
                    break
            except Exception:
                pass

        return feedback

    def has_next_question(self) -> bool:
        for sel in ["button:has-text('Next')", "[class*='next-question']", "[aria-label*='Next']"]:
            try:
                if self.page.locator(sel).first.is_visible(timeout=500):
                    return True
            except Exception:
                pass
        return False

    def go_next_question(self):
        for sel in ["button:has-text('Next')", "[class*='next-question']", "[aria-label*='Next']"]:
            try:
                btn = self.page.locator(sel).first
                if btn.is_visible(timeout=500):
                    btn.click()
                    self._wait(2)
                    return
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _wait(self, seconds=2):
        self.page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(seconds)

    def screenshot(self, path="debug.png"):
        self.page.screenshot(path=path)
