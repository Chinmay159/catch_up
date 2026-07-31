import { useMemo, useState } from "react";
import type { AppContextValue } from "../App";
import { AssignmentTable } from "../components/assignments/AssignmentTable";
import type { PriorityLevel } from "../types";

export function AssignmentsPage({ app }: { app: AppContextValue }) {
  const [query, setQuery] = useState("");
  const [course, setCourse] = useState("all");
  const [priority, setPriority] = useState<PriorityLevel | "all">("all");
  const assignments = useMemo(() => app.data.assignments.filter((assignment) => {
    const matchesQuery = `${assignment.title} ${assignment.courseName}`.toLowerCase().includes(query.toLowerCase());
    const matchesCourse = course === "all" || assignment.courseId === course;
    const matchesPriority = priority === "all" || assignment.priority === priority;
    return matchesQuery && matchesCourse && matchesPriority;
  }), [app.data.assignments, course, priority, query]);

  return (
    <main className="main">
      <div className="page-heading">
        <div><h2>Assignments</h2><p>Active Classroom work, organized by urgency and scheduling status.</p></div>
        <div className="heading-actions"><button className="btn btn-secondary" onClick={() => { setQuery(""); setCourse("all"); setPriority("all"); }}>Clear filters</button><button className="btn btn-primary" onClick={() => app.openModal({ type: "buildPlan" })}>Plan selected work</button></div>
      </div>
      <div className="toolbar">
        <div className="toolbar-left">
          <div className="search"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search assignments" /></div>
          <select className="select" value={course} onChange={(event) => setCourse(event.target.value)}><option value="all">All classes</option>{app.data.courses.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select>
          <select className="select" value={priority} onChange={(event) => setPriority(event.target.value as PriorityLevel | "all")}><option value="all">All priorities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
        </div>
      </div>
      <AssignmentTable assignments={assignments} />
    </main>
  );
}
