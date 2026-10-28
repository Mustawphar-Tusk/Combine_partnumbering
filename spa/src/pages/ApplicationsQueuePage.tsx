import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ReviewCaseDetail, ReviewCaseListItem } from "../api/types";
import { money } from "../format";
import { downloadOrderPdf } from "../orderPdf";

function reviewBadge(status: string) {
  const cls =
    status === "COMPLETED"
      ? "approved"
      : status === "ROUTING_EXCEPTION" || status === "CANCELLED"
        ? "rejected"
        : status === "CHANGES_REQUESTED"
          ? "changes"
          : "pending";
  return <span className={`badge ${cls}`}>{status.replace(/_/g, " ").toLowerCase()}</span>;
}

export function ApplicationsQueuePage() {
  const [cases, setCases] = useState<ReviewCaseListItem[]>([]);
  const [sites, setSites] = useState<string[]>([]);
  const [filter, setFilter] = useState<string>("");
  const [selected, setSelected] = useState<ReviewCaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api
      .listReviewCases(filter || undefined)
      .then((r) => {
        setCases(r.cases);
        setSites(r.authorized_sites);
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  function open(id: number) {
    api
      .getReviewCase(id)
      .then(setSelected)
      .catch((e) => setError(String(e.message || e)));
  }

  return (
    <>
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>
            Engineering queue{sites.length ? ` · ${sites.join(", ")}` : ""}
          </h2>
          <div className="field" style={{ margin: 0 }}>
            <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Status filter">
              <option value="">All</option>
              <option value="PENDING_REVIEW">Pending</option>
              <option value="CLAIMED">Claimed</option>
              <option value="CHANGES_REQUESTED">Changes requested</option>
              <option value="COMPLETED">Completed</option>
              <option value="ROUTING_EXCEPTION">Routing exception</option>
            </select>
          </div>
        </div>
        {error && <div className="notice err">{error}</div>}
        {loading ? (
          <p className="muted">Loading…</p>
        ) : cases.length === 0 ? (
          <p className="muted">No cases in your queue.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Case</th>
                <th>Quote</th>
                <th>Customer</th>
                <th>Brand/Site</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.ReviewCaseId}>
                  <td>#{c.ReviewCaseId}</td>
                  <td>{c.QuoteNumber}</td>
                  <td>{c.CustomerName || <span className="muted">—</span>}</td>
                  <td>
                    {c.Brand} / {c.ResponsibleSiteCode}
                    {c.RoutingException && <span style={{ color: "var(--err)" }}> ⚠</span>}
                  </td>
                  <td>{reviewBadge(c.Status)}</td>
                  <td>
                    <button className="btn secondary" onClick={() => open(c.ReviewCaseId)}>
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <CaseDetail
          detail={selected}
          onClose={() => setSelected(null)}
          onChanged={() => {
            load();
            open(selected.case.ReviewCaseId);
          }}
        />
      )}
    </>
  );
}

function CaseDetail({
  detail,
  onClose,
  onChanged,
}: {
  detail: ReviewCaseDetail;
  onClose: () => void;
  onChanged: () => void;
}) {
  const c = detail.case;
  const [leadTime, setLeadTime] = useState<string>(c.LeadTimeDays?.toString() ?? "");
  const [err, setErr] = useState<string | null>(null);
  const claimed = c.Status === "CLAIMED" || c.Status === "CHANGES_REQUESTED";
  const terminal = c.Status === "COMPLETED" || c.Status === "CANCELLED";

  async function act(fn: () => Promise<unknown>) {
    setErr(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      const a = e as ApiError;
      setErr(typeof a.detail === "string" ? a.detail : a.message);
    }
  }

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>
          Case #{c.ReviewCaseId} — {c.Brand}/{c.ResponsibleSiteCode} {reviewBadge(c.Status)}
        </h2>
        <button className="btn secondary" onClick={onClose}>Close</button>
      </div>
      <p className="muted">
        Quote {c.QuoteNumber} · {c.CustomerName || "no customer"} · revision {c.RevisionNo}
      </p>
      {c.RoutingException && (
        <div className="notice err">
          Routing exception — this case needs admin resolution (brand/site could not be
          determined cleanly).
        </div>
      )}
      {err && <div className="notice err">{err}</div>}

      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Part number</th>
            <th>Pricing</th>
            <th>Resolved price</th>
            <th>Custom spec</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {detail.lines.map((l) => (
            <ReviewLineRow
              key={l.ReviewCaseLineId}
              caseId={c.ReviewCaseId}
              line={l}
              editable={claimed}
              onResolved={onChanged}
            />
          ))}
        </tbody>
      </table>

      <div className="row" style={{ marginTop: 16, gap: 10, flexWrap: "wrap" }}>
        {c.Status === "PENDING_REVIEW" && (
          <button className="btn" onClick={() => act(() => api.claimReviewCase(c.ReviewCaseId))}>
            Claim
          </button>
        )}
        {claimed && (
          <>
            <div className="field" style={{ margin: 0, width: 140 }}>
              <label htmlFor="lead">Lead time (days)</label>
              <input
                id="lead"
                type="number"
                min={0}
                value={leadTime}
                onChange={(e) => setLeadTime(e.target.value)}
              />
            </div>
            <button
              className="btn"
              onClick={() =>
                act(() =>
                  api.completeReviewCase(c.ReviewCaseId, {
                    lead_time_days: leadTime === "" ? null : Number(leadTime),
                  }),
                )
              }
            >
              Complete review
            </button>
            <button
              className="btn secondary"
              onClick={() => act(() => api.requestReviewChanges(c.ReviewCaseId, "Changes requested"))}
            >
              Request changes
            </button>
          </>
        )}
        {terminal && (
          <>
            <span className="muted">
              {c.Status === "COMPLETED"
                ? `Completed${c.LeadTimeDays != null ? ` · lead time ${c.LeadTimeDays} days` : ""}.`
                : "Closed."}
            </span>
            {c.Status === "COMPLETED" && (
              <button
                className="btn secondary"
                onClick={() =>
                  act(async () => {
                    const order = await api.getOrderByCase(c.ReviewCaseId);
                    downloadOrderPdf(order);
                  })
                }
              >
                Download order PDF
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ReviewLineRow({
  caseId,
  line,
  editable,
  onResolved,
}: {
  caseId: number;
  line: import("../api/types").ReviewCaseLine;
  editable: boolean;
  onResolved: () => void;
}) {
  const [price, setPrice] = useState(line.ResolvedUnitPrice?.toString() ?? "");
  const [spec, setSpec] = useState(line.CustomSpec ?? "");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await api.resolveReviewLine(caseId, line.ReviewCaseLineId, {
        resolved_unit_price: price === "" ? null : Number(price),
        custom_spec: spec || undefined,
      });
      onResolved();
    } finally {
      setSaving(false);
    }
  }

  return (
    <tr>
      <td>{line.LineNumber}</td>
      <td>{line.PartNumber}</td>
      <td>{line.PricingStatus}</td>
      <td>
        {editable ? (
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            style={{ width: 110 }}
            placeholder="price"
          />
        ) : line.ResolvedUnitPrice != null ? (
          money(line.ResolvedUnitPrice)
        ) : (
          <span className="muted">—</span>
        )}
      </td>
      <td>
        {editable ? (
          <input value={spec} onChange={(e) => setSpec(e.target.value)} placeholder="custom spec" />
        ) : (
          line.CustomSpec || <span className="muted">—</span>
        )}
      </td>
      <td>
        {editable && (
          <button className="btn secondary" onClick={save} disabled={saving}>
            {saving ? "…" : "Save"}
          </button>
        )}
      </td>
    </tr>
  );
}
