export interface DateRange {
  start: string;
  end: string;
}

export function filterByDateRange<T extends { date: string }>(
  rows: T[],
  range: DateRange | null
): T[] {
  if (!range) return rows;
  return rows.filter(r => r.date >= range.start && r.date <= range.end);
}