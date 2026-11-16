import { useState } from "react";
import type { PendingCustom } from "../draft";
import { titleize } from "../format";

// Fresh-configuration custom pop-up: captures what the user needs customized for
// a grouping BEFORE a quote line exists. The requests are saved with the line
// when it is added to a quote and then force engineering review.
export function PendingCustomModal({
  grouping,
  fields,
  selections,
  items,
  onAdd,
  onRemove,
  onClose,
}: {
  grouping: string;
  fields: string[];
  selections: Record<string, string>;
  items: PendingCustom[];
  onAdd: (c: PendingCustom) => void;
  onRemove: (index: number) => void;
  onClose: () => void;
}) {
  const [field, setField] = useState("");
  const [change, setChange] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  function add() {
    if (!change.trim()) {
      setError("Describe what you need customized.");
      return;
    }
    setError(null);
    onAdd({
      grouping,
      field_code: field || null,
      current_value: field ? selections[field] ?? null : null,
      requested_change: change.trim(),
      notes: notes.trim() || null,
    });
    setField("");
    setChange("");
    setNotes("");
  }

  const mine = items
    .map((c, i) => ({ c, i }))
    .filter(({ c }) => c.grouping === grouping);

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal wide" onClick={(e) => e.stopPropagation()}>
        <div className="m-top">
          <h2>Customize — {titleize(grouping)}</h2>
          <button className="btn ghost" onClick={onClose}>Done</button>
        </div>
        <p className="sub">
          Describe what you need customized. It is saved with the quote line and sent to an
          application engineer for review when the quote is submitted.
        </p>
        {error && <div className="msgs err"><p>{error}</p></div>}
        {mine.length > 0 && (
          <ul className="addlist">
            {mine.map(({ c, i }) => (
              <li key={i}>
                <span>
                  <strong>{c.field_code ? titleize(c.field_code) : "(whole grouping)"}</strong> —{" "}
                  {c.requested_change}
                  {c.notes ? <span className="sub"> ({c.notes})</span> : null}
                </span>
                <button className="btn sm danger" onClick={() => onRemove(i)}>Remove</button>
              </li>
            ))}
          </ul>
        )}
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
            rows={3}
            value={change}
            onChange={(e) => setChange(e.target.value)}
            placeholder="e.g. Hastelloy C casing per customer spec"
          />
        </label>
        <div className="m-acts">
          <button className="btn primary" onClick={add}>Add customization</button>
        </div>
      </div>
    </div>
  );
}
