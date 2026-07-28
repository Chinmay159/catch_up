from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import DEFAULT_TIMEZONE
from .models import (
    AssignmentInfo,
    CalendarEvent,
    PriorityLevel,
    SchedulingFailure,
    StudyEvent,
    StudyPlan,
    TimeBlock,
)


def find_free_time_blocks(
    events: list[CalendarEvent],
    window_start: datetime,
    window_end: datetime,
) -> list[TimeBlock]:
    busy_blocks = [
        TimeBlock(start_time=event.start_time, end_time=event.end_time)
        for event in events
        if event.end_time > window_start and event.start_time < window_end
    ]
    busy_blocks = sorted(busy_blocks, key=lambda block: block.start_time)

    free_blocks = []
    cursor = window_start

    for block in busy_blocks:
        busy_start = max(block.start_time, window_start)
        busy_end = min(block.end_time, window_end)

        if busy_start > cursor:
            free_blocks.append(TimeBlock(start_time=cursor, end_time=busy_start))

        if busy_end > cursor:
            cursor = busy_end

    if cursor < window_end:
        free_blocks.append(TimeBlock(start_time=cursor, end_time=window_end))

    return free_blocks


def make_study_window(
    day: date,
    start_hour: int,
    end_hour: int,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> tuple[datetime, datetime]:
    return (
        datetime.combine(day, time(start_hour, 0), tzinfo=timezone),
        datetime.combine(day, time(end_hour, 0), tzinfo=timezone),
    )


def assignment_deadline(
    assignment: AssignmentInfo,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> datetime | None:
    if assignment.due_date is None:
        return None

    due_time = assignment.due_time or time(23, 59)
    return datetime.combine(assignment.due_date, due_time, tzinfo=timezone)


def scheduling_window_start(
    assignment: AssignmentInfo,
    now: datetime | None = None,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> datetime:
    now = now or datetime.now(timezone)
    deadline = assignment_deadline(assignment, timezone)

    if deadline is None:
        return now + timedelta(days=7)

    if deadline <= now:
        return now

    days_until_due = (deadline.date() - now.date()).days

    if days_until_due <= 2:
        return now
    if days_until_due <= 7:
        return max(now, deadline - timedelta(days=3))
    return max(now, deadline - timedelta(days=7))


def valid_blocks_for_assignment(
    assignment: AssignmentInfo,
    free_blocks: list[TimeBlock],
    now: datetime | None = None,
    timezone: ZoneInfo = DEFAULT_TIMEZONE,
) -> list[TimeBlock]:
    now = now or datetime.now(timezone)
    window_start = scheduling_window_start(assignment, now, timezone)
    deadline = assignment_deadline(assignment, timezone)
    valid_blocks = []

    for block in free_blocks:
        block_start = max(block.start_time, window_start)
        block_end = block.end_time

        if deadline is not None and deadline > now:
            block_end = min(block_end, deadline)

        if block_start < block_end:
            valid_blocks.append(TimeBlock(start_time=block_start, end_time=block_end))

    return sorted(valid_blocks, key=lambda block: block.start_time)


def propose_study_event(
    assignment: AssignmentInfo,
    free_blocks: list[TimeBlock],
    user_id: str = "me",
) -> StudyEvent | None:
    if assignment.estimated_minutes is None:
        raise ValueError("Assignment needs estimated minutes before scheduling")

    needed = timedelta(minutes=assignment.estimated_minutes)

    for block in valid_blocks_for_assignment(assignment, free_blocks):
        available = block.end_time - block.start_time

        if available >= needed:
            return StudyEvent(
                title=f"Study: {assignment.title}",
                user_id=user_id,
                assignment_id=assignment.assignment_id,
                start_time=block.start_time,
                end_time=block.start_time + needed,
                description=assignment.description,
                status="draft",
                google_calendar_event_id=None,
            )
    return None


def consume_time_block(
    free_blocks: list[TimeBlock],
    used_block: TimeBlock,
) -> list[TimeBlock]:
    remaining = []

    for block in free_blocks:
        if used_block.end_time <= block.start_time or used_block.start_time >= block.end_time:
            remaining.append(block)
            continue

        if used_block.start_time > block.start_time:
            remaining.append(TimeBlock(start_time=block.start_time, end_time=used_block.start_time))

        if used_block.end_time < block.end_time:
            remaining.append(TimeBlock(start_time=used_block.end_time, end_time=block.end_time))

    return remaining


def propose_study_sessions_for_assignment(
    assignment: AssignmentInfo,
    free_blocks: list[TimeBlock],
    user_id: str = "me",
    max_session_minutes: int = 60,
    min_session_minutes: int = 15,
) -> tuple[list[StudyEvent], list[TimeBlock], SchedulingFailure | None]:
    if assignment.estimated_minutes is None:
        return (
            [],
            free_blocks,
            SchedulingFailure(
                assignment_id=assignment.assignment_id,
                title=assignment.title,
                reason="Assignment needs estimated minutes before scheduling",
            ),
        )

    remaining_minutes = assignment.estimated_minutes
    study_events = []
    remaining_blocks = sorted(free_blocks.copy(), key=lambda block: block.start_time)

    while remaining_minutes > 0:
        valid_blocks = valid_blocks_for_assignment(assignment, remaining_blocks)

        if not valid_blocks:
            return (
                study_events,
                remaining_blocks,
                SchedulingFailure(
                    assignment_id=assignment.assignment_id,
                    title=assignment.title,
                    reason=f"Could not fit {remaining_minutes} remaining minutes before the deadline",
                ),
            )

        block = valid_blocks[0]
        available_minutes = int((block.end_time - block.start_time).total_seconds() // 60)
        session_minutes = min(remaining_minutes, max_session_minutes, available_minutes)

        if session_minutes < min_session_minutes and session_minutes < remaining_minutes:
            return (
                study_events,
                remaining_blocks,
                SchedulingFailure(
                    assignment_id=assignment.assignment_id,
                    title=assignment.title,
                    reason=f"Only found a {session_minutes}-minute block, which is shorter than the minimum session length",
                ),
            )

        session = StudyEvent(
            title=f"Study: {assignment.title}",
            user_id=user_id,
            assignment_id=assignment.assignment_id,
            start_time=block.start_time,
            end_time=block.start_time + timedelta(minutes=session_minutes),
            description=assignment.description,
            status="draft",
            google_calendar_event_id=None,
        )

        study_events.append(session)
        remaining_minutes -= session_minutes
        remaining_blocks = consume_time_block(
            free_blocks=remaining_blocks,
            used_block=TimeBlock(start_time=session.start_time, end_time=session.end_time),
        )

    return study_events, remaining_blocks, None


def propose_study_plan(
    prioritized_assignments: list[tuple[AssignmentInfo, PriorityLevel]],
    free_blocks: list[TimeBlock],
    user_id: str = "me",
    max_session_minutes: int = 60,
    min_session_minutes: int = 15,
) -> StudyPlan:
    study_events = []
    failures = []
    remaining_blocks = sorted(free_blocks.copy(), key=lambda block: block.start_time)

    dated_assignments = [
        item for item in prioritized_assignments
        if item[0].due_date is not None
    ]
    undated_assignments = [
        item for item in prioritized_assignments
        if item[0].due_date is None
    ]
    ordered_assignments = dated_assignments + undated_assignments

    for assignment, priority in ordered_assignments:
        sessions, remaining_blocks, failure = propose_study_sessions_for_assignment(
            assignment=assignment,
            free_blocks=remaining_blocks,
            user_id=user_id,
            max_session_minutes=max_session_minutes,
            min_session_minutes=min_session_minutes,
        )

        study_events.extend(sessions)
        if failure is not None:
            failures.append(failure)

    return StudyPlan(study_events=study_events, failures=failures)
