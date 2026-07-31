import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { catchupService } from "../../services/catchupService";
import type { AppContextValue } from "../../App";
import type { Assignment, ModalState } from "../../types";
import { EmptyState } from "./EmptyState";

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
  const [buildingPlan, setBuildingPlan] = useState(false);
  const assignment = useMemo<Assignment | undefined>(() => {
    if (modal && "assignmentId" in modal && modal.assignmentId) {
      return app.data.assignments.find((item) => item.id === modal.assignmentId) ?? app.data.assignments[0];
    }
    return app.data.assignments[0];
  }, [app.data.assignments, modal]);

  if (!modal) return null;

  if (modal.type === "buildPlan") {
    async function createDrafts() {
      setBuildingPlan(true);
      try {
        const preview = await catchupService.buildSchedulePreview();
        app.updateSessions(preview.studySessions);
        app.updateFailures(preview.failures);
        app.setSelectedSessionIds(preview.studySessions.filter((session) => session.status === "draft").map((session) => session.id));
        app.closeModal();
        app.toast(preview.studySessions.length ? `Draft plan created with ${preview.totalScheduledMinutes} minutes.` : "No draft sessions fit. Review the issues.");
        navigate("/planner/review");
      } catch (error) {
        console.warn(error);
        app.toast("Could not build a draft plan. Check backend logs.");
      } finally {
        setBuildingPlan(false);
      }
    }

    return (
      <ModalFrame
        title="Build a study plan"
        onClose={app.closeModal}
        actions={<><button className="btn btn-secondary" onClick={app.closeModal} disabled={buildingPlan}>Cancel</button><button className="btn btn-primary" onClick={() => void createDrafts()} disabled={buildingPlan}>{buildingPlan ? "Creating..." : "Create drafts"}</button></>}
      >
        <p>CatchUp will create editable draft sessions from the current assignment and calendar data.</p>
        <div className="modal-form">
          <label>Study window<select defaultValue="week"><option value="week">Next 7 days</option></select></label>
          <label>Maximum study time per day<select defaultValue="120"><option value="120">2 hours</option><option value="60">1 hour</option><option value="180">3 hours</option></select></label>
          <label className="inline-field"><input type="checkbox" defaultChecked /> Split large assignments across sessions</label>
        </div>
      </ModalFrame>
    );
  }

  if (modal.type === "schedule" || modal.type === "manualSession") {
    if (!assignment) {
      return (
        <ModalFrame title="Add draft session" onClose={app.closeModal} actions={<button className="btn btn-secondary" onClick={app.closeModal}>Close</button>}>
          <EmptyState title="No assignments available" copy="Active Classroom assignments will appear here after sync." />
        </ModalFrame>
      );
    }
    const estimatedMinutes = assignment.estimatedMinutes ?? 30;
    return (
      <ModalFrame
        title={modal.type === "manualSession" ? "Add draft session" : `Schedule ${assignment.title}`}
        onClose={app.closeModal}
        actions={<><button className="btn btn-secondary" onClick={app.closeModal}>Cancel</button><button className="btn btn-primary" onClick={async () => { const sessions = await catchupService.saveDraftSession({ assignmentId: assignment.id, durationMinutes: minutes }); app.updateSessions(sessions); app.closeModal(); app.toast("Draft study session saved."); }}>Save draft</button></>}
      >
        <div className="modal-form">
          <label>Assignment<select defaultValue={assignment.id}>{app.data.assignments.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label>
          <label>Date<input type="date" /></label>
          <label>Start time<input type="time" /></label>
          <label>Duration<select value={minutes} onChange={(event) => setMinutes(Number(event.target.value))}><option value={Math.min(estimatedMinutes, 45)}>{Math.min(estimatedMinutes, 45)} minutes</option><option value={estimatedMinutes}>{estimatedMinutes} minutes</option><option value={30}>30 minutes</option></select></label>
          <div className="reason-box"><div><strong>Draft only</strong><span>This session will not sync until you approve the study plan.</span></div></div>
        </div>
      </ModalFrame>
    );
  }

  if (modal.type === "estimate") {
    if (!assignment) {
      return (
        <ModalFrame title="Edit time estimate" onClose={app.closeModal} actions={<button className="btn btn-secondary" onClick={app.closeModal}>Close</button>}>
          <EmptyState title="No assignment selected" copy="Choose an active assignment before editing an estimate." />
        </ModalFrame>
      );
    }
    return (
      <ModalFrame
        title="Edit time estimate"
        onClose={app.closeModal}
        actions={<><button className="btn btn-secondary" onClick={app.closeModal}>Cancel</button><button className="btn btn-primary" onClick={async () => { const updated = await catchupService.updateEstimate(assignment.id, minutes); app.updateAssignments(updated.assignments); app.updateSessions(updated.studySessions); app.updateFailures(updated.failures); app.setSelectedSessionIds(updated.studySessions.filter((session) => session.status === "draft").map((session) => session.id)); app.closeModal(); app.toast("Estimate updated and priority recalculated."); }}>Save estimate</button></>}
      >
        <p>How long do you realistically expect <strong>{assignment.title}</strong> to take?</p>
        <div className="modal-form">
          <label>Estimated minutes<input type="number" min={5} step={5} value={minutes} onChange={(event) => setMinutes(Number(event.target.value))} /></label>
        </div>
      </ModalFrame>
    );
  }

  function earliestSessionDate(sessions: Array<{ startAt: string }>) {
    return sessions.map((session) => session.startAt.slice(0, 10)).sort()[0];
  }

  async function addApprovedSessions() {
    try {
      const result = await catchupService.approveStudySessions(app.selectedSessionIds);
      app.updateSessions(result.studySessions);
      app.setSelectedSessionIds(result.studySessions.filter((session) => session.status === "draft").map((session) => session.id));
      const approvedSessions = result.studySessions.filter((session) => result.approvedSessionIds.includes(session.id));
      app.focusPlannerSessions(result.approvedSessionIds, earliestSessionDate(approvedSessions));
      app.closeModal();
      if (result.failedSessionIds.length) {
        app.toast(`${result.addedCount} sessions added. ${result.failedSessionIds.length} failed: ${result.failedSessionIds.join(", ")}.`);
      } else {
        app.toast(`${result.addedCount} sessions added.`);
      }
      navigate("/planner");
    } catch (error) {
      console.warn(error);
      app.toast("Could not add sessions. Nothing changed.");
    }
  }

  async function saveAsDrafts() {
    try {
      const result = await catchupService.saveDraftPlan();
      app.updateSessions(result.studySessions);
      app.focusPlannerSessions(result.studySessions.map((session) => session.id), earliestSessionDate(result.studySessions));
      app.closeModal();
      app.toast(`${result.savedCount} draft sessions saved.`);
      navigate("/planner");
    } catch (error) {
      console.warn(error);
      app.toast("Could not save draft plan. Nothing changed.");
    }
  }

  return (
    <ModalFrame
      title="Add selected sessions to Google Calendar?"
      onClose={app.closeModal}
      actions={<><button className="btn btn-secondary" onClick={() => void saveAsDrafts()}>Save as drafts</button><button className="btn btn-primary" onClick={() => void addApprovedSessions()}>Add approved sessions</button></>}
    >
      <p>The selected sessions will be added to the <strong>CatchUp Study</strong> calendar. Existing commitments will not be changed.</p>
      <div className="reason-list">
        <div className="reason-item"><div className="reason-check">✓</div><div><strong>{app.selectedSessionIds.length} draft sessions</strong><span>Selected for approval</span></div></div>
        <div className="reason-item"><div className="reason-check">⌕</div><div><strong>Existing events unchanged</strong><span>Calendar commitments stay read-only.</span></div></div>
      </div>
    </ModalFrame>
  );
}
