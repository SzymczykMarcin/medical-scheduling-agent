import { CalendarDays, HeartPulse, Mic } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

export function AppShell() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="clinic-brand" aria-label="Dane placówki">
          <div className="clinic-mark">
            <HeartPulse size={22} aria-hidden="true" />
          </div>
          <div>
            <div className="clinic-name">Nazwa placówki</div>
            <div className="clinic-subtitle">Asystent umawiania wizyt</div>
          </div>
        </div>
        <nav className="nav" aria-label="Główna nawigacja">
          <NavLink to="/record">
            <Mic size={17} aria-hidden="true" /> Nagranie
          </NavLink>
          <NavLink to="/calendar">
            <CalendarDays size={17} aria-hidden="true" /> Kalendarz
          </NavLink>
        </nav>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
