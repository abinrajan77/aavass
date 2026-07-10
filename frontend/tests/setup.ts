import "@testing-library/jest-dom/vitest";

/**
 * jsdom is missing a handful of browser APIs that Radix primitives (Popover,
 * Select, Calendar/day-picker) touch during interaction — none of these are
 * implemented in jsdom by default. Stubbed here once, globally, rather than
 * per-test, per https://github.com/radix-ui/primitives known jsdom gaps.
 */
if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {};
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {};
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
