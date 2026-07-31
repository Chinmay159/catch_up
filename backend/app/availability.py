from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import DEFAULT_TIMEZONE
from .database import get_study_preferences
from .google_calendar import get_calendar_events_for_calendar, parse_calendar_commitment
from .models import (
    AvailabilityResponse,
    AvailabilityWarning,
    BusyBlock,
    CalendarCommitment,
    DailyStudyWindow,
    FreeWindow,
    StudyAvailabilityRequest,
    StudyPreferences,
)


class AvailabilityError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def timezone_from_name(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise AvailabilityError("TIMEZONE_REQUIRED", "A valid timezone is required") from error


def validate_request(request: StudyAvailabilityRequest) -> ZoneInfo:
    if request.end_date < request.start_date:
        raise AvailabilityError("INVALID_DATE_RANGE", "endDate must be on or after startDate")
    if request.timezone is None:
        raise AvailabilityError("TIMEZONE_REQUIRED", "A timezone is required")
    if request.daily_windows is None:
        raise AvailabilityError("STUDY_WINDOWS_REQUIRED", "Study windows are required")

    timezone = timezone_from_name(request.timezone)
    seen_weekdays = set()
    for window in request.daily_windows:
        if window.weekday in seen_weekdays:
            raise AvailabilityError("INVALID_STUDY_WINDOW", "Duplicate study weekdays are not supported")
        seen_weekdays.add(window.weekday)
        if window.enabled and window.end_time <= window.start_time:
            raise AvailabilityError("INVALID_STUDY_WINDOW", "Overnight study windows are not supported yet")
    return timezone


def request_from_preferences(request: StudyAvailabilityRequest, preferences: StudyPreferences) -> StudyAvailabilityRequest:
    return request.model_copy(update={
        "timezone": request.timezone or preferences.timezone,
        "daily_windows": request.daily_windows or preferences.daily_windows,
        "minimum_window_minutes": request.minimum_window_minutes or preferences.minimum_session_minutes,
    })


def resolve_request_preferences(
    request: StudyAvailabilityRequest,
    preferences: StudyPreferences | None,
) -> StudyAvailabilityRequest:
    if preferences is None:
        return request
    return request_from_preferences(request, preferences)


def blocking_commitments(commitments: list[CalendarCommitment]) -> list[CalendarCommitment]:
    return [event for event in commitments if event.transparency == "busy"]


def merge_busy_blocks(commitments: list[CalendarCommitment]) -> list[BusyBlock]:
    blocks = sorted(
        [
            BusyBlock(
                id=event.id,
                source_event_ids=[event.id],
                start_at=event.start_at,
                end_at=event.end_at,
                reason="all_day_event" if event.all_day else "calendar_event",
            )
            for event in blocking_commitments(commitments)
        ],
        key=lambda block: block.start_at,
    )
    if not blocks:
        return []

    merged = [blocks[0]]
    for block in blocks[1:]:
        current = merged[-1]
        if block.start_at <= current.end_at:
            current.end_at = max(current.end_at, block.end_at)
            current.source_event_ids.extend(block.source_event_ids)
            if block.reason == "all_day_event":
                current.reason = "all_day_event"
            current.id = "+".join(current.source_event_ids)
        else:
            merged.append(block)
    return merged


def window_minutes(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def study_windows_for_range(
    request: StudyAvailabilityRequest,
    timezone: ZoneInfo,
) -> list[tuple[datetime, datetime]]:
    windows_by_weekday = {window.weekday: window for window in request.daily_windows if window.enabled}
    windows = []
    current = request.start_date

    while current <= request.end_date:
        window = windows_by_weekday.get(current.weekday())
        if window:
            windows.append((
                datetime.combine(current, window.start_time, tzinfo=timezone),
                datetime.combine(current, window.end_time, tzinfo=timezone),
            ))
        current += timedelta(days=1)

    return windows


def free_windows_from_busy_blocks(
    study_windows: list[tuple[datetime, datetime]],
    busy_blocks: list[BusyBlock],
    minimum_minutes: int,
) -> list[FreeWindow]:
    free_windows = []
    ordered_busy = sorted(busy_blocks, key=lambda block: block.start_at)

    for study_start, study_end in study_windows:
        cursor = study_start
        for block in ordered_busy:
            busy_start = max(block.start_at, study_start)
            busy_end = min(block.end_at, study_end)
            if busy_end <= cursor or busy_start >= study_end:
                continue
            if busy_start > cursor and window_minutes(cursor, busy_start) >= minimum_minutes:
                free_windows.append(FreeWindow(
                    id=f"free-{len(free_windows) + 1}",
                    start_at=cursor,
                    end_at=busy_start,
                    duration_minutes=window_minutes(cursor, busy_start),
                ))
            cursor = max(cursor, busy_end)

        if cursor < study_end and window_minutes(cursor, study_end) >= minimum_minutes:
            free_windows.append(FreeWindow(
                id=f"free-{len(free_windows) + 1}",
                start_at=cursor,
                end_at=study_end,
                duration_minutes=window_minutes(cursor, study_end),
            ))

    return sorted(free_windows, key=lambda window: window.start_at)


def calculate_availability(
    request: StudyAvailabilityRequest,
    calendar_service=None,
    commitments: list[CalendarCommitment] | None = None,
    preferences: StudyPreferences | None = None,
    user_id: str = "me",
) -> AvailabilityResponse:
    if preferences is None and (
        request.timezone is None
        or request.daily_windows is None
        or request.minimum_window_minutes is None
    ):
        preferences = get_study_preferences(user_id)[0]
    request = resolve_request_preferences(request, preferences)
    timezone = validate_request(request)
    calendar_ids = ["primary"]

    range_start = datetime.combine(request.start_date, time(0, 0), tzinfo=timezone)
    range_end = datetime.combine(request.end_date + timedelta(days=1), time(0, 0), tzinfo=timezone)
    warnings: list[AvailabilityWarning] = []

    calendar_events: list[CalendarCommitment] = list(commitments or [])
    if commitments is None and calendar_service is not None:
        for calendar_id in calendar_ids:
            try:
                raw_events = get_calendar_events_for_calendar(calendar_service, calendar_id, range_start, range_end)
                for event in raw_events:
                    commitment = parse_calendar_commitment(event, calendar_id, timezone)
                    if commitment is not None:
                        calendar_events.append(commitment)
            except Exception:
                warnings.append(AvailabilityWarning(
                    code="CALENDAR_PARTIAL_FAILURE",
                    message="Could not fetch this calendar",
                    calendar_id=calendar_id,
                ))

    busy_blocks = merge_busy_blocks(calendar_events)
    study_windows = study_windows_for_range(request, timezone)
    free_windows = free_windows_from_busy_blocks(study_windows, busy_blocks, request.minimum_window_minutes)

    total_study = sum(window_minutes(start, end) for start, end in study_windows)
    total_busy = 0
    for study_start, study_end in study_windows:
        for block in busy_blocks:
            total_busy += window_minutes(max(study_start, block.start_at), min(study_end, block.end_at))
    total_busy = min(total_busy, total_study)
    total_free = sum(window.duration_minutes for window in free_windows)
    if total_study and total_free == 0:
        warnings.append(AvailabilityWarning(code="NO_FREE_TIME", message="No free study windows were found"))

    return AvailabilityResponse(
        range_start=range_start,
        range_end=range_end,
        timezone=request.timezone,
        calendar_events=sorted(calendar_events, key=lambda event: event.start_at),
        busy_blocks=busy_blocks,
        free_windows=free_windows,
        total_study_window_minutes=total_study,
        total_busy_minutes=total_busy,
        total_free_minutes=total_free,
        warnings=warnings,
        calculated_at=datetime.now(DEFAULT_TIMEZONE),
    )
