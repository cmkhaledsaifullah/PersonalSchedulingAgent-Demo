"""
Google Services MCP Server.

A FastMCP server that exposes Gmail and Google Calendar functionality
as MCP tools. This server is intended to be run as a subprocess and
communicated with via the MCP stdio transport.

Usage (standalone):
    python -m mcp_server.google_services_server

Usage (with MCP inspector):
    mcp dev mcp_server/google_services_server.py

The server exposes three tools:
  - read_emails          : Fetch emails from Gmail
  - create_meeting       : Create a Google Calendar event (online or in-person)
  - list_calendar_events : List upcoming calendar events
"""

import base64
import json
import os
import pickle
import sys
from pathlib import Path
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Google auth bootstrap
# ---------------------------------------------------------------------------

# Add project root to path so we can import auth module
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from auth.google_auth import get_google_credentials  # noqa: E402

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="GoogleServicesServer",
    instructions=(
        "This MCP server provides access to Gmail and Google Calendar. "
        "Use read_emails to retrieve emails, create_meeting to schedule events, "
        "and list_calendar_events to check existing events."
    ),
)


def _get_gmail_service():
    from googleapiclient.discovery import build
    creds = get_google_credentials()
    return build("gmail", "v1", credentials=creds)


def _get_calendar_service():
    from googleapiclient.discovery import build
    creds = get_google_credentials()
    return build("calendar", "v3", credentials=creds)


# ---------------------------------------------------------------------------
# Tool: read_emails
# ---------------------------------------------------------------------------

@mcp.tool()
def read_emails(
    max_results: Annotated[int, "Maximum number of emails to retrieve (1-20)"] = 5,
    query: Annotated[
        Optional[str],
        "Gmail search query, e.g. 'is:unread', 'subject:meeting'. Leave empty for recent emails.",
    ] = None,
) -> str:
    """
    Read emails from the authenticated user's Gmail inbox.

    Returns a JSON list of emails with: id, subject, from, to, date, snippet, body.
    """
    service = _get_gmail_service()

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
        emails.append(_parse_gmail_message(msg))

    return json.dumps({"emails": emails}, indent=2)


# ---------------------------------------------------------------------------
# Tool: create_meeting
# ---------------------------------------------------------------------------

@mcp.tool()
def create_meeting(
    title: Annotated[str, "Title / subject of the meeting."],
    start_datetime: Annotated[
        str, "Start date and time in ISO 8601, e.g. '2025-06-15T14:00:00'."
    ],
    end_datetime: Annotated[
        str, "End date and time in ISO 8601, e.g. '2025-06-15T15:00:00'."
    ],
    meeting_type: Annotated[
        str,
        "'online' to add a Google Meet link, 'in_person' to set a physical location.",
    ],
    description: Annotated[str, "Description or agenda of the meeting."] = "",
    timezone: Annotated[str, "IANA timezone, e.g. 'America/New_York'."] = "America/New_York",
    attendee_emails: Annotated[
        Optional[list],
        "List of attendee email addresses to invite.",
    ] = None,
    location: Annotated[
        Optional[str],
        "Physical address for in-person meetings.",
    ] = None,
) -> str:
    """
    Create a Google Calendar event and send email invitations to attendees.

    For online meetings a Google Meet video link is automatically generated.
    For in-person meetings the physical address is attached to the event.
    Returns a JSON summary with event details and the Meet link (if applicable).
    """
    service = _get_calendar_service()

    event_body: dict = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_datetime, "timeZone": timezone},
        "end": {"dateTime": end_datetime, "timeZone": timezone},
        "attendees": [{"email": e} for e in (attendee_emails or [])],
    }

    if meeting_type == "online":
        event_body["conferenceData"] = {
            "createRequest": {
                "requestId": f"meet-{title[:20].replace(' ', '-').lower()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }
    elif meeting_type == "in_person" and location:
        event_body["location"] = location

    created = (
        service.events()
        .insert(
            calendarId="primary",
            body=event_body,
            sendUpdates="all",
            conferenceDataVersion=1,
        )
        .execute()
    )

    result = {
        "event_id": created.get("id"),
        "html_link": created.get("htmlLink"),
        "title": created.get("summary"),
        "start": created.get("start", {}).get("dateTime"),
        "end": created.get("end", {}).get("dateTime"),
        "meeting_type": meeting_type,
        "attendees": [a["email"] for a in created.get("attendees", [])],
    }

    if meeting_type == "online":
        entry_points = created.get("conferenceData", {}).get("entryPoints", [])
        result["meet_link"] = next(
            (ep["uri"] for ep in entry_points if ep.get("entryPointType") == "video"),
            None,
        )

    if meeting_type == "in_person":
        result["location"] = created.get("location", location)

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool: list_calendar_events
# ---------------------------------------------------------------------------

@mcp.tool()
def list_calendar_events(
    max_results: Annotated[int, "Maximum number of events to return (1-20)."] = 10,
    time_min: Annotated[
        Optional[str],
        "Lower bound for event start time in RFC 3339, e.g. '2025-06-01T00:00:00Z'. "
        "Defaults to now.",
    ] = None,
) -> str:
    """
    List upcoming events from Google Calendar.

    Returns a JSON list of events with: id, title, start, end, attendees,
    meet_link (if present), location (if present).
    """
    from datetime import datetime, timezone as tz

    service = _get_calendar_service()

    if not time_min:
        time_min = datetime.now(tz.utc).isoformat()

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = events_result.get("items", [])
    if not events:
        return json.dumps({"events": [], "message": "No upcoming events found."})

    parsed = []
    for e in events:
        entry: dict = {
            "id": e.get("id"),
            "title": e.get("summary"),
            "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
            "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
            "attendees": [a["email"] for a in e.get("attendees", [])],
        }
        # Extract Meet link if present
        entry_points = e.get("conferenceData", {}).get("entryPoints", [])
        meet = next(
            (ep["uri"] for ep in entry_points if ep.get("entryPointType") == "video"),
            None,
        )
        if meet:
            entry["meet_link"] = meet
        if e.get("location"):
            entry["location"] = e["location"]
        parsed.append(entry)

    return json.dumps({"events": parsed}, indent=2)


# ---------------------------------------------------------------------------
# Gmail helpers (duplicated here so server is self-contained)
# ---------------------------------------------------------------------------

def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _decode_body(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")
    if mime_type == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        text = _decode_body(part)
        if text:
            return text
    return ""


def _parse_gmail_message(msg: dict) -> dict:
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
