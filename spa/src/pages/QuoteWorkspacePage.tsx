import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { QuoteDocument, QuotePricing } from "../api/types";
import { money } from "../format";
import { StatusBadge } from "../components/StatusBadge";
import { getDraft, type ConfigDraft } from "../draft";

function lineStatusBadge(status: string) {
  const cls = status === "found" ? "approved" : status === "partial" ? "pending" : "rejected";
  const label = status === "call_for_price" ? "call for price" : status;
  return <span className={`badge ${cls}`}>{label}</span>;
}

export function QuoteWorkspacePage() {
  const { id } = useParams();
  const quoteId = Number(id);
  const [doc, setDoc] = useState<QuoteDocument | null>(null);
  const [pricing, setPricing] = useState<QuotePricing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [draft, setDraftState] = useState<ConfigDraft | null>(null);
  const [adding, setAdding] = useState(false);
  const [qty, setQty] = useState(1);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([api.getQuote("FYBROC", quoteId), api.getQuotePricing(quoteId)])
      .then(([d, p]) => {
        setDoc(d);
        setPricing(p);
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [quoteId]);

  useEffect(() => {
    load();
    setDraftState(getDraft());
  }, [load]);

  async function addDraft() {
    if (!draft) return;
    setAdding(true);
    setError(null);
    try {
      await api.addQuoteLine(draft.family, quoteId, {
        series: draft.series,
        selections: { SERIES: draft.series, ...draft.selections },
        quantity: qty,
      });
      load();
    } catch (err) {
      const e = err as ApiError;
      setError(typeof e.detail === "string" ? e.detail : e.message);
    } finally {
      setAdding(false);
    }
  }

  if (loading) return <p className="muted">Loading quote…</p>;
  if (error && !doc) return <div className="notice err">{error}</div>;
  if (!doc || !pricing) return <div className="notice warn">Quote not found.</div>;

  const currency = doc.currency;

  return (
    <>
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 style={{ margin: 0 }}>
            Quote {doc.quote_number} <StatusBadge status={doc.status} />
          </h2>
          <Link to="/quotes" className="btn secondary">All quotes</Link>
        </div>
        <p className="muted">
          {doc.customer_name || "No customer"} · Site {doc.site_code} · {currency}
        </p>
      </div>

      {error && <div className="notice err">{error}</div>}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Add current configuration</h3>
        {draft ? (
          <div className="row" style={{ gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div>
              <div style={{ fontWeight: 600 }}>{draft.part_number}</div>
              <div className="muted" style={{ fontSize: 13 }}>
                {draft.family} {draft.series} · SKU {draft.sku} · list {money(draft.total_price, currency)}
              </div>
            </div>
            <div className="field" style={{ margin: 0, width: 90 }}>
              <label htmlFor="qty">Qty</label>
              <input
                id="qty"
                type="number"
                min={1}
                value={qty}
                onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
              />
            </div>
            <button className="btn" onClick={addDraft} disabled={adding}>
              {adding ? "Adding…" : "Add to quote"}
            </button>
          </div>
        ) : (
          <p className="muted">
            Build a configuration in the <Link to="/configure">Configurator</Link>, then come back to add it.
          </p>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Lines</h3>
        {doc.lines.length === 0 ? (
          <p className="muted">No lines yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Part number</th>
                <th>Qty</th>
                <th style={{ textAlign: "right" }}>Unit</th>
                <th style={{ textAlign: "right" }}>Extended</th>
                <th>Pricing</th>
              </tr>
            </thead>
            <tbody>
              {doc.lines.map((l) => (
                <tr key={l.line_number}>
                  <td>{l.line_number}</td>
                  <td>{l.part_number}</td>
                  <td>{l.quantity}</td>
                  <td style={{ textAlign: "right" }}>{money(l.unit_price, currency)}</td>
                  <td style={{ textAlign: "right" }}>{money(l.extended_price, currency)}</td>
                  <td>{lineStatusBadge(l.pricing_status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Totals</h3>
        <table>
          <tbody>
            <tr>
              <td>List total</td>
              <td style={{ textAlign: "right" }}>{money(pricing.list_total, currency)}</td>
            </tr>
            <tr>
              <td>
                Merchandise subtotal (priced lines)
                {pricing.unpriced_line_count > 0 && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    {" "}
                    · {pricing.unpriced_line_count} unpriced line
                    {pricing.unpriced_line_count > 1 ? "s" : ""} excluded from discount
                  </span>
                )}
              </td>
              <td style={{ textAlign: "right" }}>{money(pricing.merchandise_subtotal, currency)}</td>
            </tr>
            <tr>
              <td>
                Loyalty discount
                {pricing.loyalty_tier_code && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    {" "}
                    · {pricing.loyalty_tier_code} ({(pricing.discount_rate_bp / 100).toFixed(0)}%)
                  </span>
                )}
              </td>
              <td style={{ textAlign: "right", color: pricing.discount_amount > 0 ? "var(--ok)" : undefined }}>
                {pricing.discount_amount > 0 ? "−" : ""}
                {money(pricing.discount_amount, currency)}
              </td>
            </tr>
            <tr style={{ fontWeight: 700 }}>
              <td>Net total</td>
              <td style={{ textAlign: "right" }}>{money(pricing.net_total, currency)}</td>
            </tr>
          </tbody>
        </table>
        {pricing.discount_rate_bp === 0 && (
          <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>
            No loyalty discount applies to this account (list pricing).
          </p>
        )}
      </div>
    </>
  );
}
