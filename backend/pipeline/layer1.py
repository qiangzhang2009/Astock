"""
Layer 1: 情感分析
使用 DeepSeek API 对新闻进行情感分类（利好/利空/中性）+ 原因摘要
"""
import os
import json
from typing import Optional
from openai import OpenAI
from config import settings

# DeepSeek client (lazy init)
_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = settings.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise ValueError("No DeepSeek API key configured")
        _client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    return _client


SENTIMENT_PROMPT_CN = """你是一位专业的A股市场分析师。请分析以下新闻对股票走势的影响。

**任务**：对新闻进行情感分类，并简要说明原因。

**股票代码**：{symbol}
**新闻标题**：{title}
**新闻内容**：{content}

请用JSON格式返回分析结果：
{{
  "sentiment": "positive" | "negative" | "neutral",
  "sentiment_cn": "利好" | "利空" | "中性",
  "relevance": "high" | "medium" | "low",
  "key_discussion": "新闻的核心讨论点，一句话概括",
  "reason_growth": "如果利好，说明为什么可能推动股价上涨",
  "reason_decrease": "如果利空，说明为什么可能拖累股价下跌"
}}

请直接返回JSON，不要有其他文字。"""


def analyze_news_sentiment(
    symbol: str,
    news_id: str,
    title: str,
    content: Optional[str] = None,
) -> dict:
    """
    对单条新闻进行情感分析
    返回: { sentiment, sentiment_cn, relevance, key_discussion, reason_growth, reason_decrease }
    """
    api_key = settings.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")

    if not api_key or api_key == "":
        return _rule_based_sentiment(symbol, title, content)

    try:
        client = get_client()
        prompt = SENTIMENT_PROMPT_CN.format(
            symbol=symbol,
            title=title,
            content=(content or "")[:800],
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "你是一位专业的A股市场分析师，擅长从新闻中判断对股价的影响。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=500,
        )
        result_text = response.choices[0].message.content.strip()

        # 去除可能的 markdown 代码块
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1])

        result = json.loads(result_text)
        return {
            "sentiment": result.get("sentiment", "neutral"),
            "sentiment_cn": result.get("sentiment_cn", "中性"),
            "relevance": result.get("relevance", "medium"),
            "key_discussion": result.get("key_discussion", ""),
            "reason_growth": result.get("reason_growth", ""),
            "reason_decrease": result.get("reason_decrease", ""),
        }
    except Exception as e:
        print(f"[DeepSeek] API call failed: {e}, using rule-based fallback")
        return _rule_based_sentiment(symbol, title, content)


def _rule_based_sentiment(symbol: str, title: str, content: Optional[str]) -> dict:
    """
    基于关键词的规则判断情感（无 API Key 时的降级方案）
    """
    text = (title + " " + (content or ""))

    bullish_keywords = [
        "涨停", "大涨", "业绩预增", "净利润增长", "超预期",
        "增持", "买入", "推荐", "上调", "突破", "创新高", "高增长",
        "订单", "签约", "合作", "中标", "扩产", "产能释放",
        "AI", "人工智能", "新品发布", "创新", "技术突破",
        "首板", "连板", "一字板", "封单", "抢筹",
    ]
    bearish_keywords = [
        "跌停", "大跌", "业绩预减", "净利润下降", "不及预期",
        "减持", "卖出", "下调", "创新低", "亏损", "债务",
        "处罚", "调查", "诉讼", "风险", "警示函", "监管",
        "破发", "爆雷", "造假", "退市", "利空",
    ]

    bullish_count = sum(1 for kw in bullish_keywords if kw in text)
    bearish_count = sum(1 for kw in bearish_keywords if kw in text)

    if bullish_count > bearish_count:
        sentiment = "positive"
        sentiment_cn = "利好"
    elif bearish_count > bullish_count:
        sentiment = "negative"
        sentiment_cn = "利空"
    else:
        sentiment = "neutral"
        sentiment_cn = "中性"

    relevance = "high" if (bullish_count + bearish_count) >= 2 else "medium"

    return {
        "sentiment": sentiment,
        "sentiment_cn": sentiment_cn,
        "relevance": relevance,
        "key_discussion": title[:80],
        "reason_growth": "利好特征（涨停、业绩增长等）" if sentiment == "positive" else "",
        "reason_decrease": "利空特征（跌停、业绩下滑等）" if sentiment == "negative" else "",
    }


def analyze_news_deep(news_id: str, symbol: str, title: str, content: str) -> dict:
    """
    单条新闻的深度分析（Layer 2）
    使用 DeepSeek 生成更详细的分析
    """
    api_key = settings.deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {
            "discussion": f"深度分析: {title}",
            "growth_reasons": "需要 DeepSeek API Key 才能进行深度分析",
            "decrease_reasons": "",
        }

    try:
        client = get_client()
        prompt = f"""你是A股市场资深分析师。请对以下新闻进行深度分析：

股票: {symbol}
标题: {title}
内容: {content[:800] if content else '无'}

请分析:
1. 这条新闻的核心讨论点是什么？
2. 如果推动股价上涨，主要原因是什么？
3. 如果拖累股价下跌，主要风险是什么？
4. 短期内股价可能的走势判断

请用JSON格式返回：
{{
  "discussion": "核心讨论点分析",
  "growth_reasons": "看涨原因",
  "decrease_reasons": "看跌原因"
}}"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一位专业的A股市场分析师。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=800,
        )
        result_text = response.choices[0].message.content.strip()

        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:-1])

        result = json.loads(result_text)
        return {
            "discussion": result.get("discussion", ""),
            "growth_reasons": result.get("growth_reasons", ""),
            "decrease_reasons": result.get("decrease_reasons", ""),
        }
    except Exception as e:
        print(f"[DeepSeek] Depth analysis failed: {e}")
        return {
            "discussion": title,
            "growth_reasons": "",
            "decrease_reasons": f"分析失败: {e}",
        }
