import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { SkuLookupResponse } from "../api/types";
import { titleize } from "../format";
import { setSeedContext } from "../draft";

export function LookupPage() {
  const [sku, setSku] = useState("");
  const [result, setResult] = useState<SkuLookupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

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

  // Reuse this looked-up pump as the starting point for a NEW configuration.
  // Seeds the configurator with this pump's family/series/selections; the user
  // can then tweak it and add it to a quote. (Reference demo "Start from this pump".)
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

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Look up a pump</h1>
          <p className="lede">
            Enter a SKU to see exactly what that pump is, then reuse it as the
            starting point for a new configuration.
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
            <button className="btn primary" onClick={configureFromResult}>
              Configure from this pump
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
          <p className="muted" style={{ fontSize: 13, marginTop: 10 }}>
            Starting from this pump copies every selection into the configurator.
            Change anything to produce a new configuration, then add it to a quote.
          </p>
        </div>
      )}
    </>
  );
}
