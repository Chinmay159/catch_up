from datetime import date

from fastapi import HTTPException, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .availability import AvailabilityError, calculate_availability
from .config import DEFAULT_TIMEZONE, DEFAULT_USER_ID
from .database import (
    DatabaseError,
    get_calendar_events_snapshot,
    get_classroom_snapshot,
    get_study_preferences,
    initialize_database,
    list_draft_study_sessions,
    list_assignment_estimates,
    replace_study_preferences,
    replace_draft_study_sessions,
    reset_study_preferences,
    save_calendar_events_snapshot,
    save_classroom_snapshot,
    update_study_session_statuses,
    upsert_assignment_estimate,
)
from .google_auth import get_google_credentials, has_google_token
from .google_calendar import build_calendar_service, get_calendar_events, parse_calendar_events
from .google_classroom import build_classroom_service, parse_assignments, parse_courses
from .models import EstimateUpdate, SchedulePreviewRequest, StudyAvailabilityRequest, StudyPreferences, StudyPreferencesResponse, StudySessionApprovalRequest, StudySessionApprovalResult
from .preferences import PreferencesValidationError
from .priority import build_dashboard, recommend_next_assignment, sort_by_priority
from .scheduler import build_scheduling_preview, find_free_time_blocks, make_study_window, propose_study_plan


app = FastAPI(title="CatchUp Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    initialize_database()


def read_estimates_or_unknown(user_id: str = DEFAULT_USER_ID):
    try:
        return list_assignment_estimates(user_id)
    except DatabaseError as error:
        print(f"Estimate lookup failed: {error}")
        return {}


def apply_estimates(assignments, estimates):
    return assignments.model_copy(update={
        "assignments": [
            assignment.model_copy(update={
                "estimated_minutes": estimates[(assignment.course_id, assignment.assignment_id)].estimated_minutes,
                "estimated_minutes_source": "student",
            }) if (assignment.course_id, assignment.assignment_id) in estimates else assignment.model_copy(update={
                "estimated_minutes": None,
                "estimated_minutes_source": "unknown",
            })
            for assignment in assignments.assignments
        ]
    })


def apply_scheduled_session_minutes(assignments, sessions):
    minutes_by_assignment: dict[str, int] = {}
    for session in sessions:
        minutes_by_assignment[session.assignment_id] = minutes_by_assignment.get(session.assignment_id, 0) + session.duration_minutes

    return assignments.model_copy(update={
        "assignments": [
            assignment.model_copy(update={
                "scheduled_minutes": minutes_by_assignment.get(assignment.assignment_id, 0),
            })
            for assignment in assignments.assignments
        ]
    })


def load_assignments_with_estimates(classroom=None, user_id: str = DEFAULT_USER_ID, force_refresh: bool = False):
    estimates = read_estimates_or_unknown(user_id)
    try:
        persisted_sessions = list_draft_study_sessions(user_id)
    except DatabaseError as error:
        print(f"Draft session lookup failed: {error}")
        persisted_sessions = []

    if not force_refresh:
        try:
            snapshot = get_classroom_snapshot(user_id)
            if snapshot is not None:
                assignments = apply_estimates(snapshot.assignments, estimates)
                return snapshot.classes, apply_scheduled_session_minutes(assignments, persisted_sessions)
        except DatabaseError as error:
            print(f"Classroom cache lookup failed: {error}")

    if classroom is None:
        credentials = get_google_credentials()
        classroom = build_classroom_service(credentials)

    classes = parse_courses(classroom)
    assignments = parse_assignments(classroom, classes, estimates)
    try:
        save_classroom_snapshot(user_id, classes, assignments)
    except DatabaseError as error:
        print(f"Classroom cache save failed: {error}")
    return classes, apply_scheduled_session_minutes(assignments, persisted_sessions)


@app.get("/")
def health_check():
    return {"status": "ok", "app": "CatchUp"}


@app.get("/auth/status")
def read_auth_status():
    return {"google_connected": has_google_token()}


@app.post("/auth/google/connect")
def connect_google():
    get_google_credentials()
    return {"google_connected": True}


@app.get("/courses")
def read_courses(force_refresh: bool = False):
    classes, assignments = load_assignments_with_estimates(force_refresh=force_refresh)
    return classes


@app.get("/dashboard")
def read_dashboard(force_refresh: bool = False):
    classes, assignments = load_assignments_with_estimates(force_refresh=force_refresh)
    return build_dashboard(assignments)


@app.get("/recommendations/next")
def read_next_assignment_recommendation():
    classes, assignments = load_assignments_with_estimates()
    return recommend_next_assignment(assignments)


@app.get("/calendar/events")
def read_calendar_events(days_ahead: int = 7, force_refresh: bool = False):
    if not force_refresh:
        try:
            snapshot = get_calendar_events_snapshot(DEFAULT_USER_ID, days_ahead)
            if snapshot is not None:
                return snapshot.events
        except DatabaseError as error:
            print(f"Calendar cache lookup failed: {error}")

    credentials = get_google_credentials()
    calendar_service = build_calendar_service(credentials)
    raw_events = get_calendar_events(calendar_service, days_ahead)
    events = parse_calendar_events(raw_events)
    try:
        save_calendar_events_snapshot(DEFAULT_USER_ID, days_ahead, events)
    except DatabaseError as error:
        print(f"Calendar cache save failed: {error}")
    return events


@app.post("/calendar/availability")
def read_calendar_availability(request: StudyAvailabilityRequest):
    credentials = get_google_credentials()
    calendar_service = build_calendar_service(credentials)
    try:
        return calculate_availability(request, calendar_service)
    except AvailabilityError as error:
        raise HTTPException(status_code=422, detail={"code": error.code, "message": error.message}) from error
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail={"code": "STUDY_PREFERENCES_READ_FAILED", "message": str(error)}) from error


@app.get("/preferences/study")
def read_study_preferences() -> StudyPreferencesResponse:
    try:
        preferences, source = get_study_preferences(DEFAULT_USER_ID)
    except PreferencesValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": error.message, "field": error.field},
        ) from error
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail={"code": "STUDY_PREFERENCES_READ_FAILED", "message": str(error)}) from error
    return StudyPreferencesResponse(preferences=preferences, source=source)


@app.put("/preferences/study")
def update_study_preferences(preferences: StudyPreferences) -> StudyPreferencesResponse:
    try:
        saved = replace_study_preferences(DEFAULT_USER_ID, preferences)
    except PreferencesValidationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "message": error.message, "field": error.field},
        ) from error
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail={"code": "STUDY_PREFERENCES_WRITE_FAILED", "message": str(error)}) from error
    return StudyPreferencesResponse(preferences=saved, source="saved")


@app.post("/preferences/study/reset")
def reset_saved_study_preferences() -> StudyPreferencesResponse:
    try:
        preferences = reset_study_preferences(DEFAULT_USER_ID)
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail={"code": "STUDY_PREFERENCES_WRITE_FAILED", "message": str(error)}) from error
    return StudyPreferencesResponse(preferences=preferences, source="default")


@app.post("/schedule/preview")
def preview_schedule(request: SchedulePreviewRequest):
    credentials = get_google_credentials()
    calendar_service = build_calendar_service(credentials)

    classes, assignments = load_assignments_with_estimates()
    try:
        existing_sessions = list_draft_study_sessions(DEFAULT_USER_ID)
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail={"code": "DRAFT_SESSIONS_READ_FAILED", "message": str(error)}) from error
    try:
        preferences, _ = get_study_preferences(DEFAULT_USER_ID)
        availability = calculate_availability(
            StudyAvailabilityRequest(start_date=request.start_date, end_date=request.end_date),
            calendar_service=calendar_service,
            preferences=preferences,
        )
    except AvailabilityError as error:
        raise HTTPException(status_code=422, detail={"code": error.code, "message": error.message}) from error
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail={"code": "SCHEDULE_PREVIEW_FAILED", "message": str(error)}) from error

    prioritized_assignments = sort_by_priority(assignments, request.now, DEFAULT_TIMEZONE)
    preview = build_scheduling_preview(
        prioritized_assignments=prioritized_assignments,
        free_windows=availability.free_windows,
        preferences=preferences,
        now=request.now,
        include_backlog=request.include_backlog,
        assignment_ids=set(request.assignment_ids) if request.assignment_ids else None,
        existing_sessions=existing_sessions,
    )
    try:
        existing_ids = {session.id for session in existing_sessions}
        combined_sessions = existing_sessions + [
            session for session in preview.draft_sessions
            if session.id not in existing_ids
        ]
        saved_sessions = replace_draft_study_sessions(DEFAULT_USER_ID, combined_sessions)
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail={"code": "DRAFT_SESSIONS_WRITE_FAILED", "message": str(error)}) from error
    return preview.model_copy(update={
        "draft_sessions": saved_sessions,
        "total_scheduled_minutes": sum(session.duration_minutes for session in saved_sessions),
    })


@app.get("/study-sessions")
def read_study_sessions():
    try:
        return list_draft_study_sessions(DEFAULT_USER_ID)
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail={"code": "DRAFT_SESSIONS_READ_FAILED", "message": str(error)}) from error


@app.post("/study-sessions/approve")
def approve_study_sessions(request: StudySessionApprovalRequest) -> StudySessionApprovalResult:
    try:
        sessions, approved_ids, failed_ids = update_study_session_statuses(
            DEFAULT_USER_ID,
            request.session_ids,
            "approved",
        )
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail={"code": "STUDY_SESSION_APPROVAL_FAILED", "message": str(error)}) from error

    return StudySessionApprovalResult(
        sessions=sessions,
        approved_session_ids=approved_ids,
        failed_session_ids=failed_ids,
        added_count=len(approved_ids),
    )


@app.put("/assignments/{assignment_id}/estimate")
def update_assignment_estimate(assignment_id: str, update: EstimateUpdate):
    google_course_id = update.google_course_id or update.course_id
    if not google_course_id:
        raise HTTPException(status_code=422, detail="google_course_id is required")

    try:
        record = upsert_assignment_estimate(
            user_id=DEFAULT_USER_ID,
            google_course_id=google_course_id,
            google_assignment_id=assignment_id,
            estimated_minutes=update.estimated_minutes,
        )
    except DatabaseError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return {
        "assignment_id": record.google_assignment_id,
        "google_course_id": record.google_course_id,
        "estimated_minutes": record.estimated_minutes,
        "estimated_minutes_source": record.estimate_source,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@app.get("/study-plan")
def read_study_plan(
    day: date,
    start_hour: int = 7,
    end_hour: int = 22,
    days_ahead: int = 7,
):
    credentials = get_google_credentials()
    calendar_service = build_calendar_service(credentials)

    classes, assignments = load_assignments_with_estimates()
    prioritized_assignments = sort_by_priority(assignments)

    raw_events = get_calendar_events(calendar_service, days_ahead=days_ahead)
    calendar_events = parse_calendar_events(raw_events)

    window_start, window_end = make_study_window(day, start_hour, end_hour)
    free_blocks = find_free_time_blocks(calendar_events, window_start, window_end)

    return propose_study_plan(prioritized_assignments, free_blocks)
