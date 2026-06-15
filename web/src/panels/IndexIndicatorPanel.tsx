import {
  Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { filterByDateRange, DateRange } from '../charts/filterByDateRange';
import type { IndicatorKey, IndicatorPoint } from './StockIndicatorPanel';

export interface IndexIndicatorPanelProps {
  data: IndicatorPoint[];
  selected: IndicatorKey;
  onChangeSelected: (next: IndicatorKey) => void;
  chartDateRange: DateRange | null;
}

export function IndexIndicatorPanel(props: IndexIndicatorPanelProps) {
  const filtered = filterByDateRange(props.data, props.chartDateRange);

  return (
    <section className="panel">
      <div className="chart-header">
        <h3>上证指数技术指标</h3>
        <select
          value={props.selected}
          onChange={(e) => props.onChangeSelected(e.target.value as IndicatorKey)}
          style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #cbd5df', background: '#fff' }}
        >
          <option value="macd">MACD</option>
          <option value="kdj">KDJ</option>
          <option value="volume">Volume</option>
          <option value="amount">Amount (100M CNY)</option>
        </select>
      </div>

      <div className="chart-container">
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={filtered}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" minTickGap={32} />
            <YAxis domain={['auto', 'auto']} />
            <Tooltip />
            {props.selected === 'macd' && (
              <>
                <Bar dataKey="macd" isAnimationActive={false} name="MACD">
                  {filtered.map((entry, i) => (
                    <Cell key={`m-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                  ))}
                </Bar>
                <Line type="monotone" dataKey="dif" stroke="#facc15" dot={false} strokeWidth={1.4} name="DIF" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="dea" stroke="#f97316" dot={false} strokeWidth={1.4} name="DEA" isAnimationActive={false} connectNulls={false} />
              </>
            )}
            {props.selected === 'kdj' && (
              <>
                <Line type="monotone" dataKey="k" stroke="#f3f4f6" dot={false} strokeWidth={1.4} name="K" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="d" stroke="#facc15" dot={false} strokeWidth={1.4} name="D" isAnimationActive={false} connectNulls={false} />
                <Line type="monotone" dataKey="j" stroke="#a855f7" dot={false} strokeWidth={1.4} name="J" isAnimationActive={false} connectNulls={false} />
                <ReferenceLine y={80} stroke="#9ca3af" strokeDasharray="2 2" />
                <ReferenceLine y={20} stroke="#9ca3af" strokeDasharray="2 2" />
              </>
            )}
            {props.selected === 'volume' && (
              <Bar dataKey="value" isAnimationActive={false} name="Volume">
                {filtered.map((entry, i) => (
                  <Cell key={`v-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                ))}
              </Bar>
            )}
            {props.selected === 'amount' && (
              <Bar dataKey="value" isAnimationActive={false} name="Amount">
                {filtered.map((entry, i) => (
                  <Cell key={`a-${i}`} fill={entry.isUp ? '#ef4444' : '#22c55e'} />
                ))}
              </Bar>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}