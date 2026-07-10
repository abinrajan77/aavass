import { api } from "./client";
import type { Paginated, Role } from "./types";

export function listRoles(towerId: string, params?: { page?: number; page_size?: number }) {
  return api.get<Paginated<Role>>(`/api/v1/towers/${towerId}/roles`, { params });
}

export function createRole(towerId: string, input: { name: string; permission_codes: string[] }) {
  return api.post<Role>(`/api/v1/towers/${towerId}/roles`, input);
}

export function updateRole(
  towerId: string,
  roleId: string,
  input: Partial<{ name: string; permission_codes: string[] }>
) {
  return api.put<Role>(`/api/v1/towers/${towerId}/roles/${roleId}`, input);
}

export function deactivateRole(towerId: string, roleId: string) {
  return api.post<void>(`/api/v1/towers/${towerId}/roles/${roleId}/deactivate`);
}
