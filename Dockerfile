FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire repo (backend/ contains the app)
COPY . .

# Initialize SQLite DB
RUN python -c "
import sqlite3, os
db_path = os.environ.get('DATABASE_PATH', 'astock.db')
conn = sqlite3.connect(db_path)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('''CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY, name TEXT, sector TEXT, market TEXT,
    last_ohlc_fetch TEXT)''')
conn.execute('''CREATE TABLE IF NOT EXISTS ohlc (
    symbol TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL,
    volume REAL, turnover REAL, change_pct REAL, limit_up INTEGER,
    limit_down INTEGER, amplitude REAL,
    PRIMARY KEY (symbol, date))''')
conn.execute('''CREATE TABLE IF NOT EXISTS news_raw (
    id TEXT PRIMARY KEY, symbol TEXT, date TEXT, title TEXT,
    content TEXT, url TEXT, source TEXT)''')
conn.execute('''CREATE TABLE IF NOT EXISTS layer1_results (
    id TEXT PRIMARY KEY, symbol TEXT, date TEXT, sentiment TEXT,
    sentiment_cn TEXT, relevance TEXT, key_discussion TEXT,
    reason_growth TEXT, reason_decrease TEXT, created_at TEXT)''')
conn.execute('''CREATE TABLE IF NOT EXISTS predictions (
    id TEXT PRIMARY KEY, symbol TEXT, date TEXT,
    forecast_t1 TEXT, forecast_t3 TEXT, forecast_t5 TEXT,
    confidence_t1 REAL, confidence_t3 REAL, confidence_t5 REAL,
    created_at TEXT)''')
conn.commit()
conn.close()
print('Database initialized')
"

ENV PYTHONPATH=/app
ENV DATABASE_PATH=astock.db

EXPOSE 8000

CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
