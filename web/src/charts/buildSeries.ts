import { calcBoll, calcMA } from '../indicators';

export interface CandleInput {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TradeInput {
  date: string;
  pnl: number;
  pnlcomm: number;
  barlen: number;
  size: number;
}

export interface KlineRow extends CandleInput {
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
  boll_upper: number | null;
  boll_mid: number | null;
  boll_lower: number | null;
}

export type TradeSide = 'buy' | 'sell';
export interface TradeMarker {
  date: string;
  side: TradeSide;
}

export function buildKlineSeries(data: CandleInput[]): KlineRow[] {
  const closes = data.map(d => d.close);
  const ma5 = calcMA(closes, 5);
  const ma10 = calcMA(closes, 10);
  const ma20 = calcMA(closes, 20);
  const ma60 = calcMA(closes, 60);
  const { upper, mid, lower } = calcBoll(closes, 20, 2.0);

  return data.map((d, i) => ({
    ...d,
    ma5: ma5[i],
    ma10: ma10[i],
    ma20: ma20[i],
    ma60: ma60[i],
    boll_upper: upper[i],
    boll_mid: mid[i],
    boll_lower: lower[i],
  }));
}

// 复用现有 buildTradeMarkerMap 的偶/奇判定语义（见 App.tsx:124-138）
export function buildTradeMarkers(trades: TradeInput[]): TradeMarker[] {
  return trades.map((t, i) => ({
    date: t.date,
    side: (i % 2 === 0 ? 'buy' : 'sell') as TradeSide,
  }));
}