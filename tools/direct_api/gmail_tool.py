"""
Gmail LangChain tool — Direct API integration.

Provides a LangChain-compatible tool that reads emails from Gmail
using the Google Gmail API directly (no MCP layer).
"""

import base64
import json
from typing import Optional, Type

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class ReadEmailsInput(BaseModel):
    max_results: int = Field(
        default=5,
        description="Maximum number of emails to retrieve (1–20).",
        ge=1,
        le=20,
    )
    query: Optional[str] = Field(
        default=None,
        description=(
            "Gmail search query to filter emails, e.g. 'is:unread', "
            "'subject:meeting', 'from:boss@example.com'. "
            "Leave empty to fetch the most recent emails."
        ),
    )


class ReadEmailsTool(BaseTool):
    """
    Read emails from the authenticated user's Gmail inbox.

    Returns a JSON list of email summaries, each containing:
      - id, subject, from, to, date, snippet, body (plain text)
    """

    name: str = "read_emails"
    description: str = (
        "Read emails from Gmail. Use this to fetch recent emails or search "
        "for emails matching a query. Returns a list of emails with their "
        "subject, sender, recipient, date, and body text."
    )
    args_schema: Type[BaseModel] = ReadEmailsInput
    credentials: Credentials = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def _run(self, max_results: int = 5, query: Optional[str] = None) -> str:
        """Fetch emails from Gmail and return as a JSON string."""
        service = build("gmail", "v1", credentials=self.credentials)

        # List matching messages
        list_params = {"userId": "me", "maxResults": max_results}
        if query:
            list_params["q"] = query

        results = service.users().messages().list(**list_params).execute()
        messages = results.get("messages", [])

        if not messages:
            return json.dumps({"emails": [], "message": "No emails found."})

        emails = []
        for msg_ref in messages:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_ref["id"], format="full")
                .execute()
            )
            emails.append(_parse_message(msg))

        return json.dumps({"emails": emails}, indent=2)

    async def _arun(self, max_results: int = 5, query: Optional[str] = None) -> str:
        return self._run(max_results=max_results, query=query)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_header(headers: list[dict], name: str) -> str:
    """Extract a header value by name (case-insensitive)."""
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _decode_body(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    # Recurse into multipart parts
    for part in payload.get("parts", []):
        text = _decode_body(part)
        if text:
            return text

    return ""


def _parse_message(msg: dict) -> dict:
    """Convert a raw Gmail API message into a clean summary dict."""
    headers = msg.get("payload", {}).get("headers", [])
    return {
        "id": msg["id"],
        "subject": _get_header(headers, "Subject"),
        "from": _get_header(headers, "From"),
        "to": _get_header(headers, "To"),
        "date": _get_header(headers, "Date"),
        "snippet": msg.get("snippet", ""),
        "body": _decode_body(msg.get("payload", {})),
    }
