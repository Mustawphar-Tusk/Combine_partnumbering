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
