"""
Google Meet link tool — Direct API integration.

Provides a lightweight LangChain tool to create a standalone
Google Meet link by creating a minimal Calendar event.

Note: Google Meet links are tied to Calendar events. This tool
creates a minimal event and returns the Meet link, useful when
you need a Meet link quickly without full event details.

For full event creation with invites, use CreateCalendarEventTool
with meeting_type='online' instead.
"""

import json
from typing import Type

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class CreateMeetLinkInput(BaseModel):
    title: str = Field(description="Title for the Google Meet session.")
    start_datetime: str = Field(
        description="Start date and time in ISO 8601, e.g. '2025-06-15T14:00:00'."
    )
    end_datetime: str = Field(
        description="End date and time in ISO 8601, e.g. '2025-06-15T15:00:00'."
    )
    timezone: str = Field(
        default="America/New_York",
        description="IANA timezone name.",
    )


class CreateMeetLinkTool(BaseTool):
    """
    Create a Google Meet link for an online meeting.

    Creates a minimal Calendar event and extracts the auto-generated
    Google Meet video conference URL.

    Tip: For creating a full event with attendees and invites, use the
    create_calendar_event tool with meeting_type='online'.
    """

    name: str = "create_meet_link"
    description: str = (
        "Generate a Google Meet video conference link. "
        "Use this when you only need a Meet URL without creating a full calendar event. "
        "For full event scheduling with invites, use create_calendar_event instead."
    )
    args_schema: Type[BaseModel] = CreateMeetLinkInput
    credentials: Credentials = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        title: str,
        start_datetime: str,
        end_datetime: str,
        timezone: str = "America/New_York",
    ) -> str:
        service = build("calendar", "v3", credentials=self.credentials)

        event_body = {
            "summary": title,
            "start": {"dateTime": start_datetime, "timeZone": timezone},
            "end": {"dateTime": end_datetime, "timeZone": timezone},
            "conferenceData": {
                "createRequest": {
                    "requestId": f"meet-quick-{title[:15].replace(' ', '-').lower()}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }

        created = (
            service.events()
            .insert(
                calendarId="primary",
                body=event_body,
                conferenceDataVersion=1,
            )
            .execute()
        )

        entry_points = created.get("conferenceData", {}).get("entryPoints", [])
        meet_link = next(
            (ep["uri"] for ep in entry_points if ep.get("entryPointType") == "video"),
            None,
        )

        return json.dumps(
            {
                "event_id": created.get("id"),
                "meet_link": meet_link,
                "event_link": created.get("htmlLink"),
                "title": title,
            },
            indent=2,
        )

    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)
