import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Customization } from "../api/types";
import { titleize } from "../format";

// A2: modal for adding/editing/removing multiple customization requests within a
// grouping, on a draft quote line. "Add Another Customization" appends a new
// request; each row is editable/removable while the quote is a draft.
export function CustomRequestModal({
  family,
  quoteHeaderId,
  quoteLineId,
  grouping,
  fields,
  selections,
  onClose,
}: {
  family: string;
  quoteHeaderId: number;
  quoteLineId: number;
  grouping: string;
  fields: string[];
  selections: Record<string, string>;
  onClose: () => void;
}) {
  const [items, setItems] = useState<Customization[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // draft new-request form
  const [field, setField] = useState<string>("");
  const [change, setChange] = useState("");
  const [notes, setNotes] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    api
      .listLineCustomizations(family, quoteHeaderId, quoteLineId)
      .then((r) => setItems(r.customizations.filter((c) => c.grouping === grouping)))
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [family, quoteHeaderId, quoteLineId, grouping]);

  useEffect(() => {
    load();
  }, [load]);

  async function add() {
    if (!change.trim()) {
      setError("Describe the requested customization.");
      return;
    }
    setError(null);
    try {
      await api.addLineCustomization(family, quoteHeaderId, quoteLineId, {
        grouping,
        field_code: field || null,
        current_value: field ? selections[field] ?? null : null,
        requested_change: change.trim(),
        notes: notes.trim() || null,
      });
      setField("");
      setChange("");
      setNotes("");
      load();
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }

  async function remove(id: number) {
    try {
      await api.removeLineCustomization(family, quoteHeaderId, id);
      load();
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal wide" onClick={(e) => e.stopPropagation()}>
        <div className="m-top">
          <h2>Customize — {titleize(grouping)}</h2>
          <button className="btn ghost" onClick={onClose}>Close</button>
        </div>
        <p className="sub">
          Describe what you want customized in this grouping. You can add more than one
          request. Engineering will review and resolve each one.
        </p>
        {error && <div className="msgs err"><p>{error}</p></div>}

        {loading ? (
          <p className="sub">Loading…</p>
        ) : items.length > 0 ? (
          <ul className="addlist">
            {items.map((c) => (
              <li key={c.customization_id}>
                <span>
                  <strong>{c.field_code ? titleize(c.field_code) : "(grouping)"}</strong>
                  {c.current_value ? ` · current: ${c.current_value}` : ""} — {c.requested_change}
                  {c.notes ? <span className="sub"> ({c.notes})</span> : null}
                </span>
                <button className="btn sm danger" onClick={() => remove(c.customization_id)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="sub">No customization requests yet for this grouping.</p>
        )}

        <h4>Add another customization</h4>
        <div className="form2">
          <label className="blk">
            Field (optional)
            <select className="in" value={field} onChange={(e) => setField(e.target.value)}>
              <option value="">(whole grouping)</option>
              {fields.map((f) => (
                <option key={f} value={f}>
                  {titleize(f)}
                  {selections[f] ? ` — ${selections[f]}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="blk">
            Notes (optional)
            <input className="in" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
        </div>
        <label className="blk">
          Requested change
          <textarea
            className="in"
            rows={2}
            value={change}
            onChange={(e) => setChange(e.target.value)}
            placeholder="e.g. Hastelloy C casing per customer spec"
          />
        </label>
        <div className="m-acts">
          <button className="btn primary" onClick={add}>Add Another Customization</button>
        </div>
      </div>
    </div>
  );
}
