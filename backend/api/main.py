from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import threading

from database import init_db, get_conn
from api.routers import stocks, news, analysis, predict, screener
from ingest.sina_client import DEFAULT_STOCKS

app = FastAPI(title="Astock API", version="1.0.0",
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


def _sync_stock_bg(sym: str, market: str):
    """后台同步单只股票 K 线（避免阻塞启动）"""
    try:
        from ingest.sina_client import sync_ohlc_to_db
        sync_ohlc_to_db(sym, market)
    except Exception as e:
        print(f"后台同步失败 {sym}: {e}")


@app.on_event("startup")
def startup():
    init_db()
    # 确保默认股票列表已初始化
    conn = get_conn()
    for sym, name, sector, market in DEFAULT_STOCKS:
        conn.execute(
            """INSERT OR IGNORE INTO stocks (symbol, name, sector, market)
               VALUES (?, ?, ?, ?)""",
            (sym, name, sector, market)
        )
    conn.commit()
    conn.close()
    # 后台预同步前 5 只核心股票（避免启动超时）
    core_stocks = DEFAULT_STOCKS[:5]
    for sym, name, sector, market in core_stocks:
        t = threading.Thread(target=_sync_stock_bg, args=(sym, market), daemon=True)
        t.start()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Astock API", "version": "1.0.0"}


@app.get("/api")
def root():
    return {
        "name": "Astock API",
        "version": "1.0.0",
        "description": "A 股市场事件驱动分析与选股工具",
        "docs": "/docs",
    }
