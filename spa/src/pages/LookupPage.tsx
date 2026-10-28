import { useState } from "react";
import { api } from "../api/client";
import type { SkuLookupResponse } from "../api/types";
import { titleize } from "../format";

export function LookupPage() {
  const [sku, setSku] = useState("");
  const [result, setResult] = useState<SkuLookupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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

  return (
    <>
      <form className="card" onSubmit={search}>
        <h2>Look up a pump</h2>
        <div className="row" style={{ gap: 12, alignItems: "flex-end" }}>
          <div className="field" style={{ margin: 0, minWidth: 260 }}>
            <label htmlFor="sku">SKU</label>
            <input id="sku" value={sku} onChange={(e) => setSku(e.target.value)} placeholder="e.g. A1B2C3D4" />
          </div>
          <button className="btn" type="submit" disabled={loading}>
            {loading ? "Searching…" : "Look up"}
          </button>
        </div>
        {error && <div className="notice err" style={{ marginTop: 12 }}>{error}</div>}
      </form>

      {result?.found && (
        <div className="card">
          <h2>{result.part_number}</h2>
          <p className="muted">
            {result.family} {result.series} · SKU {result.sku}
          </p>
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
        </div>
      )}
    </>
  );
}
