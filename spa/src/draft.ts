// A tiny shared "configuration draft" the configurator publishes and the quote
// workspace consumes, so a user can add the current configuration to a quote.
// Persisted in sessionStorage so it survives navigation within the SPA session.

export interface ConfigDraft {
  family: string;
  series: string;
  selections: Record<string, string>;
  part_number: string;
  sku: string;
  total_price: number;
}

const KEY = "cpq.configDraft";

export function setDraft(d: ConfigDraft | null): void {
  if (d) sessionStorage.setItem(KEY, JSON.stringify(d));
  else sessionStorage.removeItem(KEY);
}

export function getDraft(): ConfigDraft | null {
  const raw = sessionStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ConfigDraft;
  } catch {
    return null;
  }
}

// A1: when the distributor clicks "Edit Configuration" on a draft quote line, we
// stash an edit context so the configurator opens seeded with that line's saved
// selections and saves back to the SAME line (PUT) instead of publishing a draft.
export interface EditContext {
  family: string;
  series: string;
  quoteHeaderId: number;
  quoteLineId: number;
  selections: Record<string, string>;
  quantity: number;
}

const EDIT_KEY = "cpq.editContext";

export function setEditContext(e: EditContext | null): void {
  if (e) sessionStorage.setItem(EDIT_KEY, JSON.stringify(e));
  else sessionStorage.removeItem(EDIT_KEY);
}

export function getEditContext(): EditContext | null {
  const raw = sessionStorage.getItem(EDIT_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as EditContext;
  } catch {
    return null;
  }
}

// "Configure from a looked-up pump": seed the configurator with an existing
// pump's family/series/selections to START A NEW configuration (not an edit of
// a quote line). The configurator bootstraps these selections, then behaves as a
// normal new config (publishes a draft the Quotes workspace can add).
export interface SeedContext {
  family: string;
  series: string;
  selections: Record<string, string>;
}

const SEED_KEY = "cpq.seedContext";

export function setSeedContext(s: SeedContext | null): void {
  if (s) sessionStorage.setItem(SEED_KEY, JSON.stringify(s));
  else sessionStorage.removeItem(SEED_KEY);
}

export function getSeedContext(): SeedContext | null {
  const raw = sessionStorage.getItem(SEED_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SeedContext;
  } catch {
    return null;
  }
}
