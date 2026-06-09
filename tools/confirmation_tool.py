"""
Human confirmation tool — pauses agent execution and waits for human approval.

Uses LangGraph's interrupt() to suspend the graph mid-run. The agent calls
this after classifying all emails and forming an action plan, before executing
any calendar or reminder creation.
"""

from langchain_core.tools import tool
from langgraph.types import interrupt


@tool
def request_human_confirmation(summary: str) -> str:
    """
    Present the planned actions to the human and wait for their approval
    before making any changes to Google Calendar.

    Call this AFTER reading emails and classifying all intended actions,
    and BEFORE calling create_calendar_event, create_meeting, or create_reminder.

    Args:
        summary: A clear, human-readable description of every action the agent
                 plans to take (one action per line is preferred).

    Returns:
        'approved' if the human confirms, 'rejected' if they decline.
    """
    response = interrupt(summary)
    return response
