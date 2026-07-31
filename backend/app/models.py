from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ClassInfo(BaseModel):
    name: str = Field(..., description="The name of the class")
    course_id: str = Field(..., description="The ID of the course")
    subject: str | None = Field(None, description="The subject of the class")
    description: str | None = Field(None, description="A brief description of the class")
    teachers: list[str] = Field(default_factory=list, description="A list of teachers for the class")


class ClassList(BaseModel):
    classes: list[ClassInfo] = Field(..., description="A list of classes")


class AssignmentInfo(BaseModel):
    title: str = Field(..., description="The title of the assignment")
    description: str | None = Field(None, description="A brief description of the assignment")
    due_date: date | None = Field(None, description="The due date of the assignment")
    due_time: time | None = Field(None, description="The due time of the assignment")
    estimated_minutes: int | None = Field(None, ge=1, description="Estimated time to complete in minutes")
    estimated_minutes_source: Literal["student", "unknown"] = Field("unknown", description="Where the estimate came from")
    course_id: str = Field(..., description="The ID of the course the assignment belongs to")
    assignment_id: str = Field(..., description="The ID of the assignment")
    submission_state: str | None = Field(None, description="The student submission state from Google Classroom")
    scheduled_minutes: int = Field(0, ge=0, description="Minutes already scheduled for this assignment")
    completed_study_minutes: int = Field(0, ge=0, description="Minutes already spent studying this assignment")
    is_active: bool = Field(True, description="Whether CatchUp should consider this assignment active")


class Assignments(BaseModel):
    assignments: list[AssignmentInfo] = Field(..., description="A list of assignments")


class EstimateUpdate(BaseModel):
    estimated_minutes: int = Field(..., ge=1, description="Student-entered estimated time to complete in minutes")
    google_course_id: str | None = Field(None, description="Google Classroom course ID for the assignment")
    course_id: str | None = Field(None, description="Alias for google_course_id used by the frontend model")


class CalendarEvent(BaseModel):
    id: str | None = Field(None, description="The ID of the calendar event")
    title: str = Field(..., description="The title of the calendar event")
    user_id: str = Field(..., description="The ID of the user associated with the calendar event")
    start_time: datetime = Field(..., description="The start time of the calendar event")
    end_time: datetime = Field(..., description="The end time of the calendar event")
    description: str | None = Field(None, description="A brief description of the calendar event")

    @model_validator(mode="after")
    def check_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class CalendarCommitment(BaseModel):
    id: str
    calendar_id: str
    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool
    status: Literal["confirmed", "tentative"]
    transparency: Literal["busy", "free"]
    read_only: bool = True
    source: Literal["google_calendar"] = "google_calendar"
    location: str | None = None
    description: str | None = None
    html_link: str | None = None

    @model_validator(mode="after")
    def check_times(self):
        if self.end_at <= self.start_at:
            raise ValueError("End time must be after start time")
        return self


class BusyBlock(BaseModel):
    id: str
    source_event_ids: list[str]
    start_at: datetime
    end_at: datetime
    reason: Literal["calendar_event", "all_day_event"]
    read_only: bool = True


class FreeWindow(BaseModel):
    id: str
    start_at: datetime
    end_at: datetime
    duration_minutes: int


class DailyStudyWindow(BaseModel):
    weekday: int = Field(..., ge=0, le=6)
    enabled: bool
    start_time: time
    end_time: time
    maximum_daily_study_minutes: int | None = Field(None, ge=1)


class StudyAvailabilityRequest(BaseModel):
    start_date: date
    end_date: date
    timezone: str | None = None
    daily_windows: list[DailyStudyWindow] | None = None
    minimum_window_minutes: int | None = Field(None, ge=1)


class StudyPreferences(BaseModel):
    user_id: str
    timezone: str
    daily_windows: list[DailyStudyWindow]
    minimum_session_minutes: int
    maximum_session_minutes: int
    break_minutes: int
    maximum_daily_study_minutes: int
    allow_assignment_splitting: bool
    created_at: datetime
    updated_at: datetime


class StudyPreferencesResponse(BaseModel):
    preferences: StudyPreferences
    source: Literal["saved", "default"]


class AvailabilityWarning(BaseModel):
    code: str
    message: str
    calendar_id: str | None = None


class AvailabilityResponse(BaseModel):
    range_start: datetime
    range_end: datetime
    timezone: str
    calendar_events: list[CalendarCommitment]
    busy_blocks: list[BusyBlock]
    free_windows: list[FreeWindow]
    total_study_window_minutes: int
    total_busy_minutes: int
    total_free_minutes: int
    warnings: list[AvailabilityWarning] = Field(default_factory=list)
    calculated_at: datetime = Field(default_factory=datetime.now)


class StudyEvent(BaseModel):
    id: str | None = Field(None, description="The ID of the study event")
    title: str = Field(..., description="The title of the study event")
    user_id: str = Field(..., description="The ID of the user associated with the study event")
    assignment_id: str = Field(..., description="The ID of the assignment associated with the study event")
    start_time: datetime = Field(..., description="The start time of the study event")
    end_time: datetime = Field(..., description="The end time of the study event")
    description: str | None = Field(None, description="A brief description of the study event")
    status: Literal["draft", "approved", "synced", "conflict"] = Field(..., description="The status of the study event")
    google_calendar_event_id: str | None = Field(None, description="The Google Calendar event ID after syncing")

    @model_validator(mode="after")
    def check_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class PriorityReason(BaseModel):
    code: str = Field(..., description="Stable reason code for the priority calculation")
    message: str = Field(..., description="Student-readable reason for this priority")
    contribution: int | None = Field(None, description="Score contribution from this reason")


class PriorityLevel(BaseModel):
    level: Literal["low", "medium", "high"] = Field(..., description="The priority level of the assignment")
    score: int = Field(..., ge=0, le=100, description="The score of the priority level")
    reasons: list[str] = Field(..., description="A list of reasons for the priority level")
    categories: list[Literal["overdue", "upcoming", "backlog", "unscheduled"]] = Field(
        default_factory=list,
        description="Dashboard categories this assignment belongs to",
    )
    reason_details: list[PriorityReason] = Field(
        default_factory=list,
        description="Structured reasons with stable codes and score contributions",
    )
    remaining_minutes: int | None = Field(None, description="Estimated work remaining after scheduled or completed study")
    calculated_at: datetime = Field(default_factory=datetime.now, description="When this priority was calculated")


class PrioritizedAssignment(BaseModel):
    assignment: AssignmentInfo = Field(..., description="The assignment information")
    priority: PriorityLevel = Field(..., description="The priority level of the assignment")


class Dashboard(BaseModel):
    to_do: list[PrioritizedAssignment] = Field(..., description="A list of prioritized assignments to do")
    upcoming_assignments: list[PrioritizedAssignment] = Field(..., description="A list of prioritized upcoming assignments")
    overdue_assignments: list[PrioritizedAssignment] = Field(..., description="A list of prioritized overdue assignments")
    unscheduled_assignments: list[PrioritizedAssignment] = Field(..., description="A list of prioritized unscheduled assignments")
    backlog_assignments: list[PrioritizedAssignment] = Field(default_factory=list, description="A list of prioritized backlog assignments")


class NextAssignmentRecommendation(BaseModel):
    assignment: AssignmentInfo | None = Field(None, description="The recommended next assignment")
    priority_score: int | None = Field(None, ge=0, le=100, description="Priority score for the recommendation")
    priority_level: Literal["low", "medium", "high"] | None = Field(None, description="Priority level for the recommendation")
    reasons: list[str] = Field(default_factory=list, description="Plain-language reasons for the recommendation")
    calculated_at: datetime = Field(default_factory=datetime.now, description="When this recommendation was calculated")


class TimeBlock(BaseModel):
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def check_times(self):
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class SchedulingFailure(BaseModel):
    assignment_id: str
    title: str
    reason: str


class StudyPlan(BaseModel):
    study_events: list[StudyEvent]
    failures: list[SchedulingFailure]


class SchedulePreviewRequest(BaseModel):
    start_date: date
    end_date: date
    assignment_ids: list[str] | None = None
    include_backlog: bool = True
    now: datetime | None = None


class DraftStudySession(BaseModel):
    id: str
    assignment_id: str
    course_id: str
    assignment_title: str
    start_at: datetime
    end_at: datetime
    duration_minutes: int
    status: Literal["draft", "approved", "synced"] = "draft"
    source: Literal["catchup_scheduler"] = "catchup_scheduler"
    sequence_number: int
    total_assignment_sessions: int
    placement_reasons: list[str]


class SchedulingPreviewFailure(BaseModel):
    assignment_id: str
    title: str
    code: Literal[
        "missing_estimate",
        "no_free_time",
        "insufficient_time_before_deadline",
        "daily_limit_reached",
        "session_too_short",
        "splitting_disabled",
        "deadline_already_passed",
        "invalid_assignment",
        "invalid_free_window",
    ]
    message: str
    requested_minutes: int | None
    scheduled_minutes: int
    unscheduled_minutes: int | None
    suggested_actions: list[str]


class SchedulingPlanPreview(BaseModel):
    draft_sessions: list[DraftStudySession]
    fully_scheduled_assignment_ids: list[str]
    partially_scheduled_assignment_ids: list[str]
    unscheduled_assignment_ids: list[str]
    failures: list[SchedulingPreviewFailure]
    total_requested_minutes: int
    total_scheduled_minutes: int
    total_unscheduled_minutes: int
    calculated_at: datetime


class StudySessionApprovalRequest(BaseModel):
    session_ids: list[str]


class StudySessionApprovalResult(BaseModel):
    sessions: list[DraftStudySession]
    approved_session_ids: list[str]
    failed_session_ids: list[str]
    added_count: int
