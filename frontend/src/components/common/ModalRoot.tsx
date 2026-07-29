import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { catchupService } from "../../services/catchupService";
import type { AppContextValue } from "../../App";
import type { Assignment, ModalState } from "../../types";

function ModalFrame({ title, children, actions, onClose }: { title: string; children: ReactNode; actions: ReactNode; onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <div className="modal-head">
          <h3 id="modal-title">{title}</h3>
          <button className="icon-button" type="button" aria-label="Close modal" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">{children}</div>
        <div className="modal-actions">{actions}</div>
      </section>
    </div>
  );
}

export function ModalRoot({ modal, app }: { modal: ModalState; app: AppContextValue }) {
  const navigate = useNavigate();
  const [minutes, setMinutes] = useState(45);
  const assignment = useMemo<Assignment>(() => {
    if (modal && "assignmentId" in modal && modal.assignmentId) {
      return app.data.assignments.find((item) => item.id === modal.assignmentId) ?? app.data.assignments[0];
    }
    return app.data.assignments[0];
  }, [app.data.assignments, modal]);

  if (!modal) return null;

  if (modal.type === "buildPlan") {
    return (
      <ModalFrame
        title="Build a study plan"
        onClose={app.closeModal}
        actions={<><button className="btn btn-secondary" onClick={app.closeModal}>Cancel</button><button className="btn btn-primary" onClick={() => { app.closeModal(); app.toast("Draft plan created. Nothing has been synced."); navigate("/planner/review"); }}>Create drafts</button></>}
      >
        <p>CatchUp will check your free time from tonight through Friday and create editable draft sessions.</p>
        <div className="modal-form">
          <label>Study window<select defaultValue="tonight"><option value="tonight">Tonight through Friday</option><option value="week">Next 7 days</option></select></label>
          <label>Maximum study time per day<select defaultValue="120"><option value="120">2 hours</option><option value="60">1 hour</option><option value="180">3 hours</option></select></label>
          <label className="inline-field"><input type="checkbox" defaultChecked /> Split large assignments across sessions</label>
        </div>
      </ModalFrame>
    );
  }

  if (modal.type === "schedule" || modal.type === "manualSession") {
    return (
      <ModalFrame
        title={modal.type === "manualSession" ? "Add draft session" : `Schedule ${assignment.title}`}
        onClose={app.closeModal}
        actions={<><button className="btn btn-secondary" onClick={app.closeModal}>Cancel</button><button className="btn btn-primary" onClick={async () => { const sessions = await catchupService.saveDraftSession({ assignmentId: assignment.id, durationMinutes: minutes }); app.updateSessions(sessions); app.closeModal(); app.toast("Draft study session saved."); }}>Save draft</button></>}
      >
        <div className="modal-form">
          <label>Assignment<select defaultValue={assignment.id}>{app.data.assignments.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label>
          <label>Date<input type="date" defaultValue="2026-07-28" /></label>
          <label>Start time<input type="time" defaultValue="20:45" /></label>
          <label>Duration<select value={minutes} onChange={(event) => setMinutes(Number(event.target.value))}><option value={Math.min(assignment.estimatedMinutes, 45)}>{Math.min(assignment.estimatedMinutes, 45)} minutes</option><option value={assignment.estimatedMinutes}>{assignment.estimatedMinutes} minutes</option><option value={30}>30 minutes</option></select></label>
          <div className="reason-box"><div><strong>Draft only</strong><span>This session will not sync until you approve the study plan.</span></div></div>
        </div>
      </ModalFrame>
    );
  }

  if (modal.type === "estimate") {
    return (
      <ModalFrame
        title="Edit time estimate"
        onClose={app.closeModal}
        actions={<><button className="btn btn-secondary" onClick={app.closeModal}>Cancel</button><button className="btn btn-primary" onClick={async () => { const assignments = await catchupService.updateEstimate(assignment.id, minutes); app.updateAssignments(assignments); app.closeModal(); app.toast("Estimate updated and priority recalculated."); }}>Save estimate</button></>}
      >
        <p>How long do you realistically expect <strong>{assignment.title}</strong> to take?</p>
        <div className="modal-form">
          <label>Estimated minutes<input type="number" min={5} step={5} value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} /></label>
        </div>
      </ModalFrame>
    );
  }

  return (
    <ModalFrame
      title="Add selected sessions to Google Calendar?"
      onClose={app.closeModal}
      actions={<><button className="btn btn-secondary" onClick={app.closeModal}>Keep as drafts</button><button className="btn btn-primary" onClick={async () => { const sessions = await catchupService.approveStudySessions(app.selectedSessionIds); app.updateSessions(sessions); app.closeModal(); app.toast(`${app.selectedSessionIds.length} sessions added to Google Calendar.`); }}>Add to Calendar</button></>}
    >
      <p>The selected sessions will be added to the <strong>CatchUp Study</strong> calendar. Existing commitments will not be changed.</p>
      <div className="reason-list">
        <div className="reason-item"><div className="reason-check">✓</div><div><strong>{app.selectedSessionIds.length} draft sessions</strong><span>Selected for approval</span></div></div>
        <div className="reason-item"><div className="reason-check">⌕</div><div><strong>Existing events unchanged</strong><span>Calendar commitments stay read-only.</span></div></div>
      </div>
    </ModalFrame>
  );
}
