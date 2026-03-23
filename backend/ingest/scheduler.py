"""
数据同步调度器
定期同步OHLC K线数据 + 新闻数据
"""
import sys
import os
import time
import threading
from datetime import datetime

_backend_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_backend_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from ingest.sync import DEFAULT_STOCKS, sync_ohlc_to_pg, seed_stocks
from ingest.news_scraper import bg_fetch_news

# Sync intervals (seconds)
OHLC_SYNC_INTERVAL = 3600      # 1 hour for OHLC
NEWS_SYNC_INTERVAL = 1800       # 30 min for news
FULL_REFRESH_INTERVAL = 21600  # 6 hours for full resync

# Batch sizes
OHLC_BATCH_SIZE = 30            # Stocks per OHLC batch
NEWS_BATCH_SIZE = 20            # Stocks per news batch


class SyncScheduler:
    """Background scheduler for periodic data synchronization."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._stocks_to_sync = list(DEFAULT_STOCKS)
        self._ohlc_index = 0
        self._news_index = 0

    def _get_ohlc_batch(self):
        """Get next batch of stocks for OHLC sync."""
        batch = []
        for _ in range(OHLC_BATCH_SIZE):
            stock = self._stocks_to_sync[self._ohlc_index % len(self._stocks_to_sync)]
            batch.append(stock)
            self._ohlc_index += 1
        return batch

    def _get_news_batch(self):
        """Get next batch of stocks for news sync."""
        batch = []
        for _ in range(NEWS_BATCH_SIZE):
            stock = self._stocks_to_sync[self._news_index % len(self._stocks_to_sync)]
            batch.append(stock)
            self._news_index += 1
        return batch

    def _run_loop(self):
        """Main scheduler loop."""
        print(f"[SCHEDULER] Started — {len(self._stocks_to_sync)} stocks in pool")
        last_full = time.time()

        while self._running:
            now = time.time()
            tick = datetime.now().strftime("%H:%M:%S")

            # Full resync every 6 hours
            if now - last_full >= FULL_REFRESH_INTERVAL:
                print(f"[SCHEDULER] Full resync at {tick}")
                last_full = now

            # OHLC sync batch
            ohlc_batch = self._get_ohlc_batch()
            print(f"[SCHEDULER] [{tick}] OHLC batch ({len(ohlc_batch)} stocks)...")
            for sym, name, sector, market in ohlc_batch:
                try:
                    sync_ohlc_to_pg(sym, market)
                except Exception as e:
                    print(f"[SCHEDULER] OHLC {sym}: {e}")
                time.sleep(0.3)  # Rate limit

            # News sync batch
            news_batch = self._get_news_batch()
            print(f"[SCHEDULER] [{tick}] News batch ({len(news_batch)} stocks)...")
            for sym, name, sector, market in news_batch:
                try:
                    bg_fetch_news(sym, market)
                except Exception as e:
                    print(f"[SCHEDULER] News {sym}: {e}")
                time.sleep(1)  # Respect rate limits

            # Sleep before next cycle
            elapsed = time.time() - now
            sleep_time = max(NEWS_SYNC_INTERVAL - elapsed, 60)
            print(f"[SCHEDULER] Sleeping {int(sleep_time)}s...")
            for _ in range(int(sleep_time)):
                if not self._running:
                    break
                time.sleep(1)

    def start(self):
        """Start the scheduler in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="SyncScheduler")
        self._thread.start()
        print("[SCHEDULER] Background scheduler thread started")

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[SCHEDULER] Stopped")


# Global scheduler instance
_scheduler = SyncScheduler()


def start_scheduler():
    """Start the global scheduler (call from FastAPI startup)."""
    _scheduler.start()


def stop_scheduler():
    """Stop the global scheduler (call from FastAPI shutdown)."""
    _scheduler.stop()


def sync_stock_now(symbol: str, market: str = "sh"):
    """Trigger immediate OHLC + news sync for a single stock."""
    threading.Thread(
        target=lambda s, m: (sync_ohlc_to_pg(s, m), bg_fetch_news(s, m)),
        args=(symbol, market),
        daemon=True
    ).start()
