import type { DashboardData } from "../types";

export const dashboardData: DashboardData = {
  recommendedAssignmentId: "",
  assignments: [],
  courses: [],
  calendarEvents: [],
  studySessions: [],
  failures: [],
  preferencesSource: "default",
  preferences: {
    userId: "me",
    timezone: "America/Chicago",
    dailyWindows: [0, 1, 2, 3, 4, 5, 6].map((weekday) => ({
      weekday,
      enabled: true,
      startTime: weekday < 5 ? "16:00" : "10:00",
      endTime: weekday < 5 ? "22:00" : "20:00",
      maximumDailyStudyMinutes: weekday < 5 ? 180 : 300,
    })),
    minimumSessionMinutes: 20,
    maximumSessionMinutes: 60,
    breakMinutes: 10,
    maximumDailyStudyMinutes: 180,
    allowAssignmentSplitting: true,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  },
};
