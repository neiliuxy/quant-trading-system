#!/usr/bin/env python3
"""
Tavily Search - 通过 Tavily API 进行网页搜索和内容提取

用法:
    python search.py "量化交易 策略"
    python search.py "新闻" --topic news --content
    python search.py "技术分析" --max-results 5
"""

import os
import sys
import json
import argparse


def search_tavily(
    query: str,
    api_key: str,
    max_results: int = 10,
    topic: str = "general",
    include_content: bool = False,
    context: str = None,
) -> dict:
    """调用 Tavily Search API"""
    import requests

    url = "https://api.tavily.com/search"

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "topic": topic,
        "include_answer": True,
        "include_raw_content": include_content,
    }

    if context:
        payload["context"] = context

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def format_results(data: dict, show_content: bool = False) -> str:
    """格式化搜索结果输出"""
    lines = []
    lines.append("=" * 60)
    lines.append(f"🔍 搜索查询: {data.get('query', 'N/A')}")
    if data.get("answer"):
        lines.append(f"📝 AI 摘要: {data['answer']}")
    lines.append("=" * 60)

    results = data.get("results", [])
    if not results:
        lines.append("未找到结果。")
        return "\n".join(lines)

    lines.append(f"\n共找到 {len(results)} 条结果:\n")

    for i, r in enumerate(results, 1):
        lines.append(f"{'─' * 60}")
        lines.append(f"  [{i}] {r.get('title', '无标题')}")
        lines.append(f"      🔗 {r.get('url', 'N/A')}")
        lines.append(f"      📊 分值: {r.get('score', 'N/A')}")

        content = r.get("content", "")
        if content:
            lines.append(f"      📄 摘要: {content[:200]}{'...' if len(content) > 200 else ''}")

        if show_content and r.get("raw_content"):
            raw = r["raw_content"]
            lines.append(f"      📖 正文: {raw[:500]}{'...' if len(raw) > 500 else ''}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Tavily Search - 网页搜索和内容提取",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s "量化交易 策略"
  %(prog)s "A股 新闻" --topic news --content
  %(prog)s "backtrader" --max-results 5
        """,
    )
    parser.add_argument("query", type=str, help="搜索关键词")
    parser.add_argument("--content", action="store_true", help="提取页面正文内容")
    parser.add_argument("--max-results", type=int, default=10, help="返回结果数量 (1-20)")
    parser.add_argument(
        "--topic",
        type=str,
        default="general",
        choices=["general", "news"],
        help="搜索类型: general 或 news",
    )
    parser.add_argument("--context", type=str, help="搜索上下文，提高相关性")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")

    args = parser.parse_args()

    # 获取 API Key
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        print("❌ 错误: 未设置 TAVILY_API_KEY 环境变量")
        print("")
        print("请设置 API Key:")
        print("  Windows PowerShell: $env:TAVILY_API_KEY='tvly-你的密钥'")
        print("  Linux/Mac/Git Bash: export TAVILY_API_KEY='tvly-你的密钥'")
        print("")
        print("从 https://tavily.com 获取 API Key")
        sys.exit(1)

    try:
        data = search_tavily(
            query=args.query,
            api_key=api_key,
            max_results=min(args.max_results, 20),
            topic=args.topic,
            include_content=args.content,
            context=args.context,
        )

        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(format_results(data, show_content=args.content))

    except ImportError:
        print("❌ 请先安装依赖: pip install requests")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 搜索出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
