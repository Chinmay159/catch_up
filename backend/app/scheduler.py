from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import DEFAULT_TIMEZONE
from .models import (
    AssignmentInfo,
    CalendarEvent,
    DraftStudySession,
    FreeWindow,
    PriorityLevel,
    SchedulingPlanPreview,
    SchedulingPreviewFailure,
    SchedulingFailure,
    StudyPreferences,
    StudyEvent,
    StudyPlan,
    TimeBlock,
)
from .priority import assignment_due_at, remaining_minutes


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


def _minutes(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 60))


def _daily_limit(preferences: StudyPreferences, weekday: int) -> int:
    for window in preferences.daily_windows:
        if window.weekday == weekday and window.maximum_daily_study_minutes:
            return window.maximum_daily_study_minutes
    return preferences.maximum_daily_study_minutes


def _failure(
    assignment: AssignmentInfo,
    code,
    requested: int | None,
    scheduled: int,
    message: str,
    actions: list[str],
) -> SchedulingPreviewFailure:
    return SchedulingPreviewFailure(
        assignment_id=assignment.assignment_id,
        title=assignment.title,
        code=code,
        message=message,
        requested_minutes=requested,
        scheduled_minutes=scheduled,
        unscheduled_minutes=None if requested is None else max(requested - scheduled, 0),
        suggested_actions=actions,
    )


def _session_id(assignment_id: str, sequence: int, start: datetime) -> str:
    return f"draft-{assignment_id}-{sequence}-{start.strftime('%Y%m%dT%H%M')}"


def _clip_deadline(window: FreeWindow, deadline: datetime | None, now: datetime) -> tuple[datetime, datetime] | None:
    start = max(window.start_at, now)
    end = window.end_at
    if deadline and deadline > now:
        end = min(end, deadline)
    if start >= end:
        return None
    return start, end


def _balanced_chunk(remaining: int, available: int, preferences: StudyPreferences) -> int:
    maximum = min(preferences.maximum_session_minutes, available, remaining)
    minimum = preferences.minimum_session_minutes
    if remaining <= maximum:
        return remaining
    if remaining <= available:
        sessions_left = max(2, -(-remaining // preferences.maximum_session_minutes))
        balanced = -(-remaining // sessions_left)
        return max(minimum, min(maximum, balanced))
    return maximum


def _subtract_session_from_windows(
    windows: list[FreeWindow],
    session: DraftStudySession,
    break_minutes: int,
) -> list[FreeWindow]:
    remaining: list[FreeWindow] = []
    blocked_end = session.end_at + timedelta(minutes=break_minutes)
    for window in windows:
        if blocked_end <= window.start_at or session.start_at >= window.end_at:
            remaining.append(window)
            continue
        if session.start_at > window.start_at:
            remaining.append(FreeWindow(
                id=f"{window.id}-before-{session.id}",
                start_at=window.start_at,
                end_at=session.start_at,
                duration_minutes=_minutes(window.start_at, session.start_at),
            ))
        if blocked_end < window.end_at:
            remaining.append(FreeWindow(
                id=f"{window.id}-after-{session.id}",
                start_at=blocked_end,
                end_at=window.end_at,
                duration_minutes=_minutes(blocked_end, window.end_at),
            ))
    return [window for window in remaining if window.duration_minutes > 0]


def _subtract_existing_sessions(
    windows: list[FreeWindow],
    existing_sessions: list[DraftStudySession],
    break_minutes: int,
) -> list[FreeWindow]:
    remaining = sorted([window.model_copy(deep=True) for window in windows], key=lambda item: item.start_at)
    for session in sorted(existing_sessions, key=lambda item: item.start_at):
        remaining = _subtract_session_from_windows(remaining, session, break_minutes)
    return sorted(remaining, key=lambda item: item.start_at)


def build_scheduling_preview(
    prioritized_assignments: list[tuple[AssignmentInfo, PriorityLevel]],
    free_windows: list[FreeWindow],
    preferences: StudyPreferences,
    now: datetime | None = None,
    include_backlog: bool = True,
    assignment_ids: set[str] | None = None,
    existing_sessions: list[DraftStudySession] | None = None,
) -> SchedulingPlanPreview:
    now = now or datetime.now(ZoneInfo(preferences.timezone))
    existing_sessions = existing_sessions or []
    windows = _subtract_existing_sessions(free_windows, existing_sessions, preferences.break_minutes)
    sessions: list[DraftStudySession] = []
    failures: list[SchedulingPreviewFailure] = []
    daily_used: dict[date, int] = {}
    for session in existing_sessions:
        day = session.start_at.date()
        daily_used[day] = daily_used.get(day, 0) + session.duration_minutes
    requested_by_assignment: dict[str, int] = {}
    scheduled_by_assignment: dict[str, int] = {}

    ordered = [
        (assignment, priority)
        for assignment, priority in prioritized_assignments
        if assignment_ids is None or assignment.assignment_id in assignment_ids
    ]
    if assignment_ids is None:
        if not include_backlog:
            ordered = [(a, p) for a, p in ordered if a.due_date is not None]
        else:
            dated = [(a, p) for a, p in ordered if a.due_date is not None]
            backlog = [(a, p) for a, p in ordered if a.due_date is None]
            ordered = dated + backlog

    for assignment, priority in ordered:
        remaining = remaining_minutes(assignment)
        if not assignment.is_active or (assignment.submission_state or "").upper() == "TURNED_IN":
            continue
        if remaining is None:
            failures.append(_failure(
                assignment,
                "missing_estimate",
                None,
                0,
                "Add a time estimate before CatchUp schedules this assignment.",
                ["Add a time estimate for this assignment."],
            ))
            continue
        if remaining <= 0:
            continue
        if not preferences.allow_assignment_splitting and remaining > preferences.maximum_session_minutes:
            failures.append(_failure(
                assignment,
                "splitting_disabled",
                remaining,
                0,
                f"This assignment requires {remaining} minutes, but your maximum session length is {preferences.maximum_session_minutes} minutes and splitting is disabled.",
                ["Allow assignment splitting.", "Increase the maximum session length.", "Reduce the estimate."],
            ))
            requested_by_assignment[assignment.assignment_id] = remaining
            scheduled_by_assignment[assignment.assignment_id] = 0
            continue

        requested_by_assignment[assignment.assignment_id] = remaining
        scheduled = 0
        sequence = 1
        deadline = assignment_due_at(assignment, ZoneInfo(preferences.timezone))
        is_overdue = bool(deadline and deadline < now)
        no_free_candidate = True
        daily_limit_blocked = False
        too_short = False

        for window in windows:
            if remaining <= 0:
                break
            clipped = _clip_deadline(window, deadline, now)
            if clipped is None:
                continue
            cursor, window_end = clipped
            no_free_candidate = False

            while remaining > 0 and cursor < window_end:
                day = cursor.date()
                limit = _daily_limit(preferences, cursor.weekday())
                used = daily_used.get(day, 0)
                if used >= limit:
                    daily_limit_blocked = True
                    break
                available = min(_minutes(cursor, window_end), limit - used)
                if available < preferences.minimum_session_minutes:
                    too_short = True
                    break

                chunk = _balanced_chunk(remaining, available, preferences)
                if chunk < preferences.minimum_session_minutes:
                    too_short = True
                    break

                start = cursor
                end = start + timedelta(minutes=chunk)
                reasons = ["Scheduled here because this is the earliest free window before the deadline."]
                if is_overdue:
                    reasons = ["This assignment is overdue, so CatchUp placed it in your next available window."]
                if requested_by_assignment[assignment.assignment_id] > preferences.maximum_session_minutes:
                    reasons.append(f"Split because it exceeds your {preferences.maximum_session_minutes}-minute maximum session length.")
                if used + chunk >= limit and remaining > chunk:
                    daily_limit_blocked = True
                    reasons.append("Stopped adding more today because your daily study limit was reached.")

                sessions.append(DraftStudySession(
                    id=_session_id(assignment.assignment_id, sequence, start),
                    assignment_id=assignment.assignment_id,
                    course_id=assignment.course_id,
                    assignment_title=assignment.title,
                    start_at=start,
                    end_at=end,
                    duration_minutes=chunk,
                    sequence_number=sequence,
                    total_assignment_sessions=1,
                    placement_reasons=reasons,
                ))
                sequence += 1
                scheduled += chunk
                remaining -= chunk
                daily_used[day] = used + chunk
                cursor = end + timedelta(minutes=preferences.break_minutes)
                window.start_at = cursor

        scheduled_by_assignment[assignment.assignment_id] = scheduled
        if remaining > 0:
            if daily_limit_blocked and not no_free_candidate:
                code = "daily_limit_reached"
                message = "Free time remains, but your daily study limit has been reached."
                actions = ["Increase the daily study limit.", "Spread work across more days."]
            elif no_free_candidate:
                code = "no_free_time"
                message = "No usable study windows were found during the selected planning period."
                actions = ["Expand study hours.", "Choose a wider planning range."]
            elif too_short and scheduled == 0:
                code = "session_too_short"
                message = f"The remaining free windows are shorter than your {preferences.minimum_session_minutes}-minute minimum session length."
                actions = ["Lower the minimum session length.", "Expand study windows."]
            else:
                code = "insufficient_time_before_deadline"
                message = f"This assignment needs {requested_by_assignment[assignment.assignment_id]} minutes, but only {scheduled} minutes are available before its deadline."
                actions = ["Expand study hours.", "Increase the daily study limit.", "Leave remaining work unscheduled."]
            failures.append(_failure(assignment, code, requested_by_assignment[assignment.assignment_id], scheduled, message, actions))

    counts: dict[str, int] = {}
    for session in sessions:
        counts[session.assignment_id] = counts.get(session.assignment_id, 0) + 1
    sessions = [session.model_copy(update={"total_assignment_sessions": counts[session.assignment_id]}) for session in sessions]

    fully = [assignment_id for assignment_id, requested in requested_by_assignment.items() if scheduled_by_assignment.get(assignment_id, 0) >= requested]
    partial = [assignment_id for assignment_id, scheduled in scheduled_by_assignment.items() if 0 < scheduled < requested_by_assignment.get(assignment_id, 0)]
    unscheduled = [assignment_id for assignment_id, requested in requested_by_assignment.items() if scheduled_by_assignment.get(assignment_id, 0) == 0 and requested > 0]
    total_requested = sum(requested_by_assignment.values())
    total_scheduled = sum(session.duration_minutes for session in sessions)

    return SchedulingPlanPreview(
        draft_sessions=sorted(sessions, key=lambda item: (item.start_at, item.assignment_id, item.sequence_number)),
        fully_scheduled_assignment_ids=fully,
        partially_scheduled_assignment_ids=partial,
        unscheduled_assignment_ids=unscheduled,
        failures=failures,
        total_requested_minutes=total_requested,
        total_scheduled_minutes=total_scheduled,
        total_unscheduled_minutes=max(total_requested - total_scheduled, 0),
        calculated_at=now,
    )
