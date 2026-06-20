import type React from 'react';
import { Eye, EyeOff } from 'lucide-react';
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceDot,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import ChartDateRangeControl from '../ChartDateRangeControl';
import { filterByDateRange, DateRange } from '../charts/filterByDateRange';

export interface EquityPoint {
  date: string;
  value?: number;
  total_score?: number;
  trend_score?: number;
  sentiment_score?: number;
  volume_score?: number;
  buy?: boolean;
  sell?: boolean;
}

export interface LineVisibility {
  equity: boolean;
  totalScore: boolean;
  trendScore: boolean;
  sentimentScore: boolean;
  volumeScore: boolean;
}

export interface EquityPanelProps {
  data: EquityPoint[];
  chartDateRange: DateRange | null;
  onChangeDateRange: (next: DateRange | null) => void;
  defaultStart: string;
  defaultEnd: string;
  lineVisibility: LineVisibility;
  onToggleLine: (key: keyof LineVisibility) => void;
}

// 图表线色（与 design tokens 对齐：--line-* 变量）
const LINE_COLORS = {
  equity: '#3b82f6',
  totalScore: '#14b8a6',
  trendScore: '#f59e0b',
  sentimentScore: '#c084fc',
  volumeScore: '#fb7185',
} as const;

const BuyMarker: React.FC<{ cx?: number; cy?: number }> = (props) => {
  const { cx, cy } = props;
  if (cx == null || cy == null) return <g data-testid="buy-marker-empty" />;
  const size = 6;
  const points = [
    `${cx},${cy - size}`,
    `${cx - size},${cy + size}`,
    `${cx + size},${cy + size}`,
  ].join(' ');
  return <polygon points={points} fill="#22c55e" stroke="#16a34a" strokeWidth={1} />;
};

const SellMarker: React.FC<{ cx?: number; cy?: number }> = (props) => {
  const { cx, cy } = props;
  if (cx == null || cy == null) return <g data-testid="sell-marker-empty" />;
  const size = 6;
  const points = [
    `${cx},${cy + size}`,
    `${cx - size},${cy - size}`,
    `${cx + size},${cy - size}`,
  ].join(' ');
  return <polygon points={points} fill="#ef4444" stroke="#dc2626" strokeWidth={1} />;
};

export function EquityPanel(props: EquityPanelProps) {
  const displayData = filterByDateRange(props.data, props.chartDateRange ?? null);
  const buyPoints = displayData.filter((p) => p.buy);
  const sellPoints = displayData.filter((p) => p.sell);

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>权益曲线 & 市场评分</h3>
      </div>

      <div className="line-toggles">
        <button
          className={`toggle-btn ${props.lineVisibility.equity ? 'active' : ''}`}
          onClick={() => props.onToggleLine('equity')}
        >
          {props.lineVisibility.equity ? <Eye size={14} /> : <EyeOff size={14} />}
          权益净值
        </button>
        <button
          className={`toggle-btn ${props.lineVisibility.totalScore ? 'active' : ''}`}
          onClick={() => props.onToggleLine('totalScore')}
        >
          {props.lineVisibility.totalScore ? <Eye size={14} /> : <EyeOff size={14} />}
          总评分
        </button>
        <button
          className={`toggle-btn ${props.lineVisibility.trendScore ? 'active' : ''}`}
          onClick={() => props.onToggleLine('trendScore')}
        >
          {props.lineVisibility.trendScore ? <Eye size={14} /> : <EyeOff size={14} />}
          趋势评分
        </button>
        <button
          className={`toggle-btn ${props.lineVisibility.sentimentScore ? 'active' : ''}`}
          onClick={() => props.onToggleLine('sentimentScore')}
        >
          {props.lineVisibility.sentimentScore ? <Eye size={14} /> : <EyeOff size={14} />}
          情绪评分
        </button>
        <button
          className={`toggle-btn ${props.lineVisibility.volumeScore ? 'active' : ''}`}
          onClick={() => props.onToggleLine('volumeScore')}
        >
          {props.lineVisibility.volumeScore ? <Eye size={14} /> : <EyeOff size={14} />}
          成交量评分
        </button>
      </div>

      <ChartDateRangeControl
        value={props.chartDateRange}
        defaultStart={props.defaultStart}
        defaultEnd={props.defaultEnd}
        onChange={props.onChangeDateRange}
      />

      <div className="chart-container">
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={displayData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="date" minTickGap={32} stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <YAxis yAxisId="left" domain={['auto', 'auto']} stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <YAxis yAxisId="right" orientation="right" domain={[0, 1]} stroke="#94a3b8" tick={{ fill: '#94a3b8', fontSize: 12 }} />
            <Tooltip
              contentStyle={{
                background: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: 6,
                color: '#e2e8f0',
              }}
              labelStyle={{ color: '#94a3b8' }}
            />
            <Legend wrapperStyle={{ color: '#94a3b8', fontSize: 12 }} />
            {props.lineVisibility.equity && (
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="value"
                stroke={LINE_COLORS.equity}
                dot={false}
                strokeWidth={2}
                name="权益净值"
                isAnimationActive={false}
              />
            )}
            {props.lineVisibility.totalScore && (
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="total_score"
                stroke={LINE_COLORS.totalScore}
                dot={false}
                strokeWidth={2}
                name="总评分"
                isAnimationActive={false}
              />
            )}
            {props.lineVisibility.trendScore && (
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="trend_score"
                stroke={LINE_COLORS.trendScore}
                dot={false}
                name="趋势评分"
                isAnimationActive={false}
              />
            )}
            {props.lineVisibility.sentimentScore && (
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="sentiment_score"
                stroke={LINE_COLORS.sentimentScore}
                dot={false}
                name="情绪评分"
                isAnimationActive={false}
              />
            )}
            {props.lineVisibility.volumeScore && (
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="volume_score"
                stroke={LINE_COLORS.volumeScore}
                dot={false}
                name="成交量评分"
                isAnimationActive={false}
              />
            )}
            {buyPoints.map((point) => (
              <ReferenceDot
                key={`buy-${point.date}`}
                x={point.date}
                y={point.value}
                yAxisId="left"
                shape={BuyMarker as never}
                ifOverflow="extendDomain"
              />
            ))}
            {sellPoints.map((point) => (
              <ReferenceDot
                key={`sell-${point.date}`}
                x={point.date}
                y={point.value}
                yAxisId="left"
                shape={SellMarker as never}
                ifOverflow="extendDomain"
              />
            ))}
          </LineChart>
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
