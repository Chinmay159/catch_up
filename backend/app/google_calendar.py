from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from .config import DEFAULT_TIMEZONE
from .models import CalendarEvent


def build_calendar_service(credentials):
    return build("calendar", "v3", credentials=credentials)


def get_calendar_events(calendar_service, days_ahead: int = 7) -> list[dict]:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days_ahead)

    response = (
        calendar_service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return response.get("items", [])


def parse_event_time(value: dict, default_timezone: ZoneInfo = DEFAULT_TIMEZONE) -> datetime:
    if "dateTime" in value:
        parsed = datetime.fromisoformat(value["dateTime"])
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=default_timezone)
        return parsed

    if "date" in value:
        return datetime.fromisoformat(value["date"] + "T00:00:00").replace(tzinfo=default_timezone)

    raise ValueError("Event time does not have date or dateTime")


def parse_calendar_events(events: list[dict], user_id: str = "me") -> list[CalendarEvent]:
    calendar_events = []

    for event in events:
        start = event.get("start", {})
        end = event.get("end", {})

        if not start or not end:
            continue

        calendar_events.append(
            CalendarEvent(
                id=event.get("id"),
                title=event.get("summary", "No Title"),
                user_id=user_id,
                start_time=parse_event_time(start),
                end_time=parse_event_time(end),
                description=event.get("description"),
            )
        )

    return calendar_events
