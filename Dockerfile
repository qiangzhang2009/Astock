FROM python:3.11-slim

WORKDIR /app

# Install system deps for akshare
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Seed default A-share stock list
RUN python -c "
import akshare as ak
import sqlite3
import os
db_path = os.environ.get('DATABASE_PATH', 'astock.db')
conn = sqlite3.connect(db_path)
conn.execute('PRAGMA journal_mode=WAL')
# Create stocks table
conn.execute('''CREATE TABLE IF NOT EXISTS stocks (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    market TEXT,
    last_fetch TEXT
)''')
conn.commit()
conn.close()
print('Database initialized')
"

ENV PYTHONPATH=/app
ENV DATABASE_PATH=astock.db

EXPOSE 8000

CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
