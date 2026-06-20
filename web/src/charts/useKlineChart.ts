import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from 'lightweight-charts';
import type { KlineRow, TradeMarker } from './buildSeries';
import { chartLocale } from '../i18n/locale';

export interface MaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
  boll: boolean;
}

export interface UseKlineChartOptions {
  container: HTMLDivElement | null;
  data: KlineRow[];
  maVisibility: MaVisibility;
  trades: TradeMarker[];
  locale?: string;
}

export interface HoverInfo {
  date: string;
  o: number;
  h: number;
  l: number;
  c: number;
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
}

export interface UseKlineChartReturn {
  fitContent: () => void;
  setVisibleRange: (start: string, end: string) => void;
  hoverInfo: HoverInfo | null;
}

/** A股后端返回 YYYYMMDD，LC v4.x 接受 YYYY-MM-DD 字符串（最稳） */
function toLcDate(date: string): string {
  return `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}`;
}

function toLineData(
  data: KlineRow[],
  key: 'ma5' | 'ma10' | 'ma20' | 'ma60' | 'boll_upper' | 'boll_mid' | 'boll_lower'
) {
  return data
    .map(d => ({ time: toLcDate(d.date), value: d[key] as number | null }))
    .filter((p): p is { time: string; value: number } => p.value !== null);
}

type SeriesBundle = {
  candle: ISeriesApi<'Candlestick'>;
  ma5: ISeriesApi<'Line'>;
  ma10: ISeriesApi<'Line'>;
  ma20: ISeriesApi<'Line'>;
  ma60: ISeriesApi<'Line'>;
  bollUpper: ISeriesApi<'Line'>;
  bollMid: ISeriesApi<'Line'>;
  bollLower: ISeriesApi<'Line'>;
};

function setDataToSeries(series: SeriesBundle, data: KlineRow[]) {
  const { candle, ma5, ma10, ma20, ma60, bollUpper, bollMid, bollLower } = series;
  const clean = data.filter(d => typeof d.date === 'string' && d.date.length === 8);
  if (clean.length === 0) return;
  const candleData = clean.map(d => ({ time: toLcDate(d.date), open: d.open, high: d.high, low: d.low, close: d.close }));
  candle.setData(candleData);
  ma5.setData(toLineData(clean, 'ma5'));
  ma10.setData(toLineData(clean, 'ma10'));
  ma20.setData(toLineData(clean, 'ma20'));
  ma60.setData(toLineData(clean, 'ma60'));
  bollUpper.setData(toLineData(clean, 'boll_upper'));
  bollMid.setData(toLineData(clean, 'boll_mid'));
  bollLower.setData(toLineData(clean, 'boll_lower'));
}

export function useKlineChart(options: UseKlineChartOptions): UseKlineChartReturn {
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<SeriesBundle | null>(null);

  // 1. Create chart + all series on mount, then immediately set data so the first paint has content.
  // Setting data inside a separate effect causes a race where the setData effect runs before
  // seriesRef.current is populated, leaving all 8 series empty and the chart blank.
  useEffect(() => {
    if (!options.container) return;
    const width = options.container.clientWidth || 400;
    const height = options.container.clientHeight || 400;
    const chart = createChart(options.container, {
      width,
      height,
      layout: { background: { color: '#0f172a' }, textColor: '#e2e8f0' },
      grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#1e293b' },
      timeScale: { borderColor: '#1e293b', timeVisible: false },
      localization: { locale: chartLocale(), dateFormat: 'yyyy-MM-dd' },
    });
    chartRef.current = chart;

    const candle = chart.addCandlestickSeries({
      upColor: '#ef4444', downColor: '#22c55e',
      borderUpColor: '#ef4444', borderDownColor: '#22c55e',
      wickUpColor: '#ef4444', wickDownColor: '#22c55e',
    });
    // MA 颜色：与涨/跌色错开，金/青/洋红/紫
    const ma5 = chart.addLineSeries({ color: '#f59e0b', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ma10 = chart.addLineSeries({ color: '#06b6d4', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ma20 = chart.addLineSeries({ color: '#ec4899', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ma60 = chart.addLineSeries({ color: '#a855f7', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const bollUpper = chart.addLineSeries({ color: '#fbbf24', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const bollMid = chart.addLineSeries({ color: '#fbbf24', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const bollLower = chart.addLineSeries({ color: '#fbbf24', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });

    const series: SeriesBundle = { candle, ma5, ma10, ma20, ma60, bollUpper, bollMid, bollLower };
    seriesRef.current = series;

    // Set initial data immediately so the first paint has content.
    if (options.data.length) {
      setDataToSeries(series, options.data);
      chart.timeScale().setVisibleLogicalRange({ from: 0, to: options.data.length - 1 });
    }

    const ro = new ResizeObserver(() => {
      const w = options.container!.clientWidth;
      const h = options.container!.clientHeight;
      if (w > 0 && h > 0) {
        chart.applyOptions({ width: w, height: h });
      }
    });
    ro.observe(options.container);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [options.container]);

  // 2. Sync data updates after the initial mount (e.g. when result data changes).
  useEffect(() => {
    if (!seriesRef.current || !options.data.length) return;
    setDataToSeries(seriesRef.current, options.data);
    chartRef.current?.timeScale().setVisibleLogicalRange({ from: 0, to: options.data.length - 1 });
  }, [options.data]);

  // 3. Sync visibility
  useEffect(() => {
    if (!seriesRef.current) return;
    const { ma5, ma10, ma20, ma60, bollUpper, bollMid, bollLower } = seriesRef.current;
    ma5.applyOptions({ visible: options.maVisibility.ma5 });
    ma10.applyOptions({ visible: options.maVisibility.ma10 });
    ma20.applyOptions({ visible: options.maVisibility.ma20 });
    ma60.applyOptions({ visible: options.maVisibility.ma60 });
    bollUpper.applyOptions({ visible: options.maVisibility.boll });
    bollMid.applyOptions({ visible: options.maVisibility.boll });
    bollLower.applyOptions({ visible: options.maVisibility.boll });
  }, [options.maVisibility]);

  // 4. Sync markers
  useEffect(() => {
    if (!seriesRef.current) return;
    const markers: SeriesMarker<Time>[] = options.trades.map(t => ({
      time: toLcDate(t.date),
      position: t.side === 'buy' ? 'belowBar' : 'aboveBar',
      color: t.side === 'buy' ? '#22c55e' : '#ef4444',
      shape: t.side === 'buy' ? 'arrowUp' : 'arrowDown',
      text: t.side === 'buy' ? 'B' : 'S',
    }));
    seriesRef.current.candle.setMarkers(markers);
  }, [options.trades]);

  // 5. Hover info via crosshair
  const [hoverInfo, setHoverInfo] = useState<HoverInfo | null>(null);
  useEffect(() => {
    if (!chartRef.current) return;
    const handler = (param: MouseEventParams) => {
      if (!param.time || !seriesRef.current) {
        setHoverInfo(null);
        return;
      }
      const paramTime = param.time as string | Date;
      let yyyymmdd: string;
      if (typeof paramTime === 'string') {
        yyyymmdd = paramTime.replace(/-/g, '');
      } else {
        const d: Date = paramTime;
        yyyymmdd = `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}`;
      }
      const row = options.data.find(d => d.date === yyyymmdd);
      if (!row) { setHoverInfo(null); return; }
      setHoverInfo({
        date: yyyymmdd, o: row.open, h: row.high, l: row.low, c: row.close,
        ma5: row.ma5 ?? null, ma10: row.ma10 ?? null,
        ma20: row.ma20 ?? null, ma60: row.ma60 ?? null,
      });
    };
    chartRef.current.subscribeCrosshairMove(handler);
    return () => chartRef.current?.unsubscribeCrosshairMove(handler);
  }, [options.data]);

  // 6. Imperative API
  const fitContent = () => chartRef.current?.timeScale().fitContent();
  const setVisibleRange = (start: string, end: string) => {
    const idx0 = options.data.findIndex(d => d.date >= start);
    const idx1 = options.data.findIndex(d => d.date > end);
    if (idx0 === -1 || idx1 === -1) return;
    chartRef.current?.timeScale().setVisibleLogicalRange({ from: idx0, to: idx1 });
  };

  // 7. Re-apply localization when language changes.
  // lightweight-charts requires applyOptions for runtime locale changes.
  useEffect(() => {
    chartRef.current?.applyOptions({
      localization: { locale: chartLocale(), dateFormat: 'yyyy-MM-dd' },
    });
  }, [options.locale]);

  return { fitContent, setVisibleRange, hoverInfo };
}