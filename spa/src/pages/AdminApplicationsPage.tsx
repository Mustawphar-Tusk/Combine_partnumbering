import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ApplicationDetail, ApplicationListItem, ReviewInput } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";

const LOYALTY_TIERS = [
  { code: "standard", label: "Standard (0%)" },
  { code: "loyalty15", label: "Loyalty 15%" },
  { code: "loyalty30", label: "Loyalty 30%" },
];

export function AdminApplicationsPage({ onReviewed }: { onReviewed: () => void }) {
  const [apps, setApps] = useState<ApplicationListItem[]>([]);
  const [filter, setFilter] = useState<string>("PENDING_APPROVAL");
  const [selected, setSelected] = useState<ApplicationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api
      .listApplications(filter || undefined)
      .then((r) => setApps(r.applications))
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  function openDetail(id: number) {
    api
      .getApplication(id)
      .then(setSelected)
      .catch((e) => setError(String(e.message || e)));
  }

  async function review(id: number, input: ReviewInput) {
    try {
      await api.reviewApplication(id, input);
      setSelected(null);
      load();
      onReviewed();
    } catch (err) {
      const e = err as ApiError;
      setError(typeof e.detail === "string" ? e.detail : e.message);
    }
  }

  return (
    <>
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>Distributor applications</h2>
          <div className="field" style={{ margin: 0 }}>
            <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter by status">
              <option value="">All</option>
              <option value="PENDING_APPROVAL">Pending</option>
              <option value="APPROVED">Approved</option>
              <option value="CHANGES_REQUESTED">Changes requested</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>
        </div>
        {error && <div className="notice err">{error}</div>}
        {loading ? (
          <p className="muted">Loading…</p>
        ) : apps.length === 0 ? (
          <p className="muted">No applications match this filter.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Company</th>
                <th>Submitted by</th>
                <th>Status</th>
                <th>Tier</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {apps.map((a) => (
                <tr key={a.ApplicationId}>
                  <td>{a.ApplicationId}</td>
                  <td>{a.CompanyName}</td>
                  <td className="muted">{a.SubmittedByEmail}</td>
                  <td><StatusBadge status={a.Status} /></td>
                  <td>{a.LoyaltyTierCode || <span className="muted">—</span>}</td>
                  <td>
                    <button className="btn secondary" onClick={() => openDetail(a.ApplicationId)}>
                      Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && <ReviewPanel detail={selected} onReview={review} onClose={() => setSelected(null)} />}
    </>
  );
}

function ReviewPanel({
  detail,
  onReview,
  onClose,
}: {
  detail: ApplicationDetail;
  onReview: (id: number, input: ReviewInput) => void;
  onClose: () => void;
}) {
  const [tier, setTier] = useState("standard");
  const [reason, setReason] = useState("");
  const app = detail.application;
  const isTerminalApproved = app.Status === "APPROVED";

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>
          Application #{app.ApplicationId} — {app.CompanyName}
        </h2>
        <button className="btn secondary" onClick={onClose}>Close</button>
      </div>
      <p>
        Status: <StatusBadge status={app.Status} />
      </p>

      <div className="grid-2">
        {detail.addresses.map((ad) => (
          <div key={ad.AddressId}>
            <h3>{ad.Kind === "CONTACT" ? "Contact" : "Ship-to"}</h3>
            <p className="muted" style={{ fontSize: 13, lineHeight: 1.7 }}>
              {(ad.FirstName || ad.LastName) && (
                <>
                  {ad.FirstName} {ad.LastName}
                  <br />
                </>
              )}
              {ad.Address1}
              <br />
              {ad.Address2 && (
                <>
                  {ad.Address2}
                  <br />
                </>
              )}
              {ad.City}
              {ad.State ? `, ${ad.State}` : ""} {ad.PostalCode}
              <br />
              {ad.Country}
              {ad.Phone && (
                <>
                  <br />
                  {ad.Phone}
                </>
              )}
            </p>
          </div>
        ))}
      </div>

      {isTerminalApproved ? (
        <div className="notice ok">This application is already approved.</div>
      ) : (
        <>
          <div className="grid-2">
            <div className="field">
              <label htmlFor="tier">Loyalty tier (on approval)</label>
              <select id="tier" value={tier} onChange={(e) => setTier(e.target.value)}>
                {LOYALTY_TIERS.map((t) => (
                  <option key={t.code} value={t.code}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="reason">Reason / note (optional)</label>
              <input id="reason" value={reason} onChange={(e) => setReason(e.target.value)} />
            </div>
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <button
              className="btn"
              onClick={() => onReview(app.ApplicationId, { outcome: "APPROVED", loyalty_tier_code: tier, reason: reason || undefined })}
            >
              Approve
            </button>
            <button
              className="btn secondary"
              onClick={() => onReview(app.ApplicationId, { outcome: "CHANGES_REQUESTED", reason: reason || undefined })}
            >
              Request changes
            </button>
            <button
              className="btn danger"
              onClick={() => onReview(app.ApplicationId, { outcome: "REJECTED", reason: reason || undefined })}
            >
              Reject
            </button>
          </div>
        </>
      )}
    </div>
  );
}
