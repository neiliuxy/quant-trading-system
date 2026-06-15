import { useMemo, useRef } from 'react';
import {
  Bar, CartesianGrid, ComposedChart, Legend, Line, ReferenceDot,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Eye, EyeOff } from 'lucide-react';
import ChartDateRangeControl from '../ChartDateRangeControl';
import { filterByDateRange, DateRange } from '../charts/filterByDateRange';

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
  ma5?: number | null;
  ma10?: number | null;
  ma20?: number | null;
  ma60?: number | null;
  boll_upper?: number | null;
  boll_mid?: number | null;
  boll_lower?: number | null;
  buy?: boolean;
  sell?: boolean;
}

export interface StockKlinePanelProps {
  data: PriceRow[];
  maVisibility: MaVisibility;
  onToggleMa: (key: keyof MaVisibility) => void;
  chartDateRange: DateRange | null;
  onChangeDateRange: (next: DateRange | null) => void;
  defaultStart: string;
  defaultEnd: string;
}

function CandleShape(props: any) {
  const { x, y, width, height, payload } = props;
  const { open, high, low, close } = payload;
  if (open === undefined || close === 0) return null;
  const isUp = close >= open;
  const color = isUp ? '#ef4444' : '#22c55e';
  const cx = x + width / 2;
  const pxPerUnit = height / close;
  const highY = y + height - high * pxPerUnit;
  const lowY = y + height - low * pxPerUnit;
  const openY = y + height - open * pxPerUnit;
  const closeY = y + height - close * pxPerUnit;
  const bodyTop = Math.min(openY, closeY);
  const bodyBottom = Math.max(openY, closeY);
  return (
    <g>
      <line x1={cx} y1={highY} x2={cx} y2={lowY} stroke={color} strokeWidth={1} />
      <rect
        x={x + 1} y={bodyTop}
        width={width - 2}
        height={Math.max(1, bodyBottom - bodyTop)}
        fill={isUp ? color : 'transparent'}
        stroke={color} strokeWidth={1}
      />
    </g>
  );
}

function BuyMarker(props: any) {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  const size = 6;
  const points = [`${cx},${cy - size}`, `${cx - size},${cy + size}`, `${cx + size},${cy + size}`].join(' ');
  return <polygon points={points} fill="#22c55e" stroke="#15803d" strokeWidth={1} />;
}

function SellMarker(props: any) {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  const size = 6;
  const points = [`${cx},${cy + size}`, `${cx - size},${cy - size}`, `${cx + size},${cy - size}`].join(' ');
  return <polygon points={points} fill="#ef4444" stroke="#b91c1c" strokeWidth={1} />;
}

export function StockKlinePanel(props: StockKlinePanelProps) {
  const filtered = filterByDateRange(props.data, props.chartDateRange);
  const filteredMap = useMemo(() => new Map(filtered.map(d => [d.date, d])), [filtered]);
  const buyPoints = filtered.filter(p => p.buy);
  const sellPoints = filtered.filter(p => p.sell);

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

      <div className="chart-container">
        <ResponsiveContainer width="100%" height={400}>
          <ComposedChart data={filtered}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={32} />
            <YAxis domain={[0, 'auto']} />
            <Tooltip
              formatter={(value: any, name: string) => {
                if (typeof value === 'number') return [value.toFixed(2), name];
                return [value, name];
              }}
              labelFormatter={(label: string) => {
                const point = filteredMap.get(label);
                if (!point) return label;
                return `${label} | O:${point.open?.toFixed(2)} H:${point.high?.toFixed(2)} L:${point.low?.toFixed(2)} C:${point.close?.toFixed(2)}`;
              }}
            />
            <Legend />
            <Bar dataKey="close" shape={CandleShape} isAnimationActive={false} legendType="none" />
            {props.maVisibility.ma5 && <Line type="monotone" dataKey="ma5" stroke="#ef4444" dot={false} strokeWidth={1.5} name="MA5" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.ma10 && <Line type="monotone" dataKey="ma10" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="MA10" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.ma20 && <Line type="monotone" dataKey="ma20" stroke="#2563eb" dot={false} strokeWidth={1.5} name="MA20" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.ma60 && <Line type="monotone" dataKey="ma60" stroke="#7c3aed" dot={false} strokeWidth={1.5} name="MA60" isAnimationActive={false} connectNulls={false} />}
            {props.maVisibility.boll && (
              <>
                <Line type="monotone" dataKey="boll_upper" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL 上轨" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="boll_mid" stroke="#eab308" dot={false} strokeWidth={1.2} name="BOLL 中轨" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="boll_lower" stroke="#a855f7" dot={false} strokeWidth={1} name="BOLL 下轨" isAnimationActive={false} connectNulls={false} />
              </>
            )}
            {buyPoints.map(point => (
              <ReferenceDot key={`buy-${point.date}`} x={point.date} y={point.low} shape={BuyMarker} ifOverflow="extendDomain" />
            ))}
            {sellPoints.map(point => (
              <ReferenceDot key={`sell-${point.date}`} x={point.date} y={point.high} shape={SellMarker} ifOverflow="extendDomain" />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
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