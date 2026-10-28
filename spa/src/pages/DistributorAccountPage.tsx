import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { MyAccount } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";

export function DistributorAccountPage({ onChange }: { onChange: () => void }) {
  const [account, setAccount] = useState<MyAccount | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .getMyAccount()
      .then((a) => !cancelled && setAccount(a))
      .catch((e) => !cancelled && setError(String(e.message || e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <p className="muted">Loading account…</p>;
  if (error) return <div className="notice err">{error}</div>;
  if (!account) return <div className="notice warn">No account found.</div>;

  return (
    <div className="card">
      <h2>{account.CompanyName}</h2>
      <p>
        Status: <StatusBadge status={account.Status} />
      </p>
      <table>
        <tbody>
          <tr>
            <th>Loyalty tier</th>
            <td>{account.LoyaltyTierCode || <span className="muted">not assigned</span>}</td>
          </tr>
          <tr>
            <th>Application status</th>
            <td><StatusBadge status={account.ApplicationStatus} /></td>
          </tr>
          {account.ReviewReason && (
            <tr>
              <th>Reviewer note</th>
              <td>{account.ReviewReason}</td>
            </tr>
          )}
        </tbody>
      </table>

      {account.Status === "APPROVED" && (
        <div className="notice ok" style={{ marginTop: 16 }}>
          Your account is approved. Configuration and quoting are now available.
        </div>
      )}
      {account.Status === "CHANGES_REQUESTED" && (
        <div className="notice warn" style={{ marginTop: 16 }}>
          Changes were requested on your application. Please contact your administrator.
        </div>
      )}
      {account.Status === "PENDING_APPROVAL" && (
        <div className="notice" style={{ marginTop: 16 }}>
          Your application is pending review.{" "}
          <button className="btn secondary" onClick={onChange}>Refresh</button>
        </div>
      )}
    </div>
  );
}
