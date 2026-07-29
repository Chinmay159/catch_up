import { Link } from "react-router-dom";
import type { Assignment } from "../../types";
import { PriorityBadge, StatusBadge } from "../common/Badge";

export function AssignmentTable({ assignments }: { assignments: Assignment[] }) {
  return (
    <section className="card assignment-table">
      <div className="table-head"><div>Assignment</div><div>Due</div><div>Estimate</div><div>Priority</div><div>Status</div><div /></div>
      {assignments.map((assignment) => (
        <Link className="table-row" to={`/assignments/${assignment.id}`} key={assignment.id}>
          <div className="table-title"><strong>{assignment.title}</strong><span>{assignment.courseName}</span></div>
          <div className="table-cell">{assignment.dueLabel}</div>
          <div className="table-cell">{assignment.estimatedMinutes} min</div>
          <div><PriorityBadge priority={assignment.priority} /></div>
          <div className="status-line"><StatusBadge tone={assignment.status === "Scheduled" ? "success" : assignment.status === "Partially scheduled" ? "medium" : "neutral"}>{assignment.status}</StatusBadge></div>
          <div aria-hidden="true">•••</div>
        </Link>
      ))}
    </section>
  );
}
