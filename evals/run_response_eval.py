import argparse
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from agent.agent import create_scheduling_agent


@tool
def read_emails(max_results: int = 5, query: str | None = None) -> str:
    """Read emails from Gmail by query and return summaries."""
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
                {
                    "id": "3",
                    "subject": "Townhall on Friday",
                    "from": "hr@example.com",
                    "body": "Company townhall on Friday at 11 AM, please attend.",
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
    return json.dumps({"status": "ok", "tool": "create_calendar_event", "title": title})


@tool
def create_meet_link(
    title: str,
    start_datetime: str,
    end_datetime: str,
    timezone: str = "America/New_York",
) -> str:
    """Create a standalone Google Meet link."""
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
    return json.dumps({"status": "ok", "tool": "create_reminder", "title": title})


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


def extract_final_text(result: dict[str, Any]) -> str:
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts: list[str] = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                    elif isinstance(block, str):
                        parts.append(block)
                return "\n".join(p for p in parts if p).strip()
            return str(content).strip()
    return ""


def run_case(agent, case: dict[str, Any]) -> dict[str, Any]:
    result = agent.invoke({"messages": [("human", case["prompt"])]})
    text = extract_final_text(result)

    lowered = text.lower()
    min_chars = int(case.get("response_min_chars", 30))
    length_ok = len(text) >= min_chars

    must_contain = [s.lower() for s in case.get("response_contains_all", [])]
    missing_all = [s for s in must_contain if s not in lowered]

    any_group = [s.lower() for s in case.get("response_contains_any", [])]
    any_ok = True
    if any_group:
        any_ok = any(token in lowered for token in any_group)

    passed = length_ok and not missing_all and any_ok

    return {
        "id": case["id"],
        "passed": passed,
        "response_chars": len(text),
        "missing_contains_all": missing_all,
        "contains_any_ok": any_ok,
        "preview": text[:180].replace("\n", " "),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run response-quality evaluations with mocked tools")
    parser.add_argument("--llm", default="google", choices=["anthropic", "openai", "google"])
    parser.add_argument("--cases", default=None)
    parser.add_argument("--bucket", default="all", help="Scenario bucket name (e.g. meeting_requests) or 'all'")
    parser.add_argument("--scenarios-dir", default="evals/scenarios")
    args = parser.parse_args()

    load_dotenv()

    if args.cases:
        cases_path = Path(args.cases)
        if not cases_path.exists():
            raise SystemExit(f"Cases file not found: {cases_path}")
        cases = load_cases(cases_path)
    else:
        scenarios_dir = Path(args.scenarios_dir)
        if not scenarios_dir.exists():
            raise SystemExit(f"Scenarios directory not found: {scenarios_dir}")
        cases = load_cases_from_bucket(scenarios_dir, args.bucket)

    tools = [read_emails, create_calendar_event, create_meet_link, create_reminder]
    agent = create_scheduling_agent(tools, llm_provider=args.llm)

    results = [run_case(agent, case) for case in cases]
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print("\nResponse Evaluation Results")
    print("-" * 60)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['id']}")
        print(f"  chars: {r['response_chars']}")
        print(f"  preview: {r['preview']}")
        if r["missing_contains_all"]:
            print(f"  missing required text: {r['missing_contains_all']}")
        if not r["contains_any_ok"]:
            print("  none of response_contains_any tokens were found")

    print("-" * 60)
    print(f"Score: {passed}/{total} ({(passed / total * 100) if total else 0:.1f}%)")

    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
