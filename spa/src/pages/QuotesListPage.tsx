import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { QuoteListItem } from "../api/types";
import { money } from "../format";
import { StatusBadge } from "../components/StatusBadge";

// Quotes log — aligned with the reference CPQ demo (vLog): a page head with a
// lede + a "New quote" action, then the quote grid inside a .tablewrap. The
// create form is a small modal-style card revealed from the page head.
export function QuotesListPage() {
  const [quotes, setQuotes] = useState<QuoteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
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

  const sorted = [...quotes].sort((a, b) =>
    b.quote_number.localeCompare(a.quote_number),
  );

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Quotes</h1>
          <p className="lede">
            Every quote you have access to. Open one to configure pumps, add
            customer details, and complete it.
          </p>
        </div>
        <button className="btn primary" onClick={() => setShowNew((v) => !v)}>
          {showNew ? "Close" : "New quote"}
        </button>
      </div>

      {error && <div className="notice err">{error}</div>}

      {showNew && (
        <form className="card" onSubmit={create}>
          <h2 style={{ marginBottom: ".7rem" }}>New quote</h2>
          <div
            className="row"
            style={{ gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}
          >
            <div className="field" style={{ margin: 0, minWidth: 240 }}>
              <label htmlFor="cust">Customer name</label>
              <input
                id="cust"
                value={customer}
                onChange={(e) => setCustomer(e.target.value)}
                placeholder="For example Cascade Chemical Supply"
              />
            </div>
            <div className="field" style={{ margin: 0, minWidth: 120 }}>
              <label htmlFor="site">Site</label>
              <select
                id="site"
                value={site}
                onChange={(e) => setSite(e.target.value)}
              >
                <option value="TEL">TEL</option>
                <option value="IND">IND</option>
              </select>
            </div>
            <button className="btn primary" type="submit" disabled={creating}>
              {creating ? "Creating…" : "Create quote"}
            </button>
          </div>
          <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>
            Contact and ship-to details are added on the quote itself.
          </p>
        </form>
      )}

      {loading ? (
        <p className="muted">Loading…</p>
      ) : sorted.length === 0 ? (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
            No quotes yet. Start one with “New quote”.
          </p>
        </div>
      ) : (
        <div className="tablewrap">
          <table className="grid">
            <thead>
              <tr>
                <th>Quote</th>
                <th>Customer</th>
                <th>Site</th>
                <th>Status</th>
                <th className="num">Lines</th>
                <th className="num">List total</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((q) => (
                <tr
                  key={q.quote_header_id}
                  className="click"
                  onClick={() => navigate(`/quotes/${q.quote_header_id}`)}
                >
                  <td className="mono strong">{q.quote_number}</td>
                  <td>
                    {q.customer_name || (
                      <span className="muted">No customer</span>
                    )}
                  </td>
                  <td>{q.site_code}</td>
                  <td>
                    <StatusBadge status={q.status} />
                  </td>
                  <td className="num">{q.line_count}</td>
                  <td className="num">
                    {money(q.total_price, q.currency_code)}
                  </td>
                  <td>
                    <button
                      className="btn secondary sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/quotes/${q.quote_header_id}`);
                      }}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
