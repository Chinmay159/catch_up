import type { ReactNode } from "react";
import type { PriorityLevel } from "../../types";

export function PriorityBadge({ priority }: { priority: PriorityLevel }) {
  return <span className={`badge badge-${priority}`}><span className="dot" />{priority[0].toUpperCase() + priority.slice(1)}</span>;
}

export function StatusBadge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "draft" | "success" | "medium" | "high" | "low" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
