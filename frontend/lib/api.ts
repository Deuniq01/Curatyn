/**
 * Thin fetch wrapper around the Curatyn FastAPI backend. Every call reads
 * the JWT from localStorage under "curatyn_token" — set by login/signup —
 * and attaches it as a Bearer token. NEXT_PUBLIC_API_BASE defaults to the
 * local dev backend from 08-execution-plan.md Phase 1.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("curatyn_token");
}

export function setToken(token: string) {
  window.localStorage.setItem("curatyn_token", token);
}

export function clearToken() {
  window.localStorage.removeItem("curatyn_token");
}

async function request(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(options.body instanceof FormData) && options.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(detail.detail || `Request to ${path} failed with ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  signup: (email: string, password: string) =>
    request("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => request("/api/auth/me"),
  devConnectProvider: (provider: "GMAIL" | "OUTLOOK") =>
    request(`/api/auth/oauth/dev-connect?provider=${provider}`, { method: "POST" }),
  // Real OAuth: fetch the provider consent URL, then hand the browser to it.
  connectEmailProvider: async (provider: "gmail" | "outlook") => {
    const { authUrl } = await request(`/api/auth/oauth/${provider}/start`);
    window.location.href = authUrl;
  },
  disconnectEmailProvider: () =>
    request("/api/auth/oauth/email-provider", { method: "DELETE" }),

  listCvs: () => request("/api/cvs"),
  uploadCv: (label: string, file: File) => {
    const form = new FormData();
    form.append("label", label);
    form.append("file", file);
    return request("/api/cvs", { method: "POST", body: form });
  },
  deleteCv: (id: string) => request(`/api/cvs/${id}`, { method: "DELETE" }),

  submitJobDescription: (rawInput: string) =>
    request("/api/job-descriptions", { method: "POST", body: JSON.stringify({ rawInput }) }),

  createApplication: (jobDescriptionId: string) =>
    request("/api/applications", { method: "POST", body: JSON.stringify({ jobDescriptionId }) }),
  listApplications: () => request("/api/applications"),
  getApplication: (id: string) => request(`/api/applications/${id}`),
  updateApplication: (id: string, fields: Record<string, unknown>) =>
    request(`/api/applications/${id}`, { method: "PUT", body: JSON.stringify(fields) }),
  regenerateCoverLetter: (id: string) =>
    request(`/api/applications/${id}/cover-letter`, { method: "POST" }),
  editCoverLetter: (id: string, coverLetter: string) =>
    request(`/api/applications/${id}/cover-letter`, { method: "PUT", body: JSON.stringify({ coverLetter }) }),
  sendApplication: (id: string, idempotencyKey: string) =>
    request(`/api/applications/${id}/send`, { method: "POST", body: JSON.stringify({ idempotencyKey }) }),
  draftApplication: (id: string, idempotencyKey: string) =>
    request(`/api/applications/${id}/draft`, { method: "POST", body: JSON.stringify({ idempotencyKey }) }),
  cancelApplication: (id: string) => request(`/api/applications/${id}`, { method: "DELETE" }),
  listEvents: (id: string) => request(`/api/applications/${id}/events`),
};
