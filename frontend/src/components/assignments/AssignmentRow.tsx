import { Link } from "react-router-dom";
import type { Assignment } from "../../types";
import { PriorityBadge } from "../common/Badge";

export function AssignmentRow({ assignment }: { assignment: Assignment }) {
  return (
    <Link className="assignment-row" to={`/assignments/${assignment.id}`}>
      <div className="assignment-title">
        <span className="course-chip" style={{ background: assignment.color }} />
        <div>
          <strong>{assignment.title}</strong>
          <small>{assignment.courseName} · {assignment.estimatedMinutes} min · {assignment.status}</small>
        </div>
      </div>
      <div className="assignment-meta">
        <span className="due">{assignment.dueShort}</span>
        <PriorityBadge priority={assignment.priority} />
      </div>
    </Link>
  );
}
