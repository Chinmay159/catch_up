import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { catchupService } from "./services/catchupService";
import type { Assignment, Course, DashboardData, ModalState, StudySession, UserPreferences } from "./types";
import { AssignmentsPage } from "./pages/AssignmentsPage";
import { AssignmentDetailPage } from "./pages/AssignmentDetailPage";
import { ClassesPage } from "./pages/ClassesPage";
import { HomePage } from "./pages/HomePage";
import { PlannerPage } from "./pages/PlannerPage";
import { ReviewPlanPage } from "./pages/ReviewPlanPage";
import { CatchUpModePage } from "./pages/CatchUpModePage";
import { SettingsPage } from "./pages/SettingsPage";
import { ModalRoot } from "./components/common/ModalRoot";
import { ToastStack } from "./components/common/ToastStack";
import { AppLayout } from "./layouts/AppLayout";

export interface AppContextValue {
  data: DashboardData;
  selectedAssignment?: Assignment;
  selectedSessionIds: string[];
  setSelectedSessionIds: (ids: string[]) => void;
  openModal: (modal: ModalState) => void;
  closeModal: () => void;
  toast: (message: string) => void;
  refresh: () => Promise<void>;
  updateCourses: (courses: Course[]) => void;
  updateAssignments: (assignments: Assignment[]) => void;
  updateSessions: (sessions: StudySession[]) => void;
  updatePreferences: (preferences: UserPreferences) => void;
}

export function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [modal, setModal] = useState<ModalState>(null);
  const [toasts, setToasts] = useState<Array<{ id: number; message: string }>>([]);
  const [selectedSessionIds, setSelectedSessionIds] = useState<string[]>([]);

  async function refresh() {
    const dashboard = await catchupService.getDashboard();
    setData(dashboard);
    setSelectedSessionIds(dashboard.studySessions.filter((session) => session.status === "draft").map((session) => session.id));
  }

  useEffect(() => {
    void refresh();
  }, []);

  function toast(message: string) {
    const id = Date.now();
    setToasts((items) => [...items, { id, message }]);
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== id)), 2800);
  }

  if (!data) {
    return (
      <main className="loading-screen">
        <div className="brand-mark">C</div>
        <p>Loading CatchUp...</p>
      </main>
    );
  }

  const context: AppContextValue = {
    data,
    selectedSessionIds,
    setSelectedSessionIds,
    openModal: setModal,
    closeModal: () => setModal(null),
    toast,
    refresh,
    updateCourses: (courses) => setData((current) => current ? { ...current, courses } : current),
    updateAssignments: (assignments) => setData((current) => current ? { ...current, assignments } : current),
    updateSessions: (studySessions) => setData((current) => current ? { ...current, studySessions } : current),
    updatePreferences: (preferences) => setData((current) => current ? { ...current, preferences } : current),
  };

  return (
    <>
      <AppLayout>
        <Routes>
          <Route path="/" element={<HomePage app={context} />} />
          <Route path="/assignments" element={<AssignmentsPage app={context} />} />
          <Route path="/assignments/:assignmentId" element={<AssignmentDetailPage app={context} />} />
          <Route path="/planner" element={<PlannerPage app={context} />} />
          <Route path="/planner/review" element={<ReviewPlanPage app={context} />} />
          <Route path="/classes" element={<ClassesPage app={context} />} />
          <Route path="/catch-up" element={<CatchUpModePage app={context} />} />
          <Route path="/settings" element={<SettingsPage app={context} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppLayout>
      <ModalRoot modal={modal} app={context} />
      <ToastStack toasts={toasts} />
    </>
  );
}

export function usePageTitle() {
  const location = useLocation();
  return useMemo(() => {
    if (location.pathname.startsWith("/assignments/")) return "Assignment";
    if (location.pathname.startsWith("/assignments")) return "Assignments";
    if (location.pathname.startsWith("/planner/review")) return "Review Study Plan";
    if (location.pathname.startsWith("/planner")) return "Planner";
    if (location.pathname.startsWith("/classes")) return "Classes";
    if (location.pathname.startsWith("/catch-up")) return "Catch-Up Mode";
    if (location.pathname.startsWith("/settings")) return "Settings";
    return "Home";
  }, [location.pathname]);
}

export function NavButton({ to, icon, label }: { to: string; icon: string; label: string }) {
  const location = useLocation();
  const active =
    to === "/"
      ? location.pathname === "/"
      : location.pathname === to || location.pathname.startsWith(`${to}/`);
  return (
    <Link className={`nav-button ${active ? "active" : ""} ${to === "/catch-up" ? "recovery" : ""}`} to={to}>
      <span className="nav-icon" aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </Link>
  );
}

export function useAssignmentNavigation() {
  const navigate = useNavigate();
  return (assignmentId: string) => navigate(`/assignments/${assignmentId}`);
}
