// Typed API client for the acct (U1) endpoints.
//
// Auth model:
//  - In production (U5) a real Entra bearer token will be attached here.
//  - In U1 we run against dev-mock auth. To exercise the distributor path
//    locally, a DEV-ONLY role can be assumed via the X-Dev-Assume-Role header.
//    This is controlled by the dev role switcher in the UI and is inert on the
//    server outside development (the backend only honors it in dev mode).

import type {
  ApplicationDetail,
  ApplicationListItem,
  Me,
  MyAccount,
  Notification,
  ReviewInput,
  SubmitApplicationInput,
  SubmitApplicationResult,
} from "./types";

const API_BASE = "/api/v2";

const DEV_ROLE_KEY = "cpq.devAssumeRole";
const DEV_SUBJECT_KEY = "cpq.devSubject";

export function getDevRole(): string | null {
  return localStorage.getItem(DEV_ROLE_KEY);
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
};
