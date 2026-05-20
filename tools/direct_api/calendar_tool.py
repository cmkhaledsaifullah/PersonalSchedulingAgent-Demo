"""
Google Calendar LangChain tool — Direct API integration.

Creates calendar events with support for:
  - Google Meet (online meetings) — a Meet link is auto-generated
  - In-person meetings           — a location/address is added to the event
"""

import json
from typing import List, Literal, Optional, Type

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class CreateCalendarEventInput(BaseModel):
    title: str = Field(description="Title / subject of the meeting.")
    description: str = Field(
        default="",
        description="Description or agenda of the meeting.",
    )
    start_datetime: str = Field(
        description=(
            "Start date and time in ISO 8601 format, e.g. '2025-06-15T14:00:00'. "
            "Always include the date and time."
        )
    )
    end_datetime: str = Field(
        description=(
            "End date and time in ISO 8601 format, e.g. '2025-06-15T15:00:00'."
        )
    )
    timezone: str = Field(
        default="America/New_York",
        description="IANA timezone name, e.g. 'America/New_York', 'America/Los_Angeles'.",
    )
    attendee_emails: List[str] = Field(
        default_factory=list,
        description="List of attendee email addresses to invite.",
    )
    meeting_type: Literal["online", "in_person"] = Field(
        description=(
            "'online' to add a Google Meet link, "
            "'in_person' to set a physical location."
        )
    )
    location: Optional[str] = Field(
        default=None,
        description=(
            "Physical address or location for in-person meetings. "
            "Required when meeting_type is 'in_person'."
        ),
    )


class CreateCalendarEventTool(BaseTool):
    """
    Create a Google Calendar event and send invites to attendees.

    For online meetings a Google Meet conference link is automatically
    generated. For in-person meetings the physical address is attached.
    """

    name: str = "create_calendar_event"
    description: str = (
        "Create a Google Calendar event. "
        "Supports both online meetings (auto-generates a Google Meet link) "
        "and in-person meetings (adds a physical address). "
        "Sends email invitations to all specified attendees."
    )
    args_schema: Type[BaseModel] = CreateCalendarEventInput
    credentials: Credentials = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        title: str,
        description: str = "",
        start_datetime: str = "",
        end_datetime: str = "",
        timezone: str = "America/New_York",
        attendee_emails: Optional[List[str]] = None,
        meeting_type: Literal["online", "in_person"] = "online",
        location: Optional[str] = None,
    ) -> str:
        """Create the calendar event and return a JSON summary."""
        service = build("calendar", "v3", credentials=self.credentials)

        event_body: dict = {
            "summary": title,
            "description": description,
            "start": {
                "dateTime": start_datetime,
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_datetime,
                "timeZone": timezone,
            },
            "attendees": [
                {"email": email} for email in (attendee_emails or [])
            ],
            # Send email invitations to all attendees
            "guestsCanModify": False,
            "guestsCanInviteOthers": False,
        }

        if meeting_type == "online":
            # Request a Google Meet conference link
            event_body["conferenceData"] = {
                "createRequest": {
                    "requestId": f"meet-{title[:20].replace(' ', '-').lower()}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
        elif meeting_type == "in_person" and location:
            event_body["location"] = location

        created_event = (
            service.events()
            .insert(
                calendarId="primary",
                body=event_body,
                sendUpdates="all",        # Send invite emails to attendees
                conferenceDataVersion=1,  # Required to generate Meet links
            )
            .execute()
        )

        result = {
            "event_id": created_event.get("id"),
            "html_link": created_event.get("htmlLink"),
            "title": created_event.get("summary"),
            "start": created_event.get("start", {}).get("dateTime"),
            "end": created_event.get("end", {}).get("dateTime"),
            "meeting_type": meeting_type,
            "attendees": [a["email"] for a in created_event.get("attendees", [])],
        }

        if meeting_type == "online":
            conference = created_event.get("conferenceData", {})
            entry_points = conference.get("entryPoints", [])
            meet_link = next(
                (ep["uri"] for ep in entry_points if ep.get("entryPointType") == "video"),
                None,
            )
            result["meet_link"] = meet_link

        if meeting_type == "in_person":
            result["location"] = created_event.get("location", location)

        return json.dumps(result, indent=2)

    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)
