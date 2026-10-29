import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type {
  FieldGroup,
  Me,
  QuoteListItem,
  ResolveResponse,
  ResolveStateResponse,
} from "../api/types";
import { money, titleize } from "../format";
import {
  setDraft,
  getEditContext,
  setEditContext,
  getSeedContext,
  setSeedContext,
  type EditContext,
} from "../draft";
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
  // Lookup→configure: seed a NEW configuration from a looked-up pump (consumed once).
  const [seed] = useState(() => (getEditContext() ? null : getSeedContext()));
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  // "Add to a quote" (new-config mode): quote picker + quantity.
  const [quotes, setQuotes] = useState<QuoteListItem[]>([]);
  const [targetQuote, setTargetQuote] = useState<string>("__new");
  const [addQty, setAddQty] = useState(1);
  const [addingToQuote, setAddingToQuote] = useState(false);
  // A2: which grouping's customization modal is open (edit mode only).
  const [customGroup, setCustomGroup] = useState<string | null>(null);
  const navigate = useNavigate();
  const seq = useRef(0);
  const bootstrapped = useRef(false);

  // Load the series list when the family changes.
  useEffect(() => {
    let cancelled = false;
    // Reset the in-progress config on a genuine family change, but NOT while an
    // edit or lookup-seed bootstrap is seeding family/series/selections itself.
    const hasContext = !!(edit || seed);
    if (!hasContext) {
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

  // Lookup→configure: seed a NEW configuration from a looked-up pump, once.
  // Starts a normal (non-edit) config so the user can tweak and add it to a quote.
  useEffect(() => {
    if (!seed || edit || bootstrapped.current) return;
    bootstrapped.current = true;
    setSeedContext(null); // consume once
    setFamily(seed.family);
    setSeries(seed.series);
    setActiveGroup(0);
    runResolveState(seed.series, seed.selections, undefined, seed.family);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed]);

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

  // Load existing DRAFT quotes for the "Add to a quote" picker (new-config mode).
  useEffect(() => {
    if (edit) return;
    api
      .listQuotes(family || "FYBROC")
      .then((r) => setQuotes(r.quotes.filter((q) => q.status === "Draft")))
      .catch(() => setQuotes([]));
  }, [edit, family, savedMsg]);

  // Add the current resolved configuration as a line to a new or existing quote.
  async function addToQuote() {
    if (!resolved || !state || !series) return;
    setAddingToQuote(true);
    setError(null);
    setSavedMsg(null);
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
        selections: { SERIES: series, ...state.selections },
        quantity: Math.max(1, addQty),
        requested_by: me.user.email || me.user.display_name || "configurator",
      });
      setDraft(null); // consumed into the quote
      navigate(`/quotes/${quoteId}`);
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail || e.message) : String(e));
    } finally {
      setAddingToQuote(false);
    }
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
        <>
          {/* Spec-number plate across the top (reference layout). */}
          <SpecPlate resolved={resolved} />

          <div className="cfg">
            {/* Left: grouped selection summary. */}
            <aside className="summary">
              <h2>Configuration</h2>
              {groups.map((g, i) => (
                <div key={g.group} className={"sgroup" + (i === activeGroup ? " on" : "")}>
                  <h3>
                    <button
                      className="navlink"
                      style={{ padding: 0, background: "none" }}
                      onClick={() => setActiveGroup(i)}
                    >
                      {g.group}
                    </button>
                  </h3>
                  {g.fields.map((gf) => {
                    const v = gf.placeholder ? "C/F" : state.selections[gf.field];
                    return (
                      <div key={gf.field} className={"srow" + (gf.placeholder ? " custom" : "")}>
                        <span className="sl">{titleize(gf.field)}</span>
                        <span className="sv">{v || "—"}</span>
                      </div>
                    );
                  })}
                </div>
              ))}
            </aside>

            {/* Right: options for the active group (radio-style rows). */}
            <section className="opts">
              <div className="gtabs">
                {groups.map((g, i) => (
                  <button
                    key={g.group}
                    className={"gtab" + (i === activeGroup ? " on" : "")}
                    onClick={() => setActiveGroup(i)}
                  >
                    {g.group}
                  </button>
                ))}
              </div>

              {edit && groups[activeGroup] && (
                <div className="row" style={{ marginBottom: 12 }}>
                  <button className="btn amber" onClick={() => setCustomGroup(groups[activeGroup].group)}>
                    Custom — request a customization for {groups[activeGroup].group}
                  </button>
                </div>
              )}

              {groups[activeGroup]?.fields.map((gf) => {
                const fc = gf.field;
                if (gf.placeholder) {
                  return (
                    <div className="cfield" key={fc}>
                      <h3>{titleize(fc)}</h3>
                      <div className="opt is-custom on" aria-disabled>
                        <span className="radio" />
                        <span className="ov">Contact Factory (C/F)</span>
                      </div>
                    </div>
                  );
                }
                const opts = state.allowable_options[fc] || [];
                const value = state.selections[fc] ?? "";
                const std = state.standard_defaults[fc];
                const conflict = conflictByField.get(fc);
                return (
                  <div className="cfield" key={fc}>
                    <h3>
                      {titleize(fc)}
                      {conflict && <span className="amber-t"> ⚠ conflict</span>}
                    </h3>
                    <div className="radios">
                      {opts.map((o) => {
                        const on = value === o;
                        return (
                          <button
                            key={o}
                            className={"opt" + (on ? " on" : "")}
                            onClick={() => onFieldChange(fc, on ? "" : o)}
                          >
                            <span className="radio" />
                            <span className="ov">
                              {o}
                              {std && o === std ? <em className="std">STD</em> : null}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                    {conflict && (
                      <span className="why err">
                        Conflicts with{" "}
                        {conflict.conflicts_with.map(titleize).join(", ") || "other selections"}.
                        {conflict.recommended.length
                          ? ` Try: ${conflict.recommended.slice(0, 6).join(", ")}`
                          : " No compatible option for this combination."}
                      </span>
                    )}
                  </div>
                );
              })}
            </section>
          </div>

          {/* New-config mode: clear next step — add this pump to a quote. */}
          {!edit && (
            <section className="addbar" style={{ marginTop: "1rem" }}>
              <div style={{ justifyContent: "space-between" }}>
                <div>
                  <span className="lbl">This configuration</span>
                  {resolved ? (
                    <span className="sub">
                      <b className="mono">{resolved.part_number}</b> · SKU {resolved.sku} ·{" "}
                      {money(resolved.total_price)}
                      {resolved.component_pricing.some((c) => c.status !== "found")
                        ? " (some items Contact Factory)"
                        : ""}
                    </span>
                  ) : (
                    <span className="sub">
                      Resolve a complete, conflict-free configuration to add it to a quote.
                    </span>
                  )}
                </div>
              </div>
              <div>
                <span className="lbl">Add to a quote</span>
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
                  <label htmlFor="add-qty">Qty</label>
                  <input
                    id="add-qty"
                    type="number"
                    min={1}
                    value={addQty}
                    onChange={(e) => setAddQty(Math.max(1, Number(e.target.value) || 1))}
                  />
                </div>
                <button
                  className="btn primary"
                  onClick={addToQuote}
                  disabled={!resolved || addingToQuote}
                  title={!resolved ? "Resolve a complete configuration first" : ""}
                >
                  {addingToQuote ? "Adding…" : "Add to quote"}
                </button>
              </div>
            </section>
          )}
        </>
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

function SpecPlate({ resolved }: { resolved: ResolveResponse | null }) {
  if (!resolved) {
    return (
      <div className="plate">
        <h3>Specification</h3>
        <p style={{ color: "var(--plate-cap)", margin: 0 }}>
          Resolve a complete, conflict-free configuration to see its part number and price.
        </p>
      </div>
    );
  }
  // Split the authoritative PN into its hyphen-delimited segments for the plate.
  const segs = resolved.part_number.split("-");
  const priced = resolved.component_pricing.filter((c) => c.status === "found").length;
  const cf = resolved.component_pricing.length - priced;
  return (
    <div className="plate">
      <h3>Specification</h3>
      <div className="plate-row">
        {segs.map((s, i) => (
          <span key={i} style={{ display: "contents" }}>
            {i > 0 && <span className="dash">-</span>}
            <span className="seg">
              <span className="code">{s}</span>
            </span>
          </span>
        ))}
      </div>
      <div className="plate-foot">
        <span>SKU <b>{resolved.sku}</b></span>
        <span>Total (priced) <b>{money(resolved.total_price)}</b></span>
        <span>Components <b>{priced} priced{cf ? ` · ${cf} C/F` : ""}</b></span>
      </div>
    </div>
  );
}
