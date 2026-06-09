import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool

from agent.agent import create_scheduling_agent


@tool
def read_emails(max_results: int = 5, query: str | None = None) -> str:
    """Read emails from Gmail by query and return summaries."""
    _CALL_LOG.append({"tool": "read_emails", "args": {"max_results": max_results, "query": query}})
    return json.dumps(
        {
            "emails": [
                {
                    "id": "1",
                    "subject": "Can we meet tomorrow?",
                    "from": "alex@example.com",
                    "body": "Can we do a quick online sync tomorrow at 2 PM?",
                },
                {
                    "id": "2",
                    "subject": "Reminder: call the dentist",
                    "from": "clinic@example.com",
                    "body": "Please call us to confirm your appointment.",
                },
            ]
        }
    )


@tool
def create_calendar_event(
    title: str,
    description: str = "",
    all_day: bool = False,
    event_date: str | None = None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    timezone: str = "America/New_York",
    attendee_emails: list[str] | None = None,
    meeting_type: str = "online",
    location: str | None = None,
) -> str:
    """Create a calendar event and optionally invite attendees."""
    _CALL_LOG.append(
        {
            "tool": "create_calendar_event",
            "args": {
                "title": title,
                "meeting_type": meeting_type,
                "all_day": all_day,
                "attendee_emails": attendee_emails or [],
            },
        }
    )
    return json.dumps({"status": "ok", "tool": "create_calendar_event", "title": title})


@tool
def create_meet_link(
    title: str,
    start_datetime: str,
    end_datetime: str,
    timezone: str = "America/New_York",
) -> str:
    """Create a standalone Google Meet link."""
    _CALL_LOG.append(
        {
            "tool": "create_meet_link",
            "args": {
                "title": title,
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
            },
        }
    )
    return json.dumps({"status": "ok", "tool": "create_meet_link", "meet_link": "https://meet.google.com/demo"})


@tool
def create_reminder(
    title: str,
    description: str = "",
    reminder_date: str = "",
    reminder_time: str | None = None,
    timezone: str = "America/New_York",
    minutes_before: int = 30,
) -> str:
    """Create a personal reminder in calendar."""
    _CALL_LOG.append(
        {
            "tool": "create_reminder",
            "args": {
                "title": title,
                "reminder_date": reminder_date,
                "reminder_time": reminder_time,
            },
        }
    )
    return json.dumps({"status": "ok", "tool": "create_reminder", "title": title})


_CALL_LOG: list[dict[str, Any]] = []


def load_cases(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def list_bucket_files(scenarios_dir: Path) -> list[Path]:
    return sorted(p for p in scenarios_dir.glob("*.jsonl") if p.is_file())


def load_cases_from_bucket(scenarios_dir: Path, bucket: str) -> list[dict[str, Any]]:
    if bucket == "all":
        files = list_bucket_files(scenarios_dir)
        if not files:
            raise SystemExit(f"No scenario bucket files found in: {scenarios_dir}")
        rows: list[dict[str, Any]] = []
        for file in files:
            rows.extend(load_cases(file))
        return rows

    bucket_file = scenarios_dir / f"{bucket}.jsonl"
    if not bucket_file.exists():
        available = [p.stem for p in list_bucket_files(scenarios_dir)]
        raise SystemExit(
            f"Bucket '{bucket}' not found in {scenarios_dir}. "
            f"Available buckets: {available}"
        )
    return load_cases(bucket_file)


def run_case(agent, case: dict[str, Any]) -> dict[str, Any]:
    _CALL_LOG.clear()
    agent.invoke({"messages": [("human", case["prompt"])]})
    called = [entry["tool"] for entry in _CALL_LOG]

    must_call = case.get("must_call", [])
    must_not_call = case.get("must_not_call", [])

    missing = [name for name in must_call if name not in called]
    forbidden = [name for name in must_not_call if name in called]
    passed = not missing and not forbidden

    return {
        "id": case["id"],
        "passed": passed,
        "called": called,
        "missing": missing,
        "forbidden": forbidden,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local agent evaluations with mocked tools")
    parser.add_argument("--llm", default="google", choices=["anthropic", "openai", "google"])
    parser.add_argument("--cases", default="evals/cases.jsonl")
    parser.add_argument("--bucket", default=None, help="Scenario bucket name (e.g. meeting_requests) or 'all'")
    parser.add_argument("--scenarios-dir", default="evals/scenarios")
    args = parser.parse_args()

    load_dotenv()

    if args.bucket:
        scenarios_dir = Path(args.scenarios_dir)
        if not scenarios_dir.exists():
            raise SystemExit(f"Scenarios directory not found: {scenarios_dir}")
        cases = load_cases_from_bucket(scenarios_dir, args.bucket)
    else:
        cases_path = Path(args.cases)
        if not cases_path.exists():
            raise SystemExit(f"Cases file not found: {cases_path}")
        cases = load_cases(cases_path)

    tools = [read_emails, create_calendar_event, create_meet_link, create_reminder]
    agent = create_scheduling_agent(tools, llm_provider=args.llm)

    results = [run_case(agent, case) for case in cases]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print("\nEvaluation Results")
    print("-" * 60)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['id']}")
        print(f"  called: {r['called']}")
        if r["missing"]:
            print(f"  missing required calls: {r['missing']}")
        if r["forbidden"]:
            print(f"  forbidden calls made: {r['forbidden']}")

    print("-" * 60)
    print(f"Score: {passed}/{total} ({(passed / total * 100) if total else 0:.1f}%)")

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
