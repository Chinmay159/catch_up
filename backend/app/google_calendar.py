from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from .config import DEFAULT_TIMEZONE
from .models import CalendarCommitment, CalendarEvent


def build_calendar_service(credentials):
    return build("calendar", "v3", credentials=credentials)


def get_calendar_events(calendar_service, days_ahead: int = 7) -> list[dict]:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days_ahead)

    return get_calendar_events_for_calendar(calendar_service, "primary", now, end)


def get_calendar_events_for_calendar(
    calendar_service,
    calendar_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    events = []
    page_token = None
    while True:
        response = (
            calendar_service.events()
            .list(
                calendarId=calendar_id,
                timeMin=start.astimezone(timezone.utc).isoformat(),
                timeMax=end.astimezone(timezone.utc).isoformat(),
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
            )
            .execute()
        )
        events.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return events


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


def parse_calendar_commitment(
    event: dict,
    calendar_id: str,
    default_timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> CalendarCommitment | None:
    if event.get("status") == "cancelled":
        return None

    transparency = "free" if event.get("transparency") == "transparent" else "busy"
    start = event.get("start", {})
    end = event.get("end", {})
    if not start or not end:
        return None

    all_day = "date" in start
    status = "tentative" if event.get("status") == "tentative" else "confirmed"

    return CalendarCommitment(
        id=f"{calendar_id}:{event.get('id', event.get('iCalUID', 'unknown'))}",
        calendar_id=calendar_id,
        title=event.get("summary", "No Title"),
        start_at=parse_event_time(start, default_timezone),
        end_at=parse_event_time(end, default_timezone),
        all_day=all_day,
        status=status,
        transparency=transparency,
        location=event.get("location"),
        description=event.get("description"),
        html_link=event.get("htmlLink"),
    )
