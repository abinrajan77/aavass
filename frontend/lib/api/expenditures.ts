import { api } from "./client";
import type {
  AttachmentUploadUrlResponse,
  AttachmentUrlResponse,
  Expenditure,
  ExpenditureCategory,
  Paginated,
  PaymentMode,
} from "./types";

/** Typed client for specs/04-special-collections-expenditure/backend.md's Expenditures endpoints. */
export interface ExpenditureCreateInput {
  expenditure_date: string;
  category: ExpenditureCategory;
  description: string;
  vendor_payee_name: string;
  amount: number;
  payment_mode: PaymentMode;
  attachment_s3_key?: string | null;
}

export interface ComplexContributionCreateInput {
  expenditure_date: string;
  description: string;
  vendor_payee_name: string;
  complex_total_amount?: number | null;
  amount: number;
  payment_mode: PaymentMode;
  category?: ExpenditureCategory;
  attachment_s3_key?: string | null;
}

export function listExpenditures(
  towerId: string,
  params?: {
    category?: ExpenditureCategory;
    is_complex_contribution?: boolean;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }
) {
  return api.get<Paginated<Expenditure>>(`/api/v1/towers/${towerId}/expenditures`, { params });
}

export function getExpenditure(towerId: string, id: string) {
  return api.get<Expenditure>(`/api/v1/towers/${towerId}/expenditures/${id}`);
}

export function createExpenditure(towerId: string, input: ExpenditureCreateInput) {
  return api.post<Expenditure>(`/api/v1/towers/${towerId}/expenditures`, input);
}

export function createComplexContribution(towerId: string, input: ComplexContributionCreateInput) {
  return api.post<Expenditure>(`/api/v1/towers/${towerId}/expenditures/complex-contribution`, input);
}

export function updateExpenditure(towerId: string, id: string, input: Partial<ExpenditureCreateInput>) {
  return api.put<Expenditure>(`/api/v1/towers/${towerId}/expenditures/${id}`, input);
}

export function deleteExpenditure(towerId: string, id: string) {
  return api.delete<void>(`/api/v1/towers/${towerId}/expenditures/${id}`);
}

export function getAttachmentUploadUrl(towerId: string, input: { filename: string; content_type: string }) {
  return api.post<AttachmentUploadUrlResponse>(`/api/v1/towers/${towerId}/expenditures/attachment-upload-url`, input);
}

export function getExpenditureAttachmentUrl(towerId: string, id: string) {
  return api.get<AttachmentUrlResponse>(`/api/v1/towers/${towerId}/expenditures/${id}/attachment`);
}

/**
 * PUTs a file directly to a pre-signed S3 URL, reporting upload progress —
 * frontend.md: "showing filename + size + a client-side progress indicator
 * once the pre-signed PUT starts." Uses XHR (not `fetch`) because `fetch`
 * has no upload-progress event.
 */
export function uploadFileWithProgress(uploadUrl: string, file: File, onProgress?: (percent: number) => void) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", file.type);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`Attachment upload failed (${xhr.status})`));
      }
    };
    xhr.onerror = () => reject(new Error("Attachment upload failed"));
    xhr.send(file);
  });
}
