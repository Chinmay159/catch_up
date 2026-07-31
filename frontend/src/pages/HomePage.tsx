import { Link } from "react-router-dom";
import type { AppContextValue } from "../App";
import { AssignmentRow } from "../components/assignments/AssignmentRow";
import { PriorityBadge, StatusBadge } from "../components/common/Badge";
import { EmptyState } from "../components/common/EmptyState";
import { formatEstimateLong } from "../utils/estimates";

export function HomePage({ app }: { app: AppContextValue }) {
  const [recommended] = app.data.assignments.filter((item) => item.id === app.data.recommendedAssignmentId);
  const important = app.data.assignments.filter((item) => item.id !== recommended?.id && !item.noDueDate).slice(0, 4);
  const upcomingPlan: Array<{ id: string; title: string; startAt: string; endAt: string; assignmentId?: string; status?: string }> = [
    ...app.data.calendarEvents,
    ...app.data.studySessions,
  ];
  upcomingPlan.sort((a, b) => new Date(a.startAt).getTime() - new Date(b.startAt).getTime());
  const visiblePlan = upcomingPlan
    .slice(0, 4);
  const overdueAssignment = app.data.assignments.find((assignment) => assignment.overdue);
  const plannedMinutes = app.data.studySessions.reduce((total, session) => total + session.durationMinutes, 0);

  return (
    <main className="main">
      <div className="page-heading">
        <div><h2>Dashboard</h2><p>Active Classroom work ranked by CatchUp priority.</p></div>
        <div className="heading-actions"><button className="btn btn-secondary" onClick={() => void app.refresh()}>Refresh</button><button className="btn btn-primary" onClick={() => app.openModal({ type: "buildPlan" })}>Build study plan</button></div>
      </div>
      <div className="dashboard-grid">
        <div className="dashboard-main">
          {recommended ? (
            <section className="card hero-card">
              <div className="hero-top"><div className="hero-label">✦ Recommended next</div><PriorityBadge priority={recommended.priority} /></div>
              <h2 className="hero-title">{recommended.title}</h2>
              <div className="course-line">{recommended.courseName} · Imported from Google Classroom</div>
              <div className="hero-meta">
                <div className="meta-item">Due {recommended.dueLabel.toLowerCase()}</div>
                <div className="meta-item">{formatEstimateLong(recommended.estimatedMinutes)}</div>
                <StatusBadge>{recommended.status}</StatusBadge>
              </div>
              <div className="reason-box"><span>✦</span><div><strong>Why this is next</strong><span>{recommended.priorityExplanation.reasons.join(", ")}.</span></div></div>
              <div className="hero-actions"><Link className="btn btn-primary" to={`/assignments/${recommended.id}`}>Start working →</Link><button className="btn btn-secondary" onClick={() => app.openModal({ type: "schedule", assignmentId: recommended.id })}>Add to plan</button><Link className="btn btn-ghost" to={`/assignments/${recommended.id}`}>View details</Link></div>
            </section>
          ) : (
            <section className="card card-pad">
              <EmptyState
                title={app.googleConnected ? "No active recommendation" : "Connect Google Classroom"}
                copy={app.googleConnected ? "CatchUp did not receive any active Classroom assignments to prioritize." : "Connect your Google account to import Classroom assignments for this demo."}
                action={app.googleConnected ? undefined : <button className="btn btn-primary" onClick={() => void app.connectGoogle()}>Connect Google</button>}
              />
            </section>
          )}
          <section className="card card-pad">
            <div className="section-title"><h3>Important assignments</h3><Link className="btn btn-ghost btn-sm" to="/assignments">View all assignments →</Link></div>
            {important.length ? <div className="assignment-list">{important.map((assignment) => <AssignmentRow assignment={assignment} key={assignment.id} />)}</div> : <EmptyState title="No additional assignments" copy="Additional prioritized assignments will appear here after Classroom sync." />}
          </section>
        </div>
        <aside className="dashboard-side">
          {visiblePlan.length > 0 && (
            <section className="card card-pad">
              <div className="section-title"><h3>Upcoming plan</h3></div>
              <div className="timeline">
                {visiblePlan.map((item) => {
                  const start = new Date(item.startAt);
                  const end = new Date(item.endAt);
                  const isSession = "assignmentId" in item;
                  return <Timeline key={item.id} time={start.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} title={item.title} meta={`${isSession ? "CatchUp" : "Google Calendar"} · ${start.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}-${end.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`} study={isSession} draft={isSession && item.status === "draft"} />;
                })}
              </div>
              <Link className="btn btn-secondary btn-sm full-width" to="/planner">Open planner</Link>
            </section>
          )}
          {overdueAssignment && <section className="card alert-card"><div className="alert-head"><div className="alert-icon">!</div><div><h4>{overdueAssignment.title} is overdue</h4><p>{overdueAssignment.courseName} · {overdueAssignment.dueLabel}</p><button className="btn btn-sm btn-secondary" onClick={() => app.openModal({ type: "schedule", assignmentId: overdueAssignment.id })}>Review options</button></div></div></section>}
          {(app.data.studySessions.length > 0 || app.data.assignments.length > 0) && <section className="card progress-card"><div className="section-title"><h3>Current workload</h3></div><div className="progress-numbers"><div className="progress-stat"><strong>{app.data.assignments.length}</strong><span>active assignments</span></div><div className="progress-stat"><strong>{app.data.studySessions.length}</strong><span>study sessions</span></div><div className="progress-stat"><strong>{Math.floor(plannedMinutes / 60)}h {plannedMinutes % 60}m</strong><span>planned time</span></div></div></section>}
        </aside>
      </div>
    </main>
  );
}

function Timeline({ time, title, meta, draft, study }: { time: string; title: string; meta: string; draft?: boolean; study?: boolean }) {
  return <div className="timeline-item"><div className="timeline-time">{time}</div><div className="timeline-marker"><span className="timeline-dot" /><span className="timeline-line" /></div><div className={`timeline-event ${draft || study ? "study" : ""} ${draft ? "draft" : ""}`}><strong>{title}</strong><span>{study ? "✓ " : ""}{meta}</span></div></div>;
}
