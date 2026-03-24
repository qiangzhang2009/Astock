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

# Sync intervals
OHLC_SYNC_INTERVAL = 1800     # 30 min
NEWS_SYNC_INTERVAL = 600     # 10 min

# Batch sizes
OHLC_BATCH_SIZE = 50        # 50 stocks per OHLC batch
NEWS_BATCH_SIZE = 30        # 30 stocks per news batch


class SyncScheduler:
    """Background scheduler for continuous data synchronization."""

    def __init__(self):
        self._running = False
        self._thread = None
        self._stocks_to_sync = list(DEFAULT_STOCKS)
        self._ohlc_index = 0
        self._news_index = 0

    def _get_batch(self, batch_size: int, index_ref: list[int]) -> list:
        idx = index_ref[0]
        batch = []
        for _ in range(batch_size):
            stock = self._stocks_to_sync[idx % len(self._stocks_to_sync)]
            batch.append(stock)
            idx += 1
        index_ref[0] = idx
        return batch

    def _run_loop(self):
        """Main scheduler loop — OHLC + news sync in parallel batches."""
        print(f"[SCHEDULER] Started — {len(self._stocks_to_sync)} stocks")

        while self._running:
            now = time.time()
            tick = datetime.now().strftime("%H:%M:%S")

            # OHLC batch (50 stocks, ~0.2s each = 10s per batch)
            ohlc_batch = self._get_batch(OHLC_BATCH_SIZE, [self._ohlc_index])
            print(f"[SCHEDULER] [{tick}] OHLC batch ({len(ohlc_batch)} stocks)...")
            for sym, name, sector, market in ohlc_batch:
                if not self._running:
                    break
                try:
                    sync_ohlc_to_pg(sym, market)
                except Exception as e:
                    print(f"[SCHEDULER] OHLC {sym}: {e}")
                time.sleep(0.15)

            # News batch (30 stocks, ~3s each = 90s per batch)
            news_batch = self._get_batch(NEWS_BATCH_SIZE, [self._news_index])
            print(f"[SCHEDULER] [{tick}] News batch ({len(news_batch)} stocks)...")
            for sym, name, sector, market in news_batch:
                if not self._running:
                    break
                try:
                    bg_fetch_news(sym, market)
                except Exception as e:
                    print(f"[SCHEDULER] News {sym}: {e}")
                time.sleep(0.3)

            # Sleep
            elapsed = time.time() - now
            sleep_time = max(OHLC_SYNC_INTERVAL - elapsed, 60)
            print(f"[SCHEDULER] Sleeping {int(sleep_time)}s...")
            for _ in range(int(sleep_time)):
                if not self._running:
                    break
                time.sleep(1)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="SyncScheduler"
        )
        self._thread.start()
        print("[SCHEDULER] Background scheduler started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[SCHEDULER] Stopped")


_scheduler = SyncScheduler()


def start_scheduler():
    _scheduler.start()


def stop_scheduler():
    _scheduler.stop()


def sync_stock_now(symbol: str, market: str = "sh"):
    """Trigger immediate OHLC + news sync for a single stock."""
    def _do():
        sync_ohlc_to_pg(symbol, market)
        bg_fetch_news(symbol, market)
    threading.Thread(target=_do, daemon=True).start()
