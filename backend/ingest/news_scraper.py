"""
新闻爬虫模块
从东方财富(eastmoney)和新浪财经获取A股新闻
保存到SQLite并进行DeepSeek情感分析
"""
import sys
import os
import json
import hashlib
import re
from datetime import datetime, timedelta
import time
import threading

_backend_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_backend_dir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import httpx
from database import SessionLocal, NewsRaw, Layer1Result, NewsAligned, DailyKline
from pipeline.layer1 import analyze_news_sentiment

EAST_MONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
}

SINA_NEWS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
    "Accept-Charset": "GBK,utf-8;q=0.7,*;q=0.3",
}


def _fetch_json(url: str, headers: dict, timeout: int = 15) -> dict | None:
    """Fetch JSON data from a URL."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        print(f"[NEWS] Fetch failed {url}: {e}")
        return None


def _fetch_text(url: str, headers: dict, timeout: int = 15) -> str | None:
    """Fetch text data from a URL."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=True) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        print(f"[NEWS] Fetch failed {url}: {e}")
        return None


# ─── East Money (东方财富) News ─────────────────────────────────────────────
def fetch_eastmoney_stock_news(symbol: str, market: str = "sh", limit: int = 20) -> list[dict]:
    """
    Fetch news for a specific stock from East Money.
    Uses East Money's stock news API.
    """
    # Convert symbol to East Money format
    em_code = _to_eastmoney_code(symbol, market)
    url = (
        f"https://np-anotice-stock.eastmoney.com/api/security/ann"
        f"?cb=&sr=-1&page_size={limit}&page_index=1&ann_type=SHA%"
        f",SZA%,BJA%&client_source=web&stock_list={em_code}"
    )
    data = _fetch_json(url, EAST_MONEY_HEADERS)
    if not data:
        return []

    news_list = []
    items = data.get("data", {}).get("list", []) or []
    for item in items:
        try:
            news_id = hashlib.md5((str(item.get("id", "")) + symbol).encode()).hexdigest()[:24]
            title = item.get("title", "")
            content = item.get("digest", "") or item.get("notice_content", "") or ""
            # Format: "2024-01-15 10:30:00"
            pub_time = item.get("publish_time", "")
            if pub_time and isinstance(pub_time, int):
                pub_time = datetime.fromtimestamp(pub_time / 1000).strftime("%Y-%m-%d %H:%M:%S")
            source = item.get("security_source", "东方财富") or "东方财富"
            url_link = item.get("art_url", "") or f"https://data.eastmoney.com/news/{item.get('id', '')}.html"

            news_list.append({
                "id": news_id,
                "title": title.strip(),
                "content": content.strip()[:2000] if content else "",
                "source": source,
                "url": url_link,
                "published_at": pub_time,
                "symbols": [symbol],
            })
        except Exception as e:
            print(f"[NEWS] Parse eastmoney item error: {e}")
            continue

    return news_list


def fetch_eastmoney_stock_plain_news(symbol: str, market: str = "sh", limit: int = 20) -> list[dict]:
    """
    Fetch plain-text news (not official announcements) from East Money.
    This is the "资讯" type news.
    """
    em_code = _to_eastmoney_code(symbol, market)
    url = (
        f"https://np-listapi.eastmoney.com/comm/web/getNPList"
        f"?client=web&bPageSize={limit}&bPage=1&dtype=4&keyword={symbol}"
        f"&orderby=0&np=1&enddate=&startdate=&fields=350"
    )
    data = _fetch_json(url, EAST_MONEY_HEADERS)
    if not data:
        return []

    news_list = []
    items = data.get("data", {}).get("list", []) or data.get("list", []) or []
    for item in items:
        try:
            news_id = hashlib.md5((str(item.get("id", "")) + symbol).encode()).hexdigest()[:24]
            title = item.get("title", "")
            content = item.get("summary", "") or item.get("content", "") or ""
            pub_time = item.get("showtime", "") or item.get("datetime", "") or ""
            source = item.get("src", "") or "东方财富"
            url_link = item.get("url", "") or ""

            if not title:
                continue

            news_list.append({
                "id": news_id,
                "title": title.strip(),
                "content": content.strip()[:2000] if content else "",
                "source": source,
                "url": url_link,
                "published_at": pub_time,
                "symbols": [symbol],
            })
        except Exception as e:
            print(f"[NEWS] Parse eastmoney plain news error: {e}")
            continue

    return news_list


# ─── Sina Finance News ────────────────────────────────────────────────────────
def fetch_sina_stock_news(symbol: str, market: str = "sh", limit: int = 20) -> list[dict]:
    """
    Fetch news from Sina Finance for a specific stock.
    """
    # Sina finance news API
    full_sym = f"{market}{symbol}"
    url = (
        f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/{symbol}.page"
    )
    text = _fetch_text(url, SINA_NEWS_HEADERS)
    if not text:
        return []

    # Parse Sina news page (simple regex for demo)
    # In practice, Sina's page structure varies; fall back to API
    news_list = []

    # Try the news API
    api_url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=1686&k={symbol}&num={limit}&page=1"
    data = _fetch_json(api_url, SINA_NEWS_HEADERS)
    if data:
        items = data.get("result", {}).get("data", []) or []
        for item in items:
            try:
                news_id = hashlib.md5((item.get("int_id", "") + symbol).encode()).hexdigest()[:24]
                title = item.get("title", "")
                content = item.get("intro", "") or item.get("text", "") or ""
                pub_time = item.get("ctime", "") or ""
                if pub_time and isinstance(pub_time, str) and len(pub_time) == 10:
                    pub_time = datetime.fromtimestamp(int(pub_time)).strftime("%Y-%m-%d %H:%M:%S")
                source = item.get("media_name", "") or "新浪财经"
                url_link = item.get("url", "") or ""

                if not title:
                    continue

                news_list.append({
                    "id": news_id,
                    "title": title.strip(),
                    "content": content.strip()[:2000] if content else "",
                    "source": source,
                    "url": url_link,
                    "published_at": pub_time,
                    "symbols": [symbol],
                })
            except Exception:
                continue

    return news_list


# ─── General Market News ─────────────────────────────────────────────────────
def fetch_market_news(days: int = 3, limit: int = 50) -> list[dict]:
    """
    Fetch general A-share market news (not stock-specific).
    Returns news that might affect multiple stocks.
    """
    news_list = []

    # East Money market news
    url = (
        f"https://np-listapi.eastmoney.com/comm/web/getNPList"
        f"?client=web&bPageSize={limit}&bPage=1&dtype=4&keyword=&orderby=0&np=1"
        f"&enddate=&startdate=&fields=350"
    )
    data = _fetch_json(url, EAST_MONEY_HEADERS)
    if data:
        items = data.get("data", {}).get("list", []) or data.get("list", []) or []
        for item in items:
            try:
                item_id = item.get("id", "") or item.get("art_id", "")
                news_id = hashlib.md5((str(item_id) + "market").encode()).hexdigest()[:24]
                title = item.get("title", "")
                content = item.get("summary", "") or item.get("intro", "") or item.get("text", "") or ""
                pub_time = item.get("showtime", "") or item.get("datetime", "") or item.get("ctime", "") or ""
                if pub_time and len(pub_time) == 10 and pub_time.isdigit():
                    pub_time = datetime.fromtimestamp(int(pub_time)).strftime("%Y-%m-%d %H:%M:%S")
                source = item.get("src", "") or item.get("media_name", "") or "东方财富"
                url_link = item.get("url", "") or item.get("art_url", "") or ""

                if not title:
                    continue

                # Check if within date range
                try:
                    pub_date = pub_time[:10]
                    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                    if pub_date < cutoff:
                        continue
                except Exception:
                    pass

                news_list.append({
                    "id": news_id,
                    "title": title.strip(),
                    "content": content.strip()[:2000] if content else "",
                    "source": source,
                    "url": url_link,
                    "published_at": pub_time,
                    "symbols": [],
                })
            except Exception as e:
                print(f"[NEWS] Parse market news error: {e}")
                continue

    return news_list


# ─── Helper ──────────────────────────────────────────────────────────────────
def _to_eastmoney_code(symbol: str, market: str = "sh") -> str:
    """Convert symbol+market to East Money code format."""
    # Shanghai: sh600036 -> 600036.sh
    # Shenzhen: sz000858 -> 000858.sz
    # GEM: sz300750 -> 300750.sz
    # STAR: sh688981 -> 688981.sh
    # BJ: bj8xxxxx -> xxxxxx.bj
    market_map = {"sh": "sh", "sz": "sz", "bj": "bj"}
    m = market_map.get(market, "sh")
    return f"{symbol}.{m}"


def _parse_date(date_str: str) -> str:
    """Parse various date formats to YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    date_str = date_str.strip()

    # Already ISO format
    if re.match(r"\d{4}-\d{2}-\d{2}", date_str):
        return date_str[:10]

    # Timestamp (10 digits)
    if re.match(r"^\d{10}$", date_str):
        return datetime.fromtimestamp(int(date_str)).strftime("%Y-%m-%d")

    # Timestamp (13 digits, ms)
    if re.match(r"^\d{13}$", date_str):
        return datetime.fromtimestamp(int(date_str) / 1000).strftime("%Y-%m-%d")

    # Try parsing
    for fmt in ["%Y/%m/%d %H:%M:%S", "%Y/%m/%d", "%m/%d %H:%M"]:
        try:
            return datetime.strptime(date_str[:19], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    return date_str[:10]


# ─── Save News to SQLite ─────────────────────────────────────────────────────
def save_news_to_db(news_items: list[dict]) -> list[str]:
    """Save news items to SQLite, return saved news IDs."""
    if not news_items:
        return []

    db = SessionLocal()
    saved_ids = []
    try:
        for item in news_items:
            news_id = item.get("id", "")
            if not news_id:
                news_id = hashlib.md5((item["title"] + item.get("published_at", "")).encode()).hexdigest()[:24]

            # Check if already exists
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
        print(f"[NEWS] Saved {len(saved_ids)} news items to DB")
    except Exception as e:
        print(f"[NEWS] Save error: {e}")
        db.rollback()
    finally:
        db.close()

    return saved_ids


# ─── Align news to trading dates + compute returns ───────────────────────────
def align_news_to_trading_dates(symbol: str):
    """
    Align news items to trading dates and compute T+0..T+5 returns.
    """
    db = SessionLocal()
    try:
        # Get all news for this symbol without aligned date
        raw_news = db.query(NewsRaw).filter(
            NewsRaw.id.in_(
                db.query(Layer1Result.news_id).filter(Layer1Result.symbol == symbol)
            )
        ).all()

        # Load kline data
        klines = db.query(DailyKline).filter(
            DailyKline.code == symbol
        ).order_by(DailyKline.date).all()

        if not klines:
            print(f"[NEWS] No kline data for {symbol}, skipping alignment")
            return

        date_map = {str(k.date)[:10]: k for k in klines}
        sorted_dates = sorted(date_map.keys())

        for news in raw_news:
            # Determine trade date from published_at
            pub_str = news.published_at or ""
            pub_date = _parse_date(pub_str[:19])

            # Find the next trading day >= pub_date
            trade_date = None
            for d in sorted_dates:
                if d >= pub_date:
                    trade_date = d
                    break
            if not trade_date:
                trade_date = sorted_dates[-1] if sorted_dates else pub_date

            # Compute returns T+0..T+5
            try:
                trade_idx = sorted_dates.index(trade_date)
            except ValueError:
                trade_date = sorted_dates[0]
                trade_idx = 0

            k0 = date_map.get(trade_date)
            ret_t0 = 0.0
            ret_t1 = 0.0
            ret_t3 = 0.0
            ret_t5 = 0.0

            if k0:
                ret_t0 = k0.change_pct or 0.0

            # T+1
            if trade_idx + 1 < len(sorted_dates):
                k1 = date_map.get(sorted_dates[trade_idx + 1])
                if k0 and k1:
                    ret_t1 = round((k1.close - k0.close) / k0.close * 100, 4)

            # T+3
            if trade_idx + 3 < len(sorted_dates):
                k3 = date_map.get(sorted_dates[trade_idx + 3])
                if k0 and k3:
                    ret_t3 = round((k3.close - k0.close) / k0.close * 100, 4)

            # T+5
            if trade_idx + 5 < len(sorted_dates):
                k5 = date_map.get(sorted_dates[trade_idx + 5])
                if k0 and k5:
                    ret_t5 = round((k5.close - k0.close) / k0.close * 100, 4)

            # Check if already aligned
            existing = db.query(NewsAligned).filter(
                NewsAligned.symbol == symbol,
                NewsAligned.news_id == news.id
            ).first()

            if not existing:
                aligned = NewsAligned(
                    news_id=news.id,
                    symbol=symbol,
                    trade_date=trade_date,
                    ret_t0=ret_t0,
                    ret_t1=ret_t1,
                    ret_t3=ret_t3,
                    ret_t5=ret_t5,
                )
                db.add(aligned)

        db.commit()
        print(f"[NEWS] Aligned news for {symbol}")
    except Exception as e:
        print(f"[NEWS] Alignment error for {symbol}: {e}")
        db.rollback()
    finally:
        db.close()


# ─── Main: Fetch + Save + Analyze ────────────────────────────────────────────
def fetch_and_analyze_stock_news(symbol: str, market: str = "sh") -> dict:
    """
    Complete pipeline: fetch news -> save to DB -> analyze sentiment -> align
    """
    results = {"fetched": 0, "saved": 0, "analyzed": 0}

    # 1. Fetch from multiple sources
    all_news = []
    all_news.extend(fetch_eastmoney_stock_news(symbol, market, limit=15))
    all_news.extend(fetch_eastmoney_stock_plain_news(symbol, market, limit=15))
    all_news.extend(fetch_sina_stock_news(symbol, market, limit=10))

    # Deduplicate by title
    seen = set()
    unique_news = []
    for n in all_news:
        if n["title"] not in seen:
            seen.add(n["title"])
            unique_news.append(n)
    all_news = unique_news

    results["fetched"] = len(all_news)
    print(f"[NEWS] Fetched {results['fetched']} news for {symbol}")

    # 2. Save to DB
    saved_ids = save_news_to_db(all_news)
    results["saved"] = len(saved_ids)

    if not saved_ids:
        return results

    # 3. Analyze sentiment for new items
    db = SessionLocal()
    try:
        for news_id in saved_ids:
            # Check if already analyzed
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
                symbol=symbol,
                news_id=news_id,
                title=news.title,
                content=news.content,
            )

            result = Layer1Result(
                news_id=news_id,
                symbol=symbol,
                sentiment=sentiment.get("sentiment", "neutral"),
                sentiment_cn=sentiment.get("sentiment_cn", "中性"),
                relevance=sentiment.get("relevance", "medium"),
                key_discussion=sentiment.get("key_discussion", ""),
                reason_growth=sentiment.get("reason_growth", ""),
                reason_decrease=sentiment.get("reason_decrease", ""),
            )
            db.add(result)
            results["analyzed"] += 1

        db.commit()
    except Exception as e:
        print(f"[NEWS] Sentiment analysis error: {e}")
        db.rollback()
    finally:
        db.close()

    # 4. Align to trading dates
    try:
        align_news_to_trading_dates(symbol)
    except Exception as e:
        print(f"[NEWS] Alignment error: {e}")

    return results


def bg_fetch_news(symbol: str, market: str = "sh"):
    """Background thread target for news fetching."""
    try:
        fetch_and_analyze_stock_news(symbol, market)
    except Exception as e:
        print(f"[BG NEWS] {symbol} failed: {e}")
