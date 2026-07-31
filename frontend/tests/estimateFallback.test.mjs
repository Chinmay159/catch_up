import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const testDir = dirname(fileURLToPath(import.meta.url));
const adapterSource = readFileSync(join(testDir, "../src/services/backendAdapters.ts"), "utf8");
const serviceSource = readFileSync(join(testDir, "../src/services/catchupService.ts"), "utf8");
const modalSource = readFileSync(join(testDir, "../src/components/common/ModalRoot.tsx"), "utf8");

if (!adapterSource.includes("const estimatedMinutes = item.estimated_minutes ?? null;")) {
  throw new Error("Backend adapter must preserve unknown estimates as null.");
}

if (adapterSource.includes("const estimatedMinutes = item.estimated_minutes ?? 30;")) {
  throw new Error("Backend adapter must not invent a 30-minute estimate fallback.");
}

if (!adapterSource.includes('scheduledMinutes > 0') || !adapterSource.includes('"Partially scheduled"')) {
  throw new Error("Backend adapter must show scheduled progress before falling back to Backlog status.");
}

if (!serviceSource.includes('failure.assignmentId === assignmentId && failure.code === "missing_estimate"')) {
  throw new Error("Saving an estimate must immediately clear the missing-estimate failure for that assignment.");
}

if (!serviceSource.includes("studySessions: structuredClone(data.studySessions)") || !serviceSource.includes("failures: structuredClone(data.failures)")) {
  throw new Error("Estimate updates must return refreshed sessions and failures for frontend state synchronization.");
}

if (!modalSource.includes("app.updateFailures(updated.failures)") || !modalSource.includes("app.updateSessions(updated.studySessions)")) {
  throw new Error("Estimate save UI must synchronize dependent scheduling state immediately.");
}

if (!modalSource.includes("await catchupService.approveStudySessions(app.selectedSessionIds)") || !modalSource.includes('navigate("/planner")')) {
  throw new Error("Approval flow must wait for backend confirmation before navigating to Planner.");
}

if (!modalSource.includes("result.failedSessionIds.length") || !modalSource.includes("failedSessionIds.join")) {
  throw new Error("Approval flow must report partial-success failed session IDs.");
}

if (!modalSource.includes("catch (error)") || !modalSource.includes("Could not add sessions. Nothing changed.")) {
  throw new Error("Approval flow must not navigate on backend failure.");
}

if (!modalSource.includes("app.focusPlannerSessions(result.approvedSessionIds") || !modalSource.includes("app.updateSessions(result.studySessions)")) {
  throw new Error("Approval flow must refresh planner data and focus newly approved sessions.");
}

if (!modalSource.includes("await catchupService.saveDraftPlan()") || !modalSource.includes("draft sessions saved")) {
  throw new Error("Save-as-drafts flow must confirm with backend before returning to Planner.");
}

console.log("estimate fallback preserved");
