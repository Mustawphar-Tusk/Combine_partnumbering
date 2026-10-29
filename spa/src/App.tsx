import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useMe } from "./useMe";
import { DevRoleSwitcher } from "./components/DevRoleSwitcher";
import { HomePage } from "./pages/HomePage";
import { DistributorOnboardingPage } from "./pages/DistributorOnboardingPage";
import { DistributorAccountPage } from "./pages/DistributorAccountPage";
import { AdminApplicationsPage } from "./pages/AdminApplicationsPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { ConfiguratorPage } from "./pages/ConfiguratorPage";
import { QuotesListPage } from "./pages/QuotesListPage";
import { QuoteWorkspacePage } from "./pages/QuoteWorkspacePage";
import { LookupPage } from "./pages/LookupPage";
import { ApplicationsQueuePage } from "./pages/ApplicationsQueuePage";
import { MyReviewsPage } from "./pages/MyReviewsPage";

export function App() {
  const meState = useMe();
  const { me, loading, error, reload } = meState;

  const caps = me?.capabilities;
  const isEngineer = !!me?.user.roles.includes("engineering");
  // A quote author is anyone who can create (distributor) OR author (engineer) a quote.
  const canQuote = !!(caps?.create_quote || caps?.author_quote);

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
          {caps?.configure && (
            <NavLink
              to="/configure"
              className={({ isActive }) => "navlink" + (isActive ? " active" : "")}
            >
              Configurator
            </NavLink>
          )}
          {canQuote && (
            <NavLink
              to="/quotes"
              className={({ isActive }) => "navlink" + (isActive ? " active" : "")}
            >
              Quotes
            </NavLink>
          )}
          {caps?.is_distributor && (
            <NavLink
              to="/my-reviews"
              className={({ isActive }) => "navlink" + (isActive ? " active" : "")}
            >
              My Reviews
            </NavLink>
          )}
          {caps?.configure && (
            <NavLink
              to="/lookup"
              className={({ isActive }) => "navlink" + (isActive ? " active" : "")}
            >
              Look up
            </NavLink>
          )}
          {isEngineer && (
            <NavLink
              to="/applications"
              className={({ isActive }) => "navlink" + (isActive ? " active" : "")}
            >
              Engineering
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
            <Route
              path="/configure"
              element={caps?.configure ? <ConfiguratorPage me={me} /> : <Navigate to="/" replace />}
            />
            <Route
              path="/lookup"
              element={caps?.configure ? <LookupPage /> : <Navigate to="/" replace />}
            />
            <Route
              path="/quotes"
              element={canQuote ? <QuotesListPage /> : <Navigate to="/" replace />}
            />
            <Route
              path="/quotes/:id"
              element={canQuote ? <QuoteWorkspacePage /> : <Navigate to="/" replace />}
            />
            <Route
              path="/applications"
              element={isEngineer ? <ApplicationsQueuePage /> : <Navigate to="/" replace />}
            />
            <Route
              path="/my-reviews"
              element={caps?.is_distributor ? <MyReviewsPage /> : <Navigate to="/" replace />}
            />
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        )}
      </main>
    </div>
  );
}
