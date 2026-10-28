// Typed API client for the acct (U1) endpoints.
//
// Auth model:
//  - In production (U5) a real Entra bearer token will be attached here.
//  - In U1 we run against dev-mock auth. To exercise the distributor path
//    locally, a DEV-ONLY role can be assumed via the X-Dev-Assume-Role header.
//    This is controlled by the dev role switcher in the UI and is inert on the
//    server outside development (the backend only honors it in dev mode).

import type {
  AddQuoteLineInput,
  ApplicationDetail,
  ApplicationListItem,
  CompleteReviewInput,
  CreateQuoteInput,
  Me,
  MyAccount,
  Notification,
  QuoteDocument,
  QuoteLine,
  QuoteListItem,
  QuotePricing,
  ResolveResponse,
  ResolveReviewLineInput,
  ResolveStateResponse,
  ReviewCaseDetail,
  ReviewCaseListItem,
  ReviewInput,
  SkuLookupResponse,
  SubmitApplicationInput,
  SubmitApplicationResult,
  SubmitForReviewResult,
} from "./types";

const API_BASE = "/api/v2";

const DEV_ROLE_KEY = "cpq.devAssumeRole";
const DEV_SUBJECT_KEY = "cpq.devSubject";

export function getDevRole(): string | null {
  return localStorage.getItem(DEV_ROLE_KEY);
}

export function getDevSubject(): string | null {
  return localStorage.getItem(DEV_SUBJECT_KEY);
}

export function setDevRole(role: string | null, subject?: string): void {
  if (role) {
    localStorage.setItem(DEV_ROLE_KEY, role);
    localStorage.setItem(DEV_SUBJECT_KEY, subject || `dev-${role}-001`);
  } else {
    localStorage.removeItem(DEV_ROLE_KEY);
    localStorage.removeItem(DEV_SUBJECT_KEY);
  }
}

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", ...extra };
  const role = getDevRole();
  if (role) {
    h["X-Dev-Assume-Role"] = role;
    const subject = localStorage.getItem(DEV_SUBJECT_KEY) || `dev-${role}-001`;
    h["X-Dev-Subject"] = subject;
    h["X-Dev-Email"] = `${subject}@dev.local`;
  }
  return h;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(API_BASE + path, {
    method,
    headers: headers(),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const detail = (data && (data.detail ?? data.error?.message)) ?? data;
    throw new ApiError(resp.status, detail);
  }
  return data as T;
}

export const api = {
  getMe: () => request<Me>("GET", "/me"),
  submitApplication: (input: SubmitApplicationInput) =>
    request<SubmitApplicationResult>("POST", "/distributor/applications", input),
  getMyAccount: () => request<MyAccount>("GET", "/distributor/account"),
  listApplications: (status?: string) =>
    request<{ applications: ApplicationListItem[] }>(
      "GET",
      "/admin/applications" + (status ? `?status=${encodeURIComponent(status)}` : ""),
    ),
  getApplication: (id: number) =>
    request<ApplicationDetail>("GET", `/admin/applications/${id}`),
  reviewApplication: (id: number, input: ReviewInput) =>
    request<{ status: string; loyalty_tier_code: string | null }>(
      "POST",
      `/admin/applications/${id}/review`,
      input,
    ),
  listNotifications: () =>
    request<{ notifications: Notification[] }>("GET", "/notifications"),
  markNotificationRead: (id: number) =>
    request<{ read: boolean }>("POST", `/notifications/${id}/read`),

  // --- U2: configurator / resolve / quotes / loyalty pricing ---
  getSeriesList: async (family: string): Promise<string[]> => {
    const data = await request<{ fields: { series_options?: Record<string, unknown> }[] }>(
      "GET",
      `/families/${family}/configuration-dictionary`,
    );
    const set = new Set<string>();
    for (const f of data.fields || []) {
      for (const s of Object.keys(f.series_options || {})) set.add(s);
    }
    return [...set].sort();
  },
  resolveState: (
    family: string,
    body: { series: string; selections: Record<string, string>; changed_field?: string | null },
  ) =>
    request<ResolveStateResponse>(
      "POST",
      `/families/${family}/configurations/resolve-state`,
      body,
    ),
  resolve: (
    family: string,
    body: { series: string; selections: Record<string, string>; requested_by?: string },
  ) =>
    request<ResolveResponse>(
      "POST",
      `/families/${family}/configured-products/resolve`,
      body,
    ),
  lookupBySku: (sku: string) =>
    request<SkuLookupResponse>("GET", `/configured-products/by-sku/${encodeURIComponent(sku)}`),
  listQuotes: (family: string) =>
    request<{ quotes: QuoteListItem[]; count: number }>("GET", `/families/${family}/quotes`),
  createQuote: (family: string, body: CreateQuoteInput) =>
    request<{
      quote_header_id: number;
      quote_number: string;
      site_code: string;
      currency_code: string;
      status: string;
      created_at: string;
    }>("POST", `/families/${family}/quotes`, body),
  getQuote: (family: string, id: number) =>
    request<QuoteDocument>("GET", `/families/${family}/quotes/${id}`),
  addQuoteLine: (family: string, id: number, body: AddQuoteLineInput) =>
    request<QuoteLine & { quote_line_id: number; bom_header_id: number }>(
      "POST",
      `/families/${family}/quotes/${id}/lines`,
      body,
    ),
  updateQuoteLine: (family: string, id: number, lineId: number, body: AddQuoteLineInput) =>
    request<QuoteLine & { quote_line_id: number; bom_header_id: number }>(
      "PUT",
      `/families/${family}/quotes/${id}/lines/${lineId}`,
      body,
    ),
  removeQuoteLine: (family: string, id: number, lineId: number) =>
    request<{ quote_header_id: number; remaining_lines: number }>(
      "DELETE",
      `/families/${family}/quotes/${id}/lines/${lineId}`,
    ),
  getQuoteLineConfig: (family: string, id: number, lineId: number) =>
    request<{
      quote_line_id: number;
      family: string;
      series: string | null;
      selections: Record<string, string>;
      quantity: number;
      part_number: string;
      sku: string;
    }>("GET", `/families/${family}/quotes/${id}/lines/${lineId}/config`),
  getQuotePricing: (id: number) =>
    request<QuotePricing>("GET", `/quotes/${id}/pricing`),

  // --- U3: engineering review queue ---
  submitQuoteForReview: (quoteId: number) =>
    request<SubmitForReviewResult>("POST", `/quotes/${quoteId}/submit-for-review`),
  listReviewCases: (status?: string) =>
    request<{ cases: ReviewCaseListItem[]; authorized_sites: string[] }>(
      "GET",
      "/engineering/cases" + (status ? `?status=${encodeURIComponent(status)}` : ""),
    ),
  getReviewCase: (id: number) =>
    request<ReviewCaseDetail>("GET", `/engineering/cases/${id}`),
  claimReviewCase: (id: number) =>
    request<{ status: string }>("POST", `/engineering/cases/${id}/claim`),
  resolveReviewLine: (caseId: number, lineId: number, body: ResolveReviewLineInput) =>
    request<{ result: string }>(
      "POST",
      `/engineering/cases/${caseId}/lines/${lineId}/resolve`,
      body,
    ),
  requestReviewChanges: (id: number, notes?: string) =>
    request<{ status: string }>("POST", `/engineering/cases/${id}/request-changes`, { notes }),
  completeReviewCase: (id: number, body: CompleteReviewInput) =>
    request<{ status: string; lead_time_days: number | null }>(
      "POST",
      `/engineering/cases/${id}/complete`,
      body,
    ),
  adminListReviewCases: (status?: string) =>
    request<{ cases: ReviewCaseListItem[] }>(
      "GET",
      "/admin/engineering/cases" + (status ? `?status=${encodeURIComponent(status)}` : ""),
    ),
};
