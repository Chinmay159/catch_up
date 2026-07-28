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
    course_id: str = Field(..., description="The ID of the course the assignment belongs to")
    assignment_id: str = Field(..., description="The ID of the assignment")
    submission_state: str | None = Field(None, description="The student submission state from Google Classroom")


class Assignments(BaseModel):
    assignments: list[AssignmentInfo] = Field(..., description="A list of assignments")


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


class PriorityLevel(BaseModel):
    level: Literal["low", "medium", "high"] = Field(..., description="The priority level of the assignment")
    score: int = Field(..., ge=0, le=100, description="The score of the priority level")
    reasons: list[str] = Field(..., description="A list of reasons for the priority level")


class PrioritizedAssignment(BaseModel):
    assignment: AssignmentInfo = Field(..., description="The assignment information")
    priority: PriorityLevel = Field(..., description="The priority level of the assignment")


class Dashboard(BaseModel):
    to_do: list[PrioritizedAssignment] = Field(..., description="A list of prioritized assignments to do")
    upcoming_assignments: list[PrioritizedAssignment] = Field(..., description="A list of prioritized upcoming assignments")
    overdue_assignments: list[PrioritizedAssignment] = Field(..., description="A list of prioritized overdue assignments")
    unscheduled_assignments: list[PrioritizedAssignment] = Field(..., description="A list of prioritized unscheduled assignments")


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
