import { useEffect, useRef } from "react";

import type { CalendarEvent, Course, StudySession } from "../../types";

function dateKey(date: Date) {
  return date.toISOString().slice(0, 10);
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function positionFor(date: string, startHour: number) {
  const parsed = new Date(date);
  const hour = parsed.getHours() + parsed.getMinutes() / 60;
  return 54 + (hour - startHour) * 90;
}

function duration(startAt: string, endAt: string) {
  return (new Date(endAt).getTime() - new Date(startAt).getTime()) / 60000;
}

export function CalendarGrid({ events, sessions, courses, filters, focusDate, highlightedSessionIds = [], onSessionClick }: { events: CalendarEvent[]; sessions: StudySession[]; courses: Course[]; filters: { google: boolean; drafts: boolean; synced: boolean }; focusDate?: string; highlightedSessionIds?: string[]; onSessionClick?: (session: StudySession) => void }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const timedItems = [
    ...events.map((event) => ({ startAt: event.startAt, endAt: event.endAt })),
    ...sessions.map((session) => ({ startAt: session.startAt, endAt: session.endAt })),
  ];
  const firstItemDate = timedItems
    .map((item) => new Date(item.startAt))
    .sort((a, b) => a.getTime() - b.getTime())[0];
  const anchorDate = focusDate ? new Date(`${focusDate}T12:00:00`) : firstItemDate ?? new Date();
  const dayKeys = Array.from({ length: 3 }, (_, index) => dateKey(addDays(anchorDate, index)));

  const now = new Date();
  const todayKey = dateKey(new Date());
  const startHour = 0;
  const endHour = 23;
  const hours = Array.from({ length: endHour - startHour + 1 }, (_, index) => startHour + index);
  const nowTop = 54 + ((now.getHours() + now.getMinutes() / 60) - startHour) * 90;
  const showNowLine = dayKeys.includes(todayKey);

  useEffect(() => {
    if (!showNowLine || !scrollRef.current) return;
    scrollRef.current.scrollTop = Math.max(0, nowTop - 220);
  }, [nowTop, showNowLine]);

  return (
    <div className="calendar-scroll" ref={scrollRef}>
      <div className="calendar-grid">
        <div className="cal-time-col">
          <div className="cal-head">TIME</div>
          {hours.map((hour) => <span className="time-label" style={{ top: `${54 + (hour - startHour) * 90}px` }} key={hour}>{hour}:00</span>)}
        </div>
        {dayKeys.map((day) => (
          <div className="cal-day" key={day}>
            <div className="cal-head"><strong>{new Date(`${day}T12:00:00`).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</strong><span>{day === todayKey ? "Today" : ""}</span></div>
            {hours.map((hour) => <span className="hour-line" style={{ top: `${54 + (hour - startHour) * 90}px` }} key={hour} />)}
            {filters.google && events.filter((event) => event.startAt.startsWith(day)).map((event) => (
              <div className="cal-event busy" key={event.id} style={{ top: positionFor(event.startAt, startHour), height: duration(event.startAt, event.endAt) * 1.5 }}>
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
                  <button className={`cal-event study ${session.status === "draft" ? `draft ${session.courseId}` : "approved"} ${highlightedSessionIds.includes(session.id) ? "highlight" : ""}`} key={session.id} type="button" onClick={() => onSessionClick?.(session)} style={{ top: positionFor(session.startAt, startHour), height: duration(session.startAt, session.endAt) * 1.5 }}>
                    <strong>{session.title}</strong>
                    <span>{session.status === "draft" ? `${course?.name ?? "CatchUp"} · draft` : "CatchUp Study · synced"}</span>
                  </button>
                );
              })}
            {day === todayKey && <span className="now-line" style={{ top: nowTop }}><span>{now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span></span>}
          </div>
        ))}
      </div>
    </div>
  );
}
