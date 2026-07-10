import { useEffect, useState } from "react";

/**
 * Generic debounce hook — used by the special-collection create dialog's
 * live per-flat split preview (frontend.md: "reactive to the `total_amount`
 * field via `watch()` ..., updates on every keystroke (debounced 200ms)").
 */
export function useDebouncedValue<T>(value: T, delayMs = 200): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
