import { dashboardData } from "../data/mockData";
import {
  adaptAvailabilityWarning,
  adaptBackendDashboard,
  adaptCalendarEvent,
  adaptCourse,
  adaptDraftStudySession,
  adaptFreeWindow,
  adaptSchedulingFailure,
  adaptStudyPreferences,
  serializeStudyPreferences,
  type BackendAvailabilityResponse,
  type BackendCalendarEvent,
  type BackendClassInfo,
  type BackendDashboard,
  type BackendDraftStudySession,
  type BackendSchedulingPlanPreview,
  type BackendStudySessionApprovalResult,
  type BackendStudyPreferencesResponse,
} from "./backendAdapters";
import type { Assignment, AvailabilityWarning, Course, DashboardData, FreeWindow, SchedulingFailure, StudyPreferencesSource, StudySession, UserPreferences } from "../types";

const pause = () => new Promise((resolve) => window.setTimeout(resolve, 120));
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface BackendClassList {
  classes: BackendClassInfo[];
}

let data: DashboardData = structuredClone(dashboardData);

export class BackendRequestError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(`CatchUp backend request failed: ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = await response.json();
    } catch {
      detail = null;
    }
    throw new BackendRequestError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

async function loadBackendDashboard(): Promise<DashboardData> {
  const [dashboard, courses] = await Promise.all([
    requestJson<BackendDashboard>("/dashboard"),
    requestJson<BackendClassList>("/courses").then((result) => result.classes).catch(() => []),
  ]);
  const calendarEvents = await requestJson<BackendCalendarEvent[]>("/calendar/events").catch(() => []);
  const studySessions = await requestJson<BackendDraftStudySession[]>("/study-sessions").catch(() => []);
  const preferencesResponse = await requestJson<BackendStudyPreferencesResponse>("/preferences/study").catch(() => null);
  const adapted = adaptBackendDashboard(dashboard, courses);

  return {
    ...data,
    ...adapted,
    courses: adapted.courses.length ? adapted.courses : data.courses,
    calendarEvents: calendarEvents.map(adaptCalendarEvent),
    studySessions: studySessions.map(adaptDraftStudySession),
    preferences: preferencesResponse ? adaptStudyPreferences(preferencesResponse.preferences) : data.preferences,
    preferencesSource: preferencesResponse?.source ?? data.preferencesSource,
  };
}

export const catchupService = {
  async getAuthStatus(): Promise<{ googleConnected: boolean }> {
    try {
      const status = await requestJson<{ google_connected: boolean }>("/auth/status");
      return { googleConnected: status.google_connected };
    } catch (error) {
      console.warn(error);
      return { googleConnected: false };
    }
  },

  async connectGoogle(): Promise<{ googleConnected: boolean }> {
    const status = await requestJson<{ google_connected: boolean }>("/auth/google/connect", { method: "POST" });
    return { googleConnected: status.google_connected };
  },

  async getDashboard(): Promise<DashboardData> {
    try {
      data = await loadBackendDashboard();
    } catch (error) {
      console.warn(error);
      await pause();
    }
    return structuredClone(data);
  },

  async getStudyPreferences(): Promise<{ preferences: UserPreferences; source: StudyPreferencesSource }> {
    const response = await requestJson<BackendStudyPreferencesResponse>("/preferences/study");
    return { preferences: adaptStudyPreferences(response.preferences), source: response.source };
  },

  async saveStudyPreferences(preferences: UserPreferences): Promise<{ preferences: UserPreferences; source: StudyPreferencesSource }> {
    const response = await requestJson<BackendStudyPreferencesResponse>("/preferences/study", {
      method: "PUT",
      body: JSON.stringify(serializeStudyPreferences(preferences)),
    });
    return { preferences: adaptStudyPreferences(response.preferences), source: response.source };
  },

  async resetStudyPreferences(): Promise<{ preferences: UserPreferences; source: StudyPreferencesSource }> {
    const response = await requestJson<BackendStudyPreferencesResponse>("/preferences/study/reset", { method: "POST" });
    return { preferences: adaptStudyPreferences(response.preferences), source: response.source };
  },

  async getAvailability(): Promise<{ freeWindows: FreeWindow[]; warnings: AvailabilityWarning[]; totalFreeMinutes: number }> {
    const now = new Date();
    const end = new Date(now);
    end.setDate(now.getDate() + 2);
    const response = await requestJson<BackendAvailabilityResponse>("/calendar/availability", {
      method: "POST",
      body: JSON.stringify({
        start_date: now.toISOString().slice(0, 10),
        end_date: end.toISOString().slice(0, 10),
      }),
    });

    return {
      freeWindows: response.free_windows.map(adaptFreeWindow),
      warnings: response.warnings.map(adaptAvailabilityWarning),
      totalFreeMinutes: response.total_free_minutes,
    };
  },

  async buildSchedulePreview(days = 7): Promise<{ studySessions: StudySession[]; failures: SchedulingFailure[]; totalScheduledMinutes: number }> {
    const now = new Date();
    const end = new Date(now);
    end.setDate(now.getDate() + days - 1);
    const response = await requestJson<BackendSchedulingPlanPreview>("/schedule/preview", {
      method: "POST",
      body: JSON.stringify({
        start_date: now.toISOString().slice(0, 10),
        end_date: end.toISOString().slice(0, 10),
        include_backlog: true,
      }),
    });
    const existingSynced = data.studySessions.filter((session) => session.status === "synced");
    const studySessions = [...existingSynced, ...response.draft_sessions.map(adaptDraftStudySession)];
    data = {
      ...data,
      studySessions,
      failures: response.failures.map(adaptSchedulingFailure),
      assignments: data.assignments.map((assignment) => {
        if (response.fully_scheduled_assignment_ids.includes(assignment.id)) return { ...assignment, status: "Scheduled" };
        if (response.partially_scheduled_assignment_ids.includes(assignment.id)) return { ...assignment, status: "Partially scheduled" };
        return assignment;
      }),
    };
    return { studySessions, failures: data.failures, totalScheduledMinutes: response.total_scheduled_minutes };
  },

  async getAssignments(): Promise<Assignment[]> {
    await pause();
    return structuredClone(data.assignments);
  },

  async getAssignment(id: string): Promise<Assignment | undefined> {
    await pause();
    return structuredClone(data.assignments.find((assignment) => assignment.id === id));
  },

  async getCourses(): Promise<Course[]> {
    try {
      const courses = await requestJson<BackendClassList>("/courses");
      data.courses = courses.classes.map(adaptCourse);
    } catch (error) {
      console.warn(error);
      await pause();
    }
    return structuredClone(data.courses);
  },

  async toggleCourseTracking(courseId: string, tracked: boolean): Promise<Course[]> {
    data.courses = data.courses.map((course) => (course.id === courseId ? { ...course, tracked } : course));
    await pause();
    return structuredClone(data.courses);
  },

  async updateEstimate(assignmentId: string, estimatedMinutes: number): Promise<{ assignments: Assignment[]; studySessions: StudySession[]; failures: SchedulingFailure[] }> {
    try {
      await requestJson(`/assignments/${assignmentId}/estimate`, {
        method: "PUT",
        body: JSON.stringify({
          estimated_minutes: estimatedMinutes,
          google_course_id: data.assignments.find((assignment) => assignment.id === assignmentId)?.courseId,
        }),
      });
      data.assignments = data.assignments.map((assignment) =>
        assignment.id === assignmentId
          ? {
              ...assignment,
              estimatedMinutes,
              estimateSource: "student",
              status: assignment.status === "Backlog" ? assignment.status : "Unscheduled",
            }
          : assignment,
      );
      data.failures = data.failures.filter((failure) =>
        !(failure.assignmentId === assignmentId && failure.code === "missing_estimate"),
      );
      try {
        await this.buildSchedulePreview();
      } catch (previewError) {
        console.warn(previewError);
      }
    } catch (error) {
      console.warn(error);
      data.assignments = data.assignments.map((assignment) =>
        assignment.id === assignmentId ? { ...assignment, estimatedMinutes, estimateSource: "student" } : assignment,
      );
      await pause();
    }
    return {
      assignments: structuredClone(data.assignments),
      studySessions: structuredClone(data.studySessions),
      failures: structuredClone(data.failures),
    };
  },

  async saveDraftSession(session: Partial<StudySession>): Promise<StudySession[]> {
    const assignment = data.assignments.find((item) => item.id === session.assignmentId) ?? data.assignments[0];
    if (!assignment) return structuredClone(data.studySessions);
    const fallbackStart = new Date();
    const fallbackDuration = session.durationMinutes ?? Math.min(assignment.estimatedMinutes ?? 30, 45);
    const fallbackEnd = new Date(fallbackStart.getTime() + fallbackDuration * 60000);
    const draft: StudySession = {
      id: `draft-${Date.now()}`,
      title: assignment.title,
      assignmentId: assignment.id,
      courseId: assignment.courseId,
      source: "catchup",
      status: "draft",
      startAt: session.startAt ?? fallbackStart.toISOString(),
      endAt: session.endAt ?? fallbackEnd.toISOString(),
      durationMinutes: fallbackDuration,
      reason: session.reason ?? "Manually added draft session",
    };
    data.studySessions = [...data.studySessions, draft];
    await pause();
    return structuredClone(data.studySessions);
  },

  async approveStudySessions(sessionIds: string[]): Promise<{ studySessions: StudySession[]; addedCount: number; failedSessionIds: string[]; approvedSessionIds: string[] }> {
    const response = await requestJson<BackendStudySessionApprovalResult>("/study-sessions/approve", {
      method: "POST",
      body: JSON.stringify({ session_ids: sessionIds }),
    });
    data.studySessions = response.sessions.map(adaptDraftStudySession);
    return {
      studySessions: structuredClone(data.studySessions),
      addedCount: response.added_count,
      failedSessionIds: response.failed_session_ids,
      approvedSessionIds: response.approved_session_ids,
    };
  },

  async saveDraftPlan(): Promise<{ studySessions: StudySession[]; savedCount: number }> {
    const sessions = await requestJson<BackendDraftStudySession[]>("/study-sessions");
    data.studySessions = sessions.map(adaptDraftStudySession);
    return {
      studySessions: structuredClone(data.studySessions),
      savedCount: data.studySessions.filter((session) => session.status === "draft").length,
    };
  },

  async updatePreferences(preferences: UserPreferences): Promise<UserPreferences> {
    data.preferences = preferences;
    await pause();
    return structuredClone(data.preferences);
  },

  async resetMockData(): Promise<DashboardData> {
    data = structuredClone(dashboardData);
    await pause();
    return structuredClone(data);
  },
};
