import { getDevRole, setDevRole } from "../api/client";

// DEV-ONLY identity switcher. Lets a local developer impersonate a distributor
// or staff role to exercise the whole onboarding->approval slice without a real
// Entra tenant. The backend only honors the X-Dev-Assume-Role header in dev
// mode, so this control is inert in UAT/prod. Clearly labelled as dev-only.
export function DevRoleSwitcher({ onChange }: { onChange: () => void }) {
  const current = getDevRole() || "";

  function change(value: string) {
    if (!value) {
      setDevRole(null);
    } else if (value === "distributor") {
      // distinct stable subject so distributor data persists across reloads
      setDevRole("distributor", "dev-distributor-001");
    } else {
      setDevRole(value, `dev-${value}-001`);
    }
    onChange();
  }

  return (
    <div className="dev-switcher" title="Development only - impersonate a role">
      <span>DEV</span>
      <select value={current} onChange={(e) => change(e.target.value)}>
        <option value="">admin (default mock)</option>
        <option value="distributor">distributor</option>
        <option value="configurator">configurator</option>
      </select>
    </div>
  );
}
