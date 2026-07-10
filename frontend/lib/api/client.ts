import type { ProblemDetails } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  errorCode: string;
  fieldErrors: Record<string, string[]> | null;

  constructor(status: number, problem: ProblemDetails) {
    super(problem.message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = problem.error_code;
    this.fieldErrors = problem.field_errors;
  }
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Extra query params appended to the URL. */
  params?: Record<string, string | number | boolean | undefined>;
}

function buildUrl(path: string, params?: RequestOptions["params"]): string {
  const url = new URL(path.replace(/^\//, ""), `${API_BASE_URL}/`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

/**
 * Typed fetch wrapper around the FastAPI backend.
 *
 * - Base URL comes from `NEXT_PUBLIC_API_BASE_URL`.
 * - `credentials: 'include'` on every call so the httpOnly `access_token` /
 *   `refresh_token` cookies set by `POST /api/v1/auth/login` are sent back on
 *   every subsequent request (specs/00-architecture-and-standards.md §1, §5.3).
 * - Errors are normalized to the RFC7807-style envelope from
 *   specs/00-architecture-and-standards.md §6 and thrown as `ApiError`.
 *
 * Usable from both server components/route handlers and client components.
 * When called from the server, the caller is responsible for forwarding any
 * inbound cookies (Next.js does not do this automatically for server-side
 * fetches) — see `lib/api/server.ts` for that variant.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, params, headers, ...rest } = options;

  const res = await fetch(buildUrl(path, params), {
    ...rest,
    credentials: "include",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      Accept: "application/json",
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) {
    return undefined as T;
  }

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json().catch(() => null) : null;

  if (!res.ok) {
    const problem: ProblemDetails = payload ?? {
      error_code: "UNKNOWN_ERROR",
      message: res.statusText || "Request failed",
      field_errors: null,
    };
    throw new ApiError(res.status, problem);
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => apiFetch<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiFetch<T>(path, { ...options, method: "PUT", body }),
  delete: <T>(path: string, options?: RequestOptions) => apiFetch<T>(path, { ...options, method: "DELETE" }),
};
