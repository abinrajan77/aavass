import { api } from "./client";
import type { ApartmentComplex, Paginated, Tower } from "./types";

export function listComplexes(params?: { page?: number; page_size?: number }) {
  return api.get<Paginated<ApartmentComplex>>("/api/v1/complexes", { params });
}

export function getComplex(complexId: string) {
  return api.get<ApartmentComplex>(`/api/v1/complexes/${complexId}`);
}

export function createComplex(input: { name: string; address: string }) {
  return api.post<ApartmentComplex>("/api/v1/complexes", input);
}

export function updateComplex(complexId: string, input: { name?: string; address?: string }) {
  return api.put<ApartmentComplex>(`/api/v1/complexes/${complexId}`, input);
}

export function listTowersForComplex(complexId: string, params?: { page?: number; page_size?: number }) {
  return api.get<Paginated<Tower>>(`/api/v1/complexes/${complexId}/towers`, { params });
}

export interface CreateTowerInput {
  name: string;
  code: string;
  total_floors: number;
  total_flats: number;
  association_name: string;
}

export function createTower(complexId: string, input: CreateTowerInput) {
  return api.post<Tower>(`/api/v1/complexes/${complexId}/towers`, input);
}
