export type PriorityLevel = "low" | "medium" | "high";
export type AssignmentStatus = "Unscheduled" | "Partially scheduled" | "Scheduled" | "Backlog";
export type StudySessionStatus = "draft" | "approved" | "synced" | "conflict";
export type CalendarSource = "google-calendar" | "catchup";

export interface PriorityExplanation {
  assignmentId: string;
  score: number;
  level: PriorityLevel;
  reasons: string[];
}

export interface Course {
  id: string;
  name: string;
  teacher: string;
  section: string;
  subject?: string;
  description?: string;
  activeAssignmentCount: number;
  tracked: boolean;
  color: string;
  initials: string;
}

export interface Assignment {
  id: string;
  classroomId: string;
  courseId: string;
  courseName: string;
  title: string;
  description: string;
  dueAt: string | null;
  dueLabel: string;
  dueShort: string;
  estimatedMinutes: number | null;
  estimateSource: "student" | "unknown";
  priority: PriorityLevel;
  priorityScore: number;
  status: AssignmentStatus;
  submissionState: string;
  source: "google-classroom";
  classroomUrl?: string;
  overdue: boolean;
  noDueDate: boolean;
  color: string;
  priorityExplanation: PriorityExplanation;
}

export interface CalendarEvent {
  id: string;
  title: string;
  source: "google-calendar";
  readonly: true;
  startAt: string;
  endAt: string;
  description?: string;
  htmlLink?: string;
}

export interface FreeWindow {
  id: string;
  startAt: string;
  endAt: string;
  durationMinutes: number;
}

export interface AvailabilityWarning {
  code: string;
  message: string;
  calendarId?: string;
}

export interface StudySession {
  id: string;
  title: string;
  assignmentId: string;
  courseId: string;
  source: "catchup";
  status: StudySessionStatus;
  startAt: string;
  endAt: string;
  durationMinutes: number;
  reason: string;
  googleCalendarEventId?: string;
  sequenceNumber?: number;
  totalAssignmentSessions?: number;
}

export interface SchedulingFailure {
  assignmentId: string;
  code?: string;
  title?: string;
  reason: string;
  requestedMinutes?: number | null;
  scheduledMinutes?: number;
  unscheduledMinutes?: number | null;
  suggestedActions?: string[];
}

export interface UserPreferences {
  userId: string;
  timezone: string;
  dailyWindows: Array<{
    weekday: number;
    enabled: boolean;
    startTime: string;
    endTime: string;
    maximumDailyStudyMinutes: number;
  }>;
  minimumSessionMinutes: number;
  maximumSessionMinutes: number;
  breakMinutes: number;
  maximumDailyStudyMinutes: number;
  allowAssignmentSplitting: boolean;
  createdAt: string;
  updatedAt: string;
}

export type StudyPreferencesSource = "saved" | "default";

export interface DashboardData {
  recommendedAssignmentId: string;
  assignments: Assignment[];
  courses: Course[];
  calendarEvents: CalendarEvent[];
  studySessions: StudySession[];
  failures: SchedulingFailure[];
  preferences: UserPreferences;
  preferencesSource: StudyPreferencesSource;
}

export type ModalState =
  | { type: "buildPlan" }
  | { type: "schedule"; assignmentId?: string; startAt?: string }
  | { type: "manualSession" }
  | { type: "estimate"; assignmentId: string }
  | { type: "sync" }
  | null;
