import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { QuoteDocument, QuotePricing } from "../api/types";
import { money } from "../format";
import { StatusBadge } from "../components/StatusBadge";
import { QuotePartyCard } from "../components/QuotePartyCard";
import { downloadOrderPdf } from "../orderPdf";
import { useMe } from "../useMe";
import { getDraft, setEditContext, type ConfigDraft } from "../draft";

// Line pricing status rendered as a reference-style chip.
function lineChip(status: string) {
  if (status === "found") return <span className="chip green">Standard</span>;
  if (status === "partial")
    return <span className="chip amber">Partial — needs review</span>;
  return <span className="chip amber">Contact factory</span>;
}

export function QuoteWorkspacePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const quoteId = Number(id);
  const [doc, setDoc] = useState<QuoteDocument | null>(null);
  const [pricing, setPricing] = useState<QuotePricing | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [draft, setDraftState] = useState<ConfigDraft | null>(null);
  const [adding, setAdding] = useState(false);
  const [qty, setQty] = useState(1);

  const [unresolved, setUnresolved] = useState<
    import("../api/types").QuoteUnresolved | null
  >(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .getQuoteUnresolved("FYBROC", quoteId)
      .then(setUnresolved)
      .catch(() => setUnresolved(null));
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

  const { me } = useMe();
  const canAuthor = !!me?.capabilities?.author_quote;

  // U4: engineer self-serve completion state.
  const [leadDays, setLeadDays] = useState<number>(14);
  const [completeMsg, setCompleteMsg] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [orderCaseId, setOrderCaseId] = useState<number | null>(null);

  async function engineerComplete() {
    if (!doc) return;
    setCompleting(true);
    setError(null);
    setCompleteMsg(null);
    try {
      // Resolve any Contact-Factory lines at their current unit price so the
      // A5 completion gate passes (engineer self-serve authoring).
      const linePrices = doc.lines
        .filter((l) => l.pricing_status !== "found")
        .map((l) => ({
          line_number: l.line_number,
          resolved_unit_price: l.unit_price || 0,
        }));
      const r = await api.engineerCompleteQuote(quoteId, {
        lead_time_days: leadDays,
        line_prices: linePrices,
      });
      setOrderCaseId(r.review_case_id);
      setCompleteMsg(
        `Completed and confirmed as ${r.cpq_order_number}${r.was_existing ? " (already confirmed)" : ""}.`,
      );
      load();
    } catch (err) {
      const e = err as ApiError;
      setError(typeof e.detail === "string" ? e.detail : e.message);
    } finally {
      setCompleting(false);
    }
  }

  async function downloadPdf() {
    if (orderCaseId == null) return;
    setError(null);
    try {
      const order = await api.getOrderByCase(orderCaseId);
      downloadOrderPdf(order);
    } catch (err) {
      const e = err as ApiError;
      setError(typeof e.detail === "string" ? e.detail : e.message);
    }
  }

  const [reviewMsg, setReviewMsg] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  async function submitForReview() {
    setSubmitting(true);
    setError(null);
    setReviewMsg(null);
    try {
      const r = await api.submitQuoteForReview(quoteId);
      setReviewMsg(
        r.routing_exception
          ? `Submitted, but routing needs admin attention (brand/site could not be resolved).`
          : `Submitted to ${r.brand} engineering (${r.responsible_site_code})${r.was_existing ? " — already in review" : ""}.`,
      );
    } catch (err) {
      const e = err as ApiError;
      setError(typeof e.detail === "string" ? e.detail : e.message);
    } finally {
      setSubmitting(false);
    }
  }

  // A1: open the configurator seeded with a line's saved config, to edit in place.
  async function editLine(l: QuoteDocument["lines"][number]) {
    try {
      const cfg = await api.getQuoteLineConfig(l.family, quoteId, l.quote_line_id);
      const { SERIES: _series, ...sel } = cfg.selections;
      setEditContext({
        family: cfg.family,
        series: cfg.series || _series || "",
        quoteHeaderId: quoteId,
        quoteLineId: l.quote_line_id,
        selections: sel,
        quantity: cfg.quantity,
      });
      navigate("/configure");
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }

  async function removeLine(l: QuoteDocument["lines"][number]) {
    setError(null);
    try {
      await api.removeQuoteLine(l.family, quoteId, l.quote_line_id);
      load();
    } catch (err) {
      const e = err as ApiError;
      setError(typeof e.detail === "string" ? e.detail : e.message);
    }
  }

  if (loading) return <p className="muted">Loading quote…</p>;
  if (error && !doc) return <div className="notice err">{error}</div>;
  if (!doc || !pricing) return <div className="notice warn">Quote not found.</div>;

  const currency = doc.currency;
  const isDraft = doc.status === "Draft";

  return (
    <>
      <Link to="/quotes" className="link back">
        ← All quotes
      </Link>

      <div className="page-head">
        <div>
          <h1>
            <span className="mono">{doc.quote_number}</span>{" "}
            <StatusBadge status={doc.status} />
          </h1>
          <p className="lede">
            {doc.customer_name || "No customer yet"} · Site {doc.site_code} ·{" "}
            {currency}
          </p>
        </div>
      </div>

      {error && <div className="notice err">{error}</div>}

      {/* Quote metadata strip — reference .qmeta (Customer / Account / Site / Currency). */}
      <section className="qmeta">
        <label>
          Customer
          <span>{doc.customer_name || "—"}</span>
        </label>
        <label>
          Account
          <span>{doc.customer_account || "—"}</span>
        </label>
        <label>
          Site
          <span>{doc.site_code}</span>
        </label>
        <label>
          Currency
          <span>{currency}</span>
        </label>
      </section>

      {/* U4: customer contact + ship-to (engineer-authored quotes). */}
      {canAuthor && (
        <div className="party-grid" style={{ marginBottom: "1rem" }}>
          <QuotePartyCard
            quoteId={quoteId}
            kind="CONTACT"
            title="Customer contact"
            editable={isDraft}
          />
          <QuotePartyCard
            quoteId={quoteId}
            kind="SHIP_TO"
            title="Ship to"
            editable={isDraft}
          />
        </div>
      )}

      {/* Lines grid — reference .lines presentation. */}
      <div className="tablewrap" style={{ marginBottom: "1rem" }}>
        <table className="grid lines">
          <thead>
            <tr>
              <th className="num">#</th>
              <th>Part number</th>
              <th className="num">Qty</th>
              <th className="num">Unit</th>
              <th className="num">Extended</th>
              <th>Pricing</th>
              {isDraft && <th></th>}
            </tr>
          </thead>
          <tbody>
            {doc.lines.length === 0 ? (
              <tr>
                <td className="emptyrow" colSpan={isDraft ? 7 : 6}>
                  No pumps on this quote yet. Configure one below.
                </td>
              </tr>
            ) : (
              doc.lines.map((l) => (
                <tr key={l.line_number}>
                  <td className="num">{l.line_number}</td>
                  <td>
                    <div className="mono strong">{l.part_number}</div>
                    <div className="sub" style={{ fontSize: 12 }}>
                      {l.family} · SKU {l.sku}
                    </div>
                    <div className="chips">{lineChip(l.pricing_status)}</div>
                  </td>
                  <td className="num">{l.quantity}</td>
                  <td className="num">{money(l.unit_price, currency)}</td>
                  <td className="num strong">
                    {money(l.extended_price, currency)}
                  </td>
                  <td>{lineChip(l.pricing_status)}</td>
                  {isDraft && (
                    <td>
                      <div className="row" style={{ gap: 6 }}>
                        <button
                          className="btn secondary sm"
                          onClick={() => editLine(l)}
                        >
                          Edit
                        </button>
                        <button
                          className="btn danger sm"
                          onClick={() => removeLine(l)}
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
          {doc.lines.length > 0 && (
            <tfoot>
              <tr>
                <td className="num" colSpan={isDraft ? 6 : 5}>
                  List total
                </td>
                <td className="num strong big">
                  {money(pricing.list_total, currency)}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {/* Add-a-pump bar — reference .addbar. */}
      {isDraft && (
        <section className="addbar">
          <div>
            <span className="lbl">Configure a pump</span>
            {draft ? (
              <>
                <div style={{ flex: 1, minWidth: 200 }}>
                  <div className="mono strong">{draft.part_number}</div>
                  <div className="sub" style={{ fontSize: 12 }}>
                    {draft.family} {draft.series} · SKU {draft.sku} · list{" "}
                    {money(draft.total_price, currency)}
                  </div>
                </div>
                <div
                  className="field"
                  style={{ margin: 0, width: 84 }}
                >
                  <label htmlFor="qty">Qty</label>
                  <input
                    id="qty"
                    type="number"
                    min={1}
                    value={qty}
                    onChange={(e) =>
                      setQty(Math.max(1, Number(e.target.value) || 1))
                    }
                  />
                </div>
                <button
                  className="btn primary"
                  onClick={addDraft}
                  disabled={adding}
                >
                  {adding ? "Adding…" : "Add to quote"}
                </button>
              </>
            ) : (
              <span className="sub">
                Build a configuration in the{" "}
                <Link to="/configure">Configurator</Link>, then come back to add
                it.
              </span>
            )}
          </div>
        </section>
      )}

      {/* U4: engineer self-serve completion. */}
      {canAuthor && (
        <section className="card">
          <h3 style={{ marginTop: 0 }}>Complete this quote</h3>
          <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
            As an application engineer you can complete this quote directly —
            it is submitted, resolved, completed, and confirmed as a CPQ order in
            one step, then you can download the PDF. Any Contact-Factory line is
            resolved at its current unit price.
          </p>
          {completeMsg && <div className="notice ok">{completeMsg}</div>}
          <div className="actions">
            <div className="field" style={{ margin: 0, width: 150 }}>
              <label htmlFor="lead">Lead time (days)</label>
              <input
                id="lead"
                type="number"
                min={1}
                value={leadDays}
                onChange={(e) =>
                  setLeadDays(Math.max(1, Number(e.target.value) || 1))
                }
                disabled={!isDraft}
              />
            </div>
            <button
              className="btn primary"
              onClick={engineerComplete}
              disabled={completing || !isDraft || doc.lines.length === 0}
            >
              {completing ? "Completing…" : "Complete & confirm order"}
            </button>
            {orderCaseId != null && (
              <button className="btn secondary" onClick={downloadPdf}>
                Download PDF
              </button>
            )}
          </div>
          {!isDraft && orderCaseId == null && (
            <p className="muted" style={{ fontSize: 12 }}>
              This quote is no longer a draft.
            </p>
          )}
        </section>
      )}

      {/* Engineering review. */}
      <section className="card">
        <h3 style={{ marginTop: 0 }}>Engineering review</h3>
        {reviewMsg && <div className="notice ok">{reviewMsg}</div>}
        {unresolved && unresolved.requires_review && (
          <div className="notice warn">
            <strong>
              {unresolved.unresolved_count} item(s) require engineering review.
            </strong>
            <ul style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 13 }}>
              {unresolved.items.map((it, i) => (
                <li key={i}>
                  Line {it.line_number}:{" "}
                  {it.kind === "pricing" ? (
                    <>
                      {it.part_number} —{" "}
                      <span className="amber-t">Contact Factory</span> (
                      {it.pricing_status})
                    </>
                  ) : (
                    <>
                      customization ({it.grouping}
                      {it.field_code ? ` · ${it.field_code}` : ""}):{" "}
                      {it.requested_change}
                    </>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {unresolved && !unresolved.requires_review && (
          <div className="notice ok">
            No unresolved items — all lines are priced and standard.
          </div>
        )}
        <p className="muted" style={{ fontSize: 13 }}>
          Submit this quote to the responsible engineering team. Routing is by
          the ordered brand (Dean → Indianapolis, Fybroc → Telford).
        </p>
        <div className="actions">
          <button
            className="btn primary"
            onClick={submitForReview}
            disabled={submitting || doc.lines.length === 0}
          >
            {submitting ? "Submitting…" : "Submit for review"}
          </button>
          {doc.lines.length === 0 && (
            <span className="muted" style={{ fontSize: 13 }}>
              Add at least one line first.
            </span>
          )}
        </div>
      </section>

      {/* Totals. */}
      <section className="card">
        <h3 style={{ marginTop: 0 }}>Totals</h3>
        <table>
          <tbody>
            <tr>
              <td>List total</td>
              <td className="num">{money(pricing.list_total, currency)}</td>
            </tr>
            <tr>
              <td>
                Merchandise subtotal (priced lines)
                {pricing.unpriced_line_count > 0 && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    {" "}
                    · {pricing.unpriced_line_count} unpriced line
                    {pricing.unpriced_line_count > 1 ? "s" : ""} excluded from
                    discount
                  </span>
                )}
              </td>
              <td className="num">
                {money(pricing.merchandise_subtotal, currency)}
              </td>
            </tr>
            <tr>
              <td>
                Loyalty discount
                {pricing.loyalty_tier_code && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    {" "}
                    · {pricing.loyalty_tier_code} (
                    {(pricing.discount_rate_bp / 100).toFixed(0)}%)
                  </span>
                )}
              </td>
              <td
                className="num"
                style={{
                  color:
                    pricing.discount_amount > 0 ? "var(--green)" : undefined,
                }}
              >
                {pricing.discount_amount > 0 ? "−" : ""}
                {money(pricing.discount_amount, currency)}
              </td>
            </tr>
            <tr style={{ fontWeight: 700 }}>
              <td>Net total</td>
              <td className="num">{money(pricing.net_total, currency)}</td>
            </tr>
          </tbody>
        </table>
        {pricing.discount_rate_bp === 0 && (
          <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>
            No loyalty discount applies to this account (list pricing).
          </p>
        )}
      </section>
    </>
  );
}
