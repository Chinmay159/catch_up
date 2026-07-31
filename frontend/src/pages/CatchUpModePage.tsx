import type { AppContextValue } from "../App";
import { PriorityBadge } from "../components/common/Badge";
import { EmptyState } from "../components/common/EmptyState";
import { formatEstimateLong } from "../utils/estimates";

export function CatchUpModePage({ app }: { app: AppContextValue }) {
  const recoveryAssignments = app.data.assignments.filter((assignment) => assignment.overdue || assignment.priority === "high");

  return (
    <main className="main">
      <div className="recovery-wrap">
        <section className="card recovery-hero">
          <span className="badge badge-draft">Guided recovery</span>
          <h2>Catch-Up Mode</h2>
          <p>Overdue and high-priority assignments appear here when CatchUp has active Classroom work to recover.</p>
        </section>
        <section className="card recovery-panel">
          <h3>Recovery work</h3>
          {recoveryAssignments.length ? (
            <>
              {recoveryAssignments.map((assignment) => (
                <label className="selectable-task" key={assignment.id}>
                  <input type="checkbox" defaultChecked />
                  <div><strong>{assignment.title}</strong><span>{assignment.courseName} · {assignment.dueLabel} · {formatEstimateLong(assignment.estimatedMinutes)}</span></div>
                  <PriorityBadge priority={assignment.priority} />
                </label>
              ))}
              <div className="recovery-actions">
                <span className="small muted">{recoveryAssignments.length} assignment{recoveryAssignments.length === 1 ? "" : "s"} selected</span>
                <button className="btn btn-primary" onClick={() => app.openModal({ type: "buildPlan" })}>Build study plan</button>
              </div>
            </>
          ) : (
            <EmptyState title="No recovery work" copy="Overdue and high-priority assignments will appear here after Classroom sync." />
          )}
        </section>
      </div>
    </main>
  );
}
