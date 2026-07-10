import { api } from "./client";
import type { LoginResponse } from "./types";

export function login(input: { email: string; password: string }) {
  return api.post<LoginResponse>("/api/v1/auth/login", input);
}

export function refresh() {
  return api.post<LoginResponse>("/api/v1/auth/refresh");
}

export function logout() {
  return api.post<void>("/api/v1/auth/logout");
}

export function forgotPassword(input: { email: string }) {
  // Always resolves (backend always returns 202 regardless of whether the
  // email exists — specs/01-auth-rbac-tower-setup/overview.md edge cases).
  return api.post<void>("/api/v1/auth/forgot-password", input);
}

export function resetPassword(input: { token: string; new_password: string }) {
  return api.post<void>("/api/v1/auth/reset-password", input);
}
