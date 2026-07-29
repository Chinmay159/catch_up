import { Link } from "react-router-dom";
import type { AppContextValue } from "../App";

export function ReviewPlanPage({ app }: { app: AppContextValue }) {
  const sessions = app.data.studySessions.filter((session) => session.status === "draft" || session.status === "synced");
  const total = sessions.reduce((sum, session) => sum + session.durationMinutes, 0);
  const grouped = ["2026-07-28", "2026-07-29", "2026-07-30"].map((day) => ({ day, sessions: sessions.filter((session) => session.startAt.startsWith(day)) }));

  function toggle(id: string, checked: boolean) {
    app.setSelectedSessionIds(checked ? [...app.selectedSessionIds, id] : app.selectedSessionIds.filter((item) => item !== id));
  }

  return (
    <main className="main">
      <div className="page-heading"><div><h2>Review your study plan</h2><p>Nothing will be added to Google Calendar until you approve it.</p></div><div className="heading-actions"><Link className="btn btn-secondary" to="/planner">Back to planner</Link></div></div>
      <div className="review-summary"><div className="card summary-card"><strong>{new Set(sessions.map((session) => session.assignmentId)).size}</strong><span>assignments included</span></div><div className="card summary-card"><strong>{sessions.length}</strong><span>study sessions</span></div><div className="card summary-card"><strong>{Math.floor(total / 60)}h {total % 60}m</strong><span>total study time</span></div><div className="card summary-card"><strong>{app.data.failures.length}</strong><span>issue to review</span></div></div>
      <div className="review-layout">
        <div>{grouped.map(({ day, sessions }) => <section className="card day-group" key={day}><h3>{new Date(`${day}T12:00:00`).toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" })}</h3>{sessions.map((session) => <div className="review-session" key={session.id}><input type="checkbox" checked={app.selectedSessionIds.includes(session.id)} disabled={session.status === "synced"} aria-label={`Approve ${session.title}`} onChange={(event) => toggle(session.id, event.target.checked)} /><div className="review-time">{new Date(session.startAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}-{new Date(session.endAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</div><div><strong>{session.title}</strong><span>{session.durationMinutes} min · {session.reason}</span></div><button className="btn btn-ghost btn-sm" onClick={() => app.openModal({ type: "schedule", assignmentId: session.assignmentId })}>Edit</button></div>)}</section>)}<section className="issue-box"><strong>Physics lab has 15 minutes of buffer</strong><p>The plan fits before the deadline, but there is little room if the assignment takes longer than estimated.</p><button className="btn btn-secondary btn-sm" onClick={() => app.openModal({ type: "estimate", assignmentId: "physics-lab" })}>Review estimate</button></section></div>
        <aside className="sticky-review"><section className="card card-pad"><div className="section-title"><h3>Before you approve</h3></div><p className="muted small">CatchUp will add selected sessions to your “CatchUp Study” calendar. Existing commitments will not be changed.</p><div className="reason-list"><div className="reason-item"><div className="reason-check">✓</div><div><strong>{app.selectedSessionIds.length} sessions selected</strong><span>You can uncheck any draft session.</span></div></div><div className="reason-item"><div className="reason-check">⌕</div><div><strong>Calendar commitments stay read-only</strong><span>Only CatchUp drafts will be added.</span></div></div></div><button className="btn btn-primary full-width review-approve" onClick={() => app.openModal({ type: "sync" })}>Add approved sessions</button><button className="btn btn-ghost full-width" onClick={() => app.toast("Draft plan saved without syncing.")}>Save as drafts</button></section></aside>
      </div>
    </main>
  );
}
