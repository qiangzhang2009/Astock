from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from api.routers import stocks, news, analysis, predict, screener, market
from ingest.sync import seed_stocks
from ingest.scheduler import start_scheduler, stop_scheduler

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


@app.on_event("startup")
def startup():
    init_db()
    seed_stocks()
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
