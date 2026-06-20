import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';
import '../i18n';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// Lightweight Charts requires ResizeObserver in jsdom (not provided)
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverMock as any;

// Mock lightweight-charts module for unit/integration tests.
// Real chart rendering is verified manually in browser (Phase 3).
vi.mock('lightweight-charts', () => {
  const noop = () => {};
  const seriesApi = {
    setData: noop,
    setMarkers: noop,
    applyOptions: noop,
  };
  return {
    createChart: () => ({
      addCandlestickSeries: () => seriesApi,
      addLineSeries: () => seriesApi,
      addHistogramSeries: () => seriesApi,
      applyOptions: noop,
      remove: noop,
      subscribeCrosshairMove: noop,
      unsubscribeCrosshairMove: noop,
      timeScale: () => ({
        fitContent: noop,
        setVisibleLogicalRange: noop,
      }),
    }),
    CrosshairMode: { Normal: 0, Magnet: 1 },
  };
});