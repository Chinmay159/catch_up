import { useEffect, useState } from "react";
import type { AppContextValue } from "../App";
import { BackendRequestError, catchupService } from "../services/catchupService";
import type { UserPreferences } from "../types";

const weekdayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

type FieldErrors = Record<string, string>;

function extractFieldError(error: unknown): FieldErrors {
  if (!(error instanceof BackendRequestError) || typeof error.detail !== "object" || error.detail === null) {
    return {};
  }
  const detail = "detail" in error.detail ? error.detail.detail : error.detail;
  if (typeof detail !== "object" || detail === null) return {};
  const field = "field" in detail && typeof detail.field === "string" ? detail.field : "form";
  const message = "message" in detail && typeof detail.message === "string" ? detail.message : "Could not save preferences.";
  return { [field]: message };
}

export function SettingsPage({ app }: { app: AppContextValue }) {
  const [draft, setDraft] = useState<UserPreferences>(app.data.preferences);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setDraft(app.data.preferences);
  }, [app.data.preferences]);

  function update(patch: Partial<UserPreferences>) {
    setDraft((current) => ({ ...current, ...patch }));
    setFieldErrors({});
  }

  function updateWindow(weekday: number, patch: Partial<UserPreferences["dailyWindows"][number]>) {
    setDraft((current) => ({
      ...current,
      dailyWindows: current.dailyWindows.map((window) => window.weekday === weekday ? { ...window, ...patch } : window),
    }));
    setFieldErrors({});
  }

  async function save() {
    setLoading(true);
    setFieldErrors({});
    try {
      const result = await catchupService.saveStudyPreferences(draft);
      app.updatePreferences(result.preferences, result.source);
      app.toast("Preferences saved.");
    } catch (error) {
      setFieldErrors(extractFieldError(error));
      app.toast("Could not save preferences.");
    } finally {
      setLoading(false);
    }
  }

  async function reset() {
    setLoading(true);
    setFieldErrors({});
    try {
      const result = await catchupService.resetStudyPreferences();
      app.updatePreferences(result.preferences, result.source);
      app.toast("Preferences reset to defaults.");
    } catch (error) {
      setFieldErrors(extractFieldError(error));
      app.toast("Could not reset preferences.");
    } finally {
      setLoading(false);
    }
  }

  const orderedWindows = [...draft.dailyWindows].sort((a, b) => a.weekday - b.weekday);

  return (
    <main className="main">
      <div className="page-heading">
        <div>
          <h2>Settings</h2>
          <p>Control integrations, study availability, and how CatchUp creates draft plans.</p>
        </div>
        <div className="heading-actions">
          <button className="btn btn-secondary" onClick={() => void reset()} disabled={loading}>Reset</button>
          <button className="btn btn-primary" onClick={() => void save()} disabled={loading}>{loading ? "Saving..." : "Save changes"}</button>
        </div>
      </div>
      <div className="settings-layout">
        <aside className="card settings-nav">
          <button className="active">Study preferences</button>
          <button>Integrations</button>
          <button>Tracked classes</button>
          <button>Calendar</button>
          <button>Notifications</button>
          <button>Data & privacy</button>
        </aside>
        <div>
          <section className="card settings-card">
            <div className="section-title needs-time">
              <h3>Study availability</h3>
              <small>{app.data.preferencesSource}</small>
            </div>
            <p>Weekday values use 0 = Monday through 6 = Sunday.</p>
            <div className="setting-row">
              <div className="setting-copy"><strong>Timezone</strong><span>Used for all scheduling calculations.</span></div>
              <input className="input compact-input" value={draft.timezone} onChange={(event) => update({ timezone: event.target.value })} />
            </div>
            {fieldErrors.timezone && <p className="field-error">{fieldErrors.timezone}</p>}
            <div className="daily-window-list">
              {orderedWindows.map((window) => (
                <div className="setting-row daily-window-row" key={window.weekday}>
                  <div className="setting-copy">
                    <strong>{weekdayNames[window.weekday]}</strong>
                    <span>Weekday {window.weekday}</span>
                  </div>
                  <label className="switch"><input type="checkbox" checked={window.enabled} onChange={(event) => updateWindow(window.weekday, { enabled: event.target.checked })} /><span className="slider" /></label>
                  <div className="field">
                    <input type="time" value={window.startTime} onChange={(event) => updateWindow(window.weekday, { startTime: event.target.value })} />
                    <span>to</span>
                    <input type="time" value={window.endTime} onChange={(event) => updateWindow(window.weekday, { endTime: event.target.value })} />
                  </div>
                  <input className="input number-input" type="number" min={1} value={window.maximumDailyStudyMinutes} onChange={(event) => updateWindow(window.weekday, { maximumDailyStudyMinutes: Number(event.target.value) })} />
                </div>
              ))}
            </div>
            {(fieldErrors.daily_windows || Object.keys(fieldErrors).some((field) => field.startsWith("daily_windows"))) && <p className="field-error">{Object.values(fieldErrors)[0]}</p>}
          </section>
          <section className="card settings-card">
            <h3>Study sessions</h3>
            <p>These constraints guide future draft plan generation.</p>
            <div className="setting-row"><div className="setting-copy"><strong>Minimum session length</strong><span>Shortest free window CatchUp should consider.</span></div><input className="input number-input" type="number" min={1} value={draft.minimumSessionMinutes} onChange={(event) => update({ minimumSessionMinutes: Number(event.target.value) })} /></div>
            <div className="setting-row"><div className="setting-copy"><strong>Maximum session length</strong><span>Long assignments can be split automatically.</span></div><input className="input number-input" type="number" min={1} value={draft.maximumSessionMinutes} onChange={(event) => update({ maximumSessionMinutes: Number(event.target.value) })} /></div>
            <div className="setting-row"><div className="setting-copy"><strong>Minimum break</strong><span>Time between CatchUp study blocks.</span></div><input className="input number-input" type="number" min={0} value={draft.breakMinutes} onChange={(event) => update({ breakMinutes: Number(event.target.value) })} /></div>
            <div className="setting-row"><div className="setting-copy"><strong>Default daily study limit</strong><span>Fallback for future scheduling constraints.</span></div><input className="input number-input" type="number" min={1} value={draft.maximumDailyStudyMinutes} onChange={(event) => update({ maximumDailyStudyMinutes: Number(event.target.value) })} /></div>
            <div className="setting-row"><div className="setting-copy"><strong>Split large assignments</strong><span>Permit multiple sessions for one assignment.</span></div><label className="switch"><input type="checkbox" checked={draft.allowAssignmentSplitting} onChange={(event) => update({ allowAssignmentSplitting: event.target.checked })} /><span className="slider" /></label></div>
            {Object.keys(fieldErrors).length > 0 && !fieldErrors.timezone && <p className="field-error">{Object.values(fieldErrors)[0]}</p>}
          </section>
          <section className="card settings-card"><h3>Google connections</h3><p>CatchUp never adds Calendar events without review.</p><div className="setting-row"><div className="setting-copy"><strong>Google Classroom</strong><span>Connected for demo account access.</span></div><span className="badge badge-success">Connected</span></div><div className="setting-row"><div className="setting-copy"><strong>Google Calendar</strong><span>Reading commitments for availability.</span></div><span className="badge badge-success">Connected</span></div></section>
        </div>
      </div>
    </main>
  );
}
