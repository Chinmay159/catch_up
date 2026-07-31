import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import DATABASE_PATH
from .models import Assignments, CalendarEvent, ClassList, DailyStudyWindow, DraftStudySession, StudyPreferences
from .preferences import default_study_preferences, preferences_with_metadata, validate_study_preferences


class DatabaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class AssignmentEstimateRecord:
    user_id: str
    google_course_id: str
    google_assignment_id: str
    estimated_minutes: int
    estimate_source: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ClassroomSnapshot:
    user_id: str
    classes: ClassList
    assignments: Assignments
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class CalendarEventsSnapshot:
    user_id: str
    days_ahead: int
    events: list[CalendarEvent]
    created_at: str
    updated_at: str


def database_path() -> Path:
    return Path(os.environ.get("CATCHUP_DATABASE_PATH", DATABASE_PATH))


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(path: Path | None = None) -> None:
    try:
        with connect(path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assignment_estimates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    google_course_id TEXT NOT NULL,
                    google_assignment_id TEXT NOT NULL,
                    estimated_minutes INTEGER NOT NULL CHECK (estimated_minutes > 0),
                    estimate_source TEXT NOT NULL CHECK (estimate_source = 'student'),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (user_id, google_course_id, google_assignment_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_assignment_estimates_user_assignment
                ON assignment_estimates (user_id, google_assignment_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS study_preferences (
                    user_id TEXT PRIMARY KEY,
                    timezone TEXT NOT NULL,
                    minimum_session_minutes INTEGER NOT NULL,
                    maximum_session_minutes INTEGER NOT NULL,
                    break_minutes INTEGER NOT NULL,
                    maximum_daily_study_minutes INTEGER NOT NULL,
                    allow_assignment_splitting INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS study_daily_windows (
                    user_id TEXT NOT NULL,
                    weekday INTEGER NOT NULL CHECK (weekday >= 0 AND weekday <= 6),
                    enabled INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    maximum_daily_study_minutes INTEGER NOT NULL,
                    PRIMARY KEY (user_id, weekday),
                    FOREIGN KEY (user_id) REFERENCES study_preferences(user_id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS classroom_snapshots (
                    user_id TEXT PRIMARY KEY,
                    classes_json TEXT NOT NULL,
                    assignments_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS calendar_events_snapshots (
                    user_id TEXT NOT NULL,
                    days_ahead INTEGER NOT NULL,
                    events_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, days_ahead)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS draft_study_sessions (
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    session_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, session_id)
                )
                """
            )
            connection.commit()
    except sqlite3.Error as error:
        raise DatabaseError("Could not initialize CatchUp database") from error


def _row_to_record(row: sqlite3.Row) -> AssignmentEstimateRecord:
    return AssignmentEstimateRecord(
        user_id=row["user_id"],
        google_course_id=row["google_course_id"],
        google_assignment_id=row["google_assignment_id"],
        estimated_minutes=row["estimated_minutes"],
        estimate_source=row["estimate_source"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_assignment_estimates(
    user_id: str,
    path: Path | None = None,
) -> dict[tuple[str, str], AssignmentEstimateRecord]:
    try:
        with connect(path) as connection:
            rows = connection.execute(
                """
                SELECT user_id, google_course_id, google_assignment_id, estimated_minutes,
                       estimate_source, created_at, updated_at
                FROM assignment_estimates
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchall()
    except sqlite3.Error as error:
        raise DatabaseError("Could not read assignment estimates") from error

    return {
        (row["google_course_id"], row["google_assignment_id"]): _row_to_record(row)
        for row in rows
    }


def get_assignment_estimate(
    user_id: str,
    google_course_id: str,
    google_assignment_id: str,
    path: Path | None = None,
) -> AssignmentEstimateRecord | None:
    try:
        with connect(path) as connection:
            row = connection.execute(
                """
                SELECT user_id, google_course_id, google_assignment_id, estimated_minutes,
                       estimate_source, created_at, updated_at
                FROM assignment_estimates
                WHERE user_id = ? AND google_course_id = ? AND google_assignment_id = ?
                """,
                (user_id, google_course_id, google_assignment_id),
            ).fetchone()
    except sqlite3.Error as error:
        raise DatabaseError("Could not read assignment estimate") from error

    return _row_to_record(row) if row else None


def upsert_assignment_estimate(
    user_id: str,
    google_course_id: str,
    google_assignment_id: str,
    estimated_minutes: int,
    path: Path | None = None,
) -> AssignmentEstimateRecord:
    now = datetime.now(timezone.utc).isoformat()

    try:
        with connect(path) as connection:
            connection.execute(
                """
                INSERT INTO assignment_estimates (
                    user_id, google_course_id, google_assignment_id,
                    estimated_minutes, estimate_source, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'student', ?, ?)
                ON CONFLICT(user_id, google_course_id, google_assignment_id)
                DO UPDATE SET
                    estimated_minutes = excluded.estimated_minutes,
                    estimate_source = 'student',
                    updated_at = excluded.updated_at
                """,
                (user_id, google_course_id, google_assignment_id, estimated_minutes, now, now),
            )
            connection.commit()
    except sqlite3.Error as error:
        raise DatabaseError("Could not save assignment estimate") from error

    record = get_assignment_estimate(user_id, google_course_id, google_assignment_id, path)
    if record is None:
        raise DatabaseError("Assignment estimate was not saved")
    return record


def get_classroom_snapshot(user_id: str, path: Path | None = None) -> ClassroomSnapshot | None:
    try:
        with connect(path) as connection:
            row = connection.execute(
                """
                SELECT user_id, classes_json, assignments_json, created_at, updated_at
                FROM classroom_snapshots
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
    except sqlite3.Error as error:
        raise DatabaseError("Could not read Classroom cache") from error

    if row is None:
        return None

    return ClassroomSnapshot(
        user_id=row["user_id"],
        classes=ClassList.model_validate_json(row["classes_json"]),
        assignments=Assignments.model_validate_json(row["assignments_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def save_classroom_snapshot(
    user_id: str,
    classes: ClassList,
    assignments: Assignments,
    path: Path | None = None,
) -> ClassroomSnapshot:
    now = datetime.now(timezone.utc).isoformat()
    existing = get_classroom_snapshot(user_id, path)
    created_at = existing.created_at if existing else now

    try:
        with connect(path) as connection:
            connection.execute(
                """
                INSERT INTO classroom_snapshots (
                    user_id, classes_json, assignments_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET
                    classes_json = excluded.classes_json,
                    assignments_json = excluded.assignments_json,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    classes.model_dump_json(),
                    assignments.model_dump_json(),
                    created_at,
                    now,
                ),
            )
            connection.commit()
    except sqlite3.Error as error:
        raise DatabaseError("Could not save Classroom cache") from error

    snapshot = get_classroom_snapshot(user_id, path)
    if snapshot is None:
        raise DatabaseError("Classroom cache was not saved")
    return snapshot


def get_calendar_events_snapshot(
    user_id: str,
    days_ahead: int,
    path: Path | None = None,
) -> CalendarEventsSnapshot | None:
    try:
        with connect(path) as connection:
            row = connection.execute(
                """
                SELECT user_id, days_ahead, events_json, created_at, updated_at
                FROM calendar_events_snapshots
                WHERE user_id = ? AND days_ahead = ?
                """,
                (user_id, days_ahead),
            ).fetchone()
    except sqlite3.Error as error:
        raise DatabaseError("Could not read Calendar cache") from error

    if row is None:
        return None

    return CalendarEventsSnapshot(
        user_id=row["user_id"],
        days_ahead=row["days_ahead"],
        events=[CalendarEvent.model_validate(item) for item in __import__("json").loads(row["events_json"])],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def save_calendar_events_snapshot(
    user_id: str,
    days_ahead: int,
    events: list[CalendarEvent],
    path: Path | None = None,
) -> CalendarEventsSnapshot:
    import json

    now = datetime.now(timezone.utc).isoformat()
    existing = get_calendar_events_snapshot(user_id, days_ahead, path)
    created_at = existing.created_at if existing else now
    try:
        with connect(path) as connection:
            connection.execute(
                """
                INSERT INTO calendar_events_snapshots (
                    user_id, days_ahead, events_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, days_ahead)
                DO UPDATE SET
                    events_json = excluded.events_json,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    days_ahead,
                    json.dumps([event.model_dump(mode="json") for event in events]),
                    created_at,
                    now,
                ),
            )
            connection.commit()
    except sqlite3.Error as error:
        raise DatabaseError("Could not save Calendar cache") from error

    snapshot = get_calendar_events_snapshot(user_id, days_ahead, path)
    if snapshot is None:
        raise DatabaseError("Calendar cache was not saved")
    return snapshot


def list_draft_study_sessions(user_id: str, path: Path | None = None) -> list[DraftStudySession]:
    try:
        with connect(path) as connection:
            rows = connection.execute(
                """
                SELECT session_json
                FROM draft_study_sessions
                WHERE user_id = ?
                ORDER BY json_extract(session_json, '$.start_at'), session_id
                """,
                (user_id,),
            ).fetchall()
    except sqlite3.Error as error:
        raise DatabaseError("Could not read draft study sessions") from error

    return [DraftStudySession.model_validate_json(row["session_json"]) for row in rows]


def replace_draft_study_sessions(
    user_id: str,
    sessions: list[DraftStudySession],
    path: Path | None = None,
) -> list[DraftStudySession]:
    now = datetime.now(timezone.utc).isoformat()
    try:
        with connect(path) as connection:
            connection.execute("DELETE FROM draft_study_sessions WHERE user_id = ?", (user_id,))
            connection.executemany(
                """
                INSERT INTO draft_study_sessions (user_id, session_id, session_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        user_id,
                        session.id,
                        session.model_dump_json(),
                        now,
                        now,
                    )
                    for session in sessions
                ],
            )
            connection.commit()
    except sqlite3.Error as error:
        raise DatabaseError("Could not save draft study sessions") from error

    return list_draft_study_sessions(user_id, path)


def update_study_session_statuses(
    user_id: str,
    session_ids: list[str],
    status: str,
    path: Path | None = None,
) -> tuple[list[DraftStudySession], list[str], list[str]]:
    requested_ids = list(dict.fromkeys(session_ids))
    sessions_by_id = {session.id: session for session in list_draft_study_sessions(user_id, path)}
    approved_ids = [session_id for session_id in requested_ids if session_id in sessions_by_id]
    failed_ids = [session_id for session_id in requested_ids if session_id not in sessions_by_id]
    now = datetime.now(timezone.utc).isoformat()

    try:
        with connect(path) as connection:
            for session_id in approved_ids:
                updated = sessions_by_id[session_id].model_copy(update={"status": status})
                connection.execute(
                    """
                    UPDATE draft_study_sessions
                    SET session_json = ?, updated_at = ?
                    WHERE user_id = ? AND session_id = ?
                    """,
                    (updated.model_dump_json(), now, user_id, session_id),
                )
            connection.commit()
    except sqlite3.Error as error:
        raise DatabaseError("Could not update study session statuses") from error

    return list_draft_study_sessions(user_id, path), approved_ids, failed_ids


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_time(value: str):
    return datetime.strptime(value, "%H:%M").time()


def _preference_from_rows(preference_row: sqlite3.Row, window_rows: list[sqlite3.Row]) -> StudyPreferences:
    return StudyPreferences(
        user_id=preference_row["user_id"],
        timezone=preference_row["timezone"],
        minimum_session_minutes=preference_row["minimum_session_minutes"],
        maximum_session_minutes=preference_row["maximum_session_minutes"],
        break_minutes=preference_row["break_minutes"],
        maximum_daily_study_minutes=preference_row["maximum_daily_study_minutes"],
        allow_assignment_splitting=bool(preference_row["allow_assignment_splitting"]),
        created_at=_parse_datetime(preference_row["created_at"]),
        updated_at=_parse_datetime(preference_row["updated_at"]),
        daily_windows=[
            DailyStudyWindow(
                weekday=row["weekday"],
                enabled=bool(row["enabled"]),
                start_time=_parse_time(row["start_time"]),
                end_time=_parse_time(row["end_time"]),
                maximum_daily_study_minutes=row["maximum_daily_study_minutes"],
            )
            for row in window_rows
        ],
    )


def get_study_preferences(
    user_id: str,
    path: Path | None = None,
) -> tuple[StudyPreferences, str]:
    try:
        with connect(path) as connection:
            preference_row = connection.execute(
                """
                SELECT user_id, timezone, minimum_session_minutes, maximum_session_minutes,
                       break_minutes, maximum_daily_study_minutes, allow_assignment_splitting,
                       created_at, updated_at
                FROM study_preferences
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            if preference_row is None:
                return default_study_preferences(user_id), "default"

            window_rows = connection.execute(
                """
                SELECT weekday, enabled, start_time, end_time, maximum_daily_study_minutes
                FROM study_daily_windows
                WHERE user_id = ?
                ORDER BY weekday
                """,
                (user_id,),
            ).fetchall()
    except sqlite3.Error as error:
        raise DatabaseError("Could not read study preferences") from error

    return validate_study_preferences(_preference_from_rows(preference_row, window_rows)), "saved"


def replace_study_preferences(
    user_id: str,
    preferences: StudyPreferences,
    path: Path | None = None,
) -> StudyPreferences:
    now = datetime.now(timezone.utc)
    existing, source = get_study_preferences(user_id, path)
    created_at = existing.created_at if source == "saved" else now
    resolved = validate_study_preferences(preferences_with_metadata(preferences, user_id, created_at, now))

    try:
        with connect(path) as connection:
            connection.execute(
                """
                INSERT INTO study_preferences (
                    user_id, timezone, minimum_session_minutes, maximum_session_minutes,
                    break_minutes, maximum_daily_study_minutes, allow_assignment_splitting,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id)
                DO UPDATE SET
                    timezone = excluded.timezone,
                    minimum_session_minutes = excluded.minimum_session_minutes,
                    maximum_session_minutes = excluded.maximum_session_minutes,
                    break_minutes = excluded.break_minutes,
                    maximum_daily_study_minutes = excluded.maximum_daily_study_minutes,
                    allow_assignment_splitting = excluded.allow_assignment_splitting,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    resolved.timezone,
                    resolved.minimum_session_minutes,
                    resolved.maximum_session_minutes,
                    resolved.break_minutes,
                    resolved.maximum_daily_study_minutes,
                    int(resolved.allow_assignment_splitting),
                    resolved.created_at.isoformat(),
                    resolved.updated_at.isoformat(),
                ),
            )
            connection.execute("DELETE FROM study_daily_windows WHERE user_id = ?", (user_id,))
            connection.executemany(
                """
                INSERT INTO study_daily_windows (
                    user_id, weekday, enabled, start_time, end_time, maximum_daily_study_minutes
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        user_id,
                        window.weekday,
                        int(window.enabled),
                        window.start_time.strftime("%H:%M"),
                        window.end_time.strftime("%H:%M"),
                        window.maximum_daily_study_minutes,
                    )
                    for window in resolved.daily_windows
                ],
            )
            connection.commit()
    except sqlite3.Error as error:
        raise DatabaseError("Could not save study preferences") from error

    saved, _ = get_study_preferences(user_id, path)
    return saved


def reset_study_preferences(user_id: str, path: Path | None = None) -> StudyPreferences:
    try:
        with connect(path) as connection:
            connection.execute("DELETE FROM study_daily_windows WHERE user_id = ?", (user_id,))
            connection.execute("DELETE FROM study_preferences WHERE user_id = ?", (user_id,))
            connection.commit()
    except sqlite3.Error as error:
        raise DatabaseError("Could not reset study preferences") from error

    return default_study_preferences(user_id)
