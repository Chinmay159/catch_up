import { dashboardData } from "../data/mockData";
import type { Assignment, Course, DashboardData, StudySession, UserPreferences } from "../types";

const pause = () => new Promise((resolve) => window.setTimeout(resolve, 120));

let data: DashboardData = structuredClone(dashboardData);

export const catchupService = {
  async getDashboard(): Promise<DashboardData> {
    await pause();
    return structuredClone(data);
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
    await pause();
    return structuredClone(data.courses);
  },

  async toggleCourseTracking(courseId: string, tracked: boolean): Promise<Course[]> {
    data.courses = data.courses.map((course) => (course.id === courseId ? { ...course, tracked } : course));
    await pause();
    return structuredClone(data.courses);
  },

  async updateEstimate(assignmentId: string, estimatedMinutes: number): Promise<Assignment[]> {
    data.assignments = data.assignments.map((assignment) =>
      assignment.id === assignmentId ? { ...assignment, estimatedMinutes } : assignment,
    );
    await pause();
    return structuredClone(data.assignments);
  },

  async saveDraftSession(session: Partial<StudySession>): Promise<StudySession[]> {
    const assignment = data.assignments.find((item) => item.id === session.assignmentId) ?? data.assignments[0];
    const draft: StudySession = {
      id: `draft-${Date.now()}`,
      title: assignment.title,
      assignmentId: assignment.id,
      courseId: assignment.courseId,
      source: "catchup",
      status: "draft",
      startAt: session.startAt ?? "2026-07-28T20:45:00-05:00",
      endAt: session.endAt ?? "2026-07-28T21:30:00-05:00",
      durationMinutes: session.durationMinutes ?? Math.min(assignment.estimatedMinutes, 45),
      reason: session.reason ?? "Manually added draft session",
    };
    data.studySessions = [...data.studySessions, draft];
    await pause();
    return structuredClone(data.studySessions);
  },

  async approveStudySessions(sessionIds: string[]): Promise<StudySession[]> {
    data.studySessions = data.studySessions.map((session) =>
      sessionIds.includes(session.id)
        ? { ...session, status: "synced", googleCalendarEventId: `mock-${session.id}` }
        : session,
    );
    await pause();
    return structuredClone(data.studySessions);
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
