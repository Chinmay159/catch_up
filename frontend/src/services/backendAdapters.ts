import type { Assignment, AvailabilityWarning, CalendarEvent, Course, DashboardData, FreeWindow, SchedulingFailure, StudySession, StudyPreferencesSource, UserPreferences } from "../types";

export interface BackendClassInfo {
  name: string;
  course_id: string;
  subject?: string | null;
  description?: string | null;
  teachers: string[];
}

export interface BackendAssignmentInfo {
  title: string;
  description?: string | null;
  due_date?: string | null;
  due_time?: string | null;
  estimated_minutes?: number | null;
  estimated_minutes_source?: "student" | "unknown";
  course_id: string;
  assignment_id: string;
  submission_state?: string | null;
  scheduled_minutes?: number;
  completed_study_minutes?: number;
  is_active?: boolean;
}

export interface BackendPriorityLevel {
  level: "low" | "medium" | "high";
  score: number;
  reasons: string[];
  categories?: Array<"overdue" | "upcoming" | "backlog" | "unscheduled">;
  remaining_minutes?: number | null;
  calculated_at?: string;
}

export interface BackendPrioritizedAssignment {
  assignment: BackendAssignmentInfo;
  priority: BackendPriorityLevel;
}

export interface BackendDashboard {
  to_do: BackendPrioritizedAssignment[];
  upcoming_assignments: BackendPrioritizedAssignment[];
  overdue_assignments: BackendPrioritizedAssignment[];
  unscheduled_assignments: BackendPrioritizedAssignment[];
  backlog_assignments?: BackendPrioritizedAssignment[];
}

export interface BackendCalendarEvent {
  id?: string | null;
  title: string;
  user_id: string;
  start_time: string;
  end_time: string;
  description?: string | null;
  html_link?: string | null;
}

export interface BackendFreeWindow {
  id: string;
  start_at: string;
  end_at: string;
  duration_minutes: number;
}

export interface BackendAvailabilityWarning {
  code: string;
  message: string;
  calendar_id?: string | null;
}

export interface BackendAvailabilityResponse {
  free_windows: BackendFreeWindow[];
  warnings: BackendAvailabilityWarning[];
  total_free_minutes: number;
}

export interface BackendDailyStudyWindow {
  weekday: number;
  enabled: boolean;
  start_time: string;
  end_time: string;
  maximum_daily_study_minutes?: number | null;
}

export interface BackendStudyPreferences {
  user_id: string;
  timezone: string;
  daily_windows: BackendDailyStudyWindow[];
  minimum_session_minutes: number;
  maximum_session_minutes: number;
  break_minutes: number;
  maximum_daily_study_minutes: number;
  allow_assignment_splitting: boolean;
  created_at: string;
  updated_at: string;
}

export interface BackendStudyPreferencesResponse {
  preferences: BackendStudyPreferences;
  source: StudyPreferencesSource;
}

export interface BackendStudyEvent {
  id?: string | null;
  title: string;
  user_id: string;
  assignment_id: string;
  start_time: string;
  end_time: string;
  description?: string | null;
  status: "draft" | "approved" | "synced" | "conflict";
  google_calendar_event_id?: string | null;
}

export interface BackendSchedulingFailure {
  assignment_id: string;
  title?: string;
  reason?: string;
  code?: string;
  message?: string;
  requested_minutes?: number | null;
  scheduled_minutes?: number;
  unscheduled_minutes?: number | null;
  suggested_actions?: string[];
}

export interface BackendDraftStudySession {
  id: string;
  assignment_id: string;
  course_id: string;
  assignment_title: string;
  start_at: string;
  end_at: string;
  duration_minutes: number;
  status: "draft" | "approved" | "synced";
  source: "catchup_scheduler";
  sequence_number: number;
  total_assignment_sessions: number;
  placement_reasons: string[];
}

export interface BackendStudySessionApprovalResult {
  sessions: BackendDraftStudySession[];
  approved_session_ids: string[];
  failed_session_ids: string[];
  added_count: number;
}

export interface BackendSchedulingPlanPreview {
  draft_sessions: BackendDraftStudySession[];
  fully_scheduled_assignment_ids: string[];
  partially_scheduled_assignment_ids: string[];
  unscheduled_assignment_ids: string[];
  failures: BackendSchedulingFailure[];
  total_requested_minutes: number;
  total_scheduled_minutes: number;
  total_unscheduled_minutes: number;
  calculated_at: string;
}

export function adaptCourse(item: BackendClassInfo): Course {
  return {
    id: item.course_id,
    name: item.name,
    teacher: item.teachers[0] ?? "Unknown teacher",
    section: item.subject ?? "Active course",
    subject: item.subject ?? undefined,
    description: item.description ?? undefined,
    activeAssignmentCount: 0,
    tracked: true,
    color: "#0F766E",
    initials: item.name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase(),
  };
}

export function adaptAssignment(item: BackendAssignmentInfo, priority: BackendPriorityLevel, courseName = "Class"): Assignment {
  const dueAt = item.due_date ? `${item.due_date}T${item.due_time ?? "23:59:00"}` : null;
  const estimatedMinutes = item.estimated_minutes ?? null;
  const categories = priority.categories ?? [];
  const scheduledMinutes = item.scheduled_minutes ?? 0;
  const remainingMinutes = priority.remaining_minutes ?? (estimatedMinutes === null ? null : Math.max(estimatedMinutes - scheduledMinutes, 0));
  const status = estimatedMinutes !== null && scheduledMinutes > 0
    ? remainingMinutes === 0
      ? "Scheduled"
      : "Partially scheduled"
    : categories.includes("backlog")
      ? "Backlog"
      : categories.includes("unscheduled")
        ? "Unscheduled"
        : "Scheduled";

  return {
    id: item.assignment_id,
    classroomId: item.assignment_id,
    courseId: item.course_id,
    courseName,
    title: item.title,
    description: item.description ?? "",
    dueAt,
    dueLabel: dueAt ? new Date(dueAt).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "No due date",
    dueShort: dueAt ? new Date(dueAt).toLocaleDateString([], { weekday: "short" }) : "Backlog",
    estimatedMinutes,
    estimateSource: item.estimated_minutes_source ?? "unknown",
    priority: priority.level,
    priorityScore: priority.score,
    status,
    submissionState: item.submission_state ?? "Assigned",
    source: "google-classroom",
    overdue: dueAt ? new Date(dueAt) < new Date() : false,
    noDueDate: !dueAt,
    color: "#0F766E",
    priorityExplanation: {
      assignmentId: item.assignment_id,
      score: priority.score,
      level: priority.level,
      reasons: priority.reasons,
    },
  };
}

export function adaptBackendDashboard(
  dashboard: BackendDashboard,
  courses: BackendClassInfo[] = [],
): Pick<DashboardData, "assignments" | "recommendedAssignmentId" | "courses"> {
  const courseById = new Map(courses.map((course) => [course.course_id, course]));
  const seen = new Set<string>();
  const orderedItems = [
    ...dashboard.to_do,
    ...dashboard.overdue_assignments,
    ...dashboard.upcoming_assignments,
    ...(dashboard.backlog_assignments ?? []),
    ...dashboard.unscheduled_assignments,
  ].filter((item) => {
    if (seen.has(item.assignment.assignment_id)) return false;
    seen.add(item.assignment.assignment_id);
    return true;
  });

  const assignments = orderedItems.map((item) => {
    const course = courseById.get(item.assignment.course_id);
    return adaptAssignment(item.assignment, item.priority, course?.name ?? "Class");
  });

  return {
    assignments,
    courses: courses.map(adaptCourse),
    recommendedAssignmentId: dashboard.to_do[0]?.assignment.assignment_id ?? assignments[0]?.id ?? "",
  };
}

export function adaptCalendarEvent(item: BackendCalendarEvent): CalendarEvent {
  return {
    id: item.id ?? item.title,
    title: item.title,
    source: "google-calendar",
    readonly: true,
    startAt: item.start_time,
    endAt: item.end_time,
    description: item.description ?? undefined,
    htmlLink: item.html_link ?? undefined,
  };
}

export function adaptFreeWindow(item: BackendFreeWindow): FreeWindow {
  return {
    id: item.id,
    startAt: item.start_at,
    endAt: item.end_at,
    durationMinutes: item.duration_minutes,
  };
}

export function adaptAvailabilityWarning(item: BackendAvailabilityWarning): AvailabilityWarning {
  return {
    code: item.code,
    message: item.message,
    calendarId: item.calendar_id ?? undefined,
  };
}

export function adaptStudyPreferences(item: BackendStudyPreferences): UserPreferences {
  return {
    userId: item.user_id,
    timezone: item.timezone,
    dailyWindows: item.daily_windows.map((window) => ({
      weekday: window.weekday,
      enabled: window.enabled,
      startTime: window.start_time.slice(0, 5),
      endTime: window.end_time.slice(0, 5),
      maximumDailyStudyMinutes: window.maximum_daily_study_minutes ?? item.maximum_daily_study_minutes,
    })),
    minimumSessionMinutes: item.minimum_session_minutes,
    maximumSessionMinutes: item.maximum_session_minutes,
    breakMinutes: item.break_minutes,
    maximumDailyStudyMinutes: item.maximum_daily_study_minutes,
    allowAssignmentSplitting: item.allow_assignment_splitting,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

export function serializeStudyPreferences(item: UserPreferences): BackendStudyPreferences {
  return {
    user_id: item.userId,
    timezone: item.timezone,
    daily_windows: item.dailyWindows.map((window) => ({
      weekday: window.weekday,
      enabled: window.enabled,
      start_time: window.startTime,
      end_time: window.endTime,
      maximum_daily_study_minutes: window.maximumDailyStudyMinutes,
    })),
    minimum_session_minutes: item.minimumSessionMinutes,
    maximum_session_minutes: item.maximumSessionMinutes,
    break_minutes: item.breakMinutes,
    maximum_daily_study_minutes: item.maximumDailyStudyMinutes,
    allow_assignment_splitting: item.allowAssignmentSplitting,
    created_at: item.createdAt,
    updated_at: item.updatedAt,
  };
}

export function adaptStudyEvent(item: BackendStudyEvent): StudySession {
  const start = new Date(item.start_time);
  const end = new Date(item.end_time);
  return {
    id: item.id ?? `${item.assignment_id}-${item.start_time}`,
    title: item.title.replace(/^Study:\s*/, ""),
    assignmentId: item.assignment_id,
    courseId: "",
    source: "catchup",
    status: item.status,
    startAt: item.start_time,
    endAt: item.end_time,
    durationMinutes: Math.round((end.getTime() - start.getTime()) / 60000),
    reason: "Generated by CatchUp scheduler",
    googleCalendarEventId: item.google_calendar_event_id ?? undefined,
  };
}

export function adaptDraftStudySession(item: BackendDraftStudySession): StudySession {
  return {
    id: item.id,
    title: item.assignment_title,
    assignmentId: item.assignment_id,
    courseId: item.course_id,
    source: "catchup",
    status: item.status,
    startAt: item.start_at,
    endAt: item.end_at,
    durationMinutes: item.duration_minutes,
    reason: item.placement_reasons.join(" "),
    sequenceNumber: item.sequence_number,
    totalAssignmentSessions: item.total_assignment_sessions,
  };
}

export function adaptSchedulingFailure(item: BackendSchedulingFailure): SchedulingFailure {
  return {
    assignmentId: item.assignment_id,
    title: item.title,
    code: item.code,
    reason: item.message ?? item.reason ?? "Scheduling failed.",
    requestedMinutes: item.requested_minutes,
    scheduledMinutes: item.scheduled_minutes,
    unscheduledMinutes: item.unscheduled_minutes,
    suggestedActions: item.suggested_actions,
  };
}
