from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from backend.app.models import AssignmentInfo, DraftStudySession, FreeWindow
from backend.app.preferences import default_study_preferences
from backend.app.priority import sort_by_priority
from backend.app.scheduler import build_scheduling_preview


TZ = ZoneInfo("America/Chicago")
NOW = datetime(2026, 7, 30, 12, 0, tzinfo=TZ)


def assignment(
    assignment_id: str,
    title: str,
    minutes: int | None,
    *,
    due: date | None = date(2026, 8, 1),
    due_time: time | None = time(23, 0),
    submission_state: str = "NEW",
    active: bool = True,
    scheduled_minutes: int = 0,
):
    return AssignmentInfo(
        assignment_id=assignment_id,
        course_id="course-1",
        title=title,
        due_date=due,
        due_time=due_time,
        estimated_minutes=minutes,
        submission_state=submission_state,
        is_active=active,
        scheduled_minutes=scheduled_minutes,
    )


def window(window_id: str, start: str, end: str):
    start_at = datetime.fromisoformat(start)
    end_at = datetime.fromisoformat(end)
    return FreeWindow(id=window_id, start_at=start_at, end_at=end_at, duration_minutes=int((end_at - start_at).total_seconds() // 60))


def plan(assignments, windows, prefs=None, **kwargs):
    prefs = prefs or default_study_preferences("me")
    return build_scheduling_preview(sort_by_priority(type("A", (), {"assignments": assignments})(), NOW, TZ), windows, prefs, NOW, **kwargs)


def test_highest_priority_assignment_is_scheduled_first_and_uses_system_one_ordering():
    low = assignment("low", "Later", 30, due=date(2026, 8, 8))
    high = assignment("high", "Soon", 30, due=date(2026, 7, 30), due_time=time(23, 0))

    result = plan([low, high], [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00")])

    assert result.draft_sessions[0].assignment_id == "high"


def test_turned_in_and_inactive_assignments_are_excluded():
    result = plan([
        assignment("turned-in", "Done", 30, submission_state="TURNED_IN"),
        assignment("inactive", "Hidden", 30, active=False),
    ], [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00")])

    assert result.draft_sessions == []
    assert result.failures == []


def test_missing_estimate_produces_failure_instead_of_invented_session():
    result = plan([assignment("missing", "Needs estimate", None)], [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00")])

    assert result.draft_sessions == []
    assert result.failures[0].code == "missing_estimate"


def test_overdue_work_uses_earliest_available_time():
    result = plan([assignment("overdue", "Overdue", 40, due=date(2026, 7, 29))], [
        window("w1", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00"),
        window("w2", "2026-07-31T16:00:00-05:00", "2026-07-31T18:00:00-05:00"),
    ])

    assert result.draft_sessions[0].start_at == datetime(2026, 7, 30, 16, 0, tzinfo=TZ)
    assert "overdue" in result.draft_sessions[0].placement_reasons[0]


def test_future_assignment_sessions_do_not_cross_deadline():
    result = plan([assignment("due", "Due", 90, due=date(2026, 7, 30), due_time=time(17, 0))], [
        window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T19:00:00-05:00"),
    ])

    assert result.draft_sessions[0].end_at <= datetime(2026, 7, 30, 17, 0, tzinfo=TZ)
    assert result.failures[0].unscheduled_minutes == 30


def test_backlog_work_follows_urgent_dated_work_when_included():
    urgent = assignment("urgent", "Urgent", 30, due=date(2026, 7, 30), due_time=time(23, 0))
    backlog = assignment("backlog", "Backlog", 30, due=None)

    result = plan([backlog, urgent], [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00")], include_backlog=True)

    assert [session.assignment_id for session in result.draft_sessions] == ["urgent", "backlog"]


def test_backlog_work_is_included_by_default_after_dated_work():
    dated = assignment("dated", "Dated", 30, due=date(2026, 8, 1))
    backlog = assignment("backlog", "Backlog", 30, due=None)

    result = plan([backlog, dated], [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00")])

    assert [session.assignment_id for session in result.draft_sessions] == ["dated", "backlog"]


def test_minimum_and_maximum_session_duration_and_splitting_are_enforced():
    result = plan([assignment("long", "Long", 100)], [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00")])

    assert [session.duration_minutes for session in result.draft_sessions] == [50, 50]
    assert all(20 <= session.duration_minutes <= 60 for session in result.draft_sessions)


def test_splitting_disabled_produces_correct_failure():
    prefs = default_study_preferences("me").model_copy(update={"allow_assignment_splitting": False})

    result = plan([assignment("long", "Long", 90)], [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00")], prefs)

    assert result.draft_sessions == []
    assert result.failures[0].code == "splitting_disabled"


def test_required_breaks_are_inserted_and_sessions_do_not_overlap():
    result = plan([
        assignment("a", "A", 60),
        assignment("b", "B", 50),
    ], [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00")])

    assert result.draft_sessions[0].end_at + timedelta(minutes=10) <= result.draft_sessions[1].start_at
    assert result.draft_sessions[1].end_at <= datetime(2026, 7, 30, 18, 0, tzinfo=TZ)


def test_daily_study_limits_are_enforced_with_distinct_failure():
    prefs = default_study_preferences("me")
    prefs.daily_windows[3].maximum_daily_study_minutes = 60

    result = plan([assignment("a", "A", 90)], [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T20:00:00-05:00")], prefs)

    assert result.total_scheduled_minutes == 60
    assert result.failures[0].code == "daily_limit_reached"


def test_no_free_time_and_too_short_windows_are_classified():
    no_free = plan([assignment("a", "A", 30)], [])
    too_short = plan([assignment("b", "B", 30)], [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T16:10:00-05:00")])

    assert no_free.failures[0].code == "no_free_time"
    assert too_short.failures[0].code == "session_too_short"


def test_multiple_days_partial_totals_and_idempotency():
    windows = [
        window("w1", "2026-07-30T16:00:00-05:00", "2026-07-30T17:00:00-05:00"),
        window("w2", "2026-07-31T16:00:00-05:00", "2026-07-31T17:00:00-05:00"),
    ]

    first = plan([assignment("project", "Project", 140)], [item.model_copy(deep=True) for item in windows])
    second = plan([assignment("project", "Project", 140)], [item.model_copy(deep=True) for item in windows])

    assert [session.duration_minutes for session in first.draft_sessions] == [60, 60]
    assert first.failures[0].unscheduled_minutes == 20
    assert first.total_scheduled_minutes == sum(session.duration_minutes for session in first.draft_sessions)
    assert first.total_unscheduled_minutes == 20
    assert [session.id for session in first.draft_sessions] == [session.id for session in second.draft_sessions]


def test_fully_scheduled_assignment_is_not_scheduled_again():
    result = plan(
        [assignment("done", "Already planned", 60, scheduled_minutes=60)],
        [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00")],
    )

    assert result.draft_sessions == []
    assert result.failures == []
    assert result.total_requested_minutes == 0


def test_existing_sessions_count_against_rebuild_and_consume_time():
    existing = DraftStudySession(
        id="draft-project-1-20260730T1600",
        assignment_id="project",
        course_id="course-1",
        assignment_title="Project",
        start_at=datetime(2026, 7, 30, 16, 0, tzinfo=TZ),
        end_at=datetime(2026, 7, 30, 17, 0, tzinfo=TZ),
        duration_minutes=60,
        sequence_number=1,
        total_assignment_sessions=1,
        placement_reasons=["Existing draft."],
    )
    prefs = default_study_preferences("me")
    prioritized = sort_by_priority(
        type("A", (), {"assignments": [assignment("project", "Project", 90, scheduled_minutes=60)]})(),
        NOW,
        TZ,
    )

    result = build_scheduling_preview(
        prioritized,
        [window("w", "2026-07-30T16:00:00-05:00", "2026-07-30T18:00:00-05:00")],
        prefs,
        NOW,
        existing_sessions=[existing],
    )

    assert [session.duration_minutes for session in result.draft_sessions] == [30]
    assert result.draft_sessions[0].start_at == datetime(2026, 7, 30, 17, 10, tzinfo=TZ)
