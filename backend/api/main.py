from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading

from database import init_db, SessionLocal, Stock
from api.routers import stocks, news, analysis, predict, screener, market
from ingest.sync import sync_ohlc_to_db, DEFAULT_STOCKS

app = FastAPI(title="Astock API", version="2.0.0",
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


def _sync_stock_bg(sym: str, market: str):
    """Background sync single stock OHLC (avoid blocking startup)."""
    try:
        sync_ohlc_to_db(sym, market)
    except Exception as e:
        print(f"[STARTUP] Background sync failed {sym}: {e}")


@app.on_event("startup")
def startup():
    # Initialize database
    init_db()

    # Ensure default stock pool is seeded
    db = SessionLocal()
    try:
        for sym, name, sector, mkt in DEFAULT_STOCKS:
            stock = db.query(Stock).filter(Stock.symbol == sym).first()
            if not stock:
                stock = Stock(
                    symbol=sym,
                    name=name,
                    sector=sector,
                    market=mkt,
                )
                db.add(stock)
        db.commit()
    finally:
        db.close()

    # Background pre-sync first 5 core stocks (avoid startup timeout)
    core_stocks = DEFAULT_STOCKS[:5]
    for sym, name, sector, mkt in core_stocks:
        t = threading.Thread(target=_sync_stock_bg, args=(sym, mkt), daemon=True)
        t.start()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Astock API", "version": "2.0.0"}


@app.get("/api")
def root():
    return {
        "name": "Astock API",
        "version": "2.0.0",
        "description": "A 股市场事件驱动分析与选股工具",
        "docs": "/docs",
    }
