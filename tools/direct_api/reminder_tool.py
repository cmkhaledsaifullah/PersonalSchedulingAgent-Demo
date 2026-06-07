"""
Google Calendar Reminder LangChain tool — Direct API integration.

Creates a personal reminder as a Google Calendar event with a popup
notification. No attendees are invited — this is for the user only.
"""

import json
from typing import Optional, Type

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class CreateReminderInput(BaseModel):
    title: str = Field(description="Title of the reminder, e.g. 'Call dentist to book appointment'.")
    description: str = Field(
        default="",
        description="Optional notes or context for the reminder.",
    )
    reminder_date: str = Field(
        description=(
            "Date for the reminder in ISO 8601 format: YYYY-MM-DD. "
            "Use the next relevant date if no specific date is given."
        )
    )
    reminder_time: Optional[str] = Field(
        default=None,
        description=(
            "Time for the reminder in HH:MM (24-hour) format, e.g. '09:00'. "
            "If omitted, the reminder is set as an all-day event."
        ),
    )
    timezone: str = Field(
        default="America/New_York",
        description="IANA timezone name, e.g. 'America/New_York'.",
    )
    minutes_before: int = Field(
        default=30,
        description="Minutes before the reminder event to trigger a popup notification.",
    )


class CreateReminderTool(BaseTool):
    """
    Create a personal reminder on Google Calendar with a popup notification.

    No email invitations are sent — this is a private reminder for the user.
    """

    name: str = "create_reminder"
    description: str = (
        "Create a personal reminder on Google Calendar. "
        "Use this when an email asks you to remember to do something "
        "(e.g. call an office, follow up on a task) rather than scheduling a meeting. "
        "Sets a popup notification at the specified time. No invites are sent."
    )
    args_schema: Type[BaseModel] = CreateReminderInput
    credentials: Credentials = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        title: str,
        description: str = "",
        reminder_date: str = "",
        reminder_time: Optional[str] = None,
        timezone: str = "America/New_York",
        minutes_before: int = 30,
    ) -> str:
        """Create the reminder event and return a JSON summary."""
        service = build("calendar", "v3", credentials=self.credentials)

        if reminder_time:
            start_datetime = f"{reminder_date}T{reminder_time}:00"
            # Default duration: 30 minutes
            hour, minute = map(int, reminder_time.split(":"))
            end_minute = minute + 30
            end_hour = hour + end_minute // 60
            end_minute = end_minute % 60
            end_datetime = f"{reminder_date}T{end_hour:02d}:{end_minute:02d}:00"

            event_body: dict = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start_datetime, "timeZone": timezone},
                "end": {"dateTime": end_datetime, "timeZone": timezone},
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": minutes_before},
                        {"method": "email", "minutes": minutes_before},
                    ],
                },
            }
        else:
            # All-day reminder
            event_body = {
                "summary": title,
                "description": description,
                "start": {"date": reminder_date},
                "end": {"date": reminder_date},
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 480},   # 8 AM popup for all-day
                        {"method": "email", "minutes": 480},
                    ],
                },
            }

        created_event = (
            service.events()
            .insert(
                calendarId="primary",
                body=event_body,
                sendUpdates="none",  # No invites — personal reminder only
            )
            .execute()
        )

        result = {
            "event_id": created_event.get("id"),
            "html_link": created_event.get("htmlLink"),
            "title": created_event.get("summary"),
            "reminder_type": "timed" if reminder_time else "all_day",
            "date": reminder_date,
            "time": reminder_time or "all-day",
            "popup_notification_minutes_before": minutes_before if reminder_time else 480,
        }

        return json.dumps(result, indent=2)

    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)
