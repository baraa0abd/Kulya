/** HTTP transport and tab-scoped authentication. Authorization remains on the server. */
import type { User } from "@/lib/types";
interface Page<T> {
  count: number;
  results: T[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: unknown = {},
  ) {
    super(message);
  }
}

const KEY = "kulya.session";

type Tokens = { access: string; refresh: string };

// sessionStorage: scoped to this tab and gone when it closes. Never localStorage.
function tokens(): Tokens | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(KEY);
  return raw ? (JSON.parse(raw) as Tokens) : null;
}

function store(value: Tokens | null) {
  if (value) window.sessionStorage.setItem(KEY, JSON.stringify(value));
  else window.sessionStorage.removeItem(KEY);
}

async function send(path: string, init: RequestInit, access?: string): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (access) headers.set("Authorization", `Bearer ${access}`);
  return fetch(`/api${path}`, { ...init, headers });
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let current = tokens();
  let response = await send(path, init, current?.access);
  if (response.status === 401 && current) {
    // Access tokens are short-lived: refresh once, then replay.
    const refreshed = await send("/auth/refresh/", {
      method: "POST",
      body: JSON.stringify({ refresh: current.refresh }),
    });
    if (refreshed.ok) {
      current = { ...current, access: ((await refreshed.json()) as { access: string }).access };
      store(current);
      response = await send(path, init, current.access);
    } else {
      store(null);
    }
  }
  if (response.status === 204) return undefined as T;
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as { error?: { code: string; message: string; details: unknown } } | null)
      ?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "error",
      error?.message ?? "Request failed.",
      error?.details,
    );
  }
  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  /** First page (50 rows) of a paginated list. */
  list: async <T>(path: string) => (await request<Page<T>>(path)).results,
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: (path: string) => request<void>(path, { method: "DELETE" }),
  async login(username: string, password: string): Promise<User> {
    const data = await request<Tokens & { user: User }>("/auth/login/", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    store({ access: data.access, refresh: data.refresh });
    return data.user;
  },
  logout: () => store(null),
  hasSession: () => tokens() !== null,
};

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    const details =
      error.details && typeof error.details === "object" ? Object.entries(error.details) : [];
    const fields = details
      .map(([field, messages]) => `${field}: ${[messages].flat().join(" ")}`)
      .join(" · ");
    return fields ? `${error.message} ${fields}` : error.message;
  }
  return "Something went wrong. Please try again.";
}
