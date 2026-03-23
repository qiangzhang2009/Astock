"""
GET /api/market/indices          — 大盘指数（上证、深证、创业板、科创板）
GET /api/market/boards           — 行业板块涨跌
GET /api/market/limit-up        — 涨停股池
GET /api/market/limit-down      — 跌停股池
GET /api/market/realtime        — 全市场实时行情（东方财富）
"""
from fastapi import APIRouter, HTTPException, Query
import httpx
import json
import re
from typing import Optional
from datetime import datetime

from database import get_conn

router = APIRouter()

# 常用指数列表
MAJOR_INDICES = [
    ("sh000001", "上证指数"),
    ("sz399001", "深证成指"),
    ("sz399006", "创业板指"),
    ("sh000688", "科创50"),
    ("sh000300", "沪深300"),
    ("sh000016", "上证50"),
    ("sz399905", "中证500"),
    ("sh000905", "中证500"),
    ("sz399673", "创业板50"),
]

EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
}


def _em_fetch(url: str, timeout: int = 10):
    """Fetch JSON from East Money."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, trust_env=True) as client:
            r = client.get(url, headers=EM_HEADERS)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[EM] Fetch error: {e}")
        return None


@router.get("/indices")
def get_indices():
    """获取大盘指数实时行情"""
    codes = ",".join(c for c, _ in MAJOR_INDICES)
    url = f"http://hq.sinajs.cn/list={codes}"
    try:
        with httpx.Client(timeout=10, follow_redirects=True, trust_env=True) as client:
            resp = client.get(
                url,
                headers={
                    "Referer": "https://finance.sina.com.cn/",
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Charset": "GBK,utf-8;q=0.7,*;q=0.3",
                }
            )
            raw = resp.content.decode("gbk", errors="replace")
    except Exception as e:
        print(f"[SINA] Indices fetch error: {e}")
        return [{"symbol": c, "name": n, "error": str(e)} for c, n in MAJOR_INDICES]

    results = []
    for m in re.finditer(r'hq_str_(\w+)="([^"]+)"', raw):
        code = m.group(1)
        name = MAJOR_INDICES[[c for c, _ in MAJOR_INDICES].index(code)][1] if code in [c for c, _ in MAJOR_INDICES] else code
        fields = m.group(2).split(",")
        try:
            price = float(fields[3]) if fields[3] else 0
            prev_close = float(fields[2]) if fields[2] else 0
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0
            high = float(fields[4]) if len(fields) > 4 and fields[4] else 0
            low = float(fields[5]) if len(fields) > 5 and fields[5] else 0
            volume = float(fields[8]) if len(fields) > 8 and fields[8] else 0
            turnover = float(fields[9]) if len(fields) > 9 and fields[9] else 0

            results.append({
                "symbol": code,
                "name": name,
                "price": round(price, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "volume": int(volume),
                "turnover": int(turnover),
                "prev_close": round(prev_close, 2),
                "direction": "up" if change > 0 else ("down" if change < 0 else "flat"),
            })
        except (IndexError, ValueError):
            results.append({"symbol": code, "name": name, "error": "parse_error"})

    return results


@router.get("/boards")
def get_sector_boards(limit: int = Query(30, ge=1, le=100)):
    """
    获取行业板块涨跌榜（东方财富）
    """
    # 东方财富板块行情 API
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?cb=&pn=1&pz=50&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        "&fltt=2&invt=2&fid=f3&fs=m:90+t:2&fields=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152"
    )
    data = _em_fetch(url)
    if not data:
        # Fallback: use screener data
        return _get_boards_from_screener(limit)

    items = data.get("data", {}).get("diff", []) or data.get("data", {}).get("list", []) or []
    results = []
    for item in items:
        try:
            code = str(item.get("f12", ""))
            name = item.get("f14", "")
            change_pct = item.get("f3", 0)
            volume = item.get("f5", 0) or 0
            amount = item.get("f6", 0) or 0
            lead = item.get("f62", 0) or 0  # 主力净流入

            results.append({
                "symbol": code,
                "name": name,
                "change_pct": change_pct,
                "volume": int(volume),
                "amount": int(amount),
                "lead_flow": int(lead),
                "direction": "up" if change_pct > 0 else ("down" if change_pct < 0 else "flat"),
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["change_pct"], reverse=True)
    return results[:limit]


@router.get("/limit-up")
def get_limit_up_pool(limit: int = Query(30, ge=1, le=100)):
    """
    获取涨停股池（东方财富）
    """
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?cb=&pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        "&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23,m:0+t:80+s:2048"
        "&fields=f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152"
    )
    data = _em_fetch(url)
    if not data:
        return _get_limit_from_screener(limit, limit_up=True)

    items = data.get("data", {}).get("diff", []) or data.get("data", {}).get("list", []) or []
    results = []
    for item in items:
        try:
            change_pct = item.get("f3", 0)
            if change_pct < 9.0:  # Filter for real limit-up (>=9.5 but allow some tolerance)
                continue
            results.append({
                "symbol": str(item.get("f12", "")),
                "name": item.get("f14", ""),
                "price": item.get("f2", 0),
                "change_pct": change_pct,
                "volume": int(item.get("f5", 0) or 0),
                "turnover": int(item.get("f6", 0) or 0),
                "amplitude": item.get("f7", 0),
                "high": item.get("f15", 0),
                "low": item.get("f16", 0),
                "prev_close": item.get("f18", 0),
                "reason": item.get("f8", ""),
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["change_pct"], reverse=True)
    return results[:limit]


@router.get("/limit-down")
def get_limit_down_pool(limit: int = Query(30, ge=1, le=100)):
    """获取跌停股池"""
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?cb=&pn=1&pz=100&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281"
        "&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23,m:0+t:80+s:2048"
        "&fields=f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152"
    )
    data = _em_fetch(url)
    if not data:
        return _get_limit_from_screener(limit, limit_up=False)

    items = data.get("data", {}).get("diff", []) or data.get("data", {}).get("list", []) or []
    results = []
    for item in items:
        try:
            change_pct = item.get("f3", 0)
            if change_pct > -9.0:  # Filter for real limit-down
                continue
            results.append({
                "symbol": str(item.get("f12", "")),
                "name": item.get("f14", ""),
                "price": item.get("f2", 0),
                "change_pct": change_pct,
                "volume": int(item.get("f5", 0) or 0),
                "turnover": int(item.get("f6", 0) or 0),
                "amplitude": item.get("f7", 0),
                "high": item.get("f15", 0),
                "low": item.get("f16", 0),
                "prev_close": item.get("f18", 0),
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["change_pct"])
    return results[:limit]


@router.get("/realtime")
def get_realtime_stocks(
    market: str = Query("all", description="sh/sz/all"),
    sort_by: str = Query("change_pct", description="change_pct/volume/turnover"),
    sort_order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
):
    """
    获取全市场实时行情（东方财富）
    """
    fs_map = {
        "sh": "m:1+t:2,m:1+t:23",
        "sz": "m:0+t:6,m:0+t:13",
        "all": "m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23,m:0+t:80+s:2048",
    }
    fid_map = {
        "change_pct": "f3",
        "volume": "f5",
        "turnover": "f6",
        "price": "f2",
    }
    fid = fid_map.get(sort_by, "f3")
    po = "1" if sort_order == "desc" else "0"
    fs = fs_map.get(market, fs_map["all"])

    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        f"?pn=1&pz={limit}&po={po}&np=1&fltt=2&invt=2&fid={fid}"
        f"&fs={fs}"
        "&fields=f2,f3,f4,f5,f6,f7,f8,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152"
    )
    data = _em_fetch(url)
    if not data:
        return {"count": 0, "results": [], "error": "Failed to fetch data"}

    items = data.get("data", {}).get("diff", []) or data.get("data", {}).get("list", []) or []
    results = []
    for item in items:
        try:
            change_pct = item.get("f3", 0)
            price = item.get("f2", 0)
            if min_price and price < min_price:
                continue
            if max_price and price > max_price:
                continue
            symbol = str(item.get("f12", ""))
            market_prefix = "sh" if symbol.startswith(("6", "9")) else "sz"
            results.append({
                "symbol": symbol,
                "name": item.get("f14", ""),
                "price": price,
                "change_pct": change_pct,
                "high": item.get("f15", 0),
                "low": item.get("f16", 0),
                "open": item.get("f17", 0),
                "prev_close": item.get("f18", 0),
                "volume": int(item.get("f5", 0) or 0),
                "turnover": int(item.get("f6", 0) or 0),
                "amplitude": item.get("f7", 0),
                "market": market_prefix,
                "sector": item.get("f100", ""),
            })
        except Exception:
            continue

    return {"count": len(results), "results": results}


@router.get("/hot")
def get_hot_stocks(limit: int = Query(20, ge=1, le=50)):
    """
    获取市场热点板块和个股（东方财富资金流入榜）
    """
    # 东方财富资金流入排行
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?pn=1&pz=50&po=1&np=1&fltt=2&invt=2&fid=f62"
        "&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23,m:0+t:80+s:2048"
        "&fields=f2,f3,f4,f5,f6,f7,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f62,f115,f128,f136"
    )
    data = _em_fetch(url)
    if not data:
        return []

    items = data.get("data", {}).get("diff", []) or data.get("data", {}).get("list", []) or []
    results = []
    for item in items:
        try:
            lead_flow = item.get("f62", 0) or 0
            if lead_flow <= 0:
                continue
            results.append({
                "symbol": str(item.get("f12", "")),
                "name": item.get("f14", ""),
                "price": item.get("f2", 0),
                "change_pct": item.get("f3", 0),
                "volume": int(item.get("f5", 0) or 0),
                "lead_flow": int(lead_flow),  # 主力净流入（元）
                "lead_flow_pct": item.get("f185", 0),  # 主力净流入占比
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["lead_flow"], reverse=True)
    return results[:limit]


# ─── Fallback helpers ─────────────────────────────────────────────────────────
def _get_boards_from_screener(limit: int):
    """Fallback: build board stats from local DB."""
    conn = get_conn()
    try:
        rows = conn.execute("""
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
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _get_limit_from_screener(limit: int, limit_up: bool = True):
    """Fallback: get limit stocks from local DB."""
    conn = get_conn()
    try:
        col = "limit_up" if limit_up else "limit_down"
        rows = conn.execute(f"""
            SELECT o.code AS symbol, s.name, o.close, o.change_pct, o.volume,
                   o.turnover, o.amplitude
            FROM daily_kline o
            LEFT JOIN stocks s ON o.code = s.symbol
            WHERE o.date = (SELECT MAX(date) FROM daily_kline)
              AND o.{col} = 1
            ORDER BY o.volume DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


@router.get("/board/{board_code}")
def get_board_stocks(
    board_code: str,
    sort_by: str = Query("change_pct", description="change_pct/volume/turnover"),
    sort_order: str = Query("desc"),
    limit: int = Query(30, ge=1, le=100),
):
    """
    获取指定板块内的个股行情（东方财富板块详情）
    board_code: 东方财富板块代码（如 f12 字段值）
    """
    url = (
        f"https://push2.eastmoney.com/api/qt/clist/get"
        f"?pn=1&pz={limit}&po=1&np=1&fltt=2&invt=2&fid=f3"
        f"&fs=b:{board_code}+f:!50&fields=f2,f3,f4,f5,f6,f7,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f62"
    )
    data = _em_fetch(url)
    if not data:
        return {"count": 0, "results": [], "error": "Failed to fetch board data"}

    items = data.get("data", {}).get("diff", []) or data.get("data", {}).get("list", []) or []
    results = []
    for item in items:
        try:
            symbol = str(item.get("f12", ""))
            market_prefix = "sh" if symbol.startswith(("6", "9")) else "sz"
            results.append({
                "symbol": symbol,
                "name": item.get("f14", ""),
                "price": item.get("f2", 0),
                "change_pct": item.get("f3", 0),
                "high": item.get("f15", 0),
                "low": item.get("f16", 0),
                "open": item.get("f17", 0),
                "prev_close": item.get("f18", 0),
                "volume": int(item.get("f5", 0) or 0),
                "turnover": int(item.get("f6", 0) or 0),
                "amplitude": item.get("f7", 0),
                "market": market_prefix,
                "lead_flow": int(item.get("f62", 0) or 0),
            })
        except Exception:
            continue

    return {"count": len(results), "results": results}


@router.get("/summary")
def get_market_summary():
    """
    获取市场综合概览（涨跌家数、涨停数、北向资金等）
    """
    # 东方财富大盘概况 API
    summary_url = "https://push2.eastmoney.com/api/qt/stock/get?secid=1.000001,0.399001,0.399006,1.000688&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f170"
    data = _em_fetch(summary_url)
    summary = {
        "up_count": 0,
        "down_count": 0,
        "limit_up_count": 0,
        "limit_down_count": 0,
        "total_volume": 0,
        "total_turnover": 0,
        "board_count": 0,
        "advancing_boards": 0,
        "declining_boards": 0,
    }

    if data:
        try:
            diff = data.get("data", {}).get("diff", [])
            if not isinstance(diff, list):
                diff = [data.get("data", {})]
            for item in diff:
                if item.get("f43"):  # price
                    prev = item.get("f60", 0) or 0
                    cur = item.get("f43", 0) or 0
                    if prev and cur:
                        pct = (cur - prev) / prev * 100
                        if pct > 0: summary["advancing_boards"] += 1
                        else: summary["declining_boards"] += 1
        except Exception:
            pass

    # 涨跌家数
    count_url = "https://push2.eastmoney.com/api/qt/stock/get?secid=1.000001&fields=f136,f137"
    cnt_data = _em_fetch(count_url)
    if cnt_data:
        try:
            d = cnt_data.get("data", {})
            summary["up_count"] = d.get("f136", 0) or 0
            summary["down_count"] = d.get("f137", 0) or 0
        except Exception:
            pass

    # 涨停跌停数（东方财富统计）
    lu_data = _em_fetch(
        "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=1&po=1&np=1&fltt=2&invt=2&fid=f3"
        "&fs=m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23&fields=f2,f3"
    )
    if lu_data:
        try:
            items = lu_data.get("data", {}).get("diff", []) or []
            limit_up = sum(1 for i in items if (i.get("f3", 0) or 0) >= 9.0)
            limit_down = sum(1 for i in items if (i.get("f3", 0) or 0) <= -9.0)
            summary["limit_up_count"] = limit_up
            summary["limit_down_count"] = limit_down
        except Exception:
            pass

    return summary


@router.get("/sparkline/{symbol}")
def get_sparkline(symbol: str):
    """
    获取个股迷你K线（最近30天，简洁数据）
    用于市场概览中的迷你图
    """
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT date, close, change_pct
            FROM daily_kline
            WHERE code = ?
            ORDER BY date DESC
            LIMIT 30
        """, (symbol,)).fetchall()
        conn.close()
        if not rows:
            return {"symbol": symbol, "data": []}
        return {
            "symbol": symbol,
            "data": [{"date": r["date"], "close": r["close"], "change_pct": r["change_pct"]} for r in reversed(rows)]
        }
    except Exception:
        conn.close()
        return {"symbol": symbol, "data": []}
