import { useMemo } from 'react';
import {
  Bar, CartesianGrid, ComposedChart, Legend, Line,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Eye, EyeOff } from 'lucide-react';
import ChartDateRangeControl from '../ChartDateRangeControl';
import { filterByDateRange, DateRange } from '../charts/filterByDateRange';
import type { MaVisibility, PriceRow } from './StockKlinePanel';

export interface IndexKlinePanelProps {
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

export function IndexKlinePanel(props: IndexKlinePanelProps) {
  const filtered = filterByDateRange(props.data, props.chartDateRange);
  const filteredMap = useMemo(() => new Map(filtered.map(d => [d.date, d])), [filtered]);

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>上证指数 K 线 + MA + BOLL</h3>
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
            <YAxis domain={['auto', 'auto']} />
            <Tooltip
              formatter={(value: any, name: string) => {
                if (value == null) return ['--', name];
                if (typeof value === 'number') return [value.toFixed(2), name];
                return [value, name];
              }}
              labelFormatter={(label: string) => {
                const point = filteredMap.get(label);
                if (!point) return label;
                return `${label} | O:${point.open.toFixed(2)} H:${point.high.toFixed(2)} L:${point.low.toFixed(2)} C:${point.close.toFixed(2)}`;
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
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}