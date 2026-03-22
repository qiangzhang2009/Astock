import sqlite3
from config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
    symbol        TEXT PRIMARY KEY,
    name          TEXT,
    sector        TEXT,
    market        TEXT,
    last_ohlc_fetch   TEXT,
    last_news_fetch   TEXT
);

CREATE TABLE IF NOT EXISTS ohlc (
    symbol        TEXT NOT NULL,
    date          TEXT NOT NULL,
    open          REAL,
    high          REAL,
    low           REAL,
    close         REAL,
    volume        REAL,
    turnover      REAL,
    change_pct    REAL,
    limit_up      INTEGER DEFAULT 0,
    limit_down    INTEGER DEFAULT 0,
    amplitude     REAL,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_date ON ohlc(symbol, date DESC);

CREATE TABLE IF NOT EXISTS news_raw (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    content       TEXT,
    source        TEXT,
    published_at  TEXT,
    url           TEXT
);

CREATE TABLE IF NOT EXISTS news_ticker (
    news_id       TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    PRIMARY KEY (news_id, symbol)
);

CREATE TABLE IF NOT EXISTS layer0_results (
    news_id       TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    passed        INTEGER NOT NULL,
    reason        TEXT,
    PRIMARY KEY (news_id, symbol)
);

CREATE TABLE IF NOT EXISTS layer1_results (
    news_id       TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    relevance     TEXT,
    key_discussion TEXT,
    sentiment     TEXT,
    sentiment_cn  TEXT,
    reason_growth TEXT,
    reason_decrease TEXT,
    PRIMARY KEY (news_id, symbol)
);

CREATE TABLE IF NOT EXISTS news_aligned (
    news_id       TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    trade_date    TEXT NOT NULL,
    published_at  TEXT,
    ret_t0        REAL,
    ret_t1        REAL,
    ret_t3        REAL,
    ret_t5        REAL,
    ret_t10       REAL,
    PRIMARY KEY (news_id, symbol)
);
CREATE INDEX IF NOT EXISTS idx_news_aligned_symbol_date ON news_aligned(symbol, trade_date DESC);

CREATE TABLE IF NOT EXISTS batch_jobs (
    batch_id      TEXT PRIMARY KEY,
    symbol        TEXT,
    status        TEXT,
    total         INTEGER,
    completed     INTEGER DEFAULT 0,
    created_at    TEXT,
    finished_at   TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    symbol        TEXT NOT NULL,
    date          TEXT NOT NULL,
    window        INTEGER NOT NULL,
    direction     TEXT,
    confidence    REAL,
    drivers       TEXT,
    conclusion    TEXT,
    model_accuracy REAL,
    baseline_accuracy REAL,
    PRIMARY KEY (symbol, date, window)
);
CREATE INDEX IF NOT EXISTS idx_predictions_symbol ON predictions(symbol, date DESC);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Database initialized at {settings.db_path}")


if __name__ == "__main__":
    init_db()
