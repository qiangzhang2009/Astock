"""
GET /api/news/{symbol}/particles   — 新闻粒子（用于图表叠加）
GET /api/news/{symbol}             — 单日新闻
GET /api/news/{symbol}/categories  — 新闻分类
GET /api/news/{symbol}/range       — 区间新闻
POST /api/news/{symbol}/fetch      — 抓取新闻
GET /api/news/{symbol}/stats       — 新闻统计
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import hashlib
from datetime import datetime

from database import SessionLocal, NewsRaw, Layer1Result, NewsAligned
from ingest.news_scraper import fetch_and_analyze_stock_news

router = APIRouter()


class NewsItem(BaseModel):
    news_id: str
    title: str
    content: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_cn: Optional[str] = None
    relevance: Optional[str] = None
    key_discussion: Optional[str] = None
    reason_growth: Optional[str] = None
    reason_decrease: Optional[str] = None
    trade_date: Optional[str] = None
    ret_t0: Optional[float] = None
    ret_t1: Optional[float] = None
    ret_t3: Optional[float] = None
    ret_t5: Optional[float] = None


class NewsParticle(BaseModel):
    news_id: str
    d: str
    s: Optional[str] = None
    r: Optional[str] = None
    t: str
    rt1: Optional[float] = None


# A股新闻分类
A_STOCK_CATEGORIES = [
    {"key": "policy", "label": "政策", "color": "#58a6ff"},
    {"key": "earnings", "label": "业绩", "color": "#3fb950"},
    {"key": "concept", "label": "概念", "color": "#bc8cff"},
    {"key": "announcement", "label": "公告", "color": "#f0883e"},
    {"key": "market", "label": "市场", "color": "#d29922"},
    {"key": "other", "label": "其他", "color": "#8b949e"},
]


def _auto_categorize(title: str, content: str = "") -> dict:
    """Auto-categorize news based on keywords."""
    text = (title + " " + content).lower()
    if any(k in text for k in ["政策", "监管", "央行", "财政部", "证监会", "国务院", "部委", "规划"]):
        return A_STOCK_CATEGORIES[0]  # policy
    if any(k in text for k in ["业绩", "净利润", "营收", "利润", "季报", "年报", "预增", "预减", "超预期"]):
        return A_STOCK_CATEGORIES[1]  # earnings
    if any(k in text for k in ["概念", "题材", "热点", "风口", "AI", "新能源", "芯片", "半导体"]):
        return A_STOCK_CATEGORIES[2]  # concept
    if any(k in text for k in ["公告", "公告称", "披露", "决议", "决议公告"]):
        return A_STOCK_CATEGORIES[3]  # announcement
    if any(k in text for k in ["大盘", "市场", "指数", "涨", "跌", "资金", "北向"]):
        return A_STOCK_CATEGORIES[4]  # market
    return A_STOCK_CATEGORIES[5]  # other


@router.get("/{symbol}/particles", response_model=list[NewsParticle])
def get_particles(symbol: str, days: int = Query(90, ge=30, le=730)):
    """
    获取新闻粒子（用于 K 线图叠加）
    返回: { news_id, d, s, r, t, rt1 } 格式
    """
    conn = _get_raw_conn()
    try:
        cutoff = _days_ago(days)
        rows = conn.execute(
            """
            SELECT na.news_id, na.trade_date as d, l1.sentiment as s,
                   l1.relevance as r, nr.title as t, na.ret_t1
            FROM news_aligned na
            JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
            JOIN news_raw nr ON na.news_id = nr.id
            WHERE na.symbol = ? AND na.trade_date >= ?
            ORDER BY na.trade_date DESC
            LIMIT 300
            """,
            (symbol, cutoff)
        ).fetchall()

        return [
            {
                "news_id": r["news_id"],
                "d": r["d"],
                "s": r["s"],
                "r": r["r"],
                "t": r["t"],
                "rt1": r["ret_t1"],
            }
            for r in rows
        ]
    finally:
        conn.close()


@router.get("/{symbol}", response_model=list[NewsItem])
def get_news(symbol: str, date: Optional[str] = Query(None)):
    """获取指定日期的新闻"""
    conn = _get_raw_conn()
    try:
        if date:
            rows = conn.execute(
                """
                SELECT na.news_id, nr.title, nr.content, nr.source, nr.published_at,
                       l1.sentiment, l1.sentiment_cn, l1.relevance,
                       l1.key_discussion, l1.reason_growth, l1.reason_decrease,
                       na.trade_date, na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5
                FROM news_aligned na
                JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
                JOIN news_raw nr ON na.news_id = nr.id
                WHERE na.symbol = ? AND na.trade_date = ?
                ORDER BY nr.published_at DESC
                """,
                (symbol, date)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT na.news_id, nr.title, nr.content, nr.source, nr.published_at,
                       l1.sentiment, l1.sentiment_cn, l1.relevance,
                       l1.key_discussion, l1.reason_growth, l1.reason_decrease,
                       na.trade_date, na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5
                FROM news_aligned na
                JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
                JOIN news_raw nr ON na.news_id = nr.id
                WHERE na.symbol = ?
                ORDER BY na.trade_date DESC, nr.published_at DESC
                LIMIT 50
                """,
                (symbol,)
            ).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/{symbol}/categories")
def get_categories(symbol: str, date: Optional[str] = Query(None)):
    """
    获取新闻分类统计
    A 股分类: 政策、业绩、概念、公告、市场、其他
    """
    conn = _get_raw_conn()
    try:
        if date:
            rows = conn.execute(
                """
                SELECT na.news_id, nr.title, nr.content, nr.source, nr.published_at,
                       l1.sentiment, l1.sentiment_cn, l1.relevance,
                       l1.key_discussion, l1.reason_growth, l1.reason_decrease,
                       na.trade_date, na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5
                FROM news_aligned na
                JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
                JOIN news_raw nr ON na.news_id = nr.id
                WHERE na.symbol = ? AND na.trade_date = ?
                """,
                (symbol, date)
            ).fetchall()
        else:
            cutoff = _days_ago(30)
            rows = conn.execute(
                """
                SELECT na.news_id, nr.title, nr.content, nr.source, nr.published_at,
                       l1.sentiment, l1.sentiment_cn, l1.relevance,
                       l1.key_discussion, l1.reason_growth, l1.reason_decrease,
                       na.trade_date, na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5
                FROM news_aligned na
                JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
                JOIN news_raw nr ON na.news_id = nr.id
                WHERE na.symbol = ? AND na.trade_date >= ?
                """,
                (symbol, cutoff)
            ).fetchall()

        # Categorize and count
        categories = {c["key"]: {"label": c["label"], "color": c["color"],
                                  "count": 0, "positive": 0, "negative": 0, "neutral": 0, "news_ids": []}
                      for c in A_STOCK_CATEGORIES}

        for r in rows:
            d = dict(r)
            cat = _auto_categorize(d.get("title") or "", d.get("content") or "")
            ck = cat["key"]
            categories[ck]["count"] += 1
            categories[ck]["news_ids"].append(d["news_id"])
            sent = d.get("sentiment", "neutral")
            if sent == "positive":
                categories[ck]["positive"] += 1
            elif sent == "negative":
                categories[ck]["negative"] += 1
            else:
                categories[ck]["neutral"] += 1

        return [
            {"key": k, **v}
            for k, v in categories.items()
            if v["count"] > 0
        ]
    finally:
        conn.close()


@router.get("/{symbol}/range")
def get_news_range(symbol: str,
                   start: str = Query(...),
                   end: str = Query(...)):
    """获取区间内的所有新闻"""
    conn = _get_raw_conn()
    try:
        rows = conn.execute(
            """
            SELECT na.news_id, nr.title, nr.content, nr.source, nr.published_at,
                   l1.sentiment, l1.sentiment_cn, l1.relevance,
                   l1.key_discussion, l1.reason_growth, l1.reason_decrease,
                   na.trade_date, na.ret_t0, na.ret_t1, na.ret_t3, na.ret_t5
            FROM news_aligned na
            JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
            JOIN news_raw nr ON na.news_id = nr.id
            WHERE na.symbol = ? AND na.trade_date >= ? AND na.trade_date <= ?
            ORDER BY na.trade_date DESC, nr.published_at DESC
            LIMIT 100
            """,
            (symbol, start, end)
        ).fetchall()

        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/{symbol}/fetch")
def fetch_news(symbol: str):
    """
    抓取指定股票的财经新闻并保存到数据库
    使用东方财富 + 新浪财经新闻源
    """
    # Determine market from symbol
    market = "sh" if symbol.startswith("6") or symbol.startswith("9") else "sz"

    try:
        results = fetch_and_analyze_stock_news(symbol, market)
        return {
            "symbol": symbol,
            "fetched": results["fetched"],
            "saved": results["saved"],
            "analyzed": results["analyzed"],
            "status": "ok",
            "message": f"获取 {results['fetched']} 条新闻，分析 {results['analyzed']} 条"
        }
    except Exception as e:
        return {
            "symbol": symbol,
            "fetched": 0,
            "saved": 0,
            "analyzed": 0,
            "status": "error",
            "message": str(e)
        }


@router.get("/{symbol}/stats")
def get_news_stats(symbol: str, days: int = Query(30, ge=1, le=365)):
    """获取新闻统计信息"""
    conn = _get_raw_conn()
    try:
        cutoff = _days_ago(days)
        rows = conn.execute(
            """
            SELECT l1.sentiment, COUNT(*) as cnt
            FROM news_aligned na
            JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
            WHERE na.symbol = ? AND na.trade_date >= ?
            GROUP BY l1.sentiment
            """,
            (symbol, cutoff)
        ).fetchall()

        total = sum(r["cnt"] for r in rows)
        sentiment_counts = {r["sentiment"]: r["cnt"] for r in rows}

        return {
            "symbol": symbol,
            "total": total,
            "positive": sentiment_counts.get("positive", 0),
            "negative": sentiment_counts.get("negative", 0),
            "neutral": sentiment_counts.get("neutral", 0),
            "days": days,
            "period_start": cutoff,
        }
    finally:
        conn.close()


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _get_raw_conn():
    """Get raw sqlite3 connection for complex queries."""
    from database import get_conn
    return get_conn()


def _days_ago(n: int) -> str:
    """Return date N days ago as YYYY-MM-DD string."""
    from datetime import datetime, timedelta
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")
