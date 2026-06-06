/**
 * K 线图技术指标公式（生产代码）。
 *
 * 与 backtest/chart_indicators.py 一一对应。
 * 改这边要同步改 Python 端的公式与测试。
 */

export function calcMA(closes: number[], period: number): (number | null)[] {
  if (period <= 0) throw new Error(`period must be positive, got ${period}`);
  if (closes.length === 0) return [];
  const result: (number | null)[] = [];
  let sum = 0;
  for (let i = 0; i < closes.length; i++) {
    sum += closes[i];
    if (i >= period) sum -= closes[i - period];
    if (i < period - 1) {
      result.push(null);
    } else {
      result.push(sum / period);
    }
  }
  return result;
}

function ema(values: number[], period: number): (number | null)[] {
  if (period <= 0) throw new Error(`period must be positive, got ${period}`);
  if (values.length === 0) return [];
  const k = 2 / (period + 1);
  const result: (number | null)[] = [];
  let prevSma: number | null = null;
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      result.push(null);
      continue;
    }
    if (prevSma === null) {
      let sum = 0;
      for (let j = i - period + 1; j <= i; j++) sum += values[j];
      prevSma = sum / period;
    } else {
      prevSma = values[i] * k + prevSma * (1 - k);
    }
    result.push(prevSma);
  }
  return result;
}

export function calcBoll(
  closes: number[],
  period = 20,
  numStd = 2.0
): { upper: (number | null)[]; mid: (number | null)[]; lower: (number | null)[] } {
  if (period <= 0) throw new Error(`period must be positive, got ${period}`);
  if (closes.length === 0) return { upper: [], mid: [], lower: [] };
  const mid: (number | null)[] = [];
  const upper: (number | null)[] = [];
  const lower: (number | null)[] = [];
  let sum = 0;
  let sumSq = 0;
  for (let i = 0; i < closes.length; i++) {
    sum += closes[i];
    sumSq += closes[i] * closes[i];
    if (i >= period) {
      sum -= closes[i - period];
      sumSq -= closes[i - period] * closes[i - period];
    }
    if (i < period - 1) {
      mid.push(null);
      upper.push(null);
      lower.push(null);
    } else {
      const mean = sum / period;
      const std = Math.sqrt(Math.max(0, sumSq / period - mean * mean));
      mid.push(mean);
      upper.push(mean + numStd * std);
      lower.push(mean - numStd * std);
    }
  }
  return { upper, mid, lower };
}

export function calcMacd(
  closes: number[],
  fast = 12,
  slow = 26,
  signal = 9
): { dif: (number | null)[]; dea: (number | null)[]; macd: (number | null)[] } {
  if (closes.length === 0) return { dif: [], dea: [], macd: [] };
  const emaFast = ema(closes, fast);
  const emaSlow = ema(closes, slow);
  const dif: (number | null)[] = emaFast.map((v, i) =>
    v !== null && emaSlow[i] !== null ? v - (emaSlow[i] as number) : null
  );
  const difForEma = dif.map((d) => d ?? 0);
  const deaRaw = ema(difForEma, signal);
  const dea: (number | null)[] = dif.map((d, i) =>
    d !== null && i >= slow - 1 + signal - 1 ? deaRaw[i] : null
  );
  const macd: (number | null)[] = dif.map((d, i) =>
    d !== null && dea[i] !== null && i >= slow - 1 + signal ? (d - (dea[i] as number)) * 2 : null
  );
  return { dif, dea, macd };
}

export function calcKdj(
  highs: number[],
  lows: number[],
  closes: number[],
  n = 9,
  kPeriod = 3,
  dPeriod = 3
): { k: (number | null)[]; d: (number | null)[]; j: (number | null)[] } {
  if (highs.length !== lows.length || highs.length !== closes.length) {
    throw new Error('highs, lows, closes must have equal length');
  }
  if (closes.length === 0) return { k: [], d: [], j: [] };
  const rsv: (number | null)[] = [];
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1) {
      rsv.push(null);
      continue;
    }
    let hh = highs[i];
    let ll = lows[i];
    for (let j = i - n + 1; j <= i; j++) {
      if (highs[j] > hh) hh = highs[j];
      if (lows[j] < ll) ll = lows[j];
    }
    const rng = hh - ll;
    rsv.push(rng !== 0 ? ((closes[i] - ll) / rng) * 100 : 50);
  }
  const kAlpha = 1 / kPeriod;
  const dAlpha = 1 / dPeriod;
  const k: (number | null)[] = [];
  const d: (number | null)[] = [];
  let prevK = 50;
  let prevD = 50;
  for (let i = 0; i < closes.length; i++) {
    if (rsv[i] === null) {
      k.push(null);
      d.push(null);
      continue;
    }
    prevK = prevK * (1 - kAlpha) + (rsv[i] as number) * kAlpha;
    prevD = prevD * (1 - dAlpha) + prevK * dAlpha;
    k.push(prevK);
    d.push(prevD);
  }
  const j: (number | null)[] = k.map((kk, i) =>
    kk !== null && d[i] !== null ? 3 * kk - 2 * (d[i] as number) : null
  );
  return { k, d, j };
}
