from datetime import date, time

import pytest

from backend.app.availability import AvailabilityError, calculate_availability, merge_busy_blocks
from backend.app.google_calendar import parse_calendar_commitment
from backend.app.models import DailyStudyWindow, StudyAvailabilityRequest


TZ = "America/Chicago"


def request(
    start: date = date(2026, 7, 29),
    end: date = date(2026, 7, 29),
    *,
    minimum: int = 15,
) -> StudyAvailabilityRequest:
    return StudyAvailabilityRequest(
        start_date=start,
        end_date=end,
        timezone=TZ,
        daily_windows=[
            DailyStudyWindow(weekday=i, enabled=True, start_time=time(16, 0), end_time=time(22, 0))
            for i in range(7)
        ],
        minimum_window_minutes=minimum,
    )


def event(
    event_id: str,
    start: str,
    end: str,
    *,
    calendar_id: str = "primary",
    title: str = "Event",
    status: str = "confirmed",
    transparency: str | None = None,
):
    raw = {
        "id": event_id,
        "summary": title,
        "status": status,
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        "htmlLink": "https://calendar.google.com/",
    }
    if transparency:
        raw["transparency"] = transparency
    return parse_calendar_commitment(raw, calendar_id)


def all_day(event_id: str, start: str, end: str, *, transparency: str | None = None):
    raw = {
        "id": event_id,
        "summary": "All day",
        "status": "confirmed",
        "start": {"date": start},
        "end": {"date": end},
    }
    if transparency:
        raw["transparency"] = transparency
    return parse_calendar_commitment(raw, "primary")


def test_timed_events_normalize_correctly():
    commitment = event("a", "2026-07-29T17:00:00-05:00", "2026-07-29T18:00:00-05:00", title="Practice")

    assert commitment.title == "Practice"
    assert commitment.calendar_id == "primary"
    assert commitment.read_only is True
    assert commitment.source == "google_calendar"
    assert commitment.all_day is False


def test_recurring_events_are_expanded_by_parsing_each_instance():
    commitments = [
        event("rec-1", "2026-07-29T17:00:00-05:00", "2026-07-29T18:00:00-05:00"),
        event("rec-2", "2026-07-30T17:00:00-05:00", "2026-07-30T18:00:00-05:00"),
    ]

    assert len([item for item in commitments if item is not None]) == 2


def test_cancelled_and_transparent_events_do_not_block_time():
    cancelled = parse_calendar_commitment({
        "id": "cancelled",
        "status": "cancelled",
        "start": {"dateTime": "2026-07-29T17:00:00-05:00"},
        "end": {"dateTime": "2026-07-29T18:00:00-05:00"},
    }, "primary")
    transparent = event("free", "2026-07-29T17:00:00-05:00", "2026-07-29T18:00:00-05:00", transparency="transparent")

    response = calculate_availability(request(), commitments=[item for item in [cancelled, transparent] if item])

    assert cancelled is None
    assert response.busy_blocks == []
    assert response.total_free_minutes == 360


def test_opaque_events_block_and_split_free_windows():
    response = calculate_availability(
        request(),
        commitments=[event("busy", "2026-07-29T17:00:00-05:00", "2026-07-29T18:00:00-05:00")],
    )

    assert len(response.busy_blocks) == 1
    assert [window.duration_minutes for window in response.free_windows] == [60, 240]


def test_overlapping_and_adjacent_events_merge():
    blocks = merge_busy_blocks([
        event("a", "2026-07-29T16:00:00-05:00", "2026-07-29T17:00:00-05:00"),
        event("b", "2026-07-29T16:30:00-05:00", "2026-07-29T18:00:00-05:00"),
        event("c", "2026-07-29T18:00:00-05:00", "2026-07-29T19:00:00-05:00"),
    ])

    assert len(blocks) == 1
    assert blocks[0].source_event_ids == ["primary:a", "primary:b", "primary:c"]
    assert blocks[0].end_at.hour == 19


def test_event_crossing_midnight_blocks_correct_day_parts():
    response = calculate_availability(
        request(date(2026, 7, 29), date(2026, 7, 30)),
        commitments=[event("overnight", "2026-07-29T21:00:00-05:00", "2026-07-30T17:00:00-05:00")],
    )

    assert response.total_free_minutes == 600


def test_all_day_opaque_blocks_study_window_and_transparent_does_not():
    opaque = calculate_availability(request(), commitments=[all_day("all", "2026-07-29", "2026-07-30")])
    transparent = calculate_availability(request(), commitments=[all_day("free-all", "2026-07-29", "2026-07-30", transparency="transparent")])

    assert opaque.total_free_minutes == 0
    assert opaque.warnings[0].code == "NO_FREE_TIME"
    assert transparent.total_free_minutes == 360


def test_multiple_calendars_combine_and_keep_ids():
    response = calculate_availability(
        request(),
        commitments=[
            event("a", "2026-07-29T17:00:00-05:00", "2026-07-29T18:00:00-05:00", calendar_id="personal"),
            event("b", "2026-07-29T19:00:00-05:00", "2026-07-29T20:00:00-05:00", calendar_id="school"),
        ],
    )

    assert [block.source_event_ids for block in response.busy_blocks] == [["personal:a"], ["school:b"]]
    assert response.total_free_minutes == 240


class FailingService:
    def events(self):
        return self
    def list(self, **kwargs):
        if kwargs["calendarId"] == "primary":
            raise RuntimeError("calendar failed")
        return self
    def execute(self):
        return {"items": []}


def test_one_calendar_failure_returns_partial_warning():
    response = calculate_availability(
        request(),
        calendar_service=FailingService(),
    )

    assert response.warnings[0].code == "CALENDAR_PARTIAL_FAILURE"
    assert response.total_free_minutes == 360


def test_minimum_window_filters_short_windows_and_ordering():
    response = calculate_availability(
        request(minimum=45),
        commitments=[event("busy", "2026-07-29T16:30:00-05:00", "2026-07-29T21:30:00-05:00")],
    )

    assert [window.duration_minutes for window in response.free_windows] == []
    assert response.warnings[0].code == "NO_FREE_TIME"


def test_timezone_conversion_and_dst_boundary():
    response = calculate_availability(
        request(date(2026, 11, 1), date(2026, 11, 1)),
        commitments=[event("dst", "2026-11-01T16:00:00-06:00", "2026-11-01T17:00:00-06:00")],
    )

    assert response.timezone == TZ
    assert response.total_free_minutes == 300


def test_invalid_date_range_and_study_window_rejected():
    with pytest.raises(AvailabilityError) as date_error:
        calculate_availability(request(date(2026, 7, 30), date(2026, 7, 29)), commitments=[])
    with pytest.raises(AvailabilityError) as window_error:
        calculate_availability(
            StudyAvailabilityRequest(
                start_date=date(2026, 7, 29),
                end_date=date(2026, 7, 29),
                timezone=TZ,
                daily_windows=[DailyStudyWindow(weekday=2, enabled=True, start_time=time(22, 0), end_time=time(4, 0))],
                minimum_window_minutes=15,
            ),
            commitments=[],
        )

    assert date_error.value.code == "INVALID_DATE_RANGE"
    assert window_error.value.code == "INVALID_STUDY_WINDOW"


def test_realistic_fixtures_normal_heavy_none_weekend():
    normal = calculate_availability(
        request(),
        commitments=[
            event("school", "2026-07-29T16:00:00-05:00", "2026-07-29T17:00:00-05:00"),
            event("sports", "2026-07-29T18:00:00-05:00", "2026-07-29T19:30:00-05:00"),
            event("dinner", "2026-07-29T20:00:00-05:00", "2026-07-29T20:30:00-05:00"),
        ],
    )
    heavy = calculate_availability(
        request(minimum=20),
        commitments=[event("heavy", "2026-07-29T16:00:00-05:00", "2026-07-29T21:30:00-05:00")],
    )
    none = calculate_availability(
        request(),
        commitments=[event("full", "2026-07-29T16:00:00-05:00", "2026-07-29T22:00:00-05:00")],
    )
    weekend = calculate_availability(
        request(date(2026, 8, 1), date(2026, 8, 1)),
        commitments=[],
    )

    assert [window.duration_minutes for window in normal.free_windows] == [60, 30, 90]
    assert [window.duration_minutes for window in heavy.free_windows] == [30]
    assert none.warnings[0].code == "NO_FREE_TIME"
    assert weekend.total_free_minutes == 360
