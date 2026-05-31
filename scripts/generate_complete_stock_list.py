#!/usr/bin/env python3
"""
生成完整的 A 股股票列表
使用 AkShare API 获取所有上市公司信息
"""

import json
import sys
from pathlib import Path

try:
    import akshare as ak
except ImportError:
    print("Error: akshare not installed. Run: pip install akshare")
    sys.exit(1)


def get_all_stocks():
    """获取所有 A 股股票列表"""
    print("正在从 AkShare 获取 A 股股票列表...")

    try:
        # 获取所有 A 股股票信息
        df = ak.stock_info_a_sina()

        # 转换为所需格式
        stocks = []
        for _, row in df.iterrows():
            code = str(row['code']).strip()
            name = str(row['name']).strip()

            # 验证代码格式（6位数字）
            if len(code) == 6 and code.isdigit():
                stocks.append({
                    'code': code,
                    'name': name
                })

        # 按代码排序
        stocks.sort(key=lambda x: x['code'])

        print(f"✓ 成功获取 {len(stocks)} 只股票")

        # 统计各市场
        shanghai = len([s for s in stocks if s['code'].startswith('6')])
        shenzhen = len([s for s in stocks if s['code'].startswith('0')])

        print(f"  - 上海主板: {shanghai} 只")
        print(f"  - 深圳主板: {shenzhen} 只")

        return stocks

    except Exception as e:
        print(f"Error: 获取股票列表失败 - {e}")
        sys.exit(1)


def generate_typescript_code(stocks):
    """生成 TypeScript 代码"""

    code = """// 完整的A股股票列表（主板）- 包含所有上市公司
// 数据来源：AkShare API
// 更新时间：自动生成
export const ALL_STOCKS = [
"""

    for stock in stocks:
        code += f"  {{ code: '{stock['code']}', name: '{stock['name']}' }},\n"

    code += """];

export function getStockLabel(code: string): string {
  const stock = ALL_STOCKS.find(s => s.code === code);
  return stock ? `${stock.code} - ${stock.name}` : code;
}

export function searchStocks(query: string): typeof ALL_STOCKS {
  if (!query) return ALL_STOCKS;
  const q = query.toLowerCase();

  const fuzzyMatch = (text: string, pattern: string): boolean => {
    let patternIdx = 0;
    for (let i = 0; i < text.length && patternIdx < pattern.length; i++) {
      if (text[i] === pattern[patternIdx]) {
        patternIdx++;
      }
    }
    return patternIdx === pattern.length;
  };

  return ALL_STOCKS.filter(s => {
    const code = s.code.toLowerCase();
    const name = s.name.toLowerCase();

    if (code.startsWith(q) || name.startsWith(q)) return true;
    if (code.includes(q) || name.includes(q)) return true;
    if (fuzzyMatch(code, q) || fuzzyMatch(name, q)) return true;

    return false;
  }).sort((a, b) => {
    const aCode = a.code.toLowerCase();
    const aName = a.name.toLowerCase();
    const bCode = b.code.toLowerCase();
    const bName = b.name.toLowerCase();

    if (aCode.startsWith(q) && !bCode.startsWith(q)) return -1;
    if (!aCode.startsWith(q) && bCode.startsWith(q)) return 1;
    if (aName.startsWith(q) && !bName.startsWith(q)) return -1;
    if (!aName.startsWith(q) && bName.startsWith(q)) return 1;

    if (aCode.includes(q) && !bCode.includes(q)) return -1;
    if (!aCode.includes(q) && bCode.includes(q)) return 1;
    if (aName.includes(q) && !bName.includes(q)) return -1;
    if (!aName.includes(q) && bName.includes(q)) return 1;

    return a.code.localeCompare(b.code);
  });
}
"""

    return code


def main():
    # 获取股票列表
    stocks = get_all_stocks()

    # 生成 TypeScript 代码
    ts_code = generate_typescript_code(stocks)

    # 保存到文件
    output_path = Path(__file__).parent.parent / "web" / "src" / "stocks-full.ts"
    output_path.write_text(ts_code, encoding='utf-8')

    print(f"\n✓ 已保存到: {output_path}")
    print(f"✓ 总共 {len(stocks)} 只股票")

    # 保存 JSON 备份
    json_path = Path(__file__).parent.parent / "data" / "stocks.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps({'stocks': stocks}, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"✓ JSON 备份: {json_path}")


if __name__ == '__main__':
    main()
