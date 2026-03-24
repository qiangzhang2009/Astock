from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading

from database import init_db, SessionLocal, Stock
from api.routers import stocks, news, analysis, predict, screener, market
from ingest.sync import DEFAULT_STOCKS, seed_stocks, sync_ohlc_to_pg
from ingest.scheduler import start_scheduler, stop_scheduler, sync_stock_now
from ingest.news_scraper import bg_fetch_news

app = FastAPI(title="Astock API", version="2.0.1",
              description="A 股市场事件驱动分析与选股工具 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(predict.router, prefix="/api/predict", tags=["predict"])
app.include_router(screener.router, prefix="/api/screener", tags=["screener"])
app.include_router(market.router, prefix="/api/market", tags=["market"])


def _quick_sync(stocks_list: list, max_count: int = 50):
    """Pre-sync OHLC + news for top N stocks quickly."""
    print(f"[STARTUP] Quick sync for top {max_count} stocks...")
    for i, (sym, name, sector, market) in enumerate(stocks_list[:max_count]):
        try:
            sync_ohlc_to_pg(sym, market)
        except Exception as e:
            print(f"[STARTUP] OHLC {sym}: {e}")
        try:
            bg_fetch_news(sym, market)
        except Exception as e:
            print(f"[STARTUP] News {sym}: {e}")
        # Fast: minimal sleep
        if i % 10 == 9:
            time.sleep(0.5)
        if i % 20 == 19:
            print(f"[STARTUP] Quick sync progress: {i+1}/{min(max_count, len(stocks_list))}")
    print(f"[STARTUP] Quick sync complete!")


@app.on_event("startup")
def startup():
    import time
    # Initialize database schema
    init_db()
    # Seed ALL stocks
    seed_stocks()

    # Quick pre-sync: top 50 core stocks (runs before accepting requests)
    # This ensures most important stocks have data immediately
    top_stocks = DEFAULT_STOCKS[:50]
    _quick_sync(top_stocks, max_count=50)

    # Start background scheduler for continuous sync of remaining stocks
    start_scheduler()


@app.on_event("shutdown")
def shutdown():
    stop_scheduler()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Astock API", "version": "2.0.1"}


@app.get("/api")
def root():
    return {
        "name": "Astock API",
        "version": "2.0.1",
        "description": "A 股市场事件驱动分析与选股工具",
        "docs": "/docs",
    }


@app.post("/api/sync/{symbol}")
def trigger_sync(symbol: str, market: str = ""):
    """手动触发单只股票的 OHLC + 新闻同步"""
    market = market or ("sh" if symbol.startswith(("6", "9")) else "sz")
    sync_stock_now(symbol, market)
    return {"status": "ok", "symbol": symbol, "message": "同步已触发"}
