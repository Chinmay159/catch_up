import type { ReactNode } from "react";

export function EmptyState({ title, copy, action }: { title: string; copy: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">✓</div>
      <h3>{title}</h3>
      <p>{copy}</p>
      {action}
    </div>
  );
}
