# 策略库文档页面设计

**日期：** 2026-05-31  
**功能：** 独立的策略说明文档页面，展示所有策略的详细信息，支持策略切换

## 概述

创建一个独立的策略库文档页面，用户可以查看每个策略的详细说明，包括原理、参数、交易特征等。该页面支持策略切换，便于以后添加新策略。

## 页面结构

### 布局设计

```
┌─────────────────────────────────────────────────────────┐
│  QuantX 回测研究工作台  |  策略库                        │
├──────────────┬──────────────────────────────────────────┤
│              │                                          │
│  策略列表    │  策略详情                                │
│  ─────────   │  ─────────────────────────────────────  │
│              │                                          │
│ • B1 Strategy│  B1 Strategy                            │
│ • Swing MA   │  ─────────────────────────────────────  │
│ • Bollinger  │                                          │
│   Reversal   │  【策略简介】                            │
│              │  Trend-following with oversold...       │
│              │                                          │
│              │  【核心原理】                            │
│              │  1. Market timing...                    │
│              │  2. Entry conditions...                 │
│              │  3. Exit strategy...                    │
│              │                                          │
│              │  【参数详解】                            │
│              │  [参数表格]                             │
│              │                                          │
│              │  【交易特征】                            │
│              │  [特征信息]                             │
│              │                                          │
└──────────────┴──────────────────────────────────────────┘
```

### 左侧策略列表
- 显示所有可用策略
- 当前选中策略高亮
- 点击切换策略

### 右侧策略详情
分为四个主要部分：

#### 1. 策略简介
- 策略名称
- 一句话描述
- 适用场景

#### 2. 核心原理
- 策略逻辑的文字说明（2-3段）
- 清晰阐述策略的核心思想

#### 3. 参数详解
表格形式，包含列：
- **参数名** — 英文参数名
- **中文名** — 中文显示名
- **含义** — 参数的具体含义
- **推荐值** — 默认/推荐的参数值
- **调整建议** — 如何调整参数以改变策略行为

#### 4. 交易特征
- **交易频率** — 低频/中频/高频
- **平均持仓周期** — 天数范围
- **适用股票类型** — 如"蓝筹股、成长股"等
- **风险等级** — 低/中/高

## 数据结构

### 策略说明数据（TypeScript）

```typescript
interface StrategyGuideData {
  id: string;                    // 策略ID，与后端对应
  name: string;                  // 策略名称
  description: string;           // 一句话描述
  applicableScenarios: string;   // 适用场景
  
  principle: {
    title: string;               // "核心原理"
    content: string;             // 多段文字说明
  };
  
  parameters: Array<{
    name: string;                // 英文参数名
    label: string;               // 中文显示名
    meaning: string;             // 参数含义
    recommendedValue: string;    // 推荐值
    adjustmentTips: string;      // 调整建议
  }>;
  
  characteristics: {
    tradingFrequency: string;    // 交易频率
    holdingPeriod: string;       // 持仓周期
    applicableStocks: string;    // 适用股票类型
    riskLevel: string;           // 风险等级
  };
}
```

### 策略说明数据示例

```typescript
const strategyGuides: Record<string, StrategyGuideData> = {
  b1_strategy: {
    id: 'b1_strategy',
    name: 'B1 Strategy',
    description: 'Trend-following with oversold pullback entry',
    applicableScenarios: '适合看好市场中期走势的投资者',
    
    principle: {
      title: '核心原理',
      content: `B1策略采用市场择时 + 个股多条件入场的组合方式...`
    },
    
    parameters: [
      {
        name: 'index_ma',
        label: '市场择时MA',
        meaning: '上证综指的移动平均线周期，用于判断市场是否处于上升趋势',
        recommendedValue: '120',
        adjustmentTips: '增大周期使择时更保守，减小周期使择时更激进'
      },
      // ... 其他参数
    ],
    
    characteristics: {
      tradingFrequency: '低频',
      holdingPeriod: '3-10个交易日',
      applicableStocks: '蓝筹股、成长股',
      riskLevel: '中'
    }
  },
  // ... 其他策略
};
```

## 技术实现

### 新建组件

**文件：** `web/src/StrategyGuide.tsx`

- 左侧策略列表组件
- 右侧策略详情组件
- 策略切换逻辑
- 样式设计

### 修改现有文件

**文件：** `web/src/App.tsx`
- 添加导航链接到策略库页面
- 添加路由或页面切换逻辑

**文件：** `web/src/types.ts`
- 添加 `StrategyGuideData` 类型定义

### 新建数据文件

**文件：** `web/src/strategyGuides.ts`
- 存储所有策略的说明数据
- 导出给 `StrategyGuide.tsx` 使用

## 页面导航

在现有 web 页面中添加导航方式（选择其一）：

1. **顶部导航栏** — 在 "QuantX 回测研究工作台" 旁添加 "策略库" 链接
2. **侧边栏导航** — 在左侧边栏顶部添加导航按钮
3. **标签页** — 在主内容区域添加标签页切换

**推荐方案：** 顶部导航栏，简洁清晰

## 样式设计

- 继承现有 web 页面的设计风格
- 左侧列表宽度：200-250px
- 右侧内容区域：自适应
- 参数表格：清晰的行列划分
- 响应式设计：支持不同屏幕尺寸

## 扩展性

添加新策略时，只需：
1. 在 `strategyGuides.ts` 中添加新策略的说明数据
2. 无需修改组件代码

## 成功标准

- ✅ 页面能正确显示所有策略的详细信息
- ✅ 策略切换功能正常
- ✅ 参数表格清晰易读
- ✅ 页面导航清晰
- ✅ 样式与现有页面保持一致
- ✅ 支持后续添加新策略
