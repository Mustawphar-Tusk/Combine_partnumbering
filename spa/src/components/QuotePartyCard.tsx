import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { QuoteParty, QuotePartyInput } from "../api/types";

// U4: editable customer party card (CONTACT or SHIP_TO) on a quote. Draft-only
// edits (the server enforces it). Mirrors the reference demo's customer block.
const FIELDS: { key: keyof QuotePartyInput; label: string; wide?: boolean }[] = [
  { key: "company_name", label: "Company", wide: true },
  { key: "first_name", label: "First name" },
  { key: "last_name", label: "Last name" },
  { key: "address1", label: "Address 1", wide: true },
  { key: "address2", label: "Address 2", wide: true },
  { key: "city", label: "City" },
  { key: "state", label: "State / region" },
  { key: "postal_code", label: "Postal code" },
  { key: "country", label: "Country" },
  { key: "phone", label: "Phone" },
  { key: "email", label: "Email" },
];

export function QuotePartyCard({
  quoteId,
  kind,
  title,
  editable,
}: {
  quoteId: number;
  kind: "CONTACT" | "SHIP_TO";
  title: string;
  editable: boolean;
}) {
  const [party, setParty] = useState<QuoteParty | null>(null);
  const [form, setForm] = useState<QuotePartyInput>({});
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  useEffect(() => {
    api
      .getQuoteParties(quoteId)
      .then((r) => {
        const p = r.parties.find((x) => x.kind === kind) || null;
        setParty(p);
        if (p) setForm(toForm(p));
      })
      .catch(() => setParty(null));
  }, [quoteId, kind]);

  function toForm(p: QuoteParty): QuotePartyInput {
    return {
      company_name: p.company_name,
      first_name: p.first_name,
      last_name: p.last_name,
      address1: p.address1,
      address2: p.address2,
      city: p.city,
      state: p.state,
      postal_code: p.postal_code,
      country: p.country,
      phone: p.phone,
      email: p.email,
    };
  }

  async function save() {
    setSaving(true);
    setError(null);
    setSavedMsg(null);
    try {
      const saved = await api.upsertQuoteParty(quoteId, kind, form);
      setParty(saved);
      setForm(toForm(saved));
      setEditing(false);
      setSavedMsg("Saved.");
    } catch (err) {
      const e = err as ApiError;
      setError(typeof e.detail === "string" ? e.detail : e.message);
    } finally {
      setSaving(false);
    }
  }

  const summaryLines = party
    ? [
        party.company_name,
        [party.first_name, party.last_name].filter(Boolean).join(" "),
        party.address1,
        party.address2,
        [party.city, party.state, party.postal_code].filter(Boolean).join(", "),
        party.country,
        party.phone ? `Tel: ${party.phone}` : null,
        party.email,
      ].filter(Boolean)
    : [];

  return (
    <div className="card">
      <header>
        <h3 style={{ margin: 0 }}>{title}</h3>
        {editable && !editing && (
          <button className="btn secondary sm" onClick={() => setEditing(true)}>
            {party ? "Edit" : "Add"}
          </button>
        )}
      </header>

      {error && <div className="notice err">{error}</div>}
      {savedMsg && !editing && (
        <div className="muted" style={{ fontSize: 12 }}>
          {savedMsg}
        </div>
      )}

      {editing ? (
        <>
          <div className="grid-2">
            {FIELDS.map((f) => (
              <div
                className="field"
                key={f.key}
                style={f.wide ? { gridColumn: "1 / -1", margin: 0 } : { margin: 0 }}
              >
                <label htmlFor={`${kind}-${f.key}`}>{f.label}</label>
                <input
                  id={`${kind}-${f.key}`}
                  value={(form[f.key] as string) || ""}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, [f.key]: e.target.value }))
                  }
                />
              </div>
            ))}
          </div>
          <div className="row" style={{ gap: 8, marginTop: 12 }}>
            <button className="btn primary" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              className="btn secondary"
              onClick={() => {
                setEditing(false);
                setError(null);
                if (party) setForm(toForm(party));
              }}
            >
              Cancel
            </button>
          </div>
        </>
      ) : summaryLines.length > 0 ? (
        <div style={{ fontSize: 14, lineHeight: 1.5 }}>
          {summaryLines.map((ln, i) => (
            <div key={i}>{ln}</div>
          ))}
        </div>
      ) : (
        <p className="muted" style={{ margin: 0 }}>
          {editable ? "Not set yet." : "—"}
        </p>
      )}
    </div>
  );
}
