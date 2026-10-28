import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { DistributorReviewCase, DistributorReviewLine } from "../api/types";
import { money } from "../format";
import { StatusBadge } from "../components/StatusBadge";

// A5: distributor-facing view of submitted review cases. Shows the reviewed
// revision (engineer-resolved prices / custom specs / lead time) and offers
// Request Further Review. (A6 adds Confirm Order + PDF to the completed view.)
export function MyReviewsPage({
  renderCompletedActions,
}: {
  // A6 injects Confirm Order / PDF actions for a COMPLETED case.
  renderCompletedActions?: (c: DistributorReviewCase, lines: DistributorReviewLine[]) => React.ReactNode;
}) {
  const [cases, setCases] = useState<DistributorReviewCase[]>([]);
  const [selected, setSelected] = useState<{ case: DistributorReviewCase; lines: DistributorReviewLine[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api
      .listMyReviewCases()
      .then((r) => setCases(r.cases))
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function open(id: number) {
    api.getMyReviewCase(id).then(setSelected).catch((e) => setError(String(e.message || e)));
  }

  async function furtherReview(id: number) {
    const notes = window.prompt("What further review do you need? (optional comments)") ?? undefined;
    try {
      await api.requestFurtherReview(id, notes);
      setSelected(null);
      load();
    } catch (e) {
      const a = e as ApiError;
      setError(typeof a.detail === "string" ? a.detail : a.message);
    }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>My engineering reviews</h2>
        {error && <div className="notice err">{error}</div>}
        {loading ? (
          <p className="muted">Loading…</p>
        ) : cases.length === 0 ? (
          <p className="muted">You have not submitted any quotes for review.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Case</th>
                <th>Quote</th>
                <th>Brand/Site</th>
                <th>Status</th>
                <th>Rev</th>
                <th>Lead time</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.ReviewCaseId}>
                  <td>#{c.ReviewCaseId}</td>
                  <td>{c.QuoteNumber}</td>
                  <td>{c.Brand}/{c.ResponsibleSiteCode}</td>
                  <td><StatusBadge status={c.Status} /></td>
                  <td>{c.RevisionNo}</td>
                  <td>{c.LeadTimeDays != null ? `${c.LeadTimeDays} days` : "—"}</td>
                  <td>
                    <button className="btn secondary" onClick={() => open(c.ReviewCaseId)}>
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h2 style={{ margin: 0 }}>
              Reviewed revision — case #{selected.case.ReviewCaseId}{" "}
              <StatusBadge status={selected.case.Status} />
            </h2>
            <button className="btn secondary" onClick={() => setSelected(null)}>Close</button>
          </div>
          <p className="muted">
            Quote {selected.case.QuoteNumber} · {selected.case.Brand}/{selected.case.ResponsibleSiteCode}
            {selected.case.LeadTimeDays != null ? ` · lead time ${selected.case.LeadTimeDays} days` : ""}
            {` · revision ${selected.case.RevisionNo}`}
          </p>
          {selected.case.ReviewNotes && <blockquote>{selected.case.ReviewNotes}</blockquote>}

          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Part number</th>
                <th>Pricing</th>
                <th style={{ textAlign: "right" }}>Resolved price</th>
                <th>Custom spec</th>
              </tr>
            </thead>
            <tbody>
              {selected.lines.map((l) => (
                <tr key={l.ReviewCaseLineId}>
                  <td>{l.LineNumber}</td>
                  <td>{l.PartNumber}</td>
                  <td>{l.PricingStatus}</td>
                  <td style={{ textAlign: "right" }}>
                    {l.ResolvedUnitPrice != null ? money(l.ResolvedUnitPrice) : <span className="muted">—</span>}
                  </td>
                  <td>{l.CustomSpec || <span className="muted">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {selected.case.Status === "COMPLETED" && (
            <div className="actions">
              {renderCompletedActions?.(selected.case, selected.lines)}
              <button className="btn secondary" onClick={() => furtherReview(selected.case.ReviewCaseId)}>
                Request further review
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
