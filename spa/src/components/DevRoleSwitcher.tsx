import { getDevRole, getDevSubject, setDevRole } from "../api/client";

// DEV-ONLY identity switcher. Lets a local developer impersonate a distributor
// or staff role to exercise the whole onboarding->approval slice without a real
// Entra tenant. The backend only honors the X-Dev-Assume-Role header in dev
// mode, so this control is inert in UAT/prod. Clearly labelled as dev-only.
export function DevRoleSwitcher({ onChange }: { onChange: () => void }) {
  const role = getDevRole();
  const subject = getDevSubject();
  // Reconstruct the option value: engineering options are pinned by subject.
  const current = !role
    ? ""
    : role === "engineering" && subject
      ? `engineering|${subject}`
      : role;

  // value "role" or "role|subject" (subject pins a specific seeded identity,
  // e.g. the IND vs TEL engineer, whose memberships are seeded in sql/28).
  function change(value: string) {
    if (!value) {
      setDevRole(null);
      onChange();
      return;
    }
    const [role, subject] = value.split("|");
    if (role === "distributor") {
      setDevRole("distributor", subject || "dev-distributor-001");
    } else {
      setDevRole(role, subject || `dev-${role}-001`);
    }
    onChange();
  }

  const engIndValue = "engineering|dev-engineering-ind";
  const engTelValue = "engineering|dev-engineering-tel";

  return (
    <div className="dev-switcher" title="Development only - impersonate a role">
      <span>DEV</span>
      <select value={current} onChange={(e) => change(e.target.value)}>
        <option value="">admin (default mock)</option>
        <option value="distributor">distributor</option>
        <option value="configurator">configurator</option>
        <option value={engIndValue}>engineering (IND / Dean)</option>
        <option value={engTelValue}>engineering (TEL / Fybroc)</option>
      </select>
    </div>
  );
}
