import asyncio
import base64
import os
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel.server import NotificationOptions
import mcp.types as types

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(DIR, "token.json")
CREDS_PATH = os.path.join(DIR, "credentials.json")


def get_service():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def make_raw(to: str, subject: str, body: str) -> str:
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


server = Server("gmail-scheduler")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="schedule_email",
            description="Schedule a Gmail to send at a specific future time",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "send_at": {
                        "type": "string",
                        "description": "RFC 3339 datetime e.g. 2025-06-02T08:50:00-04:00",
                    },
                },
                "required": ["to", "subject", "body", "send_at"],
            },
        ),
        types.Tool(
            name="send_email",
            description="Send a Gmail immediately",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    svc = get_service()
    raw = make_raw(arguments["to"], arguments["subject"], arguments["body"])
    body: dict = {"raw": raw}

    if name == "schedule_email":
        body["scheduledSendTime"] = arguments["send_at"]

    result = svc.users().messages().send(userId="me", body=body).execute()
    action = f"scheduled for {arguments['send_at']}" if name == "schedule_email" else "sent"
    return [types.TextContent(type="text", text=f"Email {action}. ID: {result['id']}")]


async def main():
    async with stdio_server() as (r, w):
        await server.run(
            r,
            w,
            InitializationOptions(
                server_name="gmail-scheduler",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
