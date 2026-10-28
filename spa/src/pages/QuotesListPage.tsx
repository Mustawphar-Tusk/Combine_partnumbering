import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { QuoteListItem } from "../api/types";
import { money } from "../format";
import { StatusBadge } from "../components/StatusBadge";

export function QuotesListPage() {
  const [quotes, setQuotes] = useState<QuoteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [customer, setCustomer] = useState("");
  const [site, setSite] = useState("TEL");
  const navigate = useNavigate();

  const load = useCallback(() => {
    setLoading(true);
    api
      .listQuotes("FYBROC") // quotes are not family-scoped; endpoint returns all
      .then((r) => setQuotes(r.quotes))
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const q = await api.createQuote("FYBROC", {
        site_code: site,
        customer_name: customer || undefined,
      });
      navigate(`/quotes/${q.quote_header_id}`);
    } catch (err) {
      const e2 = err as ApiError;
      setError(typeof e2.detail === "string" ? e2.detail : e2.message);
      setCreating(false);
    }
  }

  return (
    <>
      <form className="card" onSubmit={create}>
        <h2>New quote</h2>
        {error && <div className="notice err">{error}</div>}
        <div className="row" style={{ gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ margin: 0, minWidth: 220 }}>
            <label htmlFor="cust">Customer name</label>
            <input id="cust" value={customer} onChange={(e) => setCustomer(e.target.value)} />
          </div>
          <div className="field" style={{ margin: 0, minWidth: 120 }}>
            <label htmlFor="site">Site</label>
            <select id="site" value={site} onChange={(e) => setSite(e.target.value)}>
              <option value="TEL">TEL</option>
              <option value="IND">IND</option>
            </select>
          </div>
          <button className="btn" type="submit" disabled={creating}>
            {creating ? "Creating…" : "Create quote"}
          </button>
        </div>
      </form>

      <div className="card">
        <h2>Quotes</h2>
        {loading ? (
          <p className="muted">Loading…</p>
        ) : quotes.length === 0 ? (
          <p className="muted">No quotes yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Quote #</th>
                <th>Customer</th>
                <th>Site</th>
                <th>Status</th>
                <th>Lines</th>
                <th style={{ textAlign: "right" }}>List total</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {quotes.map((q) => (
                <tr key={q.quote_header_id}>
                  <td>{q.quote_number}</td>
                  <td>{q.customer_name || <span className="muted">—</span>}</td>
                  <td>{q.site_code}</td>
                  <td><StatusBadge status={q.status} /></td>
                  <td>{q.line_count}</td>
                  <td style={{ textAlign: "right" }}>{money(q.total_price, q.currency_code)}</td>
                  <td>
                    <button className="btn secondary" onClick={() => navigate(`/quotes/${q.quote_header_id}`)}>
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
