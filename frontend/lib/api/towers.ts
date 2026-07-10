import { api } from "./client";
import type { Tower } from "./types";

export function getTower(towerId: string) {
  return api.get<Tower>(`/api/v1/towers/${towerId}`);
}

export function updateTower(
  towerId: string,
  input: Partial<{ name: string; total_floors: number; total_flats: number; association_name: string }>
) {
  return api.put<Tower>(`/api/v1/towers/${towerId}`, input);
}

export function deactivateTower(towerId: string) {
  return api.post<void>(`/api/v1/towers/${towerId}/deactivate`);
}

export function reactivateTower(towerId: string) {
  return api.post<void>(`/api/v1/towers/${towerId}/reactivate`);
}
