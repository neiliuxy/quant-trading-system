# Web 前端中英文切换设计

## 目标

让 Web 前端的纯 UI 文本在中文 / 英文之间可切换，专业名词维持英文。后端驱动的内容（如 `StrategySpec.name`、`StrategyGuideData`、JobStatus）保持源语言，不参与翻译。

## 范围

### 进入

- 16 个前端组件中的中文字面量全部抽到翻译字典
- 顶栏新增语言切换下拉菜单（中文 / English）
- 切换后立即生效，并通过 `localStorage` 持久化
- 数字格式化、图表日期格式化跟随当前语言
- 开发期缺失键 `console.warn`，CI 通过脚本校验两版 key 集合一致

### 暂不进入

- 第三方语言（日韩等）
- 后端 API 返回多语言字段
- URL `?lang=` 参数
- 浏览器 `navigator.language` 自动检测
- 按页面懒加载翻译资源
- SSR / Next.js

## 架构

### 依赖

新增两个 npm 包：

| 包 | 用途 |
|---|---|
| `i18next` | 核心引擎 |
| `react-i18next` | React 绑定 |

不引入 `i18next-browser-languagedetector`（用户选择 localStorage 直接读取，不走浏览器自动检测）。

### 初始化

`web/src/i18n/index.ts` 在 `web/src/main.tsx` 顶层 import，确保 `i18n.init` 在 React render 之前完成，避免首屏闪烁。

### Provider 关系

i18next 实例为模块单例；React 通过 `useTranslation()` 钩子订阅语言变更，自动重渲染组件。无需额外 `<I18nProvider>`。

## 字典组织

### 目录

```
web/src/i18n/
  index.ts
  locale.ts          # chartLocale() / formatNumber() 工具
  locales/
    zh.json
    en.json
```

### 键名规范

点号分层，最多三层：

| 前缀 | 归属 | 示例 |
|---|---|---|
| `common.` | 全局通用 | `common.cancel`, `common.confirm` |
| `nav.` | 顶部导航 | `nav.backtest`, `nav.dataMgmt` |
| `form.` | 表单标签 | `form.symbol`, `form.startDate` |
| `kpi.` | KPI 顶栏 | `kpi.finalValue`, `kpi.winRate` |
| `panel.` | 图表面板标题 | `panel.equity` |
| `job.` | 任务状态 | `job.queued`, `job.running` |
| `dataMgmt.` | 数据管理页 | `dataMgmt.refreshQueue` |
| `error.` | 通用错误 | `error.network` |

### 不进字典、保留英文

- 指标缩写：`MA5`、`MA10`、`MA20`、`MA60`、`BOLL`、`MACD`、`KDJ`、`RSI`、`ADX`、`BBI`
- 技术词：`HTTP`、`API`、`KPI`、`ROI`、`SQL`、`CSV`、`JSON`
- 单位：`%`、`px`

这些是程序员和金融人士共同接受的英文术语，强行翻译只会让双语用户都看不懂。

### 翻译覆盖目标

首版覆盖这 16 个组件中所有中文字面量，预估 250-300 条键。`strategyGuides.ts`、`StrategySpec.name/description` 等后端驱动或与后端同源的内容不进字典。

## 切换器

### 位置

`App.tsx` 顶栏右侧，导航按钮组末尾。组件 `<LanguageSwitcher />` 放在 `web/src/components/LanguageSwitcher.tsx`。

### 视觉

- `Languages` 图标（lucide-react）+ 当前语言缩写（`ZH` / `EN`）
- 点击展开 2 项菜单：`中文` / `English`
- 选中项右侧 `Check` 图标

### 行为

```ts
function setLang(lng: 'zh' | 'en') {
  i18n.changeLanguage(lng);
  localStorage.setItem('lang', lng);
}
```

### 状态机

```
mount:
  saved = localStorage.getItem('lang')
  lng = saved === 'en' ? 'en' : 'zh'   // 非法值回退 zh

click:
  setLang(target)
```

非法 localStorage 值（例如 `fr`）回退到默认 `zh`，避免历史脏数据破坏首屏。

## locale 敏感格式

### 抽取工具 `web/src/i18n/locale.ts`

```ts
import i18n from './index';

export function chartLocale(): string {
  return i18n.language === 'en' ? 'en-US' : 'zh-CN';
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat(chartLocale()).format(value);
}
```

### 改写点

| 文件 | 原 | 改 |
|---|---|---|
| `web/src/data-management/CacheTable.tsx:25` | `new Intl.NumberFormat('zh-CN')` | `formatNumber(value)` |
| `web/src/charts/useKlineChart.ts:105` | `locale: 'zh-CN'` | `locale: chartLocale()` |

### 图表重建

lightweight-charts 的 `localization` 选项只在 chart 创建时生效。切换语言后，需要在 `useKlineChart` 内通过 `chart.applyOptions({ localization: {...} })` 重新设置；同时把 `locale` 加到 hook 依赖中，确保重渲染。

### 不本地化

- 日期字符串后端固定返回 `YYYYMMDD`，解析逻辑不变
- 数字精度（`toFixed(2)`）保持不变

## 缺失键策略

### 开发期

```ts
i18n.init({
  // ...
  saveMissing: import.meta.env.DEV,
  missingKeyHandler: (lngs, namespace, key) => {
    if (import.meta.env.DEV) {
      console.warn(`[i18n] missing key: ${lngs} / ${namespace} / ${key}`);
    }
  },
});
```

### CI 校验

新增脚本 `scripts/check-i18n-keys.mjs`：

```ts
import zh from '../web/src/i18n/locales/zh.json' with { type: 'json' };
import en from '../web/src/i18n/locales/en.json' with { type: 'json' };
const zhKeys = new Set(Object.keys(zh));
const enKeys = new Set(Object.keys(en));
const onlyZh = [...zhKeys].filter(k => !enKeys.has(k));
const onlyEn = [...enKeys].filter(k => !zhKeys.has(k));
if (onlyZh.length || onlyEn.length) {
  console.error('i18n key mismatch:', { onlyZh, onlyEn });
  process.exit(1);
}
```

接入 `package.json` 的 `npm run i18n:check`，并加入 `npm test` 链。

### 运行时

保留 react-i18next 默认行为：找不到 key 时返回 key 本身。生产构建时 `saveMissing` 关闭，无 console 输出。

## 测试

### 单元测试（vitest）

| 测试文件 | 覆盖 |
|---|---|
| `web/src/i18n/i18n.test.ts` | `chartLocale()`、`formatNumber()` 在 `zh` / `en` 下的输出 |
| `web/src/components/LanguageSwitcher.test.tsx` | 点击切换 → i18n.changeLanguage 调用 + localStorage 写入 |
| `web/src/i18n/check-keys.test.ts` | 故意制造 key 不一致 → 脚本检测通过 |

### 现有组件测试更新

`App.test.tsx`、`RunForm.test.tsx`、`EquityPanel.test.tsx` 等若断言中文字面量，需要：

1. 用 `i18n.t(...)` 包一层，或
2. 直接断言翻译键而非译文（推荐）

### 手工验收

- [ ] 顶栏下拉切换 → 整个页面文案切换，无残留中文
- [ ] 刷新页面 → 语言保持上次选择
- [ ] 图表日期格式在英文下显示 `MMM dd, yyyy`（或当前 en-US 默认）
- [ ] 控制台无 `[i18n] missing key` 警告
- [ ] 切换后 K 线、评分线、买卖点 marker 位置不变（仅文案变）

## 文件改动清单

### 新增

- `web/src/i18n/index.ts`
- `web/src/i18n/locale.ts`
- `web/src/i18n/locales/zh.json`
- `web/src/i18n/locales/en.json`
- `web/src/components/LanguageSwitcher.tsx`
- `web/src/components/LanguageSwitcher.test.tsx`
- `scripts/check-i18n-keys.mjs`

### 修改

- `web/src/main.tsx`（顶层 import i18n）
- `web/src/App.tsx`（嵌入 `<LanguageSwitcher />` + 替换中文串）
- `web/src/RunForm.tsx`
- `web/src/ChartDateRangeControl.tsx`
- `web/src/StockSelect.tsx`
- `web/src/StrategyGuide.tsx`
- `web/src/StrategyParamsForm.tsx`
- `web/src/panels/EquityPanel.tsx`
- `web/src/panels/StockKlinePanel.tsx`
- `web/src/panels/IndexKlinePanel.tsx`
- `web/src/panels/StockIndicatorPanel.tsx`
- `web/src/panels/IndexIndicatorPanel.tsx`
- `web/src/data-management/DataManagementView.tsx`
- `web/src/data-management/CacheTable.tsx`
- `web/src/data-management/RefreshQueue.tsx`
- `web/src/data-management/DatasetCatalog.tsx`
- `web/src/charts/useKlineChart.ts`（locale 注入）
- `web/src/App.test.tsx` 等断言中文字面量的测试文件
- `package.json`（依赖 + `i18n:check` 脚本）

## 风险与权衡

| 风险 | 缓解 |
|---|---|
| 切换时图表重建引发闪烁 | 仅切 `localization`，不重建 series；K 线主数据复用 |
| react-i18next 17KB 体积 | 项目规模小可接受；后续可拆 namespace 懒加载 |
| Key 拼写错误无 TS 检查 | 通过 CI `i18n:check` + dev console.warn 双层兜底 |
| 中文 ↔ 英文译文质量参差 | 首版人工对照翻译；后续可接入翻译平台 |
| 后端内容（StrategySpec）维持源语言造成中英混排 | 已与用户确认，文档显式记录 |