"""
GET /api/news/{symbol}             — 新闻列表（DB → East Money 回退）
GET /api/news/{symbol}/particles  — K线图新闻粒子（DB → East Money 回退）
GET /api/news/{symbol}/categories — 新闻分类统计
GET /api/news/{symbol}/range      — 区间新闻
POST /api/news/{symbol}/fetch     — 抓取新闻
GET /api/news/{symbol}/stats       — 新闻统计
"""
from fastapi import APIRouter, Query
import httpx
import re
import hashlib
import json
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

from database import get_conn, SessionLocal, NewsRaw, Layer1Result, NewsAligned, Stock
from pipeline.layer1 import analyze_news_sentiment, _rule_based_sentiment

router = APIRouter()

EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
}


def _days_ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


def _get_raw_conn():
    return get_conn()


def _parse_date(date_str: str) -> str:
    """Parse date string to YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    date_str = date_str.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
        return date_str[:10]
    if re.match(r"^\d{10}$", date_str):
        return datetime.fromtimestamp(int(date_str)).strftime("%Y-%m-%d")
    if re.match(r"^\d{13}$", date_str):
        return datetime.fromtimestamp(int(date_str) / 1000).strftime("%Y-%m-%d")
    for fmt in ["%Y/%m/%d %H:%M:%S", "%Y/%m/%d", "%m/%d %H:%M"]:
        try:
            return datetime.strptime(date_str[:19], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    return datetime.now().strftime("%Y-%m-%d")


# ─── East Money News Fallback ───────────────────────────────────────────────────
def _fetch_em_news_fallback(symbol: str, limit: int = 20) -> list[dict]:
    """
    East Money 搜索 API 作为回退，当数据库为空时实时获取新闻。
    支持股票公告、市场新闻、概念新闻。
    """
    market = "sh" if symbol.startswith("6") or symbol.startswith("9") else "sz"

    # 构建搜索参数
    param_dict = {
        "uid": "",
        "keyword": symbol,
        "type": ["cmsArticle"],
        "client": "web",
        "clientVersion": "curr",
        "clientType": "web",
        "param": {
            "cmsArticle": {
                "searchScope": "default",
                "sort": "default",
                "pageIndex": 1,
                "pageSize": limit,
                "preTag": '<span class=">',
                "postTag": "</span>",
            }
        }
    }
    param_str = json.dumps(param_dict, ensure_ascii=False)
    encoded = urllib.parse.quote(param_str)
    url = f"https://search-api-web.eastmoney.com/search/jsonp?cb=&param={encoded}"

    try:
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            resp = client.get(url, headers=EM_HEADERS)
            resp.raise_for_status()
            raw = resp.text
    except Exception as e:
        print(f"[NEWS] EM fallback fetch error: {e}")
        return []

    results = []

    # 解析 NDJSON 格式：响应为 (JSON1)(JSON2)(JSON3)
    parts = raw.lstrip("(").rstrip(")").split(")(")
    for part in parts:
        part = part.strip().rstrip(")")
        if not part.startswith("{"):
            continue
        try:
            data = json.loads(part)
            items = data.get("result", {}).get("cmsArticle", []) or []
            for item in items:
                title_raw = item.get("title", "")
                title = re.sub(r"<[^>]+>", "", title_raw).strip()
                if not title:
                    continue
                news_id = hashlib.md5(
                    (title + item.get("date", "")).encode()
                ).hexdigest()[:24]
                pub_date = item.get("date", "")[:10]
                if not pub_date:
                    pub_date = datetime.now().strftime("%Y-%m-%d")
                sentiment = _rule_based_sentiment(symbol, title, "")

                    # Clean content field: strip HTML, truncate
                    content_raw = item.get("content", "") or ""
                    content_clean = re.sub(r"<[^>]*>", "", content_raw).strip()

                    results.append({
                        "news_id": news_id,
                        "d": pub_date,
                        "s": sentiment["sentiment"],
                        "r": sentiment["relevance"],
                        "t": title,
                        "rt1": None,
                        "title": title,
                        "content": content_clean[:300] if content_clean else "",
                        "source": "东方财富",
                        "published_at": pub_date,
                        "sentiment": sentiment["sentiment"],
                        "sentiment_cn": sentiment["sentiment_cn"],
                    })
                if len(results) >= limit:
                    break
        except Exception:
            continue
        if len(results) >= limit:
            break

    print(f"[NEWS] EM fallback: fetched {len(results)} news for {symbol}")
    return results


# ─── Particles (K线图新闻点) ────────────────────────────────────────────────
@router.get("/{symbol}/particles")
def get_particles(symbol: str, days: int = Query(90, ge=30, le=730)):
    """
    获取新闻粒子（用于 K 线图叠加）
    DB有数据用DB，DB为空时实时从东方财富获取
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
        conn.close()

        results = [
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

        if not results:
            results = _fetch_em_news_fallback(symbol, limit=50)

        return results
    except Exception as e:
        conn.close()
        try:
            return _fetch_em_news_fallback(symbol, limit=50)
        except Exception:
            return []


# ─── News List ────────────────────────────────────────────────────────────────
@router.get("/{symbol}")
def get_news(symbol: str, date: Optional[str] = Query(None)):
    """获取新闻（DB → East Money 回退）"""
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
        conn.close()

        results = [dict(r) for r in rows]

        if not results:
            results = _fetch_em_news_fallback(symbol, limit=30)

        return results
    except Exception as e:
        conn.close()
        try:
            return _fetch_em_news_fallback(symbol, limit=30)
        except Exception:
            return []


@router.get("/{symbol}/categories")
def get_categories(symbol: str, date: Optional[str] = Query(None)):
    """获取新闻分类统计"""
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
                LIMIT 100
                """,
                (symbol,)
            ).fetchall()
        conn.close()

        CATEGORIES = [
            {"id": "policy", "label": "政策", "color": "#e91e63"},
            {"id": "earnings", "label": "业绩", "color": "#4caf50"},
            {"id": "concept", "label": "概念", "color": "#2196f3"},
            {"id": "announcement", "label": "公告", "color": "#ff9800"},
            {"id": "market", "label": "市场", "color": "#9c27b0"},
            {"id": "other", "label": "其他", "color": "#607d8b"},
        ]
        stats = {c["id"]: {"label": c["label"], "color": c["color"],
                           "count": 0, "positive": 0, "negative": 0, "neutral": 0} for c in CATEGORIES}

        def categorize(title: str, content: str) -> str:
            text = (title + " " + (content or ""))[:200]
            if any(k in text for k in ["政策", "国务院", "证监会", "央行", "工信部", "发改委", "财政部"]):
                return "policy"
            if any(k in text for k in ["业绩", "净利润", "营收", "年报", "季报", "超预期", "预增", "预减"]):
                return "earnings"
            if any(k in text for k in ["AI", "芯片", "新能源", "半导体", "机器人", "概念", "题材"]):
                return "concept"
            if any(k in text for k in ["公告", "决议", "临时停牌", "分红", "配股"]):
                return "announcement"
            if any(k in text for k in ["大盘", "市场", "指数", "北向", "资金"]):
                return "market"
            return "other"

        for row in rows:
            r = dict(row)
            cat = categorize(r.get("title", ""), r.get("content", ""))
            sentiment = r.get("sentiment", "neutral")
            stats[cat]["count"] += 1
            if sentiment == "positive":
                stats[cat]["positive"] += 1
            elif sentiment == "negative":
                stats[cat]["negative"] += 1
            else:
                stats[cat]["neutral"] += 1

        return list(stats.values())
    except Exception:
        conn.close()
        return []


@router.get("/{symbol}/range")
def get_news_range(symbol: str, start: str = Query(...), end: str = Query(...)):
    """获取指定日期范围的新闻"""
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
        conn.close()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/{symbol}/stats")
def get_news_stats(symbol: str):
    """获取新闻统计摘要"""
    conn = _get_raw_conn()
    try:
        rows = conn.execute(
            """
            SELECT l1.sentiment, COUNT(*) as cnt
            FROM news_aligned na
            JOIN layer1_results l1 ON na.news_id = l1.news_id AND na.symbol = l1.symbol
            WHERE na.symbol = ?
            GROUP BY l1.sentiment
            """,
            (symbol,)
        ).fetchall()
        conn.close()
        stats = {"positive": 0, "negative": 0, "neutral": 0, "total": 0}
        for r in rows:
            s = r["sentiment"] or "neutral"
            if s in stats:
                stats[s] = r["cnt"]
                stats["total"] += r["cnt"]
        return stats
    except Exception:
        conn.close()
        return {"positive": 0, "negative": 0, "neutral": 0, "total": 0}


# ─── Fetch News ──────────────────────────────────────────────────────────────
def _to_em_code(symbol: str, market: str) -> str:
    m = {"sh": "sh", "sz": "sz", "bj": "bj"}.get(market, "sh")
    return f"{symbol}.{m}"


def _fetch_eastmoney_news(symbol: str, market: str, limit: int = 15) -> list[dict]:
    em_code = _to_em_code(symbol, market)
    url = (
        f"https://np-anotice-stock.eastmoney.com/api/security/ann"
        f"?cb=&sr=-1&page_size={limit}&page_index=1&ann_type=SHA%"
        f",SZA%,BJA%&client_source=web&stock_list={em_code}"
    )
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers=EM_HEADERS)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    items = data.get("data", {}).get("list", []) or []
    results = []
    for item in items:
        title = item.get("title", "")
        if not title:
            continue
        news_id = hashlib.md5((title + item.get("notice_date", "")).encode()).hexdigest()[:24]
        pub_time = item.get("notice_date", "")[:19]
        results.append({
            "id": news_id,
            "title": title.strip(),
            "content": item.get("summary", "")[:500],
            "source": item.get("security_type_name", "东方财富"),
            "url": item.get("art_url", ""),
            "published_at": pub_time,
            "symbols": [],
        })
    return results


def _save_news(news_items: list[dict]) -> list[str]:
    if not news_items:
        return []
    db = SessionLocal()
    saved_ids = []
    try:
        for item in news_items:
            news_id = item.get("id", "")
            if not news_id:
                news_id = hashlib.md5((item["title"] + item.get("published_at", "")).encode()).hexdigest()[:24]
            existing = db.query(NewsRaw).filter(NewsRaw.id == news_id).first()
            if existing:
                saved_ids.append(news_id)
                continue
            news = NewsRaw(
                id=news_id,
                title=item["title"],
                content=item.get("content", ""),
                source=item.get("source", ""),
                url=item.get("url", ""),
                published_at=item.get("published_at", ""),
            )
            db.add(news)
            saved_ids.append(news_id)
        db.commit()
        print(f"[NEWS] Saved {len(saved_ids)} items")
    except Exception as e:
        print(f"[NEWS] Save error: {e}")
        db.rollback()
    finally:
        db.close()
    return saved_ids


def _analyze_and_align(symbol: str, saved_ids: list[str]) -> int:
    analyzed = 0
    db = SessionLocal()
    try:
        for news_id in saved_ids:
            existing = db.query(Layer1Result).filter(
                Layer1Result.news_id == news_id,
                Layer1Result.symbol == symbol
            ).first()
            if existing:
                continue
            news = db.query(NewsRaw).filter(NewsRaw.id == news_id).first()
            if not news:
                continue

            sentiment = analyze_news_sentiment(
                symbol=symbol, news_id=news_id,
                title=news.title, content=news.content,
            )
            lr = Layer1Result(
                news_id=news_id, symbol=symbol,
                sentiment=sentiment.get("sentiment", "neutral"),
                sentiment_cn=sentiment.get("sentiment_cn", "中性"),
                relevance=sentiment.get("relevance", "medium"),
                key_discussion=sentiment.get("key_discussion", ""),
                reason_growth=sentiment.get("reason_growth", ""),
                reason_decrease=sentiment.get("reason_decrease", ""),
            )
            db.add(lr)
            analyzed += 1

        db.commit()
        _align_news_to_trading_dates(symbol, db)

    except Exception as e:
        print(f"[NEWS] Analysis error: {e}")
        db.rollback()
    finally:
        db.close()
    return analyzed


def _align_news_to_trading_dates(symbol: str, db):
    try:
        raw_news = db.query(NewsRaw).filter(
            NewsRaw.id.in_(db.query(Layer1Result.news_id).filter(Layer1Result.symbol == symbol))
        ).all()

        from database import DailyKline
        klines = db.query(DailyKline).filter(
            DailyKline.code == symbol
        ).order_by(DailyKline.date).all()

        if not klines:
            return

        date_map = {str(k.date)[:10]: k for k in klines}
        sorted_dates = sorted(date_map.keys())

        for news in raw_news:
            existing = db.query(NewsAligned).filter(
                NewsAligned.symbol == symbol,
                NewsAligned.news_id == news.id
            ).first()
            if existing:
                continue

            pub_date = _parse_date(news.published_at or "")
            trade_date = None
            for d in sorted_dates:
                if d >= pub_date:
                    trade_date = d
                    break
            if not trade_date:
                trade_date = sorted_dates[-1] if sorted_dates else pub_date

            k0 = date_map.get(trade_date)
            ret_t0 = k0.change_pct if k0 else 0.0

            try:
                idx = sorted_dates.index(trade_date)
                ret_t1 = 0.0
                if idx + 1 < len(sorted_dates):
                    k1 = date_map.get(sorted_dates[idx + 1])
                    if k0 and k1:
                        ret_t1 = round((k1.close - k0.close) / k0.close * 100, 4)
            except ValueError:
                ret_t1 = 0.0

            aligned = NewsAligned(
                news_id=news.id, symbol=symbol, trade_date=trade_date,
                ret_t0=ret_t0 or 0.0, ret_t1=ret_t1 or 0.0,
                ret_t3=0.0, ret_t5=0.0,
            )
            db.add(aligned)

        db.commit()
        print(f"[NEWS] Aligned news for {symbol}")
    except Exception as e:
        print(f"[NEWS] Alignment error: {e}")
        db.rollback()


@router.post("/{symbol}/fetch")
def fetch_news(symbol: str):
    """抓取指定股票的财经新闻并保存到数据库"""
    market = "sh" if symbol.startswith("6") or symbol.startswith("9") else "sz"

    all_news = []
    all_news.extend(_fetch_eastmoney_news(symbol, market, limit=15))

    seen = set()
    unique_news = [n for n in all_news if not (n["title"] in seen or seen.add(n["title"]))]

    results = {"fetched": len(unique_news), "saved": 0, "analyzed": 0}

    saved_ids = _save_news(unique_news)
    results["saved"] = len(saved_ids)

    if saved_ids:
        results["analyzed"] = _analyze_and_align(symbol, saved_ids)

    return {
        "symbol": symbol,
        **results,
        "status": "ok",
        "message": f"获取 {results['fetched']} 条新闻，分析 {results['analyzed']} 条",
    }
