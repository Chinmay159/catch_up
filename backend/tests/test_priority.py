from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from backend.app.models import AssignmentInfo, Assignments
from backend.app.priority import build_dashboard, calculate_priority, recommend_next_assignment, sort_by_priority


TZ = ZoneInfo("America/Chicago")
NOW = datetime(2026, 7, 29, 12, 0, tzinfo=TZ)


def assignment(
    assignment_id: str,
    title: str,
    due_date: date | None,
    *,
    due_time: time | None = time(23, 59),
    estimated_minutes: int | None = 60,
    scheduled_minutes: int = 0,
    completed_study_minutes: int = 0,
    submission_state: str | None = "NEW",
    is_active: bool = True,
) -> AssignmentInfo:
    return AssignmentInfo(
        assignment_id=assignment_id,
        course_id="course-1",
        title=title,
        due_date=due_date,
        due_time=due_time,
        estimated_minutes=estimated_minutes,
        scheduled_minutes=scheduled_minutes,
        completed_study_minutes=completed_study_minutes,
        submission_state=submission_state,
        is_active=is_active,
    )


def test_overdue_assignment_is_high_priority_with_explainable_categories():
    result = calculate_priority(
        assignment("late", "Late essay", date(2026, 7, 28), estimated_minutes=90),
        now=NOW,
    )

    assert result.level == "high"
    assert "overdue" in result.categories
    assert "unscheduled" in result.categories
    assert result.remaining_minutes == 90
    assert any(reason.code == "overdue" for reason in result.reason_details)


def test_missing_estimate_is_explained_without_becoming_top_priority_by_itself():
    result = calculate_priority(
        assignment("backlog", "Optional reading", None, due_time=None, estimated_minutes=None),
        now=NOW,
    )

    assert result.level == "low"
    assert result.categories == ["backlog", "unscheduled"]
    assert result.remaining_minutes is None
    assert "This assignment does not have a time estimate." in result.reasons


def test_remaining_minutes_cannot_fall_below_zero():
    result = calculate_priority(
        assignment(
            "scheduled",
            "Worksheet",
            date(2026, 7, 30),
            estimated_minutes=45,
            scheduled_minutes=30,
            completed_study_minutes=30,
        ),
        now=NOW,
    )

    assert result.remaining_minutes == 0
    assert result.score >= 0


def test_recommendation_ignores_inactive_and_turned_in_assignments():
    assignments = Assignments(
        assignments=[
            assignment("turned-in", "Submitted project", date(2026, 7, 28), submission_state="TURNED_IN"),
            assignment("inactive", "Hidden lab", date(2026, 7, 28), is_active=False),
            assignment("next", "Revision", date(2026, 7, 30), submission_state="RETURNED"),
        ]
    )

    recommendation = recommend_next_assignment(assignments, now=NOW)

    assert recommendation.assignment is not None
    assert recommendation.assignment.assignment_id == "next"
    assert recommendation.priority_score is not None
    assert "This work was returned or reclaimed and may need action." in recommendation.reasons


def test_sort_by_priority_breaks_score_ties_by_earlier_deadline():
    assignments = Assignments(
        assignments=[
            assignment("later", "Later work", date(2026, 8, 2), estimated_minutes=60),
            assignment("earlier", "Earlier work", date(2026, 7, 31), estimated_minutes=60),
        ]
    )

    ranked = sort_by_priority(assignments, now=NOW)

    assert [item[0].assignment_id for item in ranked] == ["earlier", "later"]


def test_dashboard_to_do_matches_next_recommendation_for_same_input():
    assignments = Assignments(
        assignments=[
            assignment("soon", "Short work", date(2026, 7, 30), estimated_minutes=30),
            assignment("late", "Late work", date(2026, 7, 28), estimated_minutes=30),
        ]
    )

    dashboard = build_dashboard(assignments, now=NOW)
    recommendation = recommend_next_assignment(assignments, now=NOW)

    assert recommendation.assignment is not None
    assert dashboard.to_do[0].assignment.assignment_id == recommendation.assignment.assignment_id


def test_due_date_crossing_midnight_uses_user_timezone():
    result = calculate_priority(
        assignment("midnight", "Midnight work", date(2026, 7, 30), due_time=time(0, 30), estimated_minutes=30),
        now=datetime(2026, 7, 29, 23, 45, tzinfo=TZ),
    )

    assert result.level == "high"
    assert "upcoming" in result.categories
    assert any(reason.code == "due_very_soon" for reason in result.reason_details)


def test_date_only_deadline_uses_end_of_due_date_in_user_timezone():
    result = calculate_priority(
        assignment("date-only", "Date-only work", date(2026, 7, 30), due_time=None, estimated_minutes=30),
        now=datetime(2026, 7, 30, 20, 0, tzinfo=TZ),
    )

    assert "upcoming" in result.categories
    assert any(reason.code == "missing_due_time" for reason in result.reason_details)
    assert any(reason.code == "due_very_soon" for reason in result.reason_details)


def test_daylight_saving_boundary_uses_zoneinfo_offsets():
    result = calculate_priority(
        assignment("dst", "DST work", date(2026, 11, 1), due_time=time(1, 30), estimated_minutes=30),
        now=datetime(2026, 11, 1, 0, 30, tzinfo=TZ),
    )

    assert "upcoming" in result.categories
    assert any(reason.code == "due_very_soon" for reason in result.reason_details)


def test_normal_week_workload_recommends_overdue_assignment():
    assignments = Assignments(
        assignments=[
            assignment("overdue", "Overdue quiz", date(2026, 7, 28), estimated_minutes=30),
            assignment("soon", "Lab", date(2026, 7, 30), estimated_minutes=120),
            assignment("week", "Reading", date(2026, 8, 4), estimated_minutes=30),
        ]
    )

    recommendation = recommend_next_assignment(assignments, now=NOW)

    assert recommendation.assignment is not None
    assert recommendation.assignment.assignment_id == "overdue"


def test_multiple_overdue_assignments_recommend_larger_remaining_effort():
    assignments = Assignments(
        assignments=[
            assignment("short-late", "Short late", date(2026, 7, 28), estimated_minutes=20),
            assignment("long-late", "Long late", date(2026, 7, 28), estimated_minutes=140),
        ]
    )

    recommendation = recommend_next_assignment(assignments, now=NOW)

    assert recommendation.assignment is not None
    assert recommendation.assignment.assignment_id == "long-late"


def test_long_assignment_due_soon_beats_short_assignment_same_deadline():
    assignments = Assignments(
        assignments=[
            assignment("short", "Short same deadline", date(2026, 7, 30), estimated_minutes=20),
            assignment("long", "Long same deadline", date(2026, 7, 30), estimated_minutes=130),
        ]
    )

    recommendation = recommend_next_assignment(assignments, now=NOW)

    assert recommendation.assignment is not None
    assert recommendation.assignment.assignment_id == "long"


def test_caught_up_student_has_no_recommendation():
    assignments = Assignments(
        assignments=[
            assignment("done", "Done", date(2026, 7, 28), submission_state="TURNED_IN"),
            assignment("hidden", "Hidden", date(2026, 7, 28), is_active=False),
        ]
    )

    recommendation = recommend_next_assignment(assignments, now=NOW)

    assert recommendation.assignment is None
    assert recommendation.priority_score is None


def test_only_backlog_assignments_recommends_highest_backlog_effort():
    assignments = Assignments(
        assignments=[
            assignment("small-backlog", "Small backlog", None, estimated_minutes=20),
            assignment("large-backlog", "Large backlog", None, estimated_minutes=130),
        ]
    )

    recommendation = recommend_next_assignment(assignments, now=NOW)

    assert recommendation.assignment is not None
    assert recommendation.assignment.assignment_id == "large-backlog"


def test_scheduled_backlog_keeps_backlog_category_without_unscheduled():
    result = calculate_priority(
        assignment("backlog", "Backlog reading", None, estimated_minutes=60, scheduled_minutes=60),
        now=datetime(2026, 7, 29, 12, 0, tzinfo=TZ),
    )

    assert result.categories == ["backlog"]
    assert result.remaining_minutes == 0


def test_missing_estimate_due_soon_still_recommendable_with_reason():
    assignments = Assignments(
        assignments=[
            assignment("missing", "Missing estimate", date(2026, 7, 30), estimated_minutes=None),
            assignment("later", "Later estimate", date(2026, 8, 5), estimated_minutes=30),
        ]
    )

    recommendation = recommend_next_assignment(assignments, now=NOW)

    assert recommendation.assignment is not None
    assert recommendation.assignment.assignment_id == "missing"
    assert "This assignment does not have a time estimate." in recommendation.reasons


def test_returned_work_gets_revision_reason():
    result = calculate_priority(
        assignment("returned", "Returned essay", date(2026, 7, 31), estimated_minutes=60, submission_state="RETURNED"),
        now=NOW,
    )

    assert any(reason.code == "needs_revision" for reason in result.reason_details)


def test_unscheduled_urgent_work_beats_fully_scheduled_urgent_work():
    assignments = Assignments(
        assignments=[
            assignment("scheduled", "Scheduled urgent", date(2026, 7, 30), estimated_minutes=60, scheduled_minutes=60),
            assignment("unscheduled", "Unscheduled urgent", date(2026, 7, 30), estimated_minutes=60),
        ]
    )

    recommendation = recommend_next_assignment(assignments, now=NOW)

    assert recommendation.assignment is not None
    assert recommendation.assignment.assignment_id == "unscheduled"
