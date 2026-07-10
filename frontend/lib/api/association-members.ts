import { api } from "./client";
import type { AssociationMember, CreateAssociationMemberResponse, Paginated } from "./types";

export function listAssociationMembers(towerId: string, params?: { page?: number; page_size?: number }) {
  return api.get<Paginated<AssociationMember>>(`/api/v1/towers/${towerId}/association-members`, { params });
}

export function createAssociationMember(
  towerId: string,
  input: { name: string; email: string; phone: string; role_id: string }
) {
  return api.post<CreateAssociationMemberResponse>(`/api/v1/towers/${towerId}/association-members`, input);
}

export function updateAssociationMember(
  towerId: string,
  memberId: string,
  input: Partial<{ name: string; phone: string; role_id: string }>
) {
  return api.put<AssociationMember>(`/api/v1/towers/${towerId}/association-members/${memberId}`, input);
}

export function deactivateAssociationMember(towerId: string, memberId: string) {
  return api.post<void>(`/api/v1/towers/${towerId}/association-members/${memberId}/deactivate`);
}
