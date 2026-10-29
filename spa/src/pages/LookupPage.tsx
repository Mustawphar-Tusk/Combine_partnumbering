import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { QuoteListItem, SkuLookupResponse } from "../api/types";
import { titleize } from "../format";
import { setSeedContext } from "../draft";
import { useMe } from "../useMe";

export function LookupPage() {
  const [sku, setSku] = useState("");
  const [result, setResult] = useState<SkuLookupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { me } = useMe();
  const canQuote = !!(me?.capabilities?.create_quote || me?.capabilities?.author_quote);

  // Reorder-as-is: quote picker + qty.
  const [quotes, setQuotes] = useState<QuoteListItem[]>([]);
  const [targetQuote, setTargetQuote] = useState<string>("__new");
  const [qty, setQty] = useState(1);
  const [reordering, setReordering] = useState(false);

  useEffect(() => {
    if (!canQuote) return;
    api
      .listQuotes("FYBROC")
      .then((r) => setQuotes(r.quotes.filter((q) => q.status === "Draft")))
      .catch(() => setQuotes([]));
  }, [canQuote, result]);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (!sku.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.lookupBySku(sku.trim());
      setResult(r);
      if (!r.found) setError(r.errors[0] || "Not found.");
    } catch (err) {
      setError(String((err as Error).message || err));
    } finally {
      setLoading(false);
    }
  }

  // EDIT path: reuse this pump as the start of a NEW configuration (editable).
  function configureFromResult() {
    if (!result?.found) return;
    const { SERIES: _series, ...selections } = result.selections as Record<string, string>;
    setSeedContext({
      family: result.family || "FYBROC",
      series: result.series || _series || "",
      selections,
    });
    navigate("/configure");
  }

  // REORDER path: add this exact pump to a quote as-is (same spec/item number),
  // no configurator round-trip. Creates a new quote or appends to a chosen Draft.
  async function reorderToQuote() {
    if (!result?.found) return;
    const { SERIES: _series, ...selections } = result.selections as Record<string, string>;
    const family = result.family || "FYBROC";
    const series = result.series || _series || "";
    setReordering(true);
    setError(null);
    try {
      let quoteId: number;
      if (targetQuote === "__new") {
        const site = family === "DEAN" ? "IND" : "TEL";
        const q = await api.createQuote(family, { site_code: site });
        quoteId = q.quote_header_id;
      } else {
        quoteId = Number(targetQuote);
      }
      await api.addQuoteLine(family, quoteId, {
        series,
        selections: { SERIES: series, ...selections },
        quantity: Math.max(1, qty),
        requested_by: me?.user.email || me?.user.display_name || "lookup",
      });
      navigate(`/quotes/${quoteId}`);
    } catch (e) {
      const err = e as ApiError;
      setError(typeof err.detail === "string" ? err.detail : err.message);
    } finally {
      setReordering(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Look up a pump</h1>
          <p className="lede">
            Enter a SKU to see exactly what that pump is, then reorder it as-is or
            reuse it as the starting point for a new configuration.
          </p>
        </div>
      </div>

      <form className="card" onSubmit={search}>
        <div className="row" style={{ gap: 12, alignItems: "flex-end" }}>
          <div className="field" style={{ margin: 0, minWidth: 260 }}>
            <label htmlFor="sku">SKU</label>
            <input
              id="sku"
              value={sku}
              onChange={(e) => setSku(e.target.value)}
              placeholder="e.g. F1500-EA8F8AFDA"
            />
          </div>
          <button className="btn primary" type="submit" disabled={loading}>
            {loading ? "Searching…" : "Look up"}
          </button>
        </div>
        {error && (
          <div className="notice err" style={{ marginTop: 12 }}>
            {error}
          </div>
        )}
      </form>

      {result?.found && (
        <div className="card">
          <header>
            <div>
              <h2 style={{ margin: 0 }}>{result.part_number}</h2>
              <p className="muted" style={{ margin: ".25rem 0 0" }}>
                {result.family} {result.series} · SKU {result.sku}
              </p>
            </div>
            <button className="btn secondary" onClick={configureFromResult}>
              Edit / configure from this pump
            </button>
          </header>

          <table>
            <tbody>
              {Object.entries(result.selections).map(([k, v]) => (
                <tr key={k}>
                  <th style={{ width: "40%" }}>{titleize(k)}</th>
                  <td>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Reorder as-is. */}
          {canQuote && (
            <section className="addbar" style={{ marginTop: "1rem" }}>
              <div>
                <span className="lbl">Reorder this pump as-is</span>
                <select
                  className="in"
                  style={{ width: "auto", minWidth: 220 }}
                  value={targetQuote}
                  onChange={(e) => setTargetQuote(e.target.value)}
                  aria-label="Target quote"
                >
                  <option value="__new">+ New quote</option>
                  {quotes.map((q) => (
                    <option key={q.quote_header_id} value={q.quote_header_id}>
                      {q.quote_number}
                      {q.customer_name ? ` — ${q.customer_name}` : ""}
                    </option>
                  ))}
                </select>
                <div className="field" style={{ margin: 0, width: 80 }}>
                  <label htmlFor="reorder-qty">Qty</label>
                  <input
                    id="reorder-qty"
                    type="number"
                    min={1}
                    value={qty}
                    onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
                  />
                </div>
                <button className="btn primary" onClick={reorderToQuote} disabled={reordering}>
                  {reordering ? "Adding…" : "Reorder — add to quote"}
                </button>
              </div>
            </section>
          )}

          <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>
            Reorder adds this exact pump (same spec and item number) to a quote.
            Edit / configure copies its selections into the configurator so you can
            change anything to produce a new configuration.
          </p>
        </div>
      )}
    </>
  );
}
