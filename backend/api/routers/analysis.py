"""
POST /api/analysis/range   — 区间 AI 分析
POST /api/analysis/deep     — 单条新闻深度分析
POST /api/analysis/summary  — 新闻情感摘要
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json

from backend.database import get_conn
from backend.pipeline.layer1 import analyze_news_sentiment, analyze_news_deep

router = APIRouter()


class RangeAnalysisRequest(BaseModel):
    symbol: str
    start_date: str
    end_date: str
    question: Optional[str] = None


class DeepAnalysisRequest(BaseModel):
    news_id: str
    symbol: str


@router.post("/range")
def analyze_range(req: RangeAnalysisRequest):
    """分析区间内的新闻和价格变动，生成 AI 分析"""
    conn = get_conn()

    # 获取区间新闻
    news_rows = conn.execute(
        """
        SELECT nr.id, nr.title, nr.content, nr.published_at,
               l1.sentiment, l1.sentiment_cn, l1.key_discussion,
               l1.reason_growth, l1.reason_decrease,
               na.trade_date, na.ret_t0, na.ret_t1
        FROM news_aligned na
        JOIN news_raw nr ON na.news_id = nr.id
        JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
        WHERE na.symbol = ? AND na.trade_date >= ? AND na.trade_date <= ?
        ORDER BY na.trade_date DESC
        LIMIT 30
        """,
        (req.symbol, req.start_date, req.end_date)
    ).fetchall()

    # 获取区间价格变动
    price_rows = conn.execute(
        """
        SELECT date, open, high, low, close, change_pct, volume
        FROM ohlc
        WHERE symbol = ? AND date >= ? AND date <= ?
        ORDER BY date
        """,
        (req.symbol, req.start_date, req.end_date)
    ).fetchall()

    conn.close()

    news_list = [dict(r) for r in news_rows]
    price_list = [dict(r) for r in price_rows]

    if not price_list:
        raise HTTPException(status_code=404, detail="无价格数据")

    first_close = price_list[0]["close"]
    last_close = price_list[-1]["close"]
    total_change = ((last_close / first_close) - 1) * 100 if first_close else 0

    # 生成 AI 分析
    analysis = _generate_range_analysis(
        symbol=req.symbol,
        news=news_list,
        prices=price_list,
        total_change=total_change,
        question=req.question
    )

    return {
        "symbol": req.symbol,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "price_change_pct": round(total_change, 2),
        "news_count": len(news_list),
        "analysis": analysis,
        "prices": price_list,
        "news": news_list[:10],  # 只返回前 10 条
    }


@router.post("/deep")
def deep_analysis(req: DeepAnalysisRequest):
    """单条新闻深度分析"""
    conn = get_conn()

    row = conn.execute(
        """
        SELECT nr.id, nr.title, nr.content, nr.source, nr.published_at,
               l1.sentiment, l1.sentiment_cn, l1.key_discussion,
               l1.reason_growth, l1.reason_decrease,
               na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5
        FROM news_aligned na
        JOIN news_raw nr ON na.news_id = nr.id
        JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
        WHERE na.news_id = ? AND na.symbol = ?
        """,
        (req.news_id, req.symbol)
    ).fetchone()

    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="未找到该新闻")

    d = dict(row)
    return {
        "news_id": d["id"],
        "title": d["title"],
        "content": d["content"],
        "sentiment": d["sentiment"],
        "sentiment_cn": d.get("sentiment_cn"),
        "key_discussion": d.get("key_discussion"),
        "reason_growth": d.get("reason_growth"),
        "reason_decrease": d.get("reason_decrease"),
        "returns": {
            "t0": d.get("ret_t0"),
            "t1": d.get("ret_t1"),
            "t3": d.get("ret_t3"),
            "t5": d.get("ret_t5"),
        }
    }


def _generate_range_analysis(symbol: str, news: list, prices: list,
                              total_change: float, question: str = None) -> str:
    """基于新闻和价格数据生成分析文字"""

    if not news:
        return f"{symbol} 在 {prices[0]['date']} 至 {prices[-1]['date']} 期间\
 {'上涨' if total_change > 0 else '下跌'} {abs(total_change):.2f}%。期间无新闻数据。"

    positive = sum(1 for n in news if n.get("sentiment") == "positive")
    negative = sum(1 for n in news if n.get("sentiment") == "negative")
    neutral = sum(1 for n in news if n.get("sentiment") == "neutral")

    key_news = [n for n in news if n.get("reason_growth") or n.get("reason_decrease")][:5]

    bullish_reasons = [n["reason_growth"] for n in key_news if n.get("reason_growth")]
    bearish_reasons = [n["reason_decrease"] for n in key_news if n.get("reason_decrease")]

    direction = "看涨" if total_change > 0 else "看跌"
    confidence = "高" if abs(total_change) > 5 else ("中" if abs(total_change) > 2 else "低")

    parts = [
        f"**{symbol} 区间分析** ({prices[0]['date']} ~ {prices[-1]['date']})",
        "",
        f"**价格变动**: {'↑' if total_change > 0 else '↓'} {abs(total_change):.2f}% ({direction}，置信度{confidence})",
        "",
        f"**新闻情绪**: 共 {len(news)} 条，利好 {positive} 条，利空 {negative} 条，中性 {neutral} 条",
    ]

    if bullish_reasons:
        parts.append("")
        parts.append("**▲ 利好因素:**")
        for r in bullish_reasons[:3]:
            parts.append(f"  - {r}")

    if bearish_reasons:
        parts.append("")
        parts.append("**▼ 利空因素:**")
        for r in bearish_reasons[:3]:
            parts.append(f"  - {r}")

    if question:
        parts.append("")
        parts.append(f"**针对「{question}」的分析:**")
        parts.append(
            f"根据该区间的新闻情感和市场表现，{symbol} 的走势{'受到利好消息推动' if positive > negative else '面临利空压力' if negative > positive else '受多种因素交织影响'}。"
        )

    return "\n".join(parts)
