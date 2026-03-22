"""
POST /api/screener  — 选股筛选
GET  /api/screener/boards — 板块行情
GET  /api/screener/limit-up — 涨停股池
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from backend.database import get_conn

router = APIRouter()


class ScreenerRequest(BaseModel):
    sectors: list[str] = []
    min_change_pct: Optional[float] = None
    max_change_pct: Optional[float] = None
    min_volume: Optional[float] = None
    limit_up_only: bool = False
    limit_down_only: bool = False
    sort_by: str = "volume"
    sort_order: str = "desc"
    limit: int = Query(20, ge=1, le=100)


@router.post("")
def screener(req: ScreenerRequest):
    """
    选股器：按行业、涨跌幅、成交量等筛选股票
    """
    conn = get_conn()

    query = """
        SELECT o.symbol, s.name, s.sector, s.market,
               o.date, o.close, o.change_pct, o.volume,
               o.turnover, o.limit_up, o.limit_down, o.amplitude,
               o.high, o.low, o.open
        FROM ohlc o
        JOIN stocks s ON o.symbol = s.symbol
        WHERE o.date = (SELECT MAX(date) FROM ohlc WHERE symbol = o.symbol)
    """
    params = []

    if req.sectors:
        placeholders = ",".join(["?"] * len(req.sectors))
        query += f" AND s.sector IN ({placeholders})"
        params.extend(req.sectors)

    if req.min_change_pct is not None:
        query += " AND o.change_pct >= ?"
        params.append(req.min_change_pct)

    if req.max_change_pct is not None:
        query += " AND o.change_pct <= ?"
        params.append(req.max_change_pct)

    if req.min_volume is not None:
        query += " AND o.volume >= ?"
        params.append(req.min_volume)

    if req.limit_up_only:
        query += " AND o.limit_up = 1"
    if req.limit_down_only:
        query += " AND o.limit_down = 1"

    # 排序
    sort_col = {
        "volume": "o.volume",
        "change_pct": "o.change_pct",
        "turnover": "o.turnover",
        "amplitude": "o.amplitude",
    }.get(req.sort_by, "o.volume")
    sort_dir = "DESC" if req.sort_order == "desc" else "ASC"
    query += f" ORDER BY {sort_col} {sort_dir}"

    query += " LIMIT ?"
    params.append(req.limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        for k in ["close", "change_pct", "volume", "turnover", "amplitude", "high", "low", "open"]:
            if k in d and d[k] is not None:
                d[k] = float(d[k])
        d["limit_up"] = int(d.get("limit_up") or 0)
        d["limit_down"] = int(d.get("limit_down") or 0)
        result.append(d)

    return {
        "count": len(result),
        "filters": {
            "sectors": req.sectors,
            "min_change_pct": req.min_change_pct,
            "max_change_pct": req.max_change_pct,
            "limit_up_only": req.limit_up_only,
            "limit_down_only": req.limit_down_only,
        },
        "results": result,
    }


@router.get("/boards")
def sector_boards():
    """获取行业板块行情（按涨跌幅排序）"""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT s.sector,
               COUNT(*) AS stock_count,
               AVG(o.change_pct) AS avg_change,
               SUM(o.volume) AS total_volume
        FROM stocks s
        JOIN ohlc o ON s.symbol = o.symbol
        WHERE o.date = (SELECT MAX(date) FROM ohlc)
          AND s.sector IS NOT NULL AND s.sector != ''
        GROUP BY s.sector
        HAVING stock_count >= 1
        ORDER BY avg_change DESC
        LIMIT 30
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/limit-up")
def limit_up_pool(limit: int = Query(30, ge=1, le=100)):
    """获取涨停股池"""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT o.symbol, s.name, s.sector, o.close, o.change_pct, o.volume,
               o.turnover, o.amplitude
        FROM ohlc o
        JOIN stocks s ON o.symbol = s.symbol
        WHERE o.date = (SELECT MAX(date) FROM ohlc)
          AND o.limit_up = 1
        ORDER BY o.volume DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/limit-down")
def limit_down_pool(limit: int = Query(30, ge=1, le=100)):
    """获取跌停股池"""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT o.symbol, s.name, s.sector, o.close, o.change_pct, o.volume,
               o.turnover, o.amplitude
        FROM ohlc o
        JOIN stocks s ON o.symbol = s.symbol
        WHERE o.date = (SELECT MAX(date) FROM ohlc)
          AND o.limit_down = 1
        ORDER BY o.volume DESC
        LIMIT ?
        """,
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
