import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "./test-utils";
import { ExpenditureForm } from "@/app/(app)/towers/[towerId]/expenditures/new/expenditure-form";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

const createExpenditure = vi.fn();
const createComplexContribution = vi.fn();
const getAttachmentUploadUrl = vi.fn();
const uploadFileWithProgress = vi.fn();

vi.mock("@/lib/api/expenditures", () => ({
  createExpenditure: (...args: unknown[]) => createExpenditure(...args),
  createComplexContribution: (...args: unknown[]) => createComplexContribution(...args),
  getAttachmentUploadUrl: (...args: unknown[]) => getAttachmentUploadUrl(...args),
  uploadFileWithProgress: (...args: unknown[]) => uploadFileWithProgress(...args),
}));

describe("ExpenditureForm", () => {
  beforeEach(() => {
    createExpenditure.mockReset();
    createComplexContribution.mockReset();
    getAttachmentUploadUrl.mockReset();
    uploadFileWithProgress.mockReset();
    push.mockReset();
  });

  /**
   * frontend.md Component test #1: "Expenditure form requires vendor/payee
   * name and rejects empty submission."
   */
  it("shows a validation error and does not call the create mutation when vendor/payee name is empty", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ExpenditureForm towerId="tower-a" isComplexContribution={false} />);

    await user.click(screen.getByRole("button", { name: /record expenditure/i }));

    expect(await screen.findByText(/vendor\/payee name is required/i)).toBeInTheDocument();
    expect(createExpenditure).not.toHaveBeenCalled();
  });

  /**
   * frontend.md Component test #3: "Attachment file-type rejection."
   */
  it("rejects a .docx attachment with the expected message and blocks submission", async () => {
    // `applyAccept: false` bypasses user-event's default filtering of
    // uploaded files against the input's `accept` attribute — the whole
    // point of this test is a file that *doesn't* match `accept`, which a
    // user could still supply via drag-and-drop, so the zod-level check is
    // real defense-in-depth, not dead code.
    const user = userEvent.setup({ applyAccept: false });
    renderWithProviders(<ExpenditureForm towerId="tower-a" isComplexContribution={false} />);

    const file = new File(["dummy"], "invoice.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    const input = screen.getByLabelText(/attachment/i) as HTMLInputElement;
    await user.upload(input, file);

    expect(await screen.findByText(/only pdf, jpeg, or png files are allowed/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /record expenditure/i }));
    await waitFor(() => {
      expect(getAttachmentUploadUrl).not.toHaveBeenCalled();
      expect(createExpenditure).not.toHaveBeenCalled();
    });
  });

  /**
   * frontend.md Component test #5: "Complex-contribution field toggle."
   */
  it("shows the complex-total-amount field and relabels Amount only when type=complex-contribution", () => {
    const { unmount } = renderWithProviders(<ExpenditureForm towerId="tower-a" isComplexContribution={true} />);
    expect(screen.getByLabelText(/total complex expense amount/i)).toBeInTheDocument();
    expect(screen.getByText(/tower's share amount/i)).toBeInTheDocument();
    unmount();

    renderWithProviders(<ExpenditureForm towerId="tower-a" isComplexContribution={false} />);
    expect(screen.queryByLabelText(/total complex expense amount/i)).not.toBeInTheDocument();
    expect(screen.getByText(/^amount$/i)).toBeInTheDocument();
  });
});
