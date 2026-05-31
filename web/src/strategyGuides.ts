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
