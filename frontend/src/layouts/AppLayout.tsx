import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { NavButton, usePageTitle } from "../App";

const navItems = [
  ["/", "⌂", "Home"],
  ["/assignments", "✓", "Assignments"],
  ["/planner", "□", "Planner"],
  ["/classes", "▣", "Classes"],
  ["/catch-up", "↻", "Catch-Up Mode"],
] as const;

export function AppLayout({ children, googleConnected, onConnectGoogle }: { children: ReactNode; googleConnected: boolean; onConnectGoogle: () => Promise<void> }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const title = usePageTitle();

  return (
    <div className="shell">
      {mobileOpen && <button className="mobile-sidebar-backdrop" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`} aria-label="Primary navigation">
        <Link className="brand" to="/" onClick={() => setMobileOpen(false)}>
          <span className="brand-mark">C</span>
          <span>CatchUp</span>
        </Link>
        <div className="nav-label">Workspace</div>
        <nav className="nav" onClick={() => setMobileOpen(false)}>
          {navItems.map(([to, icon, label]) => <NavButton key={to} to={to} icon={icon} label={label} />)}
        </nav>
        <div className="nav-spacer" />
        <nav className="nav" onClick={() => setMobileOpen(false)}>
          <NavButton to="/settings" icon="⚙" label="Settings" />
        </nav>
      </aside>
      <div className="content-wrap">
        <header className="topbar">
          <div className="topbar-title">
            <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}>☰</button>
            <div>
              <h1 className="page-title">{title}</h1>
            </div>
          </div>
          <div className="top-actions">
            {googleConnected ? (
              <div className="sync-pill"><span className="sync-dot" /><span>Google connected</span></div>
            ) : (
              <button className="btn btn-primary btn-sm" onClick={() => void onConnectGoogle()}>Connect Google</button>
            )}
          </div>
        </header>
        {children}
      </div>
      <nav className="mobile-bottom" aria-label="Mobile navigation">
        <NavButton to="/" icon="⌂" label="Home" />
        <NavButton to="/assignments" icon="✓" label="Tasks" />
        <NavButton to="/planner" icon="□" label="Planner" />
        <button type="button" onClick={() => setMobileOpen(true)}><span>☰</span><span>More</span></button>
      </nav>
    </div>
  );
}
