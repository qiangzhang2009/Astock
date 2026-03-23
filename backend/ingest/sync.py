"""
股票数据同步模块
从新浪财经获取K线数据并存入SQLite
"""
import sys
import os
import json
import hashlib
import re
from datetime import datetime, timedelta
import threading

# Resolve path for direct execution
_backend_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_backend_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import pandas as pd
import httpx
from database import SessionLocal, Stock, DailyKline, init_db

# Import expanded A-share stock pool (300+ stocks across all sectors)
try:
    from .stock_pool import ASTOCK_POOL, SECTORS
    DEFAULT_STOCKS = ASTOCK_POOL
except ImportError:
    # Fallback inline if data module unavailable
    DEFAULT_STOCKS = [
    # 科技/AI
    ("002230", "科大讯飞", "AI", "sz"),
    ("688981", "中芯国际", "半导体", "sh"),
    ("688256", "寒武纪", "AI芯片", "sh"),
    ("002049", "紫光国微", "芯片", "sz"),
    ("300496", "中科创达", "软件", "sz"),
    ("002371", "北方华创", "半导体设备", "sz"),
    ("300033", "同花顺", "互联网金融", "sz"),
    ("603986", "兆易创新", "芯片", "sh"),
    ("688012", "中微公司", "半导体设备", "sh"),
    ("002415", "海康威视", "安防", "sz"),
    # 新能源
    ("300750", "宁德时代", "新能源", "sz"),
    ("002594", "比亚迪", "新能源汽车", "sz"),
    ("300274", "阳光电源", "光伏逆变器", "sz"),
    ("601012", "隆基绿能", "光伏", "sh"),
    ("601857", "中国石油", "石油", "sh"),
    ("600900", "长江电力", "电力", "sh"),
    # 白酒
    ("600519", "贵州茅台", "白酒", "sh"),
    ("000858", "五粮液", "白酒", "sz"),
    ("600809", "山西汾酒", "白酒", "sh"),
    ("000568", "泸州老窖", "白酒", "sz"),
    ("000596", "古井贡酒", "白酒", "sz"),
    ("002304", "洋河股份", "白酒", "sz"),
    # 金融
    ("600036", "招商银行", "银行", "sh"),
    ("601318", "中国平安", "保险", "sh"),
    ("300059", "东方财富", "互联网券商", "sz"),
    ("000001", "平安银行", "银行", "sz"),
    ("600000", "浦发银行", "银行", "sh"),
    ("601166", "兴业银行", "银行", "sh"),
    ("601398", "工商银行", "银行", "sh"),
    ("601288", "农业银行", "银行", "sh"),
    ("600016", "民生银行", "银行", "sh"),
    # 医药
    ("600276", "恒瑞医药", "医药", "sh"),
    ("603259", "药明康德", "医药", "sh"),
    ("000538", "云南白药", "医药", "sz"),
    ("300760", "迈瑞医疗", "医疗器械", "sz"),
    ("688271", "联影医疗", "医疗器械", "sh"),
    # 消费电子
    ("002475", "立讯精密", "消费电子", "sz"),
    ("000725", "京东方A", "面板", "sz"),
    ("002241", "歌尔股份", "消费电子", "sz"),
    ("300782", "卓胜微", "射频芯片", "sz"),
    # 通信
    ("600050", "中国联通", "通信", "sh"),
    ("000063", "中兴通讯", "通信设备", "sz"),
    ("601728", "中国电信", "通信", "sh"),
    ("600941", "中国移动", "通信", "sh"),
    # 地产基建
    ("600048", "保利发展", "房地产", "sh"),
    ("601668", "中国建筑", "建筑", "sh"),
    ("601669", "中国电建", "基建", "sh"),
    # 军工
    ("600893", "航发动力", "军工", "sh"),
    ("002013", "中航机电", "军工", "sz"),
    ("600760", "中航沈飞", "军工", "sh"),
    ("000733", "振华科技", "军工电子", "sz"),
    # 其他
    ("600887", "伊利股份", "乳业", "sh"),
    ("600600", "青岛啤酒", "啤酒", "sh"),
    ("002456", "欧菲光", "光学", "sz"),
    ("600150", "中国船舶", "造船", "sh"),
    ("601919", "中远海控", "航运", "sh"),
    ("600036", "招商银行", "银行", "sh"),
    ("300124", "汇川技术", "工业自动化", "sz"),
    ("002050", "三花智控", "热管理", "sz"),
    ]
except ImportError:
    # Minimal fallback if data module unavailable
    DEFAULT_STOCKS = [
        ("002230", "科大讯飞", "AI", "sz"),
        ("688981", "中芯国际", "半导体", "sh"),
        ("300750", "宁德时代", "新能源", "sz"),
        ("600519", "贵州茅台", "白酒", "sh"),
        ("600036", "招商银行", "银行", "sh"),
    ]

# Sina Finance HTTP headers
SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Charset": "GBK,utf-8;q=0.7,*;q=0.3",
}


def get_full_symbol(symbol: str, market: str = "sh") -> str:
    """Return full Sina-format stock code."""
    if symbol.startswith(("sh", "sz", "bj")):
        return symbol[:6]
    prefix_map = {"sh": "sh", "sz": "sz", "bj": "bj"}
    return f"{prefix_map.get(market, 'sh')}{symbol}"


def _fetch_url(url: str, timeout: int = 15) -> bytes | None:
    """Send HTTP GET request."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=True) as client:
            resp = client.get(url, headers=SINA_HEADERS)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        print(f"[SINA] Request failed {url}: {e}")
        return None


def _decode_gbk(text: bytes) -> str:
    """Decode GBK bytes to UTF-8 string."""
    return text.decode("gbk", errors="replace")


def fetch_realtime_quote(symbol: str, market: str = "sh") -> dict | None:
    """
    Fetch realtime quote for a single stock from Sina Finance.
    Returns a dict with price, change, volume, etc.
    """
    full_sym = get_full_symbol(symbol, market)
    url = f"http://hq.sinajs.cn/list={full_sym}"
    raw = _fetch_url(url, timeout=10)
    if not raw:
        return None

    text = raw.decode("gbk", errors="replace")
    m = re.search(r'hq_str_\w+="([^"]+)"', text)
    if not m:
        return None

    fields = m.group(1).split(",")
    if len(fields) < 32:
        return None

    try:
        name = fields[0]
        open_ = float(fields[1]) if fields[1] else 0
        prev_close = float(fields[2]) if fields[2] else 0
        price = float(fields[3]) if fields[3] else 0
        high = float(fields[4]) if fields[4] else 0
        low = float(fields[5]) if fields[5] else 0
        volume = float(fields[8]) if fields[8] else 0
        amount = float(fields[9]) if fields[9] else 0
        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        amplitude = ((high - low) / prev_close * 100) if prev_close else 0

        return {
            "name": name,
            "price": price,
            "open": open_,
            "prev_close": prev_close,
            "high": high,
            "low": low,
            "volume": int(volume),
            "amount": int(amount),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "amplitude": round(amplitude, 2),
        }
    except (IndexError, ValueError) as e:
        print(f"[SINA] Quote parse error {symbol}: {e}")
        return None


def fetch_realtime_quotes(symbols: list[str], markets: list[str]) -> list[dict]:
    """
    Fetch realtime quotes for multiple stocks from Sina Finance.
    symbols and markets should be parallel lists.
    """
    if not symbols:
        return []

    codes = ",".join(get_full_symbol(s, m) for s, m in zip(symbols, markets))
    url = f"http://hq.sinajs.cn/list={codes}"
    raw = _fetch_url(url, timeout=15)
    if not raw:
        return []

    text = raw.decode("gbk", errors="replace")
    results = []

    for sym, mkt in zip(symbols, markets):
        pattern = rf'hq_str_{get_full_symbol(sym, mkt)}="([^"]+)"'
        m = re.search(pattern, text)
        if not m or not m.group(1):
            results.append({"symbol": sym, "market": mkt, "error": "no_data"})
            continue

        fields = m.group(1).split(",")
        if len(fields) < 10:
            results.append({"symbol": sym, "market": mkt, "error": "parse_error"})
            continue

        try:
            prev_close = float(fields[2]) if fields[2] else 0
            price = float(fields[3]) if fields[3] else 0
            change = price - prev_close
            results.append({
                "symbol": sym,
                "name": fields[0],
                "price": price,
                "prev_close": prev_close,
                "open": float(fields[1]) if fields[1] else 0,
                "high": float(fields[4]) if fields[4] else 0,
                "low": float(fields[5]) if fields[5] else 0,
                "volume": int(float(fields[8])) if fields[8] else 0,
                "amount": int(float(fields[9])) if fields[9] else 0,
                "change": round(change, 2),
                "change_pct": round((change / prev_close * 100) if prev_close else 0, 2),
            })
        except (IndexError, ValueError):
            results.append({"symbol": sym, "market": mkt, "error": "parse_error"})

    return results


def fetch_ohlc(symbol: str, market: str = "sh", days: int = 730) -> pd.DataFrame:
    """Fetch daily K-line data from Sina Finance."""
    full_sym = get_full_symbol(symbol, market)
    datalen = min(days, 1023)
    url = (
        f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
        f"/CN_MarketData.getKLineData"
        f"?symbol={full_sym}&scale=240&ma=no&datalen={datalen}"
    )

    raw = _fetch_url(url, timeout=20)
    if not raw:
        print(f"[SINA] Failed to get K-line for {symbol}")
        return pd.DataFrame()

    try:
        text_content = raw.decode("utf-8", errors="replace")
        data = json.loads(text_content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[SINA] JSON parse error {symbol}: {e}")
        return pd.DataFrame()

    if not data or not isinstance(data, list):
        print(f"[SINA] K-line data empty for {symbol}: {text_content[:100]}")
        return pd.DataFrame()

    rows = []
    prev_close = None
    for candle in data:
        try:
            day = candle.get("day", "")
            open_ = float(candle.get("open", 0))
            high = float(candle.get("high", 0))
            low = float(candle.get("low", 0))
            close = float(candle.get("close", 0))
            volume = float(candle.get("volume", 0))

            if close <= 0:
                continue

            if prev_close is not None and prev_close > 0:
                change_pct = round((close - prev_close) / prev_close * 100, 2)
            else:
                change_pct = 0.0

            avg_price = (high + low + close) / 3
            amount = round(volume * avg_price, 2)
            amplitude = round((high - low) / prev_close * 100, 2) if prev_close and prev_close > 0 else 0

            rows.append({
                "code": symbol,
                "date": day[:10],
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": int(volume),
                "amount": int(amount),
                "change_pct": change_pct,
                "limit_up": 1 if change_pct >= 9.5 else 0,
                "limit_down": 1 if change_pct <= -9.5 else 0,
                "amplitude": amplitude,
            })
            prev_close = close
        except (ValueError, TypeError) as e:
            print(f"[SINA] K-line row parse error {symbol}: {e}")
            continue

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def sync_ohlc_to_pg(symbol: str, market: str = "sh", days: int = 730) -> int:
    """
    Fetch K-line data and sync to SQLite.
    (Renamed from pg but now uses SQLite)
    """
    df = fetch_ohlc(symbol, market, days)
    if df.empty:
        return 0

    db = SessionLocal()
    rows = 0
    try:
        for _, row in df.iterrows():
            existing = db.query(DailyKline).filter(
                DailyKline.code == symbol,
                DailyKline.date == row["date"]
            ).first()

            if not existing:
                kline = DailyKline(
                    code=symbol,
                    date=row["date"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                    amount=row["amount"],
                    change_pct=row["change_pct"],
                    limit_up=row.get("limit_up", 0),
                    limit_down=row.get("limit_down", 0),
                    amplitude=row.get("amplitude", 0),
                )
                db.add(kline)
                rows += 1

        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if stock:
            stock.last_ohlc_fetch = datetime.now().isoformat()

        db.commit()
        print(f"[DB] Synced {symbol}: {rows} new rows")
    except Exception as e:
        print(f"[ERROR] Sync {symbol} failed: {e}")
        db.rollback()
    finally:
        db.close()

    return rows


def sync_ohlc_to_db(symbol: str, market: str = "sh") -> int:
    """Alias for backward compatibility."""
    return sync_ohlc_to_pg(symbol, market)


def seed_stocks():
    """Initialize the stock pool."""
    db = SessionLocal()
    try:
        for sym, name, sector, market in DEFAULT_STOCKS:
            stock = db.query(Stock).filter(Stock.symbol == sym).first()
            if not stock:
                stock = Stock(
                    symbol=sym,
                    name=name,
                    sector=sector,
                    market=market,
                    last_ohlc_fetch=None,
                    last_news_fetch=None
                )
                db.add(stock)
        db.commit()
        print(f"[DB] Initialized {len(DEFAULT_STOCKS)} stocks")
    finally:
        db.close()


def sync_all_defaults(max_stocks: int = 50):
    """Sync all default stocks K-line data."""
    for sym, name, sector, market in DEFAULT_STOCKS[:max_stocks]:
        try:
            sync_ohlc_to_pg(sym, market)
        except Exception as e:
            print(f"[ERROR] {sym} failed: {e}")


def background_sync(symbol: str, market: str = "sh"):
    """Background sync thread target."""
    try:
        sync_ohlc_to_pg(symbol, market)
    except Exception as e:
        print(f"[BG] Sync {symbol} failed: {e}")


def start_bg_sync(symbol: str, market: str = "sh"):
    """Start a background sync thread."""
    t = threading.Thread(target=background_sync, args=(symbol, market), daemon=True)
    t.start()
    return t
