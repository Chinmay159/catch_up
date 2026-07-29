import { Link, useParams } from "react-router-dom";
import type { AppContextValue } from "../App";
import { PriorityBadge } from "../components/common/Badge";
import { EmptyState } from "../components/common/EmptyState";

export function AssignmentDetailPage({ app }: { app: AppContextValue }) {
  const { assignmentId } = useParams();
  const assignment = app.data.assignments.find((item) => item.id === assignmentId) ?? app.data.assignments[0];
  const sessions = app.data.studySessions.filter((session) => session.assignmentId === assignment.id);
  const scheduled = sessions.reduce((total, session) => total + session.durationMinutes, 0);

  return (
    <main className="main">
      <div className="detail-layout">
        <div className="dashboard-main">
          <section className="card detail-header">
            <Link className="detail-back" to="/assignments">← Back to assignments</Link>
            <div className="split-line"><div><div className="eyebrow">{assignment.courseName}</div><h2>{assignment.title}</h2></div><PriorityBadge priority={assignment.priority} /></div>
            <div className="hero-meta"><div className="meta-item">{assignment.dueLabel}</div><div className="meta-item">{assignment.estimatedMinutes} minutes estimated</div><div className="meta-item"><span className="badge badge-neutral">{assignment.status}</span></div></div>
            <p className="detail-description">{assignment.description}</p>
            <div className="info-grid"><div className="info-item"><span>Submission state</span><strong>{assignment.submissionState}</strong></div><div className="info-item"><span>Priority score</span><strong>{assignment.priorityScore}/100</strong></div><div className="info-item"><span>Source</span><strong>Google Classroom</strong></div></div>
            <div className="hero-actions detail-actions"><a className="btn btn-primary" href={assignment.classroomUrl} target="_blank" rel="noreferrer">Open in Classroom</a><button className="btn btn-secondary" onClick={() => app.openModal({ type: "estimate", assignmentId: assignment.id })}>Edit estimate</button><button className="btn btn-secondary" onClick={() => app.openModal({ type: "schedule", assignmentId: assignment.id })}>Add study time</button></div>
          </section>
          <section className="card card-pad">
            <div className="section-title"><h3>Study plan</h3><small>{scheduled} of {assignment.estimatedMinutes} minutes scheduled</small></div>
            <div className="progress-track"><div className="progress-fill" style={{ width: `${Math.min(100, (scheduled / assignment.estimatedMinutes) * 100)}%` }} /></div>
            {sessions.length ? <div className="session-list">{sessions.map((session) => <div className="session-item" key={session.id}><div><strong>{new Date(session.startAt).toLocaleString([], { weekday: "long", hour: "numeric", minute: "2-digit" })}</strong><span>{session.status} study session · {session.durationMinutes} minutes</span></div><button className="btn btn-ghost btn-sm" onClick={() => app.openModal({ type: "schedule", assignmentId: assignment.id })}>Edit</button></div>)}</div> : <EmptyState title="No study time planned" copy="CatchUp can find openings before this assignment's deadline." action={<button className="btn btn-primary" onClick={() => app.openModal({ type: "schedule", assignmentId: assignment.id })}>Find study time</button>} />}
          </section>
        </div>
        <aside className="dashboard-side">
          <section className="card card-pad"><div className="section-title"><h3>Why CatchUp ranked this here</h3></div><div className="reason-list">{assignment.priorityExplanation.reasons.map((reason) => <div className="reason-item" key={reason}><div className="reason-check">✓</div><div><strong>{reason}</strong><span>This factor contributes to the current priority.</span></div></div>)}</div></section>
          <section className="card card-pad"><div className="section-title"><h3>Suggested openings</h3><small>Before deadline</small></div><div className="slot-list"><button className="slot" onClick={() => app.openModal({ type: "schedule", assignmentId: assignment.id })}><div><strong>Today · 8:45 PM</strong><span>45-minute opening</span></div><span>→</span></button><button className="slot" onClick={() => app.openModal({ type: "schedule", assignmentId: assignment.id })}><div><strong>Tomorrow · 4:10 PM</strong><span>50-minute opening</span></div><span>→</span></button></div></section>
        </aside>
      </div>
    </main>
  );
}
