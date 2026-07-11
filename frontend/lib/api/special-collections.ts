import { api } from "./client";
import type { CreateSpecialCollectionResponse, Paginated, SpecialCollection, SpecialCollectionDue } from "./types";

/**
 * Typed client for specs/04-special-collections-expenditure/backend.md's
 * Special Collections + Special Collection Dues endpoints.
 *
 * Deliberately NOT included (out of scope for this frontend slice — see
 * frontend.md and this module's kickoff constraints): `POST
 * .../dues/{due_id}/mark-paid` and `GET .../dues/{due_id}/receipt`. Both
 * delegate to Module 3's `record_payment()`/receipt flow, and Module 3 does
 * not exist yet in this repo. The dues list/detail below render read-only —
 * no "Mark Paid" action or "View Receipt" link is wired to a nonexistent
 * endpoint.
 */
export interface CreateSpecialCollectionInput {
  title: string;
  description?: string | null;
  total_amount: number;
  split_basis: "equal";
  due_date: string; // ISO date (YYYY-MM-DD)
}

export function listSpecialCollections(
  towerId: string,
  params?: { status?: "open" | "closed"; page?: number; page_size?: number }
) {
  return api.get<Paginated<SpecialCollection>>(`/api/v1/towers/${towerId}/special-collections`, { params });
}

export function getSpecialCollection(towerId: string, id: string) {
  return api.get<SpecialCollection>(`/api/v1/towers/${towerId}/special-collections/${id}`);
}

export function createSpecialCollection(towerId: string, input: CreateSpecialCollectionInput) {
  return api.post<CreateSpecialCollectionResponse>(`/api/v1/towers/${towerId}/special-collections`, input);
}

export function deleteSpecialCollection(towerId: string, id: string) {
  return api.delete<void>(`/api/v1/towers/${towerId}/special-collections/${id}`);
}

export function listSpecialCollectionDues(
  towerId: string,
  collectionId: string,
  params?: { status?: string; flat_id?: string; owner_id?: string; page?: number; page_size?: number }
) {
  return api.get<Paginated<SpecialCollectionDue>>(
    `/api/v1/towers/${towerId}/special-collections/${collectionId}/dues`,
    { params }
  );
}

export function getSpecialCollectionDue(towerId: string, collectionId: string, dueId: string) {
  return api.get<SpecialCollectionDue>(
    `/api/v1/towers/${towerId}/special-collections/${collectionId}/dues/${dueId}`
  );
}
