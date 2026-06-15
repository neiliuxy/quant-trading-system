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

function toLineData(
  data: KlineRow[],
  key: 'ma5' | 'ma10' | 'ma20' | 'ma60' | 'boll_upper' | 'boll_mid' | 'boll_lower'
) {
  return data
    .map(d => ({ time: d.date, value: d[key] as number | null }))
    .filter((p): p is { time: string; value: number } => p.value !== null);
}

export function useKlineChart(options: UseKlineChartOptions): UseKlineChartReturn {
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<{
    candle: ISeriesApi<'Candlestick'>;
    ma5: ISeriesApi<'Line'>;
    ma10: ISeriesApi<'Line'>;
    ma20: ISeriesApi<'Line'>;
    ma60: ISeriesApi<'Line'>;
    bollUpper: ISeriesApi<'Line'>;
    bollMid: ISeriesApi<'Line'>;
    bollLower: ISeriesApi<'Line'>;
  } | null>(null);

  // 1. Create chart + all series on mount
  useEffect(() => {
    if (!options.container) return;
    const chart = createChart(options.container, {
      width: options.container.clientWidth,
      height: 400,
      layout: { background: { color: '#ffffff' }, textColor: '#1f2937' },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#d1d5db' },
      timeScale: { borderColor: '#d1d5db', timeVisible: false },
      localization: { locale: 'zh-CN', dateFormat: 'yyyy-MM-dd' },
    });
    chartRef.current = chart;

    const candle = chart.addCandlestickSeries({
      upColor: '#ef4444', downColor: '#22c55e',
      borderUpColor: '#ef4444', borderDownColor: '#22c55e',
      wickUpColor: '#ef4444', wickDownColor: '#22c55e',
    });
    const ma5 = chart.addLineSeries({ color: '#ef4444', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ma10 = chart.addLineSeries({ color: '#f59e0b', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ma20 = chart.addLineSeries({ color: '#2563eb', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ma60 = chart.addLineSeries({ color: '#7c3aed', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const bollUpper = chart.addLineSeries({ color: '#a855f7', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const bollMid = chart.addLineSeries({ color: '#eab308', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const bollLower = chart.addLineSeries({ color: '#a855f7', lineWidth: 1, priceLineVisible: false, lastValueVisible: false });

    seriesRef.current = { candle, ma5, ma10, ma20, ma60, bollUpper, bollMid, bollLower };

    const ro = new ResizeObserver(() => {
      chart.applyOptions({ width: options.container!.clientWidth });
    });
    ro.observe(options.container);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [options.container]);

  // 2. Sync K line + MA/BOLL data
  useEffect(() => {
    if (!seriesRef.current || !options.data.length) return;
    const { candle, ma5, ma10, ma20, ma60, bollUpper, bollMid, bollLower } = seriesRef.current;
    candle.setData(
      options.data.map(d => ({ time: d.date, open: d.open, high: d.high, low: d.low, close: d.close }))
    );
    ma5.setData(toLineData(options.data, 'ma5'));
    ma10.setData(toLineData(options.data, 'ma10'));
    ma20.setData(toLineData(options.data, 'ma20'));
    ma60.setData(toLineData(options.data, 'ma60'));
    bollUpper.setData(toLineData(options.data, 'boll_upper'));
    bollMid.setData(toLineData(options.data, 'boll_mid'));
    bollLower.setData(toLineData(options.data, 'boll_lower'));
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
      time: t.date,
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
      const date = param.time as string;
      const row = options.data.find(d => d.date === date);
      if (!row) { setHoverInfo(null); return; }
      setHoverInfo({
        date, o: row.open, h: row.high, l: row.low, c: row.close,
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

  return { fitContent, setVisibleRange, hoverInfo };
}