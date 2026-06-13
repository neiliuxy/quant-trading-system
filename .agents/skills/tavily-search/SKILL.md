---
name: tavily-search
description: Web search and content extraction via Tavily Search API. Use for searching real-time web content, news, financial data, and documentation. Ideal for market research and information gathering.
---

# Tavily Search

Tavily Search API 是一个专为 AI Agent 设计的搜索引擎，支持实时网页搜索和内容提取。

## 安装依赖

首次使用前安装：

```bash
pip install tavily-python
```

## 环境变量

设置 Tavily API Key（从 https://tavily.com 获取）：

```bash
# Windows PowerShell
$env:TAVILY_API_KEY="tvly-你的API密钥"

# 或永久设置
setx TAVILY_API_KEY "tvly-你的API密钥"

# Linux / macOS / Git Bash
export TAVILY_API_KEY="tvly-你的API密钥"
```

## 使用方法

### 基本搜索

```bash
python .pi/skills/tavily-search/search.py "quantitative trading strategies python"
```

### 搜索并获取页面内容

```bash
python .pi/skills/tavily-search/search.py "A股 量化交易 策略" --content
```

### 限定搜索数量

```bash
python .pi/skills/tavily-search/search.py "backtrader 多策略" --max-results 5
```

### 搜索新闻（适合金融/市场信息）

```bash
python .pi/skills/tavily-search/search.py "中国 股市 最新政策" --topic news
```

### 指定搜索上下文（提高相关性）

```bash
python .pi/skills/tavily-search/search.py "均线策略" --context "A股量化交易回测"
```

## 搜索参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 搜索关键词（必需） | - |
| `--content` | 是否提取页面正文内容 | 否 |
| `--max-results` | 返回结果数量（1-20） | 10 |
| `--topic` | 搜索类型：`general` 或 `news` | general |
| `--context` | 搜索上下文，提高相关性 | 无 |

## 在策略开发中的应用

- 🔍 搜索最新的 A 股市场数据和研究报告
- 📰 获取实时财经新闻和政策动态
- 📚 查找量化策略实现代码和文档
- 💡 搜索特定股票的财务数据和市场分析

参考 [Tavily API 官方文档](https://docs.tavily.com) 了解更多高级用法。
