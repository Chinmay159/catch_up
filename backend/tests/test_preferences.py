from datetime import date, time

import pytest
from pydantic import ValidationError

from backend.app.availability import calculate_availability
from backend.app.database import (
    get_study_preferences,
    initialize_database,
    replace_study_preferences,
    reset_study_preferences,
)
from backend.app.models import DailyStudyWindow, StudyAvailabilityRequest
from backend.app.preferences import PreferencesValidationError, default_study_preferences


def temp_db(tmp_path):
    path = tmp_path / "catchup.sqlite3"
    initialize_database(path)
    return path


def preference(user_id="user-1"):
    return default_study_preferences(user_id).model_copy(deep=True)


def replace_window(preferences, weekday: int, **changes):
    preferences.daily_windows = [
        window.model_copy(update=changes) if window.weekday == weekday else window
        for window in preferences.daily_windows
    ]
    return preferences


def test_default_preferences_are_returned_for_new_user(tmp_path):
    preferences, source = get_study_preferences("new-user", temp_db(tmp_path))

    assert source == "default"
    assert preferences.user_id == "new-user"
    assert preferences.timezone == "America/Chicago"
    assert preferences.minimum_session_minutes == 20
    assert preferences.maximum_session_minutes == 60
    assert preferences.break_minutes == 10
    assert preferences.allow_assignment_splitting is True


def test_all_seven_weekdays_resolve_correctly(tmp_path):
    preferences, _ = get_study_preferences("new-user", temp_db(tmp_path))

    assert [window.weekday for window in preferences.daily_windows] == [0, 1, 2, 3, 4, 5, 6]
    assert preferences.daily_windows[0].start_time == time(16, 0)
    assert preferences.daily_windows[5].start_time == time(10, 0)


def test_saving_preferences_persists_and_survives_new_connection(tmp_path):
    path = temp_db(tmp_path)
    saved = preference().model_copy(update={
        "timezone": "America/New_York",
        "maximum_session_minutes": 45,
        "break_minutes": 15,
        "allow_assignment_splitting": False,
    })
    replace_window(saved, 0, start_time=time(17, 0), end_time=time(21, 0), maximum_daily_study_minutes=120)

    replace_study_preferences("user-1", saved, path)
    loaded, source = get_study_preferences("user-1", path)

    assert source == "saved"
    assert loaded.timezone == "America/New_York"
    assert loaded.maximum_session_minutes == 45
    assert loaded.break_minutes == 15
    assert loaded.allow_assignment_splitting is False
    assert loaded.daily_windows[0].start_time == time(17, 0)
    assert loaded.daily_windows[0].maximum_daily_study_minutes == 120


def test_different_users_preferences_are_isolated(tmp_path):
    path = temp_db(tmp_path)
    user_one = preference("user-1").model_copy(update={"timezone": "America/New_York"})
    user_two = preference("user-2").model_copy(update={"timezone": "America/Los_Angeles"})

    replace_study_preferences("user-1", user_one, path)
    replace_study_preferences("user-2", user_two, path)

    assert get_study_preferences("user-1", path)[0].timezone == "America/New_York"
    assert get_study_preferences("user-2", path)[0].timezone == "America/Los_Angeles"


def test_updating_preferences_replaces_values(tmp_path):
    path = temp_db(tmp_path)
    replace_study_preferences("user-1", preference(), path)
    updated = preference().model_copy(update={"minimum_session_minutes": 30, "maximum_session_minutes": 90})
    replace_window(updated, 0, end_time=time(23, 0))

    loaded = replace_study_preferences("user-1", updated, path)

    assert loaded.minimum_session_minutes == 30
    assert loaded.maximum_session_minutes == 90


def test_reset_restores_defaults(tmp_path):
    path = temp_db(tmp_path)
    replace_study_preferences("user-1", preference().model_copy(update={"timezone": "America/New_York"}), path)

    reset = reset_study_preferences("user-1", path)
    loaded, source = get_study_preferences("user-1", path)

    assert source == "default"
    assert reset.timezone == "America/Chicago"
    assert loaded.timezone == "America/Chicago"


def test_invalid_timezone_is_rejected(tmp_path):
    with pytest.raises(PreferencesValidationError) as error:
        replace_study_preferences("user-1", preference().model_copy(update={"timezone": "Mars/Base"}), temp_db(tmp_path))

    assert error.value.code == "INVALID_TIMEZONE"
    assert error.value.field == "timezone"


def test_start_time_after_end_time_and_overnight_are_rejected(tmp_path):
    invalid = replace_window(preference(), 0, start_time=time(22, 0), end_time=time(4, 0))

    with pytest.raises(PreferencesValidationError) as error:
        replace_study_preferences("user-1", invalid, temp_db(tmp_path))

    assert error.value.code == "INVALID_STUDY_WINDOW"


def test_minimum_greater_than_maximum_is_rejected(tmp_path):
    invalid = preference().model_copy(update={"minimum_session_minutes": 90, "maximum_session_minutes": 60})

    with pytest.raises(PreferencesValidationError) as error:
        replace_study_preferences("user-1", invalid, temp_db(tmp_path))

    assert error.value.code == "INVALID_SESSION_DURATION"


def test_negative_break_duration_is_rejected(tmp_path):
    invalid = preference().model_copy(update={"break_minutes": -1})

    with pytest.raises(PreferencesValidationError) as error:
        replace_study_preferences("user-1", invalid, temp_db(tmp_path))

    assert error.value.code == "INVALID_BREAK_DURATION"


def test_invalid_weekday_is_rejected():
    with pytest.raises(ValidationError):
        DailyStudyWindow(weekday=7, enabled=True, start_time=time(16, 0), end_time=time(17, 0), maximum_daily_study_minutes=60)


def test_disabled_days_produce_no_permitted_study_window():
    preferences = replace_window(preference(), 2, enabled=False)

    response = calculate_availability(
        StudyAvailabilityRequest(start_date=date(2026, 7, 29), end_date=date(2026, 7, 29)),
        commitments=[],
        preferences=preferences,
    )

    assert response.free_windows == []
    assert response.total_study_window_minutes == 0


def test_calendar_availability_uses_persisted_windows_and_timezone(tmp_path, monkeypatch):
    path = temp_db(tmp_path)
    monkeypatch.setenv("CATCHUP_DATABASE_PATH", str(path))
    saved = replace_window(
        preference(),
        2,
        start_time=time(18, 0),
        end_time=time(20, 0),
        maximum_daily_study_minutes=90,
    ).model_copy(update={"timezone": "America/New_York", "minimum_session_minutes": 30})
    replace_study_preferences("user-1", saved, path)

    response = calculate_availability(
        StudyAvailabilityRequest(start_date=date(2026, 7, 29), end_date=date(2026, 7, 29)),
        commitments=[],
        user_id="user-1",
    )

    assert response.timezone == "America/New_York"
    assert response.total_free_minutes == 120
    assert response.free_windows[0].start_at.hour == 18


def test_explicit_one_time_constraints_override_saved_preferences(tmp_path, monkeypatch):
    path = temp_db(tmp_path)
    monkeypatch.setenv("CATCHUP_DATABASE_PATH", str(path))
    saved = replace_window(preference(), 2, start_time=time(18, 0), end_time=time(20, 0))
    replace_study_preferences("user-1", saved, path)

    response = calculate_availability(
        StudyAvailabilityRequest(
            start_date=date(2026, 7, 29),
            end_date=date(2026, 7, 29),
            timezone="America/Chicago",
            daily_windows=[
                DailyStudyWindow(weekday=2, enabled=True, start_time=time(16, 0), end_time=time(17, 0), maximum_daily_study_minutes=60)
            ],
            minimum_window_minutes=15,
        ),
        commitments=[],
        user_id="user-1",
    )

    assert response.timezone == "America/Chicago"
    assert response.total_free_minutes == 60


def test_saved_preferences_override_defaults(tmp_path, monkeypatch):
    path = temp_db(tmp_path)
    monkeypatch.setenv("CATCHUP_DATABASE_PATH", str(path))
    saved = preference()
    replace_window(saved, 2, enabled=False)
    replace_study_preferences("user-1", saved, path)

    response = calculate_availability(
        StudyAvailabilityRequest(start_date=date(2026, 7, 29), end_date=date(2026, 7, 29)),
        commitments=[],
        user_id="user-1",
    )

    assert response.free_windows == []
    assert response.total_study_window_minutes == 0


def test_maximum_daily_study_minutes_is_returned_for_scheduler_contract(tmp_path):
    preferences, _ = get_study_preferences("new-user", temp_db(tmp_path))

    assert preferences.maximum_daily_study_minutes == 180
    assert preferences.daily_windows[5].maximum_daily_study_minutes == 300
