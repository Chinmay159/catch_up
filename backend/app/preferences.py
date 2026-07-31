from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import DEFAULT_USER_ID
from .models import DailyStudyWindow, StudyPreferences


WEEKDAY_CONVENTION = "0 = Monday, 1 = Tuesday, 2 = Wednesday, 3 = Thursday, 4 = Friday, 5 = Saturday, 6 = Sunday"
DEFAULT_PREFERENCE_TIMEZONE = "America/Chicago"
MAX_SESSION_UPPER_BOUND_MINUTES = 480
MAX_DAILY_UPPER_BOUND_MINUTES = 720


class PreferencesValidationError(ValueError):
    def __init__(self, code: str, message: str, field: str):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def default_daily_windows() -> list[DailyStudyWindow]:
    return [
        DailyStudyWindow(
            weekday=weekday,
            enabled=True,
            start_time=time(16, 0) if weekday < 5 else time(10, 0),
            end_time=time(22, 0) if weekday < 5 else time(20, 0),
            maximum_daily_study_minutes=180 if weekday < 5 else 300,
        )
        for weekday in range(7)
    ]


def default_study_preferences(user_id: str = DEFAULT_USER_ID) -> StudyPreferences:
    now = utc_now()
    return StudyPreferences(
        user_id=user_id,
        timezone=DEFAULT_PREFERENCE_TIMEZONE,
        daily_windows=default_daily_windows(),
        minimum_session_minutes=20,
        maximum_session_minutes=60,
        break_minutes=10,
        maximum_daily_study_minutes=180,
        allow_assignment_splitting=True,
        created_at=now,
        updated_at=now,
    )


def validate_timezone(name: str) -> None:
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise PreferencesValidationError("INVALID_TIMEZONE", "Choose a valid timezone.", "timezone") from error


def window_minutes(window: DailyStudyWindow) -> int:
    start = window.start_time.hour * 60 + window.start_time.minute
    end = window.end_time.hour * 60 + window.end_time.minute
    return end - start


def validate_study_preferences(preferences: StudyPreferences) -> StudyPreferences:
    validate_timezone(preferences.timezone)

    if preferences.minimum_session_minutes <= 0:
        raise PreferencesValidationError("INVALID_SESSION_DURATION", "Minimum session length must be positive.", "minimum_session_minutes")
    if preferences.maximum_session_minutes < preferences.minimum_session_minutes:
        raise PreferencesValidationError("INVALID_SESSION_DURATION", "Maximum session length must be at least the minimum.", "maximum_session_minutes")
    if preferences.maximum_session_minutes > MAX_SESSION_UPPER_BOUND_MINUTES:
        raise PreferencesValidationError("INVALID_SESSION_DURATION", "Maximum session length is too large.", "maximum_session_minutes")
    if preferences.break_minutes < 0:
        raise PreferencesValidationError("INVALID_BREAK_DURATION", "Break duration cannot be negative.", "break_minutes")
    if preferences.break_minutes > MAX_SESSION_UPPER_BOUND_MINUTES:
        raise PreferencesValidationError("INVALID_BREAK_DURATION", "Break duration is too large.", "break_minutes")
    if preferences.maximum_daily_study_minutes <= 0 or preferences.maximum_daily_study_minutes > MAX_DAILY_UPPER_BOUND_MINUTES:
        raise PreferencesValidationError("INVALID_DAILY_LIMIT", "Maximum daily study time must be realistic.", "maximum_daily_study_minutes")

    seen: set[int] = set()
    for index, window in enumerate(preferences.daily_windows):
        field_prefix = f"daily_windows.{index}"
        if window.weekday in seen:
            raise PreferencesValidationError("STUDY_PREFERENCES_INVALID", "Each weekday can only appear once.", f"{field_prefix}.weekday")
        seen.add(window.weekday)

        if window.end_time <= window.start_time:
            raise PreferencesValidationError("INVALID_STUDY_WINDOW", "Study start time must be earlier than end time.", field_prefix)

        daily_limit = window.maximum_daily_study_minutes
        if daily_limit is None or daily_limit <= 0 or daily_limit > MAX_DAILY_UPPER_BOUND_MINUTES:
            raise PreferencesValidationError("INVALID_DAILY_LIMIT", "Maximum daily study time must be realistic.", f"{field_prefix}.maximum_daily_study_minutes")
        if window.enabled and preferences.maximum_session_minutes > window_minutes(window):
            raise PreferencesValidationError("INVALID_SESSION_DURATION", "Maximum session length cannot exceed an enabled daily study window.", "maximum_session_minutes")

    missing = set(range(7)) - seen
    if missing:
        raise PreferencesValidationError("STUDY_PREFERENCES_INVALID", f"All seven weekdays are required. Missing: {sorted(missing)}.", "daily_windows")

    return preferences


def preferences_with_metadata(
    preferences: StudyPreferences,
    user_id: str,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> StudyPreferences:
    return preferences.model_copy(update={
        "user_id": user_id,
        "created_at": created_at or preferences.created_at or utc_now(),
        "updated_at": updated_at or utc_now(),
    })
