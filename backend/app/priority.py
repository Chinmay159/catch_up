from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from .config import DEFAULT_TIMEZONE
from .models import (
    AssignmentInfo,
    Assignments,
    Dashboard,
    NextAssignmentRecommendation,
    PrioritizedAssignment,
    PriorityLevel,
    PriorityReason,
)

ACTIVE_SUBMISSION_STATES = {"NEW", "CREATED", "RETURNED", "RECLAIMED", "UNKNOWN"}


def is_recommendable_assignment(assignment: AssignmentInfo) -> bool:
    if not assignment.is_active:
        return False

    state = (assignment.submission_state or "UNKNOWN").upper()
    return state != "TURNED_IN"


def assignment_due_at(
    assignment: AssignmentInfo,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> datetime | None:
    if assignment.due_date is None:
        return None

    due_time = assignment.due_time or time(23, 59)
    return datetime.combine(assignment.due_date, due_time, tzinfo=timezone)


def remaining_minutes(assignment: AssignmentInfo) -> int | None:
    if assignment.estimated_minutes is None:
        return None

    studied_minutes = assignment.scheduled_minutes + assignment.completed_study_minutes
    return max(assignment.estimated_minutes - studied_minutes, 0)


def priority_categories(assignment: AssignmentInfo, now: datetime) -> list[str]:
    due_at = assignment_due_at(assignment, now.tzinfo or DEFAULT_TIMEZONE)

    if due_at is None:
        categories = ["backlog"]
        if remaining_minutes(assignment) is None or remaining_minutes(assignment) > 0:
            categories.append("unscheduled")
        return categories

    categories = ["overdue"] if due_at < now else ["upcoming"]

    if remaining_minutes(assignment) is None or assignment.scheduled_minutes < (remaining_minutes(assignment) or 0):
        categories.append("unscheduled")

    return categories


def _add_reason(
    reasons: list[PriorityReason],
    code: str,
    message: str,
    contribution: int | None = None,
) -> int:
    reasons.append(PriorityReason(code=code, message=message, contribution=contribution))
    return contribution or 0


def calculate_priority(
    assignment: AssignmentInfo,
    now: datetime | None = None,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> PriorityLevel:
    now = now or datetime.now(timezone)
    due_at = assignment_due_at(assignment, timezone)
    reasons: list[PriorityReason] = []
    score = 0

    if due_at is None:
        score += _add_reason(
            reasons,
            "no_due_date",
            "This assignment has no due date, so it belongs in the backlog unless other details make it urgent.",
            5,
        )
    else:
        hours_until_due = (due_at - now).total_seconds() / 3600
        if hours_until_due < 0:
            score += _add_reason(reasons, "overdue", "This assignment is overdue.", 70)
        elif hours_until_due <= 12:
            score += _add_reason(reasons, "due_very_soon", "This assignment is due within 12 hours.", 65)
        elif hours_until_due <= 24:
            score += _add_reason(reasons, "due_today", "This assignment is due within 24 hours.", 55)
        elif hours_until_due <= 72:
            score += _add_reason(reasons, "due_soon", "This assignment is due in the next three days.", 40)
        elif hours_until_due <= 168:
            score += _add_reason(reasons, "due_this_week", "This assignment is due within a week.", 25)
        else:
            score += _add_reason(reasons, "future_due_date", "This assignment is due more than a week from now.", 10)

        if assignment.due_time is None:
            score += _add_reason(
                reasons,
                "missing_due_time",
                "Google Classroom did not provide an exact due time.",
                3,
            )

    remaining = remaining_minutes(assignment)
    if remaining is None:
        score += _add_reason(
            reasons,
            "missing_estimate",
            "This assignment does not have a time estimate.",
            5,
        )
    elif remaining == 0:
        score += _add_reason(
            reasons,
            "fully_allocated",
            "The estimated work is already covered by scheduled or completed study time.",
            -10,
        )
    elif remaining >= 120:
        score += _add_reason(reasons, "large_remaining_effort", "This assignment still needs at least two hours of work.", 20)
    elif remaining >= 60:
        score += _add_reason(reasons, "moderate_remaining_effort", "This assignment still needs about an hour or more of work.", 12)
    else:
        score += _add_reason(reasons, "small_remaining_effort", "This assignment appears to need less than an hour of work.", 5)

    if remaining and assignment.estimated_minutes:
        scheduled_gap = max(assignment.estimated_minutes - assignment.scheduled_minutes, 0)
        if scheduled_gap > 0:
            score += _add_reason(
                reasons,
                "not_fully_scheduled",
                "This assignment does not appear to have all needed study time scheduled yet.",
                8,
            )

    state = (assignment.submission_state or "UNKNOWN").upper()
    if state in {"RETURNED", "RECLAIMED"}:
        score += _add_reason(reasons, "needs_revision", "This work was returned or reclaimed and may need action.", 12)
    elif state not in ACTIVE_SUBMISSION_STATES:
        score += _add_reason(reasons, "unknown_submission_state", "CatchUp does not recognize this Classroom submission state.", 0)

    score = max(0, min(score, 100))

    if score >= 70:
        level = "high"
    elif score >= 35:
        level = "medium"
    else:
        level = "low"

    return PriorityLevel(
        level=level,
        score=score,
        reasons=[reason.message for reason in reasons],
        categories=priority_categories(assignment, now),
        reason_details=reasons,
        remaining_minutes=remaining,
        calculated_at=now,
    )


def sort_by_priority(
    assignments: Assignments,
    now: datetime | None = None,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> list[tuple[AssignmentInfo, PriorityLevel]]:
    calculated_at = now or datetime.now(timezone)
    prioritized = [
        (assignment, calculate_priority(assignment, calculated_at, timezone))
        for assignment in assignments.assignments
        if is_recommendable_assignment(assignment)
    ]
    return sorted(
        prioritized,
        key=lambda item: (
            -item[1].score,
            item[0].due_date or date.max,
            item[0].due_time or time(23, 59),
            item[0].title.lower(),
        ),
    )


def recommend_next_assignment(
    assignments: Assignments,
    now: datetime | None = None,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> NextAssignmentRecommendation:
    calculated_at = now or datetime.now(timezone)
    prioritized = sort_by_priority(assignments, calculated_at, timezone)

    if not prioritized:
        return NextAssignmentRecommendation(calculated_at=calculated_at)

    assignment, priority = prioritized[0]
    return NextAssignmentRecommendation(
        assignment=assignment,
        priority_score=priority.score,
        priority_level=priority.level,
        reasons=priority.reasons,
        calculated_at=priority.calculated_at,
    )


def build_dashboard(
    assignments: Assignments,
    now: datetime | None = None,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> Dashboard:
    calculated_at = now or datetime.now(timezone)
    prioritized = sort_by_priority(assignments, calculated_at, timezone)
    items = [
        PrioritizedAssignment(assignment=assignment, priority=priority)
        for assignment, priority in prioritized
    ]

    overdue_work = [item for item in items if "overdue" in item.priority.categories]
    upcoming_assignments = [item for item in items if "upcoming" in item.priority.categories]
    backlog_assignments = [item for item in items if "backlog" in item.priority.categories]
    unscheduled_assignments = [item for item in items if "unscheduled" in item.priority.categories]

    return Dashboard(
        to_do=items[:5],
        upcoming_assignments=upcoming_assignments,
        overdue_assignments=overdue_work,
        unscheduled_assignments=unscheduled_assignments,
        backlog_assignments=backlog_assignments,
    )
