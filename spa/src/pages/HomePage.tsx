import { Link } from "react-router-dom";
import type { Me } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";

export function HomePage({ me }: { me: Me }) {
  const caps = me.capabilities;
  return (
    <>
      <div className="card">
        <h2>Welcome</h2>
        <p className="muted">
          Signed in as <strong>{me.user.display_name || me.user.email}</strong> with role(s){" "}
          <strong>{me.user.roles.join(", ")}</strong>.
        </p>
        <p className="muted" style={{ fontSize: 13 }}>
          Identity is provided by Microsoft Entra. In this development build a mock
          identity is used; the dev role switcher (top-right) impersonates roles for
          local testing only.
        </p>
      </div>

      {caps.is_distributor && (
        <div className="card">
          <h2>Distributor</h2>
          {caps.account_status ? (
            <p>
              Your account status: <StatusBadge status={caps.account_status} />.{" "}
              <Link to="/distributor">View my account</Link>
            </p>
          ) : (
            <p>
              You have not applied yet.{" "}
              <Link to="/distributor/apply">Start your distributor application</Link>
            </p>
          )}
          <ul className="muted" style={{ fontSize: 13 }}>
            <li>Configure products: {caps.configure ? "enabled" : "locked until approved"}</li>
            <li>Create quotes: {caps.create_quote ? "enabled" : "locked until approved"}</li>
          </ul>
        </div>
      )}

      {caps.review_applications && (
        <div className="card">
          <h2>Administration</h2>
          <p>
            Review distributor onboarding applications and assign loyalty tiers.{" "}
            <Link to="/admin/applications">Open the applications queue</Link>
          </p>
        </div>
      )}
    </>
  );
}
