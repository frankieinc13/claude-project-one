"""
Google Docs integration using OAuth 2.0.
Creates/updates answer key documents in the user's Google Drive root.
"""

import os
import pickle
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


class GoogleDocsWriter:
    def __init__(self, credentials_path: str, token_path: str):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None
        self.docs = None
        self.drive = None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def authenticate(self):
        """Run OAuth flow (opens browser on first run, then uses cached token)."""
        if os.path.exists(self.token_path):
            with open(self.token_path, "rb") as f:
                self.creds = pickle.load(f)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            with open(self.token_path, "wb") as f:
                pickle.dump(self.creds, f)

        self.docs = build("docs", "v1", credentials=self.creds)
        self.drive = build("drive", "v3", credentials=self.creds)

    # ------------------------------------------------------------------
    # Doc management
    # ------------------------------------------------------------------

    def find_or_create_doc(self, course_name: str, assignment_name: str) -> str:
        """Return doc ID for this course/assignment, creating it if needed."""
        title = f"McGraw Hill — {course_name} — {assignment_name}"

        result = (
            self.drive.files()
            .list(
                q=f"name='{title}' and mimeType='application/vnd.google-apps.document' and trashed=false",
                fields="files(id)",
            )
            .execute()
        )
        files = result.get("files", [])
        if files:
            return files[0]["id"]

        doc = self.docs.documents().create(body={"title": title}).execute()
        return doc["documentId"]

    # ------------------------------------------------------------------
    # Writing content
    # ------------------------------------------------------------------

    def write_answer_key(
        self,
        doc_id: str,
        course_name: str,
        assignment_name: str,
        questions_answers: list[dict],
        study_guide: str,
    ) -> str:
        """
        Overwrites the doc with a formatted answer key + study guide.
        Returns the doc URL.
        """
        now = datetime.now().strftime("%B %d, %Y — %I:%M %p")

        # Build plain text content
        lines = []
        lines.append(f"{course_name}  |  {assignment_name}\n")
        lines.append(f"Last updated: {now}\n\n")
        lines.append("━" * 60 + "\n")
        lines.append("ANSWER KEY\n")
        lines.append("━" * 60 + "\n\n")

        for i, qa in enumerate(questions_answers, 1):
            lines.append(f"Q{i}. {qa['question']}\n")
            lines.append(f"     Answer: {qa['correct_answer']}\n")
            if qa.get("explanation"):
                lines.append(f"     Why: {qa['explanation']}\n")
            lines.append("\n")

        lines.append("\n" + "━" * 60 + "\n")
        lines.append("STUDY GUIDE\n")
        lines.append("━" * 60 + "\n\n")
        lines.append(study_guide)

        full_text = "".join(lines)

        # Clear existing body content
        doc = self.docs.documents().get(documentId=doc_id).execute()
        body_content = doc.get("body", {}).get("content", [])
        requests = []

        if len(body_content) > 1:
            end_index = body_content[-1].get("endIndex", 2) - 1
            if end_index > 1:
                requests.append(
                    {
                        "deleteContentRange": {
                            "range": {"startIndex": 1, "endIndex": end_index}
                        }
                    }
                )
                self.docs.documents().batchUpdate(
                    documentId=doc_id, body={"requests": requests}
                ).execute()

        # Insert new content
        insert_requests = [
            {"insertText": {"location": {"index": 1}, "text": full_text}},
            # Style the title line as Heading 1
            {
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": 1,
                        "endIndex": len(lines[0]) + 1,
                    },
                    "paragraphStyle": {"namedStyleType": "HEADING_1"},
                    "fields": "namedStyleType",
                }
            },
        ]

        self.docs.documents().batchUpdate(
            documentId=doc_id, body={"requests": insert_requests}
        ).execute()

        return f"https://docs.google.com/document/d/{doc_id}/edit"
