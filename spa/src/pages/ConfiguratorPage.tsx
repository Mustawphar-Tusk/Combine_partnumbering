import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type { FieldGroup, Me, ResolveResponse, ResolveStateResponse } from "../api/types";
import { money, titleize } from "../format";
import { setDraft } from "../draft";

const FAMILIES = ["FYBROC", "DEAN"] as const;

export function ConfiguratorPage({ me }: { me: Me }) {
  const [family, setFamily] = useState<string>("FYBROC");
  const [seriesList, setSeriesList] = useState<string[]>([]);
  const [series, setSeries] = useState<string>("");
  const [state, setState] = useState<ResolveStateResponse | null>(null);
  const [resolved, setResolved] = useState<ResolveResponse | null>(null);
  const [activeGroup, setActiveGroup] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  // Load the series list when the family changes.
  useEffect(() => {
    let cancelled = false;
    setSeries("");
    setState(null);
    setResolved(null);
    api
      .getSeriesList(family)
      .then((list) => !cancelled && setSeriesList(list))
      .catch((e) => !cancelled && setError(String(e.message || e)));
    return () => {
      cancelled = true;
    };
  }, [family]);

  const runResolveState = useCallback(
    async (nextSeries: string, selections: Record<string, string>, changedField?: string) => {
      if (!nextSeries) return;
      const mine = ++seq.current;
      setLoading(true);
      setError(null);
      try {
        const st = await api.resolveState(family, {
          series: nextSeries,
          selections,
          changed_field: changedField ?? null,
        });
        if (mine !== seq.current) return;
        setState(st);
        // Resolve PN/SKU/price from the full selection set (include SERIES).
        runResolve(nextSeries, { SERIES: nextSeries, ...st.selections });
      } catch (e) {
        if (mine !== seq.current) return;
        setError(e instanceof ApiError ? String(e.detail || e.message) : String(e));
      } finally {
        if (mine === seq.current) setLoading(false);
      }
    },
    [family],
  );

  const runResolve = useCallback(
    async (nextSeries: string, selections: Record<string, string>) => {
      try {
        const r = await api.resolve(family, { series: nextSeries, selections });
        setResolved(r);
        // Publish the current resolvable config so the Quotes workspace can add it.
        setDraft({
          family,
          series: nextSeries,
          selections,
          part_number: r.part_number,
          sku: r.sku,
          total_price: r.total_price,
        });
      } catch {
        // resolve can legitimately fail when the config isn't resolvable yet
        // (e.g. conflicts). Keep the state; just clear the plate.
        setResolved(null);
        setDraft(null);
      }
    },
    [family],
  );

  function onSeriesChange(s: string) {
    setSeries(s);
    setActiveGroup(0);
    runResolveState(s, {}); // empty -> STD seed
  }

  function onFieldChange(field: string, value: string) {
    if (!state) return;
    const next = { ...state.selections };
    if (value === "") delete next[field];
    else next[field] = value;
    runResolveState(series, next, field);
  }

  const groups: FieldGroup[] =
    state && state.field_groups.length
      ? state.field_groups
      : state
        ? [
            {
              group: "Configuration",
              fields: state.ordered_fields.map((f) => ({ field: f, placeholder: false })),
            },
          ]
        : [];
  const conflictByField = new Map((state?.conflicts || []).map((c) => [c.field, c]));

  return (
    <>
      <div className="card">
        <div className="row" style={{ gap: 16, flexWrap: "wrap" }}>
          <div className="field" style={{ margin: 0, minWidth: 160 }}>
            <label htmlFor="family">Family</label>
            <select id="family" value={family} onChange={(e) => setFamily(e.target.value)}>
              {FAMILIES.map((f) => (
                <option key={f} value={f}>
                  {titleize(f)}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ margin: 0, minWidth: 200 }}>
            <label htmlFor="series">Series</label>
            <select id="series" value={series} onChange={(e) => onSeriesChange(e.target.value)}>
              <option value="">— Select series —</option>
              {seriesList.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          {loading && <span className="muted">Resolving…</span>}
        </div>
        {error && <div className="notice err" style={{ marginTop: 12 }}>{error}</div>}
      </div>

      {state && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20, alignItems: "start" }}>
          <div className="card">
            {/* Group tabs */}
            <div className="row" style={{ gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
              {groups.map((g, i) => (
                <button
                  key={g.group}
                  className={"btn " + (i === activeGroup ? "" : "secondary")}
                  onClick={() => setActiveGroup(i)}
                  style={{ padding: "5px 12px" }}
                >
                  {g.group}
                </button>
              ))}
            </div>

            {/* Fields for the active group */}
            {groups[activeGroup]?.fields.map((gf) => {
              const fc = gf.field;
              if (gf.placeholder) {
                return (
                  <div className="field" key={fc}>
                    <label>{titleize(fc)}</label>
                    <input value="Contact Factory (C/F)" disabled />
                  </div>
                );
              }
              const opts = state.allowable_options[fc] || [];
              const value = state.selections[fc] ?? "";
              const std = state.standard_defaults[fc];
              const conflict = conflictByField.get(fc);
              return (
                <div className="field" key={fc}>
                  <label htmlFor={`f-${fc}`}>
                    {titleize(fc)}
                    {conflict && <span style={{ color: "var(--err)" }}> ⚠ conflict</span>}
                  </label>
                  <select
                    id={`f-${fc}`}
                    value={value}
                    onChange={(e) => onFieldChange(fc, e.target.value)}
                    style={conflict ? { outline: "2px solid var(--err)" } : undefined}
                  >
                    <option value="">— Not set —</option>
                    {opts.map((o) => (
                      <option key={o} value={o}>
                        {o}
                        {std && o === std ? "  (standard)" : ""}
                      </option>
                    ))}
                  </select>
                  {conflict && (
                    <span className="err">
                      Conflicts with {conflict.conflicts_with.map(titleize).join(", ") || "other selections"}.
                      {conflict.recommended.length
                        ? ` Try: ${conflict.recommended.slice(0, 6).join(", ")}`
                        : " No compatible option for this combination."}
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Live spec plate */}
          <SpecPlate family={family} resolved={resolved} me={me} />
        </div>
      )}
    </>
  );
}

function SpecPlate({
  family,
  resolved,
  me,
}: {
  family: string;
  resolved: ResolveResponse | null;
  me: Me;
}) {
  const canQuote = me.capabilities.create_quote;
  return (
    <div className="card" style={{ position: "sticky", top: 16 }}>
      <h3 style={{ marginTop: 0 }}>Specification</h3>
      {!resolved ? (
        <p className="muted">Resolve a complete, conflict-free configuration to see its part number and price.</p>
      ) : (
        <>
          <div className="field">
            <label>Part number</label>
            <input readOnly value={resolved.part_number} />
          </div>
          <div className="field">
            <label>SKU</label>
            <input readOnly value={resolved.sku} />
          </div>
          <table style={{ marginTop: 8 }}>
            <tbody>
              {resolved.component_pricing.map((c, i) => (
                <tr key={i}>
                  <td style={{ fontSize: 13 }}>{c.component}</td>
                  <td style={{ textAlign: "right", fontSize: 13 }}>
                    {c.status === "found" ? money(c.amount) : <span className="muted">C/F</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ justifyContent: "space-between", marginTop: 12, fontWeight: 700 }}>
            <span>Total (priced)</span>
            <span>{money(resolved.total_price)}</span>
          </div>
          {canQuote && (
            <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>
              Use the Quotes page to add this configuration to a quote.
            </p>
          )}
          <p className="muted" style={{ fontSize: 12 }}>
            Family: {titleize(family)}. Prices are list; loyalty discount is applied on the quote.
          </p>
        </>
      )}
    </div>
  );
}
