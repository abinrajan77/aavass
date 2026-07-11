/**
 * Shared empty-state block for report preview tables —
 * specs/05-reporting-owner-portal-notifications/frontend.md §2: "Empty
 * state: when `items` is `[]`, render a centered `<EmptyState>` message ...
 * — never an empty `<Table>` shell, never an error toast." Also covers
 * overview.md's edge case: "a period with zero underlying records ... is a
 * valid empty state, not an error."
 */
export function ReportEmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
      {message}
    </div>
  );
}
