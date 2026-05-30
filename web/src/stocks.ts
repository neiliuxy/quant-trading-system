// 导入完整的股票列表
import { ALL_STOCKS, searchStocks as searchAllStocks } from './stocks-full';

// 导出完整的股票列表
export const STOCKS = ALL_STOCKS;

export function getStockLabel(code: string): string {
  const stock = STOCKS.find(s => s.code === code);
  return stock ? `${stock.code} - ${stock.name}` : code;
}

export function searchStocks(query: string): typeof STOCKS {
  return searchAllStocks(query);
}
