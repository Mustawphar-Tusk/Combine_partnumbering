import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useMe } from "./useMe";
import { DevRoleSwitcher } from "./components/DevRoleSwitcher";
import { HomePage } from "./pages/HomePage";
import { DistributorOnboardingPage } from "./pages/DistributorOnboardingPage";
import { DistributorAccountPage } from "./pages/DistributorAccountPage";
import { AdminApplicationsPage } from "./pages/AdminApplicationsPage";
import { NotificationsPage } from "./pages/NotificationsPage";

export function App() {
  const meState = useMe();
  const { me, loading, error, reload } = meState;

  const caps = me?.capabilities;

  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="brand">CPQ Portal</span>
        <nav>
          <NavLink to="/" end className={({ isActive }) => "navlink" + (isActive ? " active" : "")}>
            Home
          </NavLink>
          {caps?.is_distributor && (
            <NavLink
              to="/distributor"
              className={({ isActive }) => "navlink" + (isActive ? " active" : "")}
            >
              My Account
            </NavLink>
          )}
          {caps?.review_applications && (
            <NavLink
              to="/admin/applications"
              className={({ isActive }) => "navlink" + (isActive ? " active" : "")}
            >
              Applications
            </NavLink>
          )}
          <NavLink
            to="/notifications"
            className={({ isActive }) => "navlink" + (isActive ? " active" : "")}
          >
            Notifications
          </NavLink>
        </nav>
        <span className="spacer" />
        {me && (
          <span className="muted" style={{ fontSize: 13 }}>
            {me.user.display_name || me.user.email} ({me.user.roles.join(", ")})
          </span>
        )}
        <DevRoleSwitcher onChange={reload} />
      </header>

      <main className="content">
        {loading && <p className="muted">Loading…</p>}
        {error && <div className="notice err">Could not load identity: {error}</div>}
        {!loading && me && (
          <Routes>
            <Route path="/" element={<HomePage me={me} />} />
            <Route
              path="/distributor"
              element={
                caps?.is_distributor ? (
                  caps.account_status ? (
                    <DistributorAccountPage onChange={reload} />
                  ) : (
                    <DistributorOnboardingPage onSubmitted={reload} />
                  )
                ) : (
                  <Navigate to="/" replace />
                )
              }
            />
            <Route
              path="/distributor/apply"
              element={
                caps?.submit_application ? (
                  <DistributorOnboardingPage onSubmitted={reload} />
                ) : (
                  <Navigate to="/" replace />
                )
              }
            />
            <Route
              path="/admin/applications"
              element={
                caps?.review_applications ? (
                  <AdminApplicationsPage onReviewed={reload} />
                ) : (
                  <Navigate to="/" replace />
                )
              }
            />
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        )}
      </main>
    </div>
  );
}
