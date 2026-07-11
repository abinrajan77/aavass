import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * INR currency formatting shared by Module 4's special-collection and
 * expenditure screens (per-flat split preview, stat cards, list columns) —
 * kept here rather than duplicated per-component.
 */
export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

/**
 * Triggers a browser download of an in-memory `Blob` — used by Module 5's
 * report export flow (specs/05-reporting-owner-portal-notifications/
 * frontend.md §2: "trigger the download from the returned pre-signed URL").
 * The backend renders the file server-side (WeasyPrint/ReportLab/CSV
 * writer per backend.md §2.6); the frontend never generates file content,
 * only surfaces a `Blob` it already received (sync path) or fetched from a
 * pre-signed S3 GET URL (async path) as a save-as download.
 */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
