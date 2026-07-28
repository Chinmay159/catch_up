from datetime import date

from fastapi import FastAPI

from .google_auth import get_google_credentials
from .google_calendar import build_calendar_service, get_calendar_events, parse_calendar_events
from .google_classroom import build_classroom_service, parse_assignments, parse_courses
from .priority import build_dashboard, sort_by_priority
from .scheduler import find_free_time_blocks, make_study_window, propose_study_plan


app = FastAPI(title="CatchUp Backend")


@app.get("/")
def health_check():
    return {"status": "ok", "app": "CatchUp"}


@app.get("/courses")
def read_courses():
    credentials = get_google_credentials()
    classroom = build_classroom_service(credentials)
    return parse_courses(classroom)


@app.get("/dashboard")
def read_dashboard():
    credentials = get_google_credentials()
    classroom = build_classroom_service(credentials)
    classes = parse_courses(classroom)
    assignments = parse_assignments(classroom, classes)
    return build_dashboard(assignments)


@app.get("/study-plan")
def read_study_plan(
    day: date,
    start_hour: int = 7,
    end_hour: int = 22,
    days_ahead: int = 7,
):
    credentials = get_google_credentials()
    classroom = build_classroom_service(credentials)
    calendar_service = build_calendar_service(credentials)

    classes = parse_courses(classroom)
    assignments = parse_assignments(classroom, classes)
    prioritized_assignments = sort_by_priority(assignments)

    raw_events = get_calendar_events(calendar_service, days_ahead=days_ahead)
    calendar_events = parse_calendar_events(raw_events)

    window_start, window_end = make_study_window(day, start_hour, end_hour)
    free_blocks = find_free_time_blocks(calendar_events, window_start, window_end)

    return propose_study_plan(prioritized_assignments, free_blocks)
