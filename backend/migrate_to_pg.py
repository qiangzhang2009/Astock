"""
股票数据迁移脚本
从新浪财经获取数据并存入 PostgreSQL
"""

import sys
sys.path.insert(0, '/Users/john/stock-analysis/astock/backend')

from datetime import datetime
import pandas as pd
from sqlalchemy import text
from database import engine, SessionLocal, Stock, DailyKline

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
    ("002415", "海康威视", "安防", "sh"),
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

# 新浪财经 HTTP 头
SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Charset": "GBK,utf-8;q=0.7,*;q=0.3",
}


def get_full_symbol(symbol: str, market: str = "sh") -> str:
    """返回新浪格式的完整股票代码"""
    if symbol.startswith(("sh", "sz", "bj", "沪", "深")):
        return symbol[:6]
    prefix_map = {"sh": "sh", "sz": "sz", "bj": "bj"}
    return f"{prefix_map.get(market, 'sh')}{symbol}"


def _fetch_url(url: str, timeout: int = 10) -> bytes | None:
    """发送 HTTP GET 请求"""
    import httpx
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=True) as client:
            resp = client.get(url, headers=SINA_HEADERS)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        print(f"[SINA] 请求失败 {url}: {e}")
        return None


def fetch_ohlc(symbol: str, market: str = "sh", days: int = 730) -> pd.DataFrame:
    """获取单只股票日线 K 线数据"""
    import json
    full_sym = get_full_symbol(symbol, market)
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
        text_content = raw.decode("utf-8", errors="replace")
        data = json.loads(text_content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"[SINA] JSON解析失败 {symbol}: {e}")
        return pd.DataFrame()

    if not data or not isinstance(data, list):
        print(f"[SINA] K线数据为空 {symbol}")
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

            if prev_close is not None and prev_close > 0:
                change_pct = round((close - prev_close) / prev_close * 100, 2)
            else:
                change_pct = 0.0

            avg_price = (high + low + close) / 3
            amount = round(volume * avg_price, 2)

            rows.append({
                "code": symbol,
                "date": day,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": int(volume),
                "amount": int(amount),
                "change_pct": change_pct,
            })
            prev_close = close
        except (ValueError, TypeError) as e:
            print(f"[SINA] 解析K线行失败 {symbol}: {e}")
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    return df


def seed_stocks():
    """初始化股票池"""
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
        print(f"[DB] 已初始化 {len(DEFAULT_STOCKS)} 只股票")
    finally:
        db.close()


def sync_ohlc_to_pg(symbol: str, market: str = "sh") -> int:
    """获取K线数据并同步到 PostgreSQL"""
    df = fetch_ohlc(symbol, market)
    if df.empty:
        return 0

    db = SessionLocal()
    rows = 0
    try:
        for _, row in df.iterrows():
            # 检查是否已存在
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
                )
                db.add(kline)
                rows += 1

        # 更新股票的 last_ohlc_fetch
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if stock:
            stock.last_ohlc_fetch = datetime.now().isoformat()

        db.commit()
        print(f"[SINA] 已同步 {symbol} {rows} 条K线")
    except Exception as e:
        print(f"[ERROR] 同步 {symbol} 失败: {e}")
        db.rollback()
    finally:
        db.close()

    return rows


def main():
    print("=" * 50)
    print("股票数据迁移到 PostgreSQL")
    print("=" * 50)

    # 1. 初始化股票池
    print("\n[1/3] 初始化股票池...")
    seed_stocks()

    # 2. 获取并导入K线数据
    print("\n[2/3] 获取K线数据...")
    total_rows = 0
    for sym, name, sector, market in DEFAULT_STOCKS:
        print(f"\n获取 {sym} {name} 的K线数据...")
        rows = sync_ohlc_to_pg(sym, market)
        total_rows += rows

    # 3. 验证
    print("\n[3/3] 验证数据...")
    db = SessionLocal()
    try:
        stock_count = db.query(Stock).count()
        kline_count = db.query(DailyKline).count()
        print(f"\n{'=' * 50}")
        print(f"迁移完成！")
        print(f"  - 股票数量: {stock_count}")
        print(f"  - K线记录: {kline_count}")
        print(f"{'=' * 50}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
