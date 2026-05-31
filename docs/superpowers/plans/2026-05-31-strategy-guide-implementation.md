# Strategy Guide 策略库页面实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建一个独立的策略说明文档页面，用户可在回测工作台和策略库之间切换

**Architecture:** 新建 `strategyGuides.ts` 存放所有策略的说明数据，新建 `StrategyGuide.tsx` 作为页面组件，在 `App.tsx` 中添加顶部导航切换。纯前端实现，数据写死在前端。

**Tech Stack:** React, TypeScript, CSS, Recharts 已有的样式体系

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `web/src/strategyGuides.ts` | 新建 | 存放所有策略的说明数据 |
| `web/src/StrategyGuide.tsx` | 新建 | 策略库页面组件（左侧列表 + 右侧详情） |
| `web/src/App.tsx` | 修改 | 添加导航和页面切换状态 |
| `web/src/types.ts` | 修改 | 添加 `StrategyGuideData` 类型 |
| `web/src/style.css` | 修改 | 添加策略库相关样式 |

---

### Task 1: 添加类型定义

**Files:**
- Modify: `web/src/types.ts`

- [ ] **Step 1: 添加 StrategyGuideData 类型**

在 `web/src/types.ts` 末尾添加：

```typescript
export interface StrategyGuideParam {
  name: string;
  label: string;
  meaning: string;
  recommendedValue: string;
  adjustmentTips: string;
}

export interface StrategyGuideData {
  id: string;
  name: string;
  description: string;
  applicableScenarios: string;
  principle: {
    title: string;
    content: string;
  };
  parameters: StrategyGuideParam[];
  characteristics: {
    tradingFrequency: string;
    holdingPeriod: string;
    applicableStocks: string;
    riskLevel: string;
  };
}
```

- [ ] **Step 2: 验证 TypeScript 编译**

Run: `npx tsc --noEmit`（预期: 类型检查通过）

- [ ] **Step 3: Commit**

```bash
git add web/src/types.ts
git commit -m "feat: add StrategyGuideData type for strategy docs"
```

---

### Task 2: 创建策略说明数据

**Files:**
- Create: `web/src/strategyGuides.ts`

- [ ] **Step 1: 创建 B1 Strategy 的说明数据**

```typescript
import type { StrategyGuideData } from './types';

export const strategyGuides: StrategyGuideData[] = [
  {
    id: 'b1_strategy',
    name: 'B1 Strategy',
    description: '趋势跟踪 + 超卖回调入场策略，结合市场择时和 7 个买入条件',
    applicableScenarios: '适合中期上升趋势明显、个股跟随大盘走势的市场环境',

    principle: {
      title: '核心原理',
      content: `B1 策略采用"市场择时 + 个股筛选"的双层架构。首先通过上证综指的 120 日均线判断市场是否处于上升趋势，只有在大盘处于上升趋势时才允许开仓，从根本上规避系统性风险。

入场端采用严格的 7 条件过滤机制：短期均线上穿长期均线确认趋势、60 日波动率不超过 100% 排除过热个股、BBI 连续多日上行确认中期走势、KDJ 的 J 值接近 0 识别超卖机会，再结合当日涨跌幅小、振幅低、成交量低三个条件筛选出处于"缩量企稳"状态的个股。

出场采用双重止盈止损：移动止盈基于均线死叉（短均线下穿长均线），硬止损则设为入场当日最低价以下，跌破立即离场。这种双保险机制确保单笔亏损可控。`,
    },

    parameters: [
      {
        name: 'index_ma',
        label: '市场择时 MA',
        meaning: '上证综指的移动平均线周期，用于判断市场是否处于上升趋势。均线上行时才允许开仓',
        recommendedValue: '120',
        adjustmentTips: '增大周期（如 250）使择时更保守，减少交易频率；减小周期（如 60）使择时更敏感',
      },
      {
        name: 'short_ma',
        label: '短期均线',
        meaning: '用于跟踪短期趋势，与长期均线配合形成买入/卖出信号',
        recommendedValue: '20',
        adjustmentTips: '减小周期（如 10）使入场更敏感；增大周期（如 30）过滤更多假信号',
      },
      {
        name: 'long_ma',
        label: '长期均线',
        meaning: '用于确认中长期趋势方向，短期均线在其上方表示多头排列',
        recommendedValue: '60',
        adjustmentTips: '增大周期（如 120）要求更强的趋势确认；减小周期（如 30）放宽趋势要求',
      },
      {
        name: 'j_threshold',
        label: 'KDJ J 值阈值',
        meaning: 'KDJ 指标的 J 值买入阈值。J 值低于该阈值时认为股票处于超卖状态',
        recommendedValue: '5',
        adjustmentTips: '增大（如 10）放松超卖要求，更多入场机会但质量可能下降；减小（如 0）要求极度超卖',
      },
      {
        name: 'vol_window',
        label: '波动率窗口',
        meaning: '计算波动率的天数范围，波动率 = (期间最高 - 最低) / 最低',
        recommendedValue: '60',
        adjustmentTips: '增大周期（如 120）使波动率更平滑；减小周期（如 30）对近期波动更敏感',
      },
      {
        name: 'vol_max',
        label: '最大波动率',
        meaning: '允许的最大波动率阈值，超过该值的品种被排除（避免过热股）',
        recommendedValue: '1.0 (100%)',
        adjustmentTips: '降低（如 0.8）只选低波动品种；提高（如 1.5）放宽筛选包容更多股票',
      },
      {
        name: 'amp_ratio',
        label: '振幅比率',
        meaning: '当日振幅与 20 日均振幅的比率上限，限制日间波动',
        recommendedValue: '0.5',
        adjustmentTips: '降低（如 0.3）要求极低振幅（更平稳）；提高（如 0.8）放宽振幅限制',
      },
      {
        name: 'vol_ratio',
        label: '成交量比率',
        meaning: '当日成交量与 20 日均成交量的比率上限，用于识别缩量企稳',
        recommendedValue: '0.6',
        adjustmentTips: '降低（如 0.4）要求极度缩量；提高（如 0.8）容忍更多成交量',
      },
      {
        name: 'max_pct_change',
        label: '最大日涨跌幅',
        meaning: '当日价格变动百分比上限，排除大幅波动的品种',
        recommendedValue: '0.02 (2%)',
        adjustmentTips: '降低（如 0.01）只选极稳定品种；提高（如 0.03）扩大选股范围',
      },
      {
        name: 'bbuphold_days',
        label: 'BBI 连涨天数',
        meaning: 'BBI 指标连续上涨的天数，确认中期上行趋势强度',
        recommendedValue: '3',
        adjustmentTips: '增大（如 5）要求更强趋势确认；减小（如 1）放宽趋势要求',
      },
    ],

    characteristics: {
      tradingFrequency: '低频',
      holdingPeriod: '3-10 个交易日',
      applicableStocks: '流动性好的蓝筹股、大盘股，跟随大盘走势的品种',
      riskLevel: '中',
    },
  },

  {
    id: 'swing_ma_boll',
    name: 'Swing MA + Bollinger',
    description: '双均线交叉 + 布林带确认的波段趋势策略',
    applicableScenarios: '适合有明显趋势行情的股票，在趋势启动时入场',

    principle: {
      title: '核心原理',
      content: `该策略融合了趋势跟踪和波动率两种技术分析工具。核心逻辑是：当短期均线（默认 10 日）上穿长期均线（默认 20 日）形成"金叉"，同时价格位于布林带中轨（20 日均线）之上时，确认上升趋势有效，触发买入信号。

布林带在这里起到了双重作用：中轨作为趋势确认的过滤器，避免在均线纠缠时入场；上下轨则用于判断出场时机。当价格跌破下轨时，表明趋势可能反转或进入盘整，触发卖出。

出场机制同样采用均线和布林带双保险：短期均线下穿长期均线（死叉）或价格跌破布林带下轨，任一条件满足即平仓离场。这种设计确保在趋势延续时持有，在趋势转弱时及时退出。

回看期参数（boll_period）控制布林带计算的敏感度：较短的周期使布林带更快适应价格变化，但信号更多；较长的周期使布林带更平滑，信号更少但更可靠。`,
    },

    parameters: [
      {
        name: 'fast_ma',
        label: '快线 MA',
        meaning: '快速移动平均线周期，用于捕捉短期趋势变化',
        recommendedValue: '10',
        adjustmentTips: '减小（如 5）使入场更敏感；增大（如 15）过滤更多震荡信号',
      },
      {
        name: 'slow_ma',
        label: '慢线 MA',
        meaning: '慢速移动平均线周期，用于确认中长期趋势方向',
        recommendedValue: '20',
        adjustmentTips: '增大（如 30）要求更强趋势确认；减小（如 15）放宽趋势要求',
      },
      {
        name: 'boll_period',
        label: '布林带周期',
        meaning: '布林带计算使用的回看周期，影响中轨和标准差的计算',
        recommendedValue: '20',
        adjustmentTips: '增大（如 30）使布林带更平滑；减小（如 10）对价格变化更敏感',
      },
      {
        name: 'boll_devfactor',
        label: '布林带标准差倍数',
        meaning: '布林带上下轨的标准差倍数，决定通道宽度',
        recommendedValue: '2.0',
        adjustmentTips: '增大（如 2.5）使通道更宽，减少触及概率；减小（如 1.5）使通道更窄，增加信号频率',
      },
    ],

    characteristics: {
      tradingFrequency: '低频',
      holdingPeriod: '5-15 个交易日',
      applicableStocks: '趋势性较强的股票，避免长时间横盘震荡的品种',
      riskLevel: '中低',
    },
  },

  {
    id: 'bollinger_reversal',
    name: 'Bollinger Reversal',
    description: '布林带回归反转策略，捕捉价格从下轨反弹的机会',
    applicableScenarios: '适合震荡市中价格回归均值的机会型交易',

    principle: {
      title: '核心原理',
      content: `该策略基于布林带均值回归理论：当价格大幅偏离移动平均线（跌破下轨）后，往往会向均值回归。策略首先等待价格跌破布林带下轨，标记"超卖"状态，然后等待价格重新站上下轨上方时买入。

出场规则相对简单：当价格上涨触及布林带中轨或上轨时平仓离场。这意味着策略只捕捉从下轨到中轨/上轨的回归行情，不追求趋势延续。

该策略在震荡市中表现较好，但在强趋势市场中可能过早出场（趋势行情中价格可能沿上轨持续上行）。受限于只有 1 个买入条件，策略简单透明，但选股能力有限，更适合作为辅助策略使用。`,
    },

    parameters: [
      {
        name: 'boll_period',
        label: '布林带周期',
        meaning: '布林带计算使用的回看周期',
        recommendedValue: '20',
        adjustmentTips: '增大（如 30）使布林带更平滑，信号更少但更可靠；减小（如 10）捕捉更多反转机会',
      },
      {
        name: 'boll_devfactor',
        label: '布林带标准差倍数',
        meaning: '上下轨的标准差倍数，控制触发买入的极端程度',
        recommendedValue: '2.0',
        adjustmentTips: '增大（如 2.5）要求更极端的价格偏离才入场；减小（如 1.5）增加入场机会',
      },
    ],

    characteristics: {
      tradingFrequency: '中频',
      holdingPeriod: '2-7 个交易日',
      applicableStocks: '波动率适中的股票，适合震荡区间运行的品种',
      riskLevel: '中低',
    },
  },
];
```

- [ ] **Step 2: Commit**

```bash
git add web/src/strategyGuides.ts
git commit -m "feat: add strategy guide data for all 3 strategies"
```

---

### Task 3: 创建策略库页面组件

**Files:**
- Create: `web/src/StrategyGuide.tsx`

- [ ] **Step 1: 写入 StrategyGuide 组件**

```tsx
import { useState } from 'react';
import { BookOpen } from 'lucide-react';
import type { StrategyGuideData } from './types';
import { strategyGuides } from './strategyGuides';

type Props = {
  onBack: () => void;
};

export default function StrategyGuide({ onBack }: Props) {
  const [selectedId, setSelectedId] = useState(strategyGuides[0]?.id ?? '');
  const selected = strategyGuides.find((s) => s.id === selectedId);

  return (
    <div className="strategy-guide">
      <aside className="guide-sidebar">
        <div className="guide-sidebar-header">
          <BookOpen size={20} />
          <h2>策略库</h2>
        </div>
        <nav className="guide-nav">
          {strategyGuides.map((s) => (
            <button
              key={s.id}
              className={`guide-nav-item${s.id === selectedId ? ' active' : ''}`}
              onClick={() => setSelectedId(s.id)}
            >
              {s.name}
            </button>
          ))}
        </nav>
        <button className="guide-back-btn" onClick={onBack}>
          &larr; 返回回测
        </button>
      </aside>

      <section className="guide-content">
        {selected ? (
          <>
            <header className="guide-header">
              <h1>{selected.name}</h1>
              <p className="guide-desc">{selected.description}</p>
              <span className="guide-scenario">{selected.applicableScenarios}</span>
            </header>

            <section className="guide-section">
              <h2>{selected.principle.title}</h2>
              {selected.principle.content.split('\n\n').map((para, i) => (
                <p key={i}>{para.trim()}</p>
              ))}
            </section>

            <section className="guide-section">
              <h2>参数详解</h2>
              <div className="guide-params-table-wrapper">
                <table className="guide-params-table">
                  <thead>
                    <tr>
                      <th>参数名</th>
                      <th>含义</th>
                      <th>推荐值</th>
                      <th>调整建议</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.parameters.map((p) => (
                      <tr key={p.name}>
                        <td><code>{p.name}</code><br /><span className="param-label">{p.label}</span></td>
                        <td>{p.meaning}</td>
                        <td className="param-value">{p.recommendedValue}</td>
                        <td>{p.adjustmentTips}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="guide-section guide-chars">
              <h2>交易特征</h2>
              <div className="chars-grid">
                <div className="char-card">
                  <span className="char-label">交易频率</span>
                  <strong>{selected.characteristics.tradingFrequency}</strong>
                </div>
                <div className="char-card">
                  <span className="char-label">持仓周期</span>
                  <strong>{selected.characteristics.holdingPeriod}</strong>
                </div>
                <div className="char-card">
                  <span className="char-label">适用股票</span>
                  <strong>{selected.characteristics.applicableStocks}</strong>
                </div>
                <div className="char-card">
                  <span className="char-label">风险等级</span>
                  <strong>{selected.characteristics.riskLevel}</strong>
                </div>
              </div>
            </section>
          </>
        ) : (
          <div className="guide-empty">未找到策略说明</div>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/StrategyGuide.tsx
git commit -m "feat: add StrategyGuide page component"
```

---

### Task 4: 添加样式

**Files:**
- Modify: `web/src/style.css`

- [ ] **Step 1: 在 style.css 末尾添加策略库样式**

```css
/* ── 策略库页面 ── */
.strategy-guide {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.guide-sidebar {
  width: 220px;
  min-width: 220px;
  background: #0f172a;
  border-right: 1px solid #1e293b;
  display: flex;
  flex-direction: column;
  padding: 1rem;
}

.guide-sidebar-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #94a3b8;
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
}

.guide-sidebar-header h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.guide-nav {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.guide-nav-item {
  background: none;
  border: none;
  color: #94a3b8;
  padding: 0.6rem 0.75rem;
  text-align: left;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.15s;
}

.guide-nav-item:hover {
  background: #1e293b;
  color: #e2e8f0;
}

.guide-nav-item.active {
  background: #2563eb;
  color: #fff;
  font-weight: 500;
}

.guide-back-btn {
  background: none;
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 0.5rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
  margin-top: 1rem;
  transition: all 0.15s;
}

.guide-back-btn:hover {
  background: #1e293b;
  color: #e2e8f0;
}

.guide-content {
  flex: 1;
  overflow-y: auto;
  padding: 2rem 2.5rem;
  background: #0b1120;
}

.guide-header {
  margin-bottom: 2rem;
}

.guide-header h1 {
  margin: 0 0 0.5rem;
  font-size: 1.75rem;
  color: #f1f5f9;
}

.guide-desc {
  color: #94a3b8;
  margin: 0 0 0.75rem;
  font-size: 1rem;
}

.guide-scenario {
  display: inline-block;
  background: #1e293b;
  color: #60a5fa;
  padding: 0.3rem 0.75rem;
  border-radius: 20px;
  font-size: 0.8rem;
}

.guide-section {
  margin-bottom: 2.5rem;
}

.guide-section h2 {
  font-size: 1.2rem;
  color: #e2e8f0;
  margin: 0 0 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #1e293b;
}

.guide-section p {
  color: #cbd5e1;
  line-height: 1.8;
  margin: 0 0 1rem;
  font-size: 0.9rem;
}

.guide-params-table-wrapper {
  overflow-x: auto;
}

.guide-params-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.guide-params-table th {
  text-align: left;
  padding: 0.75rem 1rem;
  background: #1e293b;
  color: #94a3b8;
  font-weight: 500;
  white-space: nowrap;
}

.guide-params-table th:first-child {
  border-radius: 6px 0 0 0;
}

.guide-params-table th:last-child {
  border-radius: 0 6px 0 0;
}

.guide-params-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #1e293b;
  color: #cbd5e1;
  vertical-align: top;
}

.guide-params-table td code {
  background: #1e293b;
  padding: 0.15rem 0.4rem;
  border-radius: 3px;
  font-size: 0.8rem;
  color: #f59e0b;
}

.guide-params-table .param-label {
  font-size: 0.8rem;
  color: #64748b;
}

.guide-params-table .param-value {
  white-space: nowrap;
  color: #34d399;
  font-weight: 500;
}

.guide-params-table tr:hover td {
  background: #0f172a;
}

.chars-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
}

.char-card {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.char-label {
  font-size: 0.8rem;
  color: #64748b;
}

.char-card strong {
  font-size: 1rem;
  color: #e2e8f0;
}

.guide-empty {
  color: #64748b;
  text-align: center;
  padding: 4rem 0;
}
```

- [ ] **Step 2: Commit**

```bash
git add web/src/style.css
git commit -m "feat: add strategy guide page styles"
```

---

### Task 5: 在 App.tsx 中添加导航和页面切换

**Files:**
- Modify: `web/src/App.tsx`

- [ ] **Step 1: 添加导入和页面切换状态**

在 App.tsx 顶部添加导入：

```typescript
import { BookOpen } from 'lucide-react';
import StrategyGuide from './StrategyGuide';
```

在 `export default function App()` 内部添加页面状态：

```typescript
// 在已有 state 之后添加
const [showGuide, setShowGuide] = useState(false);
```

- [ ] **Step 2: 添加页面切换逻辑**

在 App.tsx 的 `return` 语句之前，如果 `showGuide` 为 true 则显示策略库页面：

```tsx
if (showGuide) {
  return <StrategyGuide onBack={() => setShowGuide(false)} />;
}
```

在品牌标识 `QuantX 回测研究工作台` 旁边添加导航按钮：

```tsx
{/* 在 <div className="brand-row"> 内的 <h1>QuantX</h1> 旁边 */}
<button className="nav-guide-btn" onClick={() => setShowGuide(true)} title="策略库">
  <BookOpen size={16} />
  策略库
</button>
```

需要找到 `brand-row` 中的具体位置来修改。

- [ ] **Step 3: 添加导航按钮样式**

在 style.css 末尾添加：

```css
.nav-guide-btn {
  background: none;
  border: 1px solid #334155;
  color: #94a3b8;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.3rem;
  transition: all 0.15s;
}

.nav-guide-btn:hover {
  background: #1e293b;
  color: #e2e8f0;
  border-color: #475569;
}
```

- [ ] **Step 4: Commit**

```bash
git add web/src/App.tsx web/src/style.css
git commit -m "feat: add strategy guide navigation to main app"
```

---

### Task 6: 验证和测试

- [ ] **Step 1: 检查 TypeScript 编译**

Run: `npx tsc --noEmit`
Expected: 无类型错误

- [ ] **Step 2: 启动开发服务器验证**

```bash
cd web && npm run dev
```
手动检查：
1. 点击"策略库"按钮，应切换到策略库页面
2. 左侧策略列表应显示三个策略
3. 点击不同策略，右侧详情应切换
4. 参数表格应正确显示
5. "返回回测"按钮应回到主页面
6. 样式应与现有页面保持一致

- [ ] **Step 3: 最终提交**

```bash
git add -A
git commit -m "feat: add strategy guide page with docs for all strategies"
```
