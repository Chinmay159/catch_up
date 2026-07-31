import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { AppContextValue } from "../App";
import { CalendarGrid } from "../components/planner/CalendarGrid";
import { catchupService } from "../services/catchupService";
import type { AvailabilityWarning, FreeWindow } from "../types";
import { formatEstimate } from "../utils/estimates";

export function PlannerPage({ app }: { app: AppContextValue }) {
  const navigate = useNavigate();
  const [filters, setFilters] = useState({ google: true, drafts: true, synced: true });
  const [freeWindows, setFreeWindows] = useState<FreeWindow[]>([]);
  const [warnings, setWarnings] = useState<AvailabilityWarning[]>([]);
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const unscheduled = app.data.assignments.filter((assignment) => assignment.status === "Unscheduled").slice(0, 3);

  async function refreshAvailability() {
    setLoadingAvailability(true);
    try {
      const availability = await catchupService.getAvailability();
      setFreeWindows(availability.freeWindows);
      setWarnings(availability.warnings);
    } catch (error) {
      console.warn(error);
      setWarnings([{ code: "GOOGLE_CALENDAR_FETCH_FAILED", message: "Could not load Calendar availability." }]);
    } finally {
      setLoadingAvailability(false);
    }
  }

  useEffect(() => {
    void refreshAvailability();
  }, []);

  return (
    <main className="main">
      <div className="page-heading"><div><h2>Plan around real life.</h2><p>Calendar commitments are read-only. CatchUp study sessions remain editable drafts until you approve them.</p></div><div className="heading-actions"><button className="btn btn-secondary" onClick={() => app.openModal({ type: "manualSession" })}>Add draft</button><button className="btn btn-primary" onClick={() => app.openModal({ type: "buildPlan" })}>Build study plan</button></div></div>
      <div className="planner-shell">
        <aside className="card planner-side">
          <div className="filter-list">
            <label className="check-row"><input type="checkbox" checked={filters.google} onChange={(event) => setFilters({ ...filters, google: event.target.checked })} /> Google Calendar</label>
            <label className="check-row"><input type="checkbox" checked={filters.drafts} onChange={(event) => setFilters({ ...filters, drafts: event.target.checked })} /> CatchUp drafts</label>
            <label className="check-row"><input type="checkbox" checked={filters.synced} onChange={(event) => setFilters({ ...filters, synced: event.target.checked })} /> Synced study sessions</label>
          </div>
          <div className="section-title needs-time"><h3>Free windows</h3><small>{loadingAvailability ? "Loading" : freeWindows.length}</small></div>
          <div className="unscheduled-list">{freeWindows.slice(0, 4).map((window) => <div className="unscheduled-card" key={window.id}><strong>{new Date(window.startAt).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}</strong><span>{window.durationMinutes} minutes free</span></div>)}</div>
          {warnings.map((warning) => <div className="issue-box compact" key={`${warning.code}-${warning.calendarId ?? ""}`}><strong>{warning.code}</strong><p>{warning.message}</p></div>)}
          <div className="section-title needs-time"><h3>Still needs time</h3><small>{unscheduled.length}</small></div>
          <div className="unscheduled-list">{unscheduled.map((assignment) => <button className="unscheduled-card" key={assignment.id} onClick={() => app.openModal({ type: "schedule", assignmentId: assignment.id })}><strong>{assignment.title}</strong><span>{formatEstimate(assignment.estimatedMinutes)} · {assignment.dueLabel}</span></button>)}</div>
        </aside>
        <section className="card calendar-card"><div className="calendar-toolbar"><div><h3>Calendar</h3><span className="small muted">Events and CatchUp sessions</span></div></div><CalendarGrid events={app.data.calendarEvents} sessions={app.data.studySessions} courses={app.data.courses} filters={filters} focusDate={app.plannerFocusDate} highlightedSessionIds={app.highlightedSessionIds} onSessionClick={(session) => navigate(`/assignments/${session.assignmentId}`)} /></section>
      </div>
    </main>
  );
}
