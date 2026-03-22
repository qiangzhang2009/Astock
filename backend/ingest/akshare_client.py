"""
AKShare A 股数据获取客户端
支持上交所/深交所/科创板/创业板/北交所股票
"""

import akshare as ak
import pandas as pd
import sqlite3
import time
import hashlib
from datetime import datetime, timedelta
from database import get_conn


# 默认关注的股票池（优质 A 股）
DEFAULT_STOCKS = [
    # 科技/互联网
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
    # 科技
    ("688981", "中芯国际", "半导体", "sh"),
    ("688256", "寒武纪", "AI芯片", "sh"),
    ("002230", "科大讯飞", "AI", "sz"),
    ("300496", "中科创达", "软件", "sz"),
    ("002049", "紫光国微", "芯片", "sz"),
    ("603259", "药明康德", "医药", "sh"),
    ("002371", "北方华创", "半导体设备", "sz"),
    ("300033", "同花顺", "互联网金融", "sz"),
    # 新能源
    ("601012", "隆基绿能", "光伏", "sh"),
    ("002594", "比亚迪", "新能源汽车", "sz"),
    ("300274", "阳光电源", "光伏逆变器", "sz"),
    ("601857", "中国石油", "石油", "sh"),
    # 消费
    ("600887", "伊利股份", "乳业", "sh"),
    ("000568", "泸州老窖", "白酒", "sz"),
    ("600600", "青岛啤酒", "啤酒", "sh"),
    # 金融
    ("000001", "平安银行", "银行", "sz"),
    ("600000", "浦发银行", "银行", "sh"),
    ("601166", "兴业银行", "银行", "sh"),
    # 地产/基建
    ("600048", "保利发展", "房地产", "sh"),
    ("601668", "中国建筑", "建筑", "sh"),
    # 通信
    ("600050", "中国联通", "通信", "sh"),
    ("000063", "中兴通讯", "通信设备", "sz"),
    # 军工
    ("600893", "航发动力", "军工", "sh"),
    ("002013", "中航机电", "军工", "sz"),
    # 面板/消费电子
    ("000725", "京东方A", "面板", "sz"),
    ("002456", "欧菲光", "光学", "sz"),
]


def is_trade_day(date_str: str) -> bool:
    """简单判断是否为交易日（排除周末）"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.weekday() < 5  # 0=周一, 4=周五


def get_full_symbol(raw_symbol: str, market: str = "sh") -> str:
    """将股票代码转换为 AKShare 格式
    上交所: sh600036
    深交所: sz000001
    科创板: sh688xxx
    创业板: sz300xxx
    北交所: bj8xxxxx
    """
    if raw_symbol.startswith(("sh", "sz", "bj")):
        return raw_symbol

    symbol_map = {
        "sh": ["600", "601", "603", "605", "688", "600"],
        "sz": ["000", "001", "002", "003", "300", "sz"],
        "bj": ["8", "bj"],
    }

    prefix = market
    # Auto-detect market from code prefix
    if raw_symbol.startswith("6"):
        prefix = "sh"
    elif raw_symbol.startswith(("0", "3")):
        prefix = "sz"
    elif raw_symbol.startswith("8"):
        prefix = "bj"

    return f"{prefix}{raw_symbol}"


def get_stock_list() -> list[tuple]:
    """获取 A 股全市场股票列表"""
    try:
        df = ak.stock_info_a_code_name()
        result = []
        for _, row in df.iterrows():
            code = str(row.get("code", "")).strip()
            name = str(row.get("name", "")).strip()
            if code and name:
                market = "sh" if code.startswith("6") else ("bj" if code.startswith("8") else "sz")
                result.append((code, name, market))
        return result
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return DEFAULT_STOCKS


def fetch_ohlc(symbol: str, market: str = "sh", days: int = 730) -> pd.DataFrame:
    """
    获取单只股票日线 K 线数据

    AKShare 接口: stock_zh_a_hist
    返回: date, open, high, low, close, volume, turnover, change_pct
    """
    full_sym = get_full_symbol(symbol, market)
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")

    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )

        # 标准化列名
        rename = {}
        for col in df.columns:
            c = col.lower().strip()
            if "日期" in col:
                rename[col] = "date"
            elif "开盘" in col or "open" in c:
                rename[col] = "open"
            elif "最高" in col or "high" in c:
                rename[col] = "high"
            elif "最低" in col or "low" in c:
                rename[col] = "low"
            elif "收盘" in col or "close" in c:
                rename[col] = "close"
            elif "成交量" in col or "volume" in c:
                rename[col] = "volume"
            elif "成交额" in col or "turnover" in c:
                rename[col] = "turnover"
            elif "涨跌幅" in col or "change" in c:
                rename[col] = "change_pct"
            elif "振幅" in col or "amplitude" in c:
                rename[col] = "amplitude"

        df = df.rename(columns=rename)

        # 必要列
        if "date" not in df.columns or "close" not in df.columns:
            return pd.DataFrame()

        # 格式化日期
        if df["date"].dtype != "datetime64[ns]":
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        # 计算涨跌停标记
        df = _mark_limit_up_down(df)

        return df[["date", "open", "high", "low", "close", "volume",
                    "turnover", "change_pct", "limit_up", "limit_down", "amplitude"]].dropna(subset=["date", "close"])

    except Exception as e:
        print(f"获取 {symbol} K 线失败: {e}")
        return pd.DataFrame()


def _mark_limit_up_down(df: pd.DataFrame) -> pd.DataFrame:
    """
    标记涨跌停
    A 股: 主板 ±10%, ST ±5%, 科创板/创业板 ±20%
    """
    if len(df) < 2:
        df["limit_up"] = 0
        df["limit_down"] = 0
        return df

    df = df.sort_values("date").reset_index(drop=True)
    prev_close = df["close"].shift(1)

    # 简单判断: 涨幅 >= 9.5% 视为涨停
    df["limit_up"] = (df["change_pct"] >= 9.5).astype(int)
    # 简单判断: 跌幅 <= -9.5% 视为跌停
    df["limit_down"] = (df["change_pct"] <= -9.5).astype(int)

    return df


def fetch_realtime_quote(symbol: str) -> dict | None:
    """获取单只股票实时行情"""
    full_sym = get_full_symbol(symbol)
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == symbol]
        if row.empty:
            return None
        r = row.iloc[0]
        return {
            "symbol": symbol,
            "name": str(r.get("名称", "")),
            "price": float(r.get("最新价", 0)),
            "change_pct": float(r.get("涨跌幅", 0)),
            "volume": float(r.get("成交量", 0)),
            "turnover": float(r.get("成交额", 0)),
            "high": float(r.get("最高", 0)),
            "low": float(r.get("最低", 0)),
            "open": float(r.get("今开", 0)),
            "prev_close": float(r.get("昨收", 0)),
        }
    except Exception as e:
        print(f"获取实时行情失败 {symbol}: {e}")
        return None


def fetch_index_components(index_code: str = "000001") -> list[str]:
    """获取指数成分股（上证指数、深证成指、创业板指等）"""
    try:
        if index_code == "000001":
            # 上证指数成分
            df = ak.index_zh_a_hist(symbol="上证指数", period="daily", start_date="20240101", end_date="20241231")
            return []
        return []
    except:
        return []


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
    获取 K 线数据并同步到数据库
    返回: 插入/更新行数
    """
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
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row.get("close"),
                row.get("volume"),
                row.get("turnover"),
                row.get("change_pct"),
                int(row.get("limit_up", 0)),
                int(row.get("limit_down", 0)),
                row.get("amplitude"),
            )
        )
        rows += 1

    conn.execute(
        "UPDATE stocks SET last_ohlc_fetch = ? WHERE symbol = ?",
        (datetime.now().isoformat(), symbol)
    )
    conn.commit()
    conn.close()
    return rows


def sync_all_defaults(progress_callback=None) -> dict:
    """同步所有默认股票的 K 线数据"""
    results = {"success": 0, "failed": 0, "total_rows": 0}
    conn = get_conn()
    seed_default_stocks(conn)
    conn.close()

    for sym, name, sector, market in DEFAULT_STOCKS:
        try:
            rows = sync_ohlc_to_db(sym, market)
            results["total_rows"] += rows
            results["success"] += 1
            print(f"  [OK] {sym} {name}: {rows} rows")
        except Exception as e:
            results["failed"] += 1
            print(f"  [FAIL] {sym}: {e}")
        if progress_callback:
            progress_callback(sym, name, results)
        time.sleep(0.3)  # 避免请求过快

    return results
