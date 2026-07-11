import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NotificationPreviewClient } from "@/app/(app)/towers/[towerId]/notifications/preview/[dueId]/notification-preview-client";
import type { NotificationPreviewResponse } from "@/lib/api/types";

/**
 * specs/05-reporting-owner-portal-notifications/frontend.md "Frontend Test
 * Plan": "notification preview screen shows two distinct message cards only
 * when `messages.length === 2` in the API response — snapshot test asserts
 * card count matches recipient count, and that no send/dispatch button is
 * rendered under any state."
 */
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("event=overdue_reminder&due_type=maintenance"),
}));

function renderPreview() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <NotificationPreviewClient towerId="tower-a" dueId="due-1" />
    </QueryClientProvider>
  );
}

function mockPreviewResponse(body: NotificationPreviewResponse) {
  return vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    })
  );
}

describe("NotificationPreviewClient", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  afterEach(() => {
    fetchSpy?.mockRestore();
  });

  it("renders exactly 2 message cards for a tenant-occupied flat (tenant + owner copy)", async () => {
    fetchSpy = mockPreviewResponse({
      event: "overdue_reminder",
      due_id: "due-1",
      flat_number: "A-101",
      messages: [
        {
          recipient: "tenant",
          recipient_name: "Rahul Tenant",
          recipient_phone: "9000000001",
          message_text: "Dear Rahul, your maintenance is overdue.",
        },
        {
          recipient: "owner",
          recipient_name: "Asha Owner",
          recipient_phone: "9000000002",
          message_text: "Dear Asha, your tenant's maintenance is overdue.",
        },
      ],
    });

    renderPreview();

    const cards = await screen.findAllByTestId("notification-message-card");
    expect(cards).toHaveLength(2);
    expect(screen.getByText(/Rahul Tenant/)).toBeInTheDocument();
    expect(screen.getByText(/Asha Owner/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /dispatch/i })).not.toBeInTheDocument();
  });

  it("renders exactly 1 message card for an owner-occupied flat", async () => {
    fetchSpy = mockPreviewResponse({
      event: "overdue_reminder",
      due_id: "due-1",
      flat_number: "B-202",
      messages: [
        {
          recipient: "owner",
          recipient_name: "Asha Owner",
          recipient_phone: "9000000002",
          message_text: "Dear Asha, your maintenance is overdue.",
        },
      ],
    });

    renderPreview();

    const cards = await screen.findAllByTestId("notification-message-card");
    expect(cards).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /dispatch/i })).not.toBeInTheDocument();
  });

  it("never renders a send/dispatch button, even in the loading or error state", async () => {
    fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ error_code: "NO_RESIDENT", message: "No resident assigned", field_errors: null }),
        { status: 422, headers: { "content-type": "application/json" } }
      )
    );

    renderPreview();

    expect(await screen.findByText(/no resident assigned/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /dispatch/i })).not.toBeInTheDocument();
  });
});
