import { Link } from "react-router-dom";
import type { AppContextValue } from "../App";
import { AssignmentRow } from "../components/assignments/AssignmentRow";
import { PriorityBadge, StatusBadge } from "../components/common/Badge";

export function HomePage({ app }: { app: AppContextValue }) {
  const [recommended] = app.data.assignments.filter((item) => item.id === app.data.recommendedAssignmentId);
  const important = app.data.assignments.filter((item) => !item.overdue && !item.noDueDate).slice(0, 4);

  return (
    <main className="main">
      <div className="page-heading">
        <div><h2>Good evening, Chinmay.</h2><p>You have one clear priority tonight. CatchUp found time for most of your upcoming work.</p></div>
        <div className="heading-actions"><button className="btn btn-secondary" onClick={() => app.toast("Classroom and Calendar refreshed.")}>Refresh</button><button className="btn btn-primary" onClick={() => app.openModal({ type: "buildPlan" })}>Build study plan</button></div>
      </div>
      <div className="dashboard-grid">
        <div className="dashboard-main">
          <section className="card hero-card">
            <div className="hero-top"><div className="hero-label">✦ Recommended next</div><PriorityBadge priority={recommended.priority} /></div>
            <h2 className="hero-title">{recommended.title}</h2>
            <div className="course-line">{recommended.courseName} · Imported from Google Classroom</div>
            <div className="hero-meta">
              <div className="meta-item">Due {recommended.dueLabel.toLowerCase()}</div>
              <div className="meta-item">About {recommended.estimatedMinutes} minutes</div>
              <StatusBadge>Not scheduled</StatusBadge>
            </div>
            <div className="reason-box"><span>✦</span><div><strong>Why this is next</strong><span>{recommended.priorityExplanation.reasons.join(", ")}.</span></div></div>
            <div className="hero-actions"><Link className="btn btn-primary" to={`/assignments/${recommended.id}`}>Start working →</Link><button className="btn btn-secondary" onClick={() => app.openModal({ type: "schedule", assignmentId: recommended.id })}>Add to plan</button><Link className="btn btn-ghost" to={`/assignments/${recommended.id}`}>View details</Link></div>
          </section>
          <section className="card card-pad">
            <div className="section-title"><h3>Important assignments</h3><Link className="btn btn-ghost btn-sm" to="/assignments">View all assignments →</Link></div>
            <div className="assignment-list">{important.map((assignment) => <AssignmentRow assignment={assignment} key={assignment.id} />)}</div>
          </section>
        </div>
        <aside className="dashboard-side">
          <section className="card card-pad">
            <div className="section-title"><h3>Today’s plan</h3><small>4:00-10:00 PM</small></div>
            <div className="timeline">
              <Timeline time="4:00" title="Soccer practice" meta="Google Calendar · 4:00-5:30 PM" />
              <Timeline time="6:10" title="English essay draft" meta="Draft study session · 40 min" draft />
              <Timeline time="7:00" title="Dinner" meta="Google Calendar · 7:00-7:45 PM" />
              <Timeline time="8:00" title="Cold War reading notes" meta="Synced study session · 30 min" study />
            </div>
            <Link className="btn btn-secondary btn-sm full-width" to="/planner">Open planner</Link>
          </section>
          <section className="card alert-card"><div className="alert-head"><div className="alert-icon">!</div><div><h4>Calculus problem set is overdue</h4><p>CatchUp found a 45-minute opening tonight, but it has not been added to your plan.</p><button className="btn btn-sm btn-secondary" onClick={() => app.openModal({ type: "schedule", assignmentId: "chapter-7" })}>Review options</button></div></div></section>
          <section className="card progress-card"><div className="section-title"><h3>This week</h3><small>Quiet progress</small></div><div className="progress-numbers"><div className="progress-stat"><strong>3</strong><span>tasks finished</span></div><div className="progress-stat"><strong>4</strong><span>study sessions</span></div><div className="progress-stat"><strong>4.2h</strong><span>planned time</span></div></div></section>
        </aside>
      </div>
    </main>
  );
}

function Timeline({ time, title, meta, draft, study }: { time: string; title: string; meta: string; draft?: boolean; study?: boolean }) {
  return <div className="timeline-item"><div className="timeline-time">{time}</div><div className="timeline-marker"><span className="timeline-dot" /><span className="timeline-line" /></div><div className={`timeline-event ${draft || study ? "study" : ""} ${draft ? "draft" : ""}`}><strong>{title}</strong><span>{study ? "✓ " : ""}{meta}</span></div></div>;
}
