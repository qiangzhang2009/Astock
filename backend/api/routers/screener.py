"""
POST /api/screener  — 选股筛选
GET  /api/screener/boards — 板块行情
GET  /api/screener/limit-up — 涨停股池
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import httpx
from database import get_conn

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
    market: Optional[str] = None  # sh/sz/all


@router.post("")
def screener(req: ScreenerRequest):
    """
    选股器：按行业、涨跌幅、成交量等筛选股票
    Uses local DB (ohlc table) when available, falls back to East Money realtime API
    """
    conn = get_conn()
    try:
        # Build query
        query = """
            SELECT o.code AS symbol, s.name, s.sector, s.market,
                   o.date, o.close, o.change_pct, o.volume,
                   o.turnover, o.limit_up, o.limit_down, o.amplitude,
                   o.high, o.low, o.open
            FROM daily_kline o
            LEFT JOIN stocks s ON o.code = s.symbol
            WHERE o.date = (SELECT MAX(date) FROM daily_kline WHERE code = o.code)
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

        # Sort
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

        if not result:
            return _screener_from_em(req)

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
    except Exception:
        conn.close()
        return _screener_from_em(req)


@router.get("/boards")
def sector_boards():
    """获取行业板块行情（按涨跌幅排序）"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT s.sector,
                   COUNT(*) AS stock_count,
                   AVG(o.change_pct) AS avg_change,
                   SUM(o.volume) AS total_volume
            FROM stocks s
            JOIN daily_kline o ON s.symbol = o.code
            WHERE o.date = (SELECT MAX(date) FROM daily_kline)
              AND s.sector IS NOT NULL AND s.sector != ''
            GROUP BY s.sector
            HAVING stock_count >= 1
            ORDER BY avg_change DESC
            LIMIT 30
            """
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        conn.close()
        return []


@router.get("/limit-up")
def limit_up_pool(limit: int = Query(30, ge=1, le=100)):
    """获取涨停股池"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT o.code AS symbol, s.name, s.sector, o.close, o.change_pct, o.volume,
                   o.turnover, o.amplitude
            FROM daily_kline o
            LEFT JOIN stocks s ON o.code = s.symbol
            WHERE o.date = (SELECT MAX(date) FROM daily_kline)
              AND o.limit_up = 1
            ORDER BY o.volume DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        conn.close()
        return []


@router.get("/limit-down")
def limit_down_pool(limit: int = Query(30, ge=1, le=100)):
    """获取跌停股池"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT o.code AS symbol, s.name, s.sector, o.close, o.change_pct, o.volume,
                   o.turnover, o.amplitude
            FROM daily_kline o
            LEFT JOIN stocks s ON o.code = s.symbol
            WHERE o.date = (SELECT MAX(date) FROM daily_kline)
              AND o.limit_down = 1
            ORDER BY o.volume DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        conn.close()
        return []


# ─── Fallback: Screener from East Money ──────────────────────────────────────
EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.eastmoney.com/",
}


def _em_fetch(url: str, timeout: int = 10):
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=True) as client:
            r = client.get(url, headers=EM_HEADERS)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[EM] Screener fetch error: {e}")
        return None


def _screener_from_em(req: ScreenerRequest):
    """Fallback screener using East Money realtime API."""
    fid_map = {
        "volume": "f5",
        "change_pct": "f3",
        "turnover": "f6",
        "amplitude": "f7",
    }
    fid = fid_map.get(req.sort_by, "f5")
    po = "1" if req.sort_order == "desc" else "0"
    fs = "m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23,m:0+t:80+s:2048"

    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        f"?pn=1&pz={req.limit}&po={po}&np=1&fltt=2&invt=2&fid={fid}"
        f"&fs={fs}"
        "&fields=f2,f3,f4,f5,f6,f7,f8,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62"
    )
    data = _em_fetch(url)
    if not data:
        return {"count": 0, "results": [], "error": "Failed to fetch from East Money"}

    items = data.get("data", {}).get("diff", []) or data.get("data", {}).get("list", []) or []
    results = []
    for item in items:
        try:
            change_pct = item.get("f3", 0)
            if req.min_change_pct is not None and change_pct < req.min_change_pct:
                continue
            if req.max_change_pct is not None and change_pct > req.max_change_pct:
                continue
            symbol = str(item.get("f12", ""))
            market_prefix = "sh" if symbol.startswith(("6", "9")) else "sz"
            results.append({
                "symbol": symbol,
                "name": item.get("f14", ""),
                "market": market_prefix,
                "price": item.get("f2", 0),
                "change_pct": change_pct,
                "high": item.get("f15", 0),
                "low": item.get("f16", 0),
                "open": item.get("f17", 0),
                "prev_close": item.get("f18", 0),
                "volume": int(item.get("f5", 0) or 0),
                "turnover": int(item.get("f6", 0) or 0),
                "amplitude": item.get("f7", 0),
            })
        except Exception:
            continue

    return {
        "count": len(results),
        "filters": {
            "sectors": req.sectors,
            "min_change_pct": req.min_change_pct,
            "max_change_pct": req.max_change_pct,
            "limit_up_only": req.limit_up_only,
            "limit_down_only": req.limit_down_only,
        },
        "results": results,
    }
