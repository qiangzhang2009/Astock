"""
Database module — unified SQLite for Astock
Supports both SQLAlchemy ORM and raw sqlite3 (for complex queries)
"""
import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import Generator

from sqlalchemy import create_engine, Column, String, Integer, Float, Date, DateTime, Boolean, Text, Index
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

# ─── Path resolution ────────────────────────────────────────────────────────
_backend_dir = Path(__file__).parent
_project_root = _backend_dir.parent
_DB_PATH = os.environ.get("DATABASE_PATH", str(_project_root / "astock.db"))

os.makedirs(os.path.dirname(_DB_PATH) if os.path.dirname(_DB_PATH) else ".", exist_ok=True)

# ─── SQLAlchemy engine & session ────────────────────────────────────────────
engine = create_engine(
    f"sqlite:///{_DB_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─── SQLAlchemy ORM models ──────────────────────────────────────────────────
class Stock(Base):
    __tablename__ = "stocks"

    symbol = Column(String(10), primary_key=True)
    name = Column(String(100))
    sector = Column(String(50))
    market = Column(String(10))
    last_ohlc_fetch = Column(String(20))
    last_news_fetch = Column(String(20))


class DailyKline(Base):
    __tablename__ = "daily_kline"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # ISO format YYYY-MM-DD
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    change_pct = Column(Float)
    turnover = Column(Float)
    limit_up = Column(Integer, default=0)
    limit_down = Column(Integer, default=0)
    amplitude = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class NewsRaw(Base):
    __tablename__ = "news_raw"

    id = Column(String(64), primary_key=True)
    title = Column(Text)
    content = Column(Text)
    source = Column(String(64))
    url = Column(String(512))
    published_at = Column(String(32))
    created_at = Column(DateTime, default=datetime.utcnow)


class Layer1Result(Base):
    __tablename__ = "layer1_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    news_id = Column(String(64), index=True)
    symbol = Column(String(10), index=True)
    sentiment = Column(String(16))
    sentiment_cn = Column(String(16))
    relevance = Column(String(16))
    key_discussion = Column(Text)
    reason_growth = Column(Text)
    reason_decrease = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_layer1_symbol_news", "symbol", "news_id", unique=True),
    )


class NewsAligned(Base):
    __tablename__ = "news_aligned"

    id = Column(Integer, primary_key=True, autoincrement=True)
    news_id = Column(String(64), index=True)
    symbol = Column(String(10), index=True)
    trade_date = Column(String(10), index=True)
    ret_t0 = Column(Float)
    ret_t1 = Column(Float)
    ret_t3 = Column(Float)
    ret_t5 = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_aligned_symbol_date", "symbol", "trade_date"),
        Index("ix_aligned_symbol_news", "symbol", "news_id", unique=True),
    )


# ─── Raw sqlite3 connection ────────────────────────────────────────────────
def get_conn() -> sqlite3.Connection:
    """Returns a raw sqlite3 connection for complex queries."""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_db() -> Generator:
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Schema initialization ──────────────────────────────────────────────────
_SCHEMA_SQL = """
-- Stocks master table
CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    market TEXT,
    last_ohlc_fetch TEXT,
    last_news_fetch TEXT
);

-- Daily OHLC data
CREATE TABLE IF NOT EXISTS daily_kline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL, amount REAL, change_pct REAL,
    turnover REAL, limit_up INTEGER DEFAULT 0,
    limit_down INTEGER DEFAULT 0, amplitude REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(code, date)
);
CREATE INDEX IF NOT EXISTS ix_kline_code ON daily_kline(code);
CREATE INDEX IF NOT EXISTS ix_kline_date ON daily_kline(date);
CREATE INDEX IF NOT EXISTS ix_kline_code_date ON daily_kline(code, date);

-- Raw news
CREATE TABLE IF NOT EXISTS news_raw (
    id TEXT PRIMARY KEY,
    title TEXT,
    content TEXT,
    source TEXT,
    url TEXT,
    published_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Layer1 sentiment analysis results
CREATE TABLE IF NOT EXISTS layer1_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id TEXT,
    symbol TEXT,
    sentiment TEXT,
    sentiment_cn TEXT,
    relevance TEXT,
    key_discussion TEXT,
    reason_growth TEXT,
    reason_decrease TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, news_id)
);
CREATE INDEX IF NOT EXISTS ix_l1_news ON layer1_results(news_id);
CREATE INDEX IF NOT EXISTS ix_l1_symbol ON layer1_results(symbol);

-- News aligned to trading dates
CREATE TABLE IF NOT EXISTS news_aligned (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id TEXT,
    symbol TEXT,
    trade_date TEXT,
    ret_t0 REAL, ret_t1 REAL, ret_t3 REAL, ret_t5 REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, news_id)
);
CREATE INDEX IF NOT EXISTS ix_na_symbol_date ON news_aligned(symbol, trade_date);
CREATE INDEX IF NOT EXISTS ix_na_news ON news_aligned(news_id);
"""


def init_db():
    """Initialize all database tables and schema."""
    # Ensure directory exists
    db_dir = os.path.dirname(_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # Run schema SQL
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()

    # Also ensure SQLAlchemy tables are registered
    Base.metadata.create_all(bind=engine)
    print(f"[DB] Initialized at: {_DB_PATH}")


if __name__ == "__main__":
    init_db()
