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
from datetime import datetime

from database import SessionLocal, Stock, DailyKline
from ingest.sync import (
    DEFAULT_STOCKS, fetch_realtime_quote, get_full_symbol,
    sync_ohlc_to_pg, seed_stocks,
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
    db = SessionLocal()
    try:
        stocks = db.query(Stock).order_by(Stock.symbol).all()
        result = [
            StockResponse(
                symbol=s.symbol,
                name=s.name,
                sector=s.sector,
                market=s.market,
                last_ohlc_fetch=s.last_ohlc_fetch,
            )
            for s in stocks
        ]
        if not result:
            result = [
                {"symbol": code, "name": name, "sector": sector, "market": market}
                for code, name, sector, market in DEFAULT_STOCKS
            ]
        return result
    finally:
        db.close()


@router.get("/search")
def search_stocks(q: str = Query(..., min_length=1)):
    """搜索股票（代码或名称）"""
    matches = [
        {"symbol": code, "name": name, "sector": sector, "market": market}
        for code, name, sector, market in DEFAULT_STOCKS
        if q.upper() in code.upper() or q in name
    ]
    return matches[:20]


@router.get("/{symbol}/ohlc")
def get_ohlc(symbol: str, days: int = Query(365, ge=30, le=2000)):
    """获取 K 线数据"""
    db = SessionLocal()
    try:
        klines = (
            db.query(DailyKline)
            .filter(DailyKline.code == symbol)
            .order_by(DailyKline.date.desc())
            .limit(days)
            .all()
        )

        if not klines:
            # 从新浪财经获取
            market = "sh" if symbol.startswith("6") or symbol.startswith("9") else "sz"
            from ingest.sync import fetch_ohlc
            df = fetch_ohlc(symbol, market, days)
            if df.empty:
                raise HTTPException(status_code=404, detail=f"无 {symbol} 的 K 线数据")
            return df.to_dict(orient="records")

        result = [
            {
                "date": k.date[:10] if hasattr(k.date, 'startswith') else str(k.date)[:10],
                "open": k.open,
                "high": k.high,
                "low": k.low,
                "close": k.close,
                "volume": k.volume,
                "amount": k.amount,
                "change_pct": k.change_pct,
            }
            for k in klines
        ]
        return result
    finally:
        db.close()


@router.get("/{symbol}/info")
def get_stock_info(symbol: str):
    """获取股票基本信息 + 实时行情"""
    db = SessionLocal()
    try:
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()

        if not stock:
            for code, name, sector, market in DEFAULT_STOCKS:
                if code == symbol:
                    info = {"symbol": code, "name": name, "sector": sector, "market": market}
                    break
            else:
                raise HTTPException(status_code=404, detail=f"股票 {symbol} 不在跟踪列表中")
        else:
            info = {
                "symbol": stock.symbol,
                "name": stock.name,
                "sector": stock.sector,
                "market": stock.market,
            }

        try:
            market = info.get("market", "sh")
            quote = fetch_realtime_quote(symbol, market)
            if quote:
                info.update(quote)
        except Exception:
            pass

        return info
    finally:
        db.close()


@router.get("/{symbol}/realtime")
def get_realtime_quote(symbol: str):
    """
    获取股票实时行情（新浪财经）
    Returns: {symbol, name, price, change, change_pct, volume, amount, high, low, open, prev_close}
    """
    market = "sh" if symbol.startswith(("6", "9")) else "sz"
    quote = fetch_realtime_quote(symbol, market)

    if quote:
        quote["symbol"] = symbol
        quote["market"] = market
        return quote

    # Fallback: try from database
    db = SessionLocal()
    try:
        kline = db.query(DailyKline).filter(
            DailyKline.code == symbol
        ).order_by(DailyKline.date.desc()).first()

        if kline:
            stock = db.query(Stock).filter(Stock.symbol == symbol).first()
            return {
                "symbol": symbol,
                "name": stock.name if stock else symbol,
                "market": market,
                "price": kline.close,
                "change": kline.change_pct,
                "change_pct": kline.change_pct,
                "prev_close": kline.close / (1 + kline.change_pct / 100) if kline.change_pct != 0 else kline.close,
                "open": kline.open,
                "high": kline.high,
                "low": kline.low,
                "volume": int(kline.volume),
                "amount": int(kline.amount) if kline.amount else 0,
                "source": "db",
            }
        raise HTTPException(status_code=404, detail=f"股票 {symbol} 实时行情获取失败")
    finally:
        db.close()


@router.post("/{symbol}/sync")
def sync_stock(symbol: str):
    """手动触发 K 线同步"""
    market = "sh" if symbol.startswith("6") or symbol.startswith("9") else "sz"

    # Ensure stock in DB
    db = SessionLocal()
    try:
        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            for code, n, sec, m in DEFAULT_STOCKS:
                if code == symbol:
                    stock = Stock(
                        symbol=code,
                        name=n,
                        sector=sec,
                        market=m,
                    )
                    db.add(stock)
                    break
            else:
                stock = Stock(
                    symbol=symbol,
                    name=symbol,
                    sector="",
                    market=market,
                )
                db.add(stock)
            db.commit()
    finally:
        db.close()

    try:
        rows = sync_ohlc_to_pg(symbol, market)
        return {"symbol": symbol, "rows_synced": rows, "status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-all")
def sync_all():
    """同步所有默认股票 K 线数据"""
    results = {"success": [], "failed": []}
    for sym, name, sector, market in DEFAULT_STOCKS:
        try:
            rows = sync_ohlc_to_pg(sym, market)
            results["success"].append({"symbol": sym, "name": name, "rows": rows})
        except Exception as e:
            results["failed"].append({"symbol": sym, "name": name, "error": str(e)})

    return results
