"""
GET /api/stocks                          — 股票列表
GET /api/stocks/{symbol}/ohlc            — K 线数据
GET /api/stocks/search?q=               — 搜索股票
POST /api/stocks/{symbol}/sync          — 手动同步 K 线
POST /api/stocks/sync-all              — 同步所有默认股票
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from database import get_conn
from ingest.sina_client import (
    sync_ohlc_to_db, fetch_ohlc, seed_default_stocks,
    DEFAULT_STOCKS, fetch_realtime_quote, fetch_realtime_batch,
    get_full_symbol,
)

router = APIRouter()


class StockResponse(BaseModel):
    symbol: str
    name: Optional[str] = None
    sector: Optional[str] = None
    market: Optional[str] = None
    last_ohlc_fetch: Optional[str] = None


@router.get("", response_model=list[StockResponse])
def list_stocks():
    """获取所有已跟踪的股票"""
    conn = get_conn()
    rows = conn.execute(
        """SELECT symbol, name, sector, market, last_ohlc_fetch
           FROM stocks ORDER BY symbol"""
    ).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    if not result:
        # 如果数据库为空，返回默认股票列表
        result = [
            {"symbol": code, "name": name, "sector": sector, "market": market}
            for code, name, sector, market in DEFAULT_STOCKS
        ]
    return result


@router.get("/search")
def search_stocks(q: str = Query(..., min_length=1)):
    """搜索股票（代码或名称）"""
    # 直接搜索 DEFAULT_STOCKS（避免 DB 查询延迟）
    matches = [
        {"symbol": code, "name": name, "sector": sector, "market": market}
        for code, name, sector, market in DEFAULT_STOCKS
        if q.upper() in code.upper() or q in name
    ]
    return matches[:20]


@router.get("/{symbol}/ohlc")
def get_ohlc(symbol: str, days: int = Query(365, ge=30, le=2000)):
    """获取 K 线数据"""
    conn = get_conn()
    rows = conn.execute(
        """SELECT date, open, high, low, close, volume, turnover,
                  change_pct, limit_up, limit_down, amplitude
           FROM ohlc WHERE symbol = ?
           ORDER BY date DESC LIMIT ?""",
        (symbol, days)
    ).fetchall()
    conn.close()

    if not rows:
        # 从新浪财经获取
        market = "sh" if symbol.startswith("6") else ("bj" if symbol.startswith("8") else "sz")
        df = fetch_ohlc(symbol, market, days)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"无 {symbol} 的 K 线数据")
        return df.to_dict(orient="records")

    result = [dict(r) for r in rows]
    for r in result:
        for k in ["open", "high", "low", "close", "volume", "turnover",
                  "change_pct", "amplitude"]:
            if k in r and r[k] is not None:
                r[k] = float(r[k])
        for k in ["limit_up", "limit_down"]:
            if k in r:
                r[k] = int(r[k] or 0)
    return result


@router.get("/{symbol}/info")
def get_stock_info(symbol: str):
    """获取股票基本信息 + 实时行情"""
    conn = get_conn()
    row = conn.execute(
        "SELECT symbol, name, sector, market FROM stocks WHERE symbol = ?",
        (symbol,)
    ).fetchone()
    conn.close()

    if not row:
        # 尝试从 DEFAULT_STOCKS 查找
        for code, name, sector, market in DEFAULT_STOCKS:
            if code == symbol:
                info = {"symbol": code, "name": name, "sector": sector, "market": market}
                break
        else:
            raise HTTPException(status_code=404, detail=f"股票 {symbol} 不在跟踪列表中")
    else:
        info = dict(row)

    try:
        market = info.get("market", "sh")
        quote = fetch_realtime_quote(symbol, market)
        if quote:
            info.update(quote)
    except Exception:
        pass

    return info


@router.post("/{symbol}/sync")
def sync_stock(symbol: str):
    """手动触发 K 线同步"""
    market = "sh" if symbol.startswith("6") else ("bj" if symbol.startswith("8") else "sz")
    # 确保股票在 DB 中
    conn = get_conn()
    conn.execute(
        """INSERT OR IGNORE INTO stocks (symbol, name, sector, market)
           SELECT ?, COALESCE((SELECT name FROM stocks WHERE symbol=?), ''), '', ?""",
        (symbol, symbol, market)
    )
    conn.commit()
    conn.close()
    try:
        rows = sync_ohlc_to_db(symbol, market)
        return {"symbol": symbol, "rows_synced": rows, "status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-all")
def sync_all():
    """同步所有默认股票 K 线数据（来自新浪财经）"""
    conn = get_conn()
    seed_default_stocks(conn)
    conn.close()

    results = {"success": [], "failed": []}
    for sym, name, sector, market in DEFAULT_STOCKS:
        try:
            rows = sync_ohlc_to_db(sym, market)
            results["success"].append({"symbol": sym, "name": name, "rows": rows})
        except Exception as e:
            results["failed"].append({"symbol": sym, "name": name, "error": str(e)})

    return results
