"""
CLI wrapper for word_writer — called by the Playwright MCP agent.

Usage:
    python word_writer_cli.py "<course>" "<assignment>" '<json_array>'
"""

import json
import sys
from pathlib import Path

from word_writer import write_answer_key

if len(sys.argv) < 4:
    print("Usage: word_writer_cli.py <course> <assignment> <json>")
    sys.exit(1)

course = sys.argv[1]
assignment = sys.argv[2]
data = json.loads(sys.argv[3])

output_dir = Path(__file__).parent / "output"
path = write_answer_key(output_dir, course, assignment, data, "")
print(f"Saved: {path}")
