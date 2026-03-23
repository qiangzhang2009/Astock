"""
新浪财经 A 股数据获取客户端
支持上交所/深交所/科创板/创业板/北交所股票
无需 API Key，直接从新浪财经获取数据

新浪接口文档：
- 实时行情: http://hq.sinajs.cn/list=<code>
- 历史K线: http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData
"""

import re
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

import httpx
import pandas as pd


# 默认关注的优质 A 股股票池
DEFAULT_STOCKS = [
    ("600036", "招商银行", "银行", "sh"),
    ("600519", "贵州茅台", "白酒", "sh"),
    ("000858", "五粮液", "白酒", "sz"),
    ("601318", "中国平安", "保险", "sh"),
    ("600276", "恒瑞医药", "医药", "sh"),
    ("300750", "宁德时代", "新能源", "sz"),
    ("300059", "东方财富", "互联网券商", "sz"),
    ("002475", "立讯精密", "消费电子", "sz"),
    ("600809", "山西汾酒", "白酒", "sh"),
    ("002415", "海康威视", "安防", "sz"),
    ("688981", "中芯国际", "半导体", "sh"),
    ("688256", "寒武纪", "AI芯片", "sh"),
    ("002230", "科大讯飞", "AI", "sz"),
    ("300496", "中科创达", "软件", "sz"),
    ("002049", "紫光国微", "芯片", "sz"),
    ("603259", "药明康德", "医药", "sh"),
    ("002371", "北方华创", "半导体设备", "sz"),
    ("300033", "同花顺", "互联网金融", "sz"),
    ("601012", "隆基绿能", "光伏", "sh"),
    ("002594", "比亚迪", "新能源汽车", "sz"),
    ("300274", "阳光电源", "光伏逆变器", "sz"),
    ("601857", "中国石油", "石油", "sh"),
    ("600887", "伊利股份", "乳业", "sh"),
    ("000568", "泸州老窖", "白酒", "sz"),
    ("600600", "青岛啤酒", "啤酒", "sh"),
    ("000001", "平安银行", "银行", "sz"),
    ("600000", "浦发银行", "银行", "sh"),
    ("601166", "兴业银行", "银行", "sh"),
    ("600048", "保利发展", "房地产", "sh"),
    ("601668", "中国建筑", "建筑", "sh"),
    ("600050", "中国联通", "通信", "sh"),
    ("000063", "中兴通讯", "通信设备", "sz"),
    ("600893", "航发动力", "军工", "sh"),
    ("002013", "中航机电", "军工", "sz"),
    ("000725", "京东方A", "面板", "sz"),
    ("002456", "欧菲光", "光学", "sz"),
]

# 新浪财经 HTTP 头（必需）
SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Charset": "GBK,utf-8;q=0.7,*;q=0.3",
}


def _fetch_url(url: str, timeout: int = 10) -> Optional[bytes]:
    """发送 HTTP GET 请求，返回原始字节（使用系统代理）"""
    try:
        # httpx 需要 TRUST_ENV=True 才能自动使用系统代理
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=True) as client:
            resp = client.get(url, headers=SINA_HEADERS)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        print(f"[SINA] 请求失败 {url}: {e}")
        return None


def get_full_symbol(symbol: str, market: str = "sh") -> str:
    """返回新浪格式的完整股票代码"""
    if symbol.startswith(("sh", "sz", "bj", "沪", "深")):
        return symbol[:6]
    prefix_map = {"sh": "sh", "sz": "sz", "bj": "bj"}
    return f"{prefix_map.get(market, 'sh')}{symbol}"


def _decode_gbk(text: bytes) -> str:
    """将 GBK 编码的字节串解码为 UTF-8 字符串"""
    return text.decode("gbk", errors="replace")


# ─────────────────────────────────────────────
# 1. 实时行情
# ─────────────────────────────────────────────
def fetch_realtime_quote(symbol: str, market: str = "sh") -> Optional[dict]:
    """
    获取单只股票实时行情

    返回字段:
      name, price, open, prev_close, high, low,
      volume(股), turnover(元),
      change_pct(涨跌幅%), bid1-ask5 等
    """
    full_sym = get_full_symbol(symbol, market)
    url = f"http://hq.sinajs.cn/list={full_sym}"
    raw = _fetch_url(url)
    if not raw:
        return None

    text = _decode_gbk(raw)

    # 格式: var hq_str_sh600519="贵州茅台,今日开盘价,昨日收盘价,......"
    m = re.search(r'hq_str_[a-z]{2}(\d+)="([^"]+)"', text)
    if not m:
        return None

    code = m.group(1)
    fields = m.group(2).split(",")

    # 新浪实时行情字段说明（A股）：
    # 0: 名称, 1: 今开, 2: 昨收, 3: 现价, 4: 最高, 5: 最低
    # 6: 买一价, 7: 卖一价, 8: 成交量(股), 9: 成交额(元)
    # 10-19: 买1-5档(价/量), 20-29: 卖1-5档(价/量)
    # 30: 日期(YYYY-MM-DD), 31: 时间(HH:MM:SS), 32: 状态码

    try:
        name = fields[0]
        open_ = float(fields[1]) if fields[1] else 0
        prev_close = float(fields[2]) if fields[2] else 0
        price = float(fields[3]) if fields[3] else 0
        high = float(fields[4]) if fields[4] else 0
        low = float(fields[5]) if fields[5] else 0
        volume = float(fields[8]) if fields[8] else 0   # 成交量（股）
        turnover = float(fields[9]) if fields[9] else 0  # 成交额（元）

        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        return {
            "symbol": code,
            "name": name,
            "price": price,
            "open": open_,
            "prev_close": prev_close,
            "high": high,
            "low": low,
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": volume,
            "turnover": turnover,
            "bid1": float(fields[10]) if len(fields) > 10 else 0,
            "bid_vol1": float(fields[11]) if len(fields) > 11 else 0,
            "ask1": float(fields[20]) if len(fields) > 20 else 0,
            "ask_vol1": float(fields[21]) if len(fields) > 21 else 0,
            "date": fields[30] if len(fields) > 30 else "",
            "time": fields[31] if len(fields) > 31 else "",
        }
    except (IndexError, ValueError) as e:
        print(f"[SINA] 解析实时行情失败 {code}: {e} | fields={fields[:5]}")
        return None


def fetch_realtime_batch(symbols: list[tuple[str, str]]) -> list[dict]:
    """
    批量获取多只股票实时行情
    symbols: [(symbol, market), ...]
    """
    if not symbols:
        return []
    codes = ",".join(get_full_symbol(s, m) for s, m in symbols)
    url = f"http://hq.sinajs.cn/list={codes}"
    raw = _fetch_url(url)
    if not raw:
        return []

    text = _decode_gbk(raw)
    results = []

    # 匹配所有 hq_str_xxNNNNNN="..."
    for m in re.finditer(r'hq_str_[a-z]{2}(\d+)="([^"]+)"', text):
        code = m.group(1)
        # 找到对应的 market
        market = "sh"
        for s, mv in symbols:
            if s == code:
                market = mv
                break

        fields = m.group(2).split(",")
        try:
            name = fields[0]
            price = float(fields[3]) if fields[3] else 0
            prev_close = float(fields[2]) if fields[2] else 0
            change = price - prev_close if prev_close else 0
            change_pct = (change / prev_close * 100) if prev_close else 0

            results.append({
                "symbol": code,
                "name": name,
                "market": market,
                "price": price,
                "change_pct": round(change_pct, 2),
                "change": round(change, 2),
                "volume": float(fields[8]) if fields[8] else 0,
                "turnover": float(fields[9]) if fields[9] else 0,
                "high": float(fields[4]) if fields[4] else 0,
                "low": float(fields[5]) if fields[5] else 0,
                "open": float(fields[1]) if fields[1] else 0,
            })
        except (IndexError, ValueError):
            continue

    return results


# ─────────────────────────────────────────────
# 2. 历史 K 线（日线）
# ─────────────────────────────────────────────
def fetch_ohlc(symbol: str, market: str = "sh", days: int = 730) -> pd.DataFrame:
    """
    获取单只股票日线 K 线数据（来自新浪财经）

    返回 DataFrame:
      date, open, high, low, close, volume, turnover, change_pct,
      limit_up, limit_down, amplitude
    """
    full_sym = get_full_symbol(symbol, market)

    # scale=240 表示日线（240分钟），datalen 最大 1023
    datalen = min(days, 1023)
    url = (
        f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
        f"/CN_MarketData.getKLineData"
        f"?symbol={full_sym}&scale=240&ma=no&datalen={datalen}"
    )

    raw = _fetch_url(url, timeout=15)
    if not raw:
        print(f"[SINA] 获取K线失败 {symbol}")
        return pd.DataFrame()

    try:
        text = raw.decode("utf-8", errors="replace")
        data = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[SINA] JSON解析失败 {symbol}: {e}")
        return pd.DataFrame()

    if not data or not isinstance(data, list):
        print(f"[SINA] K线数据为空 {symbol}: {text[:100]}")
        return pd.DataFrame()

    rows = []
    prev_close = None
    for i, candle in enumerate(data):
        try:
            day = candle.get("day", "")
            open_ = float(candle.get("open", 0))
            high = float(candle.get("high", 0))
            low = float(candle.get("low", 0))
            close = float(candle.get("close", 0))
            volume = float(candle.get("volume", 0))

            if close <= 0:
                continue

            # 计算涨跌幅（根据前后收盘价）
            if prev_close is not None and prev_close > 0:
                change_pct = round((close - prev_close) / prev_close * 100, 2)
            else:
                change_pct = 0.0

            # 估算成交额（量为股，均价×量）
            avg_price = (high + low + close) / 3
            turnover = round(volume * avg_price, 2)

            # 振幅
            amplitude = round((high - low) / prev_close * 100, 2) if prev_close and prev_close > 0 else 0

            rows.append({
                "date": day,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": int(volume),
                "turnover": int(turnover),
                "change_pct": change_pct,
                "limit_up": 1 if change_pct >= 9.5 else 0,
                "limit_down": 1 if change_pct <= -9.5 else 0,
                "amplitude": amplitude,
            })
            prev_close = close
        except (ValueError, TypeError) as e:
            print(f"[SINA] 解析K线行失败 {symbol}: {e}")
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # 数据按日期升序返回
    return df[["date", "open", "high", "low", "close", "volume",
               "turnover", "change_pct", "limit_up", "limit_down", "amplitude"]]


# ─────────────────────────────────────────────
# 3. 涨停/跌停板股票池
# ─────────────────────────────────────────────
def fetch_limit_up_stocks() -> list[dict]:
    """获取今日涨停股票列表（通过搜索实时涨幅榜）"""
    # 新浪没有直接的涨停榜，改用财联社等接口
    # 这里返回空列表，实际筛选在 screener API 中做
    return []


# ─────────────────────────────────────────────
# 4. 指数行情
# ─────────────────────────────────────────────
def fetch_index_quote(index_code: str = "sh000001") -> Optional[dict]:
    """获取指数实时行情（上证指数 sh000001、深证成指 sz399001 等）"""
    url = f"http://hq.sinajs.cn/list={index_code}"
    raw = _fetch_url(url)
    if not raw:
        return None

    text = _decode_gbk(raw)
    m = re.search(r'hq_str_(\w+)="([^"]+)"', text)
    if not m:
        return None

    fields = m.group(2).split(",")
    try:
        name = fields[0]
        price = float(fields[3]) if fields[3] else 0
        prev_close = float(fields[2]) if fields[2] else 0
        change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0

        return {
            "symbol": index_code,
            "name": name,
            "price": price,
            "change_pct": change_pct,
            "high": float(fields[4]) if fields[4] else 0,
            "low": float(fields[5]) if fields[5] else 0,
            "volume": float(fields[8]) if fields[8] else 0,
            "turnover": float(fields[9]) if fields[9] else 0,
        }
    except (IndexError, ValueError):
        return None


# ─────────────────────────────────────────────
# 5. 北向资金（沪深港通）
# ─────────────────────────────────────────────
def fetch_northbound_flow() -> dict:
    """
    获取北向资金（沪深港通）净流入数据
    新浪无直接接口，返回空占位
    """
    return {
        "north_bound": 0,
        "shanghai_connect": 0,
        "shenzhen_connect": 0,
        "timestamp": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────
# 6. 数据库同步
# ─────────────────────────────────────────────
def seed_default_stocks(conn: sqlite3.Connection):
    """初始化默认股票池"""
    for sym, name, sector, market in DEFAULT_STOCKS:
        conn.execute(
            """INSERT OR IGNORE INTO stocks (symbol, name, sector, market)
               VALUES (?, ?, ?, ?)""",
            (sym, name, sector, market)
        )
    conn.commit()


def sync_ohlc_to_db(symbol: str, market: str = "sh") -> int:
    """
    获取K线数据并同步到数据库
    返回: 插入/更新行数
    """
    from database import get_conn

    df = fetch_ohlc(symbol, market)
    if df.empty:
        return 0

    conn = get_conn()
    rows = 0
    for _, row in df.iterrows():
        conn.execute(
            """INSERT OR REPLACE INTO ohlc
               (symbol, date, open, high, low, close, volume, turnover, change_pct, limit_up, limit_down, amplitude)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                symbol,
                row["date"],
                row["open"],
                row["high"],
                row["low"],
                row["close"],
                int(row["volume"]),
                int(row["turnover"]),
                row["change_pct"],
                int(row["limit_up"]),
                int(row["limit_down"]),
                row["amplitude"],
            )
        )
        rows += 1

    conn.execute(
        "UPDATE stocks SET last_ohlc_fetch = ? WHERE symbol = ?",
        (datetime.now().isoformat(), symbol)
    )
    conn.commit()
    conn.close()

    print(f"[SINA] 已同步 {symbol} {rows} 条K线")
    return rows
