import { useCallback, useMemo, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import ChartDateRangeControl from '../ChartDateRangeControl';
import { buildKlineSeries, buildTradeMarkers, type KlineRow, type TradeMarker } from '../charts/buildSeries';
import { useKlineChart } from '../charts/useKlineChart';
import type { DateRange } from '../charts/filterByDateRange';

export interface MaVisibility {
  ma5: boolean;
  ma10: boolean;
  ma20: boolean;
  ma60: boolean;
  boll: boolean;
}

export interface PriceRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  pnl?: number;
  pnlcomm?: number;
  barlen?: number;
  size?: number;
}

export interface StockKlinePanelProps {
  data: PriceRow[];
  trades?: { date: string; pnl: number; pnlcomm: number; barlen: number; size: number }[];
  maVisibility: MaVisibility;
  onToggleMa: (key: keyof MaVisibility) => void;
  chartDateRange: DateRange | null;
  onChangeDateRange: (next: DateRange | null) => void;
  defaultStart: string;
  defaultEnd: string;
  locale?: string;
}

function fmt(v: number | null) {
  return v == null ? '--' : v.toFixed(2);
}

export function StockKlinePanel(props: StockKlinePanelProps) {
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const ref = useCallback((node: HTMLDivElement | null) => setContainer(node), []);

  const klineData: KlineRow[] = useMemo(() => buildKlineSeries(props.data), [props.data]);

  const markers: TradeMarker[] = useMemo(
    () => buildTradeMarkers(
      (props.trades ?? []).map(t => ({
        date: t.date, pnl: t.pnl ?? 0, pnlcomm: t.pnlcomm ?? 0, barlen: t.barlen ?? 0, size: t.size ?? 0,
      }))
    ),
    [props.trades]
  );

  const { hoverInfo } = useKlineChart({
    container,
    data: klineData,
    maVisibility: props.maVisibility,
    trades: markers,
    locale: props.locale,
  });

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>回测股票 K 线 + MA + BOLL</h3>
      </div>

      <div className="line-toggles">
        {(['ma5', 'ma10', 'ma20', 'ma60', 'boll'] as const).map(key => (
          <button
            key={key}
            className={`toggle-btn ${props.maVisibility[key] ? 'active' : ''}`}
            onClick={() => props.onToggleMa(key)}
          >
            {props.maVisibility[key] ? <Eye size={14} /> : <EyeOff size={14} />}
            {key === 'boll' ? 'BOLL' : key.toUpperCase()}
          </button>
        ))}
      </div>

      <ChartDateRangeControl
        value={props.chartDateRange}
        defaultStart={props.defaultStart}
        defaultEnd={props.defaultEnd}
        onChange={props.onChangeDateRange}
      />

      <div ref={ref} className="chart-container" style={{ height: 400, position: 'relative' }} data-testid="kline-container">
        {hoverInfo && (
          <div
            className="kline-tooltip"
            style={{
              position: 'absolute', top: 8, left: 8, zIndex: 10,
              background: 'rgba(31,41,55,0.9)', color: '#fff', padding: '6px 10px',
              borderRadius: 4, fontSize: 12, lineHeight: 1.5, pointerEvents: 'none',
            }}
            data-testid="kline-tooltip"
          >
            <div>{hoverInfo.date}</div>
            <div>O {fmt(hoverInfo.o)} H {fmt(hoverInfo.h)} L {fmt(hoverInfo.l)} C {fmt(hoverInfo.c)}</div>
            <div>MA5 {fmt(hoverInfo.ma5)} MA10 {fmt(hoverInfo.ma10)} MA20 {fmt(hoverInfo.ma20)} MA60 {fmt(hoverInfo.ma60)}</div>
          </div>
        )}
      </div>

      <div className="trade-legend">
        <div className="trade-legend-item">
          <div className="trade-legend-dot buy"></div>
          <span>买入点</span>
        </div>
        <div className="trade-legend-item">
          <div className="trade-legend-dot sell"></div>
          <span>卖出点</span>
        </div>
      </div>
    </section>
  );
}