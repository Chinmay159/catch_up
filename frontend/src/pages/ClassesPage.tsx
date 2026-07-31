import type { AppContextValue } from "../App";
import { catchupService } from "../services/catchupService";
import { EmptyState } from "../components/common/EmptyState";

export function ClassesPage({ app }: { app: AppContextValue }) {
  return (
    <main className="main">
      <div className="page-heading"><div><h2>Tracked classes</h2><p>Choose which active Google Classroom courses should contribute assignments to CatchUp.</p></div><div className="heading-actions"><button className="btn btn-secondary" onClick={() => void app.refresh()}>Refresh</button><button className="btn btn-primary" onClick={async () => { let courses = app.data.courses; for (const course of app.data.courses) courses = await catchupService.toggleCourseTracking(course.id, true); app.updateCourses(courses); app.toast("All active classes are now tracked."); }}>Track all active</button></div></div>
      {app.data.courses.length ? <div className="class-grid">{app.data.courses.map((course) => <section className="card class-card" key={course.id}><div className="class-color" style={{ background: course.color }}>{course.initials}</div><h3>{course.name}</h3><p>{course.teacher} · {course.section}</p><div className="class-stats"><span>{course.activeAssignmentCount ? `${course.activeAssignmentCount} active assignment${course.activeAssignmentCount === 1 ? "" : "s"}` : "No active assignments"}</span><label className="switch" aria-label={`Track ${course.name}`}><input type="checkbox" checked={course.tracked} onChange={async (event) => { const courses = await catchupService.toggleCourseTracking(course.id, event.target.checked); app.updateCourses(courses); app.toast(event.target.checked ? `${course.name} is now tracked.` : `${course.name} will stop importing new work.`); }} /><span className="slider" /></label></div></section>)}</div> : <section className="card card-pad"><EmptyState title="No classes loaded" copy="Active Google Classroom courses will appear here after sync." /></section>}
    </main>
  );
}
