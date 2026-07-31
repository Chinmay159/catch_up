from datetime import date, time

import pytest
from pydantic import ValidationError

from backend.app.database import (
    get_assignment_estimate,
    initialize_database,
    list_assignment_estimates,
    upsert_assignment_estimate,
)
from backend.app.google_classroom import parse_assignments
from backend.app.models import ClassInfo, ClassList, EstimateUpdate
from backend.app.priority import calculate_priority


class FakeClassroom:
    def __init__(self, coursework_by_course: dict[str, list[dict]]):
        self.coursework_by_course = coursework_by_course
        self.current_course_id = ""
        self.mode = ""

    def courses(self):
        return self

    def courseWork(self):
        self.mode = "coursework"
        return self

    def studentSubmissions(self):
        self.mode = "submissions"
        return self

    def list(self, **kwargs):
        self.current_course_id = kwargs.get("courseId", "")
        return self

    def execute(self):
        if self.mode == "submissions":
            return {"studentSubmissions": [{"state": "NEW"}]}
        if self.current_course_id:
            return {"courseWork": self.coursework_by_course.get(self.current_course_id, [])}
        return {}


def temp_db(tmp_path):
    path = tmp_path / "catchup.sqlite3"
    initialize_database(path)
    return path


def coursework(
    title: str = "Original title",
    *,
    assignment_id: str = "assignment-1",
    due_year: int = 2026,
    due_month: int = 7,
    due_day: int = 30,
) -> dict:
    return {
        "id": assignment_id,
        "title": title,
        "state": "PUBLISHED",
        "dueDate": {"year": due_year, "month": due_month, "day": due_day},
        "dueTime": {"hours": 23, "minutes": 59},
    }


def classes() -> ClassList:
    return ClassList(classes=[ClassInfo(name="Math", course_id="course-1")])


def test_creating_student_estimate(tmp_path):
    path = temp_db(tmp_path)

    record = upsert_assignment_estimate("user-1", "course-1", "assignment-1", 45, path)

    assert record.user_id == "user-1"
    assert record.google_course_id == "course-1"
    assert record.google_assignment_id == "assignment-1"
    assert record.estimated_minutes == 45
    assert record.estimate_source == "student"


def test_updating_existing_estimate_does_not_create_duplicate(tmp_path):
    path = temp_db(tmp_path)
    upsert_assignment_estimate("user-1", "course-1", "assignment-1", 45, path)
    record = upsert_assignment_estimate("user-1", "course-1", "assignment-1", 90, path)

    estimates = list_assignment_estimates("user-1", path)

    assert record.estimated_minutes == 90
    assert len(estimates) == 1


def test_reading_estimate_after_new_database_session(tmp_path):
    path = temp_db(tmp_path)
    upsert_assignment_estimate("user-1", "course-1", "assignment-1", 45, path)

    record = get_assignment_estimate("user-1", "course-1", "assignment-1", path)

    assert record is not None
    assert record.estimated_minutes == 45


def test_different_users_estimates_are_separate(tmp_path):
    path = temp_db(tmp_path)
    upsert_assignment_estimate("user-1", "course-1", "assignment-1", 45, path)
    upsert_assignment_estimate("user-2", "course-1", "assignment-1", 75, path)

    assert get_assignment_estimate("user-1", "course-1", "assignment-1", path).estimated_minutes == 45
    assert get_assignment_estimate("user-2", "course-1", "assignment-1", path).estimated_minutes == 75


def test_different_assignment_estimates_are_separate(tmp_path):
    path = temp_db(tmp_path)
    upsert_assignment_estimate("user-1", "course-1", "assignment-1", 45, path)
    upsert_assignment_estimate("user-1", "course-1", "assignment-2", 75, path)

    assert get_assignment_estimate("user-1", "course-1", "assignment-1", path).estimated_minutes == 45
    assert get_assignment_estimate("user-1", "course-1", "assignment-2", path).estimated_minutes == 75


def test_estimate_survives_assignment_title_change(tmp_path):
    path = temp_db(tmp_path)
    upsert_assignment_estimate("user-1", "course-1", "assignment-1", 45, path)
    estimates = list_assignment_estimates("user-1", path)

    assignments = parse_assignments(
        FakeClassroom({"course-1": [coursework(title="Renamed title")]}),
        classes(),
        estimates,
    )

    assert assignments.assignments[0].title == "Renamed title"
    assert assignments.assignments[0].estimated_minutes == 45
    assert assignments.assignments[0].estimated_minutes_source == "student"


def test_estimate_survives_assignment_due_date_change(tmp_path):
    path = temp_db(tmp_path)
    upsert_assignment_estimate("user-1", "course-1", "assignment-1", 45, path)
    estimates = list_assignment_estimates("user-1", path)

    assignments = parse_assignments(
        FakeClassroom({"course-1": [coursework(due_day=31)]}),
        classes(),
        estimates,
    )

    assert assignments.assignments[0].due_date == date(2026, 7, 31)
    assert assignments.assignments[0].estimated_minutes == 45


def test_missing_estimate_returns_null_and_unknown():
    assignments = parse_assignments(
        FakeClassroom({"course-1": [coursework()]}),
        classes(),
        {},
    )

    assert assignments.assignments[0].estimated_minutes is None
    assert assignments.assignments[0].estimated_minutes_source == "unknown"


def test_invalid_estimates_are_rejected():
    with pytest.raises(ValidationError):
        EstimateUpdate(estimated_minutes=0, google_course_id="course-1")


def test_priority_recalculates_after_estimate_update(tmp_path):
    path = temp_db(tmp_path)
    classroom = FakeClassroom({"course-1": [coursework()]})
    without_estimate = parse_assignments(classroom, classes(), {})
    first_priority = calculate_priority(without_estimate.assignments[0])

    upsert_assignment_estimate("user-1", "course-1", "assignment-1", 140, path)
    with_estimate = parse_assignments(
        FakeClassroom({"course-1": [coursework()]}),
        classes(),
        list_assignment_estimates("user-1", path),
    )
    updated_priority = calculate_priority(with_estimate.assignments[0])

    assert with_estimate.assignments[0].estimated_minutes == 140
    assert updated_priority.score > first_priority.score
    assert "This assignment still needs at least two hours of work." in updated_priority.reasons
