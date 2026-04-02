"""
Claude-powered answer engine.
Answers multiple choice, fill-in-the-blank, and matching questions
for Business Law and Business Strategies subjects.
"""

import json
import anthropic


class AnswerEngine:
    MODEL = "claude-opus-4-6"

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    # ------------------------------------------------------------------
    # Public answering methods
    # ------------------------------------------------------------------

    def answer_multiple_choice(self, question: str, options: list[str], subject: str) -> dict:
        """
        Returns:
            {answer_index: int, answer_text: str, explanation: str}
        """
        numbered = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))
        prompt = f"""You are an expert in {subject}. Answer this practice question accurately.

Question: {question}

Options:
{numbered}

Reply with ONLY valid JSON (no markdown fences):
{{"answer_index": 0, "answer_text": "exact text of the correct option", "explanation": "one sentence why"}}

answer_index is 0-based."""

        return self._call(prompt)

    def answer_fill_blank(self, question: str, num_blanks: int, subject: str) -> dict:
        """
        Returns:
            {answers: [str], explanation: str}
        """
        prompt = f"""You are an expert in {subject}. Fill in the blank(s) for this practice question.

Question: {question}
Number of blanks: {num_blanks}

Reply with ONLY valid JSON (no markdown fences):
{{"answers": ["answer1"], "explanation": "one sentence why"}}

Provide exactly {num_blanks} answer(s) in order."""

        return self._call(prompt)

    def answer_matching(self, question: str, left_items: list[str], right_items: list[str], subject: str) -> dict:
        """
        Returns:
            {matches: {"term": "definition", ...}, explanation: str}
        """
        left_fmt = "\n".join(f"- {item}" for item in left_items)
        right_fmt = "\n".join(f"- {item}" for item in right_items)
        prompt = f"""You are an expert in {subject}. Match each left item to the correct right item.

Question: {question}

Left items:
{left_fmt}

Right items:
{right_fmt}

Reply with ONLY valid JSON (no markdown fences):
{{"matches": {{"Left item text": "Right item text"}}, "explanation": "one sentence why"}}"""

        return self._call(prompt)

    def generate_study_guide(self, questions_answers: list[dict], subject: str, assignment_name: str) -> str:
        """Generate a study guide summary from all Q&A collected."""
        qa_block = "\n\n".join(
            f"Q: {qa['question']}\nA: {qa['correct_answer']}\n"
            + (f"Note: {qa['explanation']}" if qa.get("explanation") else "")
            for qa in questions_answers
        )

        prompt = f"""You are creating a study guide for a {subject} student.

Assignment: {assignment_name}

Completed practice questions and answers:
{qa_block}

Write a study guide that includes:
1. Key Concepts (bullet points)
2. Important Terms & Definitions
3. Rules / Principles to Remember
4. Common Traps / Mistakes to Avoid

Use clear headers and bullet points. Be concise and exam-focused."""

        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call(self, prompt: str) -> dict:
        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        start = raw.find("{")
        end = raw.rfind("}") + 1
        return json.loads(raw[start:end])
