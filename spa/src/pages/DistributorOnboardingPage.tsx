import { useMemo, useState } from "react";
import { api, ApiError } from "../api/client";
import type { AddressInput, SubmitApplicationInput } from "../api/types";

type AddressForm = {
  first_name: string;
  last_name: string;
  address1: string;
  address2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  phone: string;
};

const EMPTY: AddressForm = {
  first_name: "",
  last_name: "",
  address1: "",
  address2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "USA",
  phone: "",
};

function toInput(a: AddressForm): AddressInput {
  return {
    first_name: a.first_name || undefined,
    last_name: a.last_name || undefined,
    address1: a.address1.trim(),
    address2: a.address2 || undefined,
    city: a.city.trim(),
    state: a.state || undefined,
    postal_code: a.postal_code.trim(),
    country: a.country.trim(),
    phone: a.phone || undefined,
  };
}

function AddressFields({
  value,
  onChange,
  disabled,
  prefix,
}: {
  value: AddressForm;
  onChange: (v: AddressForm) => void;
  disabled?: boolean;
  prefix: string;
}) {
  const set = (k: keyof AddressForm) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...value, [k]: e.target.value });
  return (
    <>
      <div className="grid-2">
        <div className="field">
          <label htmlFor={`${prefix}-first`}>First name</label>
          <input id={`${prefix}-first`} value={value.first_name} onChange={set("first_name")} disabled={disabled} />
        </div>
        <div className="field">
          <label htmlFor={`${prefix}-last`}>Last name</label>
          <input id={`${prefix}-last`} value={value.last_name} onChange={set("last_name")} disabled={disabled} />
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${prefix}-addr1`}>Address line 1 *</label>
        <input id={`${prefix}-addr1`} value={value.address1} onChange={set("address1")} disabled={disabled} />
      </div>
      <div className="field">
        <label htmlFor={`${prefix}-addr2`}>Address line 2</label>
        <input id={`${prefix}-addr2`} value={value.address2} onChange={set("address2")} disabled={disabled} />
      </div>
      <div className="grid-2">
        <div className="field">
          <label htmlFor={`${prefix}-city`}>City *</label>
          <input id={`${prefix}-city`} value={value.city} onChange={set("city")} disabled={disabled} />
        </div>
        <div className="field">
          <label htmlFor={`${prefix}-state`}>State / Province</label>
          <input id={`${prefix}-state`} value={value.state} onChange={set("state")} disabled={disabled} />
        </div>
      </div>
      <div className="grid-2">
        <div className="field">
          <label htmlFor={`${prefix}-postal`}>Postal code *</label>
          <input id={`${prefix}-postal`} value={value.postal_code} onChange={set("postal_code")} disabled={disabled} />
        </div>
        <div className="field">
          <label htmlFor={`${prefix}-country`}>Country *</label>
          <input id={`${prefix}-country`} value={value.country} onChange={set("country")} disabled={disabled} />
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${prefix}-phone`}>Phone</label>
        <input id={`${prefix}-phone`} value={value.phone} onChange={set("phone")} disabled={disabled} />
      </div>
    </>
  );
}

function missingRequired(a: AddressForm): boolean {
  return !a.address1.trim() || !a.city.trim() || !a.postal_code.trim() || !a.country.trim();
}

export function DistributorOnboardingPage({ onSubmitted }: { onSubmitted: () => void }) {
  const [company, setCompany] = useState("");
  const [contact, setContact] = useState<AddressForm>({ ...EMPTY });
  const [shipTo, setShipTo] = useState<AddressForm>({ ...EMPTY });
  const [sameAsContact, setSameAsContact] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  // Stable idempotency key for this form instance: a re-submit of the same form
  // (e.g. double-click or retry) collapses to a single application server-side.
  const idempotencyKey = useMemo(
    () => `spa-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    [],
  );

  const effectiveShipTo = sameAsContact ? contact : shipTo;

  function validate(): string | null {
    if (!company.trim()) return "Company name is required.";
    if (missingRequired(contact)) return "Contact address: address 1, city, postal code, and country are required.";
    if (!sameAsContact && missingRequired(shipTo))
      return "Ship-to address: address 1, city, postal code, and country are required.";
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const v = validate();
    if (v) {
      setError(v);
      return;
    }
    setError(null);
    setSubmitting(true);
    const payload: SubmitApplicationInput = {
      idempotency_key: idempotencyKey,
      company_name: company.trim(),
      contact: toInput(contact),
      ship_to: toInput(effectiveShipTo),
    };
    try {
      const res = await api.submitApplication(payload);
      setDone(
        res.was_duplicate
          ? "This application was already submitted; showing the existing one."
          : "Application submitted. An administrator will review it shortly.",
      );
      onSubmitted();
    } catch (err) {
      const e2 = err as ApiError;
      setError(typeof e2.detail === "string" ? e2.detail : e2.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="card">
        <div className="notice ok">{done}</div>
        <p className="muted">Your account status will update once an administrator reviews your application.</p>
      </div>
    );
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Distributor application</h2>
      <p className="muted">
        Tell us about your company. After submission an administrator reviews your
        application and assigns a loyalty tier before configuration and quoting unlock.
      </p>
      {error && <div className="notice err">{error}</div>}

      <div className="field">
        <label htmlFor="company">Company name *</label>
        <input id="company" value={company} onChange={(e) => setCompany(e.target.value)} />
      </div>

      <h3>Contact address</h3>
      <AddressFields value={contact} onChange={setContact} prefix="contact" />

      <h3>Ship-to address</h3>
      <label className="row" style={{ marginBottom: 10 }}>
        <input
          type="checkbox"
          checked={sameAsContact}
          onChange={(e) => setSameAsContact(e.target.checked)}
        />
        <span>Same as contact address</span>
      </label>
      {!sameAsContact && <AddressFields value={shipTo} onChange={setShipTo} prefix="shipto" />}

      <div className="row" style={{ marginTop: 16 }}>
        <button className="btn" type="submit" disabled={submitting}>
          {submitting ? "Submitting…" : "Submit application"}
        </button>
      </div>
    </form>
  );
}
