import { useState } from 'react';
import { Eye, EyeOff, ZoomIn, ZoomOut } from 'lucide-react';
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

function BuyMarker(props: any) {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  const size = 6;
  const points = [
    `${cx},${cy - size}`,
    `${cx - size},${cy + size}`,
    `${cx + size},${cy + size}`,
  ].join(' ');
  return <polygon points={points} fill="#22c55e" stroke="#15803d" strokeWidth={1} />;
}

function SellMarker(props: any) {
  const { cx, cy } = props;
  if (cx == null || cy == null) return null;
  const size = 6;
  const points = [
    `${cx},${cy + size}`,
    `${cx - size},${cy - size}`,
    `${cx + size},${cy - size}`,
  ].join(' ');
  return <polygon points={points} fill="#ef4444" stroke="#b91c1c" strokeWidth={1} />;
}

export function EquityPanel(props: EquityPanelProps) {
  const [zoom, setZoom] = useState({ start: 0, end: 100 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState(0);

  const filteredData = filterByDateRange(props.data, props.chartDateRange ?? null);

  // Apply zoom only when chartDateRange is not set
  const displayData = props.chartDateRange
    ? filteredData
    : (() => {
        const start = Math.floor((props.data.length * zoom.start) / 100);
        const end = Math.ceil((props.data.length * zoom.end) / 100);
        return props.data.slice(start, end);
      })();

  const buyPoints = displayData.filter(p => p.buy);
  const sellPoints = displayData.filter(p => p.sell);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart(e.clientX);
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const delta = e.clientX - dragStart;
    const range = zoom.end - zoom.start;
    const movePercent = (delta / 800) * 100;
    let newStart = zoom.start - movePercent;
    let newEnd = zoom.end - movePercent;
    if (newStart < 0) { newStart = 0; newEnd = range; }
    if (newEnd > 100) { newEnd = 100; newStart = 100 - range; }
    setZoom({ start: newStart, end: newEnd });
    setDragStart(e.clientX);
  };
  const handleMouseUp = () => setIsDragging(false);

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>权益曲线 & 市场评分</h3>
        <div className="zoom-controls">
          <button
            className="zoom-btn"
            onClick={() => setZoom({ start: Math.max(0, zoom.start - 10), end: Math.min(100, zoom.end + 10) })}
            title="缩小（显示更多数据）"
          >
            <ZoomOut size={16} /> 缩小
          </button>
          <button
            className="zoom-btn"
            onClick={() => setZoom({ start: Math.min(50, zoom.start + 10), end: Math.max(50, zoom.end - 10) })}
            title="放大（显示更少数据）"
          >
            <ZoomIn size={16} /> 放大
          </button>
          <button
            className="zoom-btn"
            onClick={() => setZoom({ start: 0, end: 100 })}
            title="重置"
          >
            重置
          </button>
        </div>
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

      <div
        className="chart-container"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      >
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={displayData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={32} />
            <YAxis yAxisId="left" domain={['auto', 'auto']} />
            <YAxis yAxisId="right" orientation="right" domain={[0, 1]} />
            <Tooltip />
            <Legend />
            {props.lineVisibility.equity && (
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="value"
                stroke="#2563eb"
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
                stroke="#0f766e"
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
                stroke="#f59e0b"
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
                stroke="#7c3aed"
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
                stroke="#dc2626"
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
                shape={BuyMarker}
                ifOverflow="extendDomain"
              />
            ))}
            {sellPoints.map((point) => (
              <ReferenceDot
                key={`sell-${point.date}`}
                x={point.date}
                y={point.value}
                yAxisId="left"
                shape={SellMarker}
                ifOverflow="extendDomain"
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="chart-hint">提示：拖动图表左右查看相邻时间段数据。</p>
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