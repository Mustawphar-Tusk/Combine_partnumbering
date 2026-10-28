import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { FieldGroup, Me, ResolveResponse, ResolveStateResponse } from "../api/types";
import { money, titleize } from "../format";
import { setDraft, getEditContext, setEditContext, type EditContext } from "../draft";
import { CustomRequestModal } from "../components/CustomRequestModal";

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
  // A1: edit context (set when arriving via "Edit Configuration" on a draft line).
  const [edit, setEdit] = useState<EditContext | null>(() => getEditContext());
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  // A2: which grouping's customization modal is open (edit mode only).
  const [customGroup, setCustomGroup] = useState<string | null>(null);
  const navigate = useNavigate();
  const seq = useRef(0);
  const bootstrapped = useRef(false);

  // Load the series list when the family changes.
  useEffect(() => {
    let cancelled = false;
    // Do not reset in the middle of an edit bootstrap.
    if (!edit || bootstrapped.current) {
      setSeries("");
      setState(null);
      setResolved(null);
    }
    api
      .getSeriesList(family)
      .then((list) => !cancelled && setSeriesList(list))
      .catch((e) => !cancelled && setError(String(e.message || e)));
    return () => {
      cancelled = true;
    };
  }, [family]);

  // A1: when launched to edit a draft line, seed family/series/selections once.
  useEffect(() => {
    if (!edit || bootstrapped.current) return;
    bootstrapped.current = true;
    setFamily(edit.family);
    setSeries(edit.series);
    setActiveGroup(0);
    runResolveState(edit.series, edit.selections, undefined, edit.family);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [edit]);

  const runResolveState = useCallback(
    async (
      nextSeries: string,
      selections: Record<string, string>,
      changedField?: string,
      familyOverride?: string,
    ) => {
      if (!nextSeries) return;
      const fam = familyOverride || family;
      const mine = ++seq.current;
      setLoading(true);
      setError(null);
      try {
        const st = await api.resolveState(fam, {
          series: nextSeries,
          selections,
          changed_field: changedField ?? null,
        });
        if (mine !== seq.current) return;
        setState(st);
        // Resolve PN/SKU/price from the full selection set (include SERIES).
        runResolve(nextSeries, { SERIES: nextSeries, ...st.selections }, fam);
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
    async (nextSeries: string, selections: Record<string, string>, familyOverride?: string) => {
      const fam = familyOverride || family;
      try {
        const r = await api.resolve(fam, { series: nextSeries, selections });
        setResolved(r);
        // Publish the current resolvable config so the Quotes workspace can add it.
        setDraft({
          family: fam,
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

  // A1: save the current (edited) configuration back to the draft line in place.
  async function saveEdit() {
    if (!edit || !state) return;
    setSaving(true);
    setError(null);
    setSavedMsg(null);
    try {
      await api.updateQuoteLine(edit.family, edit.quoteHeaderId, edit.quoteLineId, {
        series: edit.series,
        selections: { SERIES: edit.series, ...state.selections },
        quantity: edit.quantity || 1,
        requested_by: me.user.email || me.user.display_name || "distributor",
      });
      setEditContext(null);
      setSavedMsg("Saved to the quote.");
      navigate(`/quotes/${edit.quoteHeaderId}`);
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail || e.message) : String(e));
    } finally {
      setSaving(false);
    }
  }

  function cancelEdit() {
    setEditContext(null);
    setEdit(null);
    const target = edit ? `/quotes/${edit.quoteHeaderId}` : "/";
    navigate(target);
  }

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
        {savedMsg && <div className="notice ok" style={{ marginTop: 12 }}>{savedMsg}</div>}
        {edit && (
          <div className="notice" style={{ marginTop: 12 }}>
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <span>
                Editing line {edit.quoteLineId} of quote {edit.quoteHeaderId}. Change permitted
                selections, then save back to the draft.
              </span>
              <span className="row" style={{ gap: 8 }}>
                <button className="btn" onClick={saveEdit} disabled={saving || !resolved}>
                  {saving ? "Saving…" : "Save to quote"}
                </button>
                <button className="btn secondary" onClick={cancelEdit} disabled={saving}>
                  Cancel
                </button>
              </span>
            </div>
          </div>
        )}
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

            {/* A2: per-grouping Custom button (edit mode only - needs a quote line). */}
            {edit && groups[activeGroup] && (
              <div className="row" style={{ marginBottom: 12 }}>
                <button
                  className="btn amber"
                  onClick={() => setCustomGroup(groups[activeGroup].group)}
                >
                  Custom — request a customization for {groups[activeGroup].group}
                </button>
              </div>
            )}

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

      {edit && customGroup && state && (
        <CustomRequestModal
          family={edit.family}
          quoteHeaderId={edit.quoteHeaderId}
          quoteLineId={edit.quoteLineId}
          grouping={customGroup}
          fields={
            (groups.find((g) => g.group === customGroup)?.fields || [])
              .filter((f) => !f.placeholder)
              .map((f) => f.field)
          }
          selections={state.selections}
          onClose={() => setCustomGroup(null)}
        />
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
