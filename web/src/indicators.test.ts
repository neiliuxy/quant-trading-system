import { describe, expect, it } from 'vitest';
import { calcBoll, calcMA } from './indicators';

describe('indicators', () => {
  it('calcMA matches the expected rolling average output', () => {
    expect(calcMA([10, 11, 12, 13, 14, 15], 3)).toEqual([
      null,
      null,
      11,
      12,
      13,
      14,
    ]);
  });

  it('calcBoll matches the expected Bollinger band output', () => {
    const result = calcBoll([10, 11, 12, 13, 14, 15], 3, 2);

    expect(result.mid).toEqual([null, null, 11, 12, 13, 14]);
    expect(result.upper[0]).toBeNull();
    expect(result.upper[1]).toBeNull();
    expect(result.lower[0]).toBeNull();
    expect(result.lower[1]).toBeNull();

    [12.632993161855452, 13.632993161855452, 14.632993161855452, 15.632993161855452].forEach(
      (value, index) => {
        expect(result.upper[index + 2]).toBeCloseTo(value, 12);
      }
    );
    [9.367006838144548, 10.367006838144548, 11.367006838144548, 12.367006838144548].forEach(
      (value, index) => {
        expect(result.lower[index + 2]).toBeCloseTo(value, 12);
      }
    );
  });
});
