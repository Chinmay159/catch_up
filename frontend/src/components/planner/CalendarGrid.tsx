import type { CalendarEvent, Course, StudySession } from "../../types";

const dayKeys = ["2026-07-28", "2026-07-29", "2026-07-30"];
const dayLabels = ["Tue 28", "Wed 29", "Thu 30"];
const hours = [4, 5, 6, 7, 8, 9, 10];

function positionFor(date: string) {
  const parsed = new Date(date);
  const hour = parsed.getHours() + parsed.getMinutes() / 60;
  return 54 + (hour - 16) * 90;
}

function duration(startAt: string, endAt: string) {
  return (new Date(endAt).getTime() - new Date(startAt).getTime()) / 60000;
}

export function CalendarGrid({ events, sessions, courses, filters }: { events: CalendarEvent[]; sessions: StudySession[]; courses: Course[]; filters: { google: boolean; drafts: boolean; synced: boolean } }) {
  return (
    <div className="calendar-grid">
      <div className="cal-time-col">
        <div className="cal-head">TIME</div>
        {hours.map((hour) => <span className="time-label" style={{ top: `${54 + (hour - 4) * 90}px` }} key={hour}>{hour}:00</span>)}
      </div>
      {dayKeys.map((day, index) => (
        <div className="cal-day" key={day}>
          <div className="cal-head"><strong>{dayLabels[index]}</strong><span>{index === 0 ? "Today" : index === 1 ? "Tomorrow" : ""}</span></div>
          {hours.map((hour) => <span className="hour-line" style={{ top: `${54 + (hour - 4) * 90}px` }} key={hour} />)}
          {filters.google && events.filter((event) => event.startAt.startsWith(day)).map((event) => (
            <div className="cal-event busy" key={event.id} style={{ top: positionFor(event.startAt), height: duration(event.startAt, event.endAt) * 1.5 }}>
              <strong>{event.title}</strong>
              <span>Google Calendar · read-only</span>
            </div>
          ))}
          {sessions
            .filter((session) => session.startAt.startsWith(day))
            .filter((session) => session.status === "draft" ? filters.drafts : filters.synced)
            .map((session) => {
              const course = courses.find((item) => item.id === session.courseId);
              return (
                <div className={`cal-event study ${session.status === "draft" ? `draft ${session.courseId}` : "approved"}`} key={session.id} style={{ top: positionFor(session.startAt), height: duration(session.startAt, session.endAt) * 1.5 }}>
                  <strong>{session.title}</strong>
                  <span>{session.status === "draft" ? `${course?.name ?? "CatchUp"} · draft` : "CatchUp Study · synced"}</span>
                </div>
              );
            })}
          {index === 0 && <span className="now-line" style={{ top: 54 + (18.62 - 16) * 90 }} />}
        </div>
      ))}
    </div>
  );
}
