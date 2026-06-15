import { describe, expect, it } from 'vitest';
import { filterByDateRange } from './filterByDateRange';

describe('filterByDateRange', () => {
  const rows = [
    { date: '20240101', v: 1 },
    { date: '20240115', v: 2 },
    { date: '20240201', v: 3 },
    { date: '20240215', v: 4 },
  ];

  it('returns input unchanged when range is null', () => {
    expect(filterByDateRange(rows, null)).toEqual(rows);
  });

  it('filters rows within inclusive range', () => {
    const out = filterByDateRange(rows, { start: '20240115', end: '20240201' });
    expect(out.map(r => r.date)).toEqual(['20240115', '20240201']);
  });

  it('returns empty array when no rows match', () => {
    expect(filterByDateRange(rows, { start: '20250101', end: '20250131' })).toEqual([]);
  });
});