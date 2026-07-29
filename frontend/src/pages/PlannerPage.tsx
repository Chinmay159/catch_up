import { Link } from "react-router-dom";
import { useState } from "react";
import type { AppContextValue } from "../App";
import { CalendarGrid } from "../components/planner/CalendarGrid";

export function PlannerPage({ app }: { app: AppContextValue }) {
  const [filters, setFilters] = useState({ google: true, drafts: true, synced: true });
  const unscheduled = app.data.assignments.filter((assignment) => assignment.status === "Unscheduled").slice(0, 3);
  return (
    <main className="main">
      <div className="page-heading"><div><h2>Plan around real life.</h2><p>Calendar commitments are read-only. CatchUp study sessions remain editable drafts until you approve them.</p></div><div className="heading-actions"><button className="btn btn-secondary" onClick={() => app.openModal({ type: "manualSession" })}>Add draft</button><button className="btn btn-primary" onClick={() => app.openModal({ type: "buildPlan" })}>Build study plan</button></div></div>
      <div className="planner-shell">
        <aside className="card planner-side">
          <div className="section-title"><h3>July 2026</h3></div>
          <div className="mini-cal">{["S", "M", "T", "W", "T", "F", "S"].map((day) => <span key={day}>{day}</span>)}{[26, 27, 28, 29, 30, 31, 1, 2, 3, 4, 5, 6, 7, 8].map((day) => <button className={day === 28 ? "active" : ""} key={`${day}`}>{day}</button>)}</div>
          <div className="filter-list">
            <label className="check-row"><input type="checkbox" checked={filters.google} onChange={(event) => setFilters({ ...filters, google: event.target.checked })} /> Google Calendar</label>
            <label className="check-row"><input type="checkbox" checked={filters.drafts} onChange={(event) => setFilters({ ...filters, drafts: event.target.checked })} /> CatchUp drafts</label>
            <label className="check-row"><input type="checkbox" checked={filters.synced} onChange={(event) => setFilters({ ...filters, synced: event.target.checked })} /> Synced study sessions</label>
          </div>
          <div className="section-title needs-time"><h3>Still needs time</h3><small>{unscheduled.length}</small></div>
          <div className="unscheduled-list">{unscheduled.map((assignment) => <button className="unscheduled-card" key={assignment.id} onClick={() => app.openModal({ type: "schedule", assignmentId: assignment.id })}><strong>{assignment.title}</strong><span>{assignment.estimatedMinutes} min · {assignment.dueLabel}</span></button>)}</div>
        </aside>
        <section className="card calendar-card"><div className="calendar-toolbar"><div><h3>July 28-30</h3><span className="small muted">Three-day view</span></div><div className="tabs"><button className="tab">Day</button><button className="tab active">3 days</button><button className="tab">Week</button></div></div><CalendarGrid events={app.data.calendarEvents} sessions={app.data.studySessions} courses={app.data.courses} filters={filters} /></section>
        <aside><section className="card context-card"><div className="badge badge-draft">Draft selected</div><h3 className="context-title">English essay draft</h3><p>Tuesday, 6:10-6:50 PM · 40 minutes</p><div className="reason-box compact"><div><strong>Why here</strong><span>This is your longest open block before dinner.</span></div></div><button className="btn btn-secondary btn-sm full-width" onClick={() => app.openModal({ type: "schedule", assignmentId: "gatsby-draft" })}>Edit session</button></section><section className="card context-card"><h3>Plan status</h3><p>Five assignments are fully scheduled. Physics and Calculus still need time.</p><Link className="btn btn-primary btn-sm full-width" to="/planner/review">Review drafts</Link></section></aside>
      </div>
    </main>
  );
}
