"""
McGraw Hill Study Agent — main entry point.

Usage:
    python agent.py "Business Law"
    python agent.py "Business Strategies" --assignment "Chapter 5"
    python agent.py "Business Law" --headless
    python agent.py --list-courses
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load credentials from the .env file next to this script
load_dotenv(Path(__file__).parent / "credentials.env")

from mcgraw_connect import McGrawHillConnect
from answer_engine import AnswerEngine
import word_writer

SKILL_DIR = Path(__file__).parent


def load_config() -> dict:
    with open(SKILL_DIR / "config.json") as f:
        return json.load(f)


def run(course_keyword: str, assignment_filter: str | None, headless: bool):
    email = os.getenv("MCGRAW_EMAIL")
    password = os.getenv("MCGRAW_PASSWORD")
    api_key = os.getenv("ANTHROPIC_API_KEY")

    missing = [k for k, v in {"MCGRAW_EMAIL": email, "MCGRAW_PASSWORD": password, "ANTHROPIC_API_KEY": api_key}.items() if not v]
    if missing:
        print(f"ERROR: Missing credentials in credentials.env: {', '.join(missing)}")
        sys.exit(1)

    config = load_config()
    course_config = next(
        (c for c in config["courses"] if course_keyword.lower() in c["name"].lower()),
        None,
    )
    if not course_config:
        print(f"ERROR: Course '{course_keyword}' not found in config.json")
        print("Available courses:", [c["name"] for c in config["courses"]])
        sys.exit(1)

    subject = course_config["name"]
    course_keyword_nav = course_config.get("nav_keyword", subject)

    print(f"\n{'='*60}")
    print(f"  McGraw Hill Study Agent")
    print(f"  Course: {subject}")
    if assignment_filter:
        print(f"  Filter: {assignment_filter}")
    print(f"{'='*60}\n")

    output_dir = SKILL_DIR / "output"
    bot = McGrawHillConnect(headless=headless)
    engine = AnswerEngine(api_key)

    try:
        bot.start()

        print("Logging in to McGraw Hill Connect...")
        bot.login(email, password)
        print("Login: OK\n")

        print(f"Navigating to course: {subject}")
        bot.navigate_to_course(course_keyword_nav)

        assignments = bot.get_practice_assignments()
        if not assignments:
            print("No assignments found on this page. Taking debug screenshot...")
            bot.screenshot(str(SKILL_DIR / "debug_assignments.png"))
            sys.exit(1)

        print(f"Found {len(assignments)} assignment(s)\n")

        for assignment in assignments:
            name = assignment["text"]

            if assignment_filter and assignment_filter.lower() not in name.lower():
                print(f"  Skipping: {name[:60]}")
                continue

            print(f"Opening: {name[:70]}")
            bot.open_assignment(assignment["locator"])

            questions_answers = []
            q_num = 1

            while True:
                print(f"  [{q_num}] Reading question...", end=" ", flush=True)
                q = bot.get_current_question()

                if not q["text"]:
                    print("no text found, skipping")
                    if not bot.has_next_question():
                        break
                    bot.go_next_question()
                    continue

                print(f"({q['type']})", end=" ", flush=True)

                record = {
                    "question": q["text"],
                    "type": q["type"],
                    "correct_answer": "",
                    "explanation": "",
                }

                try:
                    if q["type"] == "multiple_choice":
                        ans = engine.answer_multiple_choice(q["text"], q["options"], subject)
                        record["explanation"] = ans.get("explanation", "")
                        bot.select_multiple_choice(ans["answer_text"])

                    elif q["type"] == "fill_blank":
                        ans = engine.answer_fill_blank(q["text"], q["num_blanks"], subject)
                        record["explanation"] = ans.get("explanation", "")
                        bot.fill_blanks(ans["answers"])

                    elif q["type"] == "matching":
                        ans = engine.answer_matching(q["text"], q["left_items"], q["right_items"], subject)
                        record["explanation"] = ans.get("explanation", "")
                        bot.select_matching(ans["matches"])

                    else:
                        print("unknown type, skipping")
                        if not bot.has_next_question():
                            break
                        bot.go_next_question()
                        continue

                except Exception as e:
                    print(f"answer error: {e}")
                    record["explanation"] = f"Could not answer automatically: {e}"

                bot.submit_current()
                feedback = bot.get_feedback()

                # Use Connect's shown correct answer if available, else our answer
                if feedback.get("correct_answer"):
                    record["correct_answer"] = feedback["correct_answer"]
                elif q["type"] == "multiple_choice":
                    record["correct_answer"] = ans.get("answer_text", "")
                elif q["type"] == "fill_blank":
                    record["correct_answer"] = ", ".join(ans.get("answers", []))
                elif q["type"] == "matching":
                    record["correct_answer"] = str(ans.get("matches", {}))

                status = "✓" if feedback.get("correct") else "→"
                print(f"{status} {record['correct_answer'][:50]}")

                questions_answers.append(record)
                q_num += 1

                if not bot.has_next_question():
                    break
                bot.go_next_question()

            if not questions_answers:
                print(f"  No questions collected for: {name}\n")
                continue

            print(f"\n  Generating study guide ({len(questions_answers)} questions)...")
            study_guide = engine.generate_study_guide(questions_answers, subject, name)

            print("  Saving to Word doc...")
            filepath = word_writer.write_answer_key(output_dir, subject, name, questions_answers, study_guide)
            print(f"  Saved: {filepath}\n")

    finally:
        bot.stop()

    print("Done.")


def main():
    parser = argparse.ArgumentParser(
        description="McGraw Hill Connect practice agent — answers questions and saves study guide to a Word doc"
    )
    parser.add_argument("course", nargs="?", help='Course name, e.g. "Business Law"')
    parser.add_argument(
        "--assignment", "-a",
        help="Filter to a specific assignment by name substring",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser without a visible window",
    )
    parser.add_argument(
        "--list-courses",
        action="store_true",
        help="Print configured courses and exit",
    )

    args = parser.parse_args()

    if args.list_courses:
        config = load_config()
        print("Configured courses:")
        for c in config["courses"]:
            print(f"  - {c['name']}")
        return

    if not args.course:
        parser.print_help()
        sys.exit(1)

    run(args.course, args.assignment, args.headless)


if __name__ == "__main__":
    main()
