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
