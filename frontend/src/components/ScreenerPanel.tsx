import { useState } from 'react';
import axios from 'axios';
import type { ScreenerResult } from '../types';

const SECTORS = ['银行', '白酒', '新能源', '医药', 'AI', '半导体', '消费电子', '军工', '通信', '消费', '地产', '能源', '软件'];

export default function ScreenerPanel() {
  const [results, setResults] = useState<ScreenerResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    limitUp: false,
    limitDown: false,
    sectors: [] as string[],
  });

  async function runScreener() {
    setLoading(true);
    try {
      const res = await axios.post('/api/screener', {
        limit_up_only: filters.limitUp,
        limit_down_only: filters.limitDown,
        sectors: filters.sectors,
        sort_by: 'change_pct',
        sort_order: 'desc',
        limit: 30,
      });
      setResults(res.data.results || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  function toggleSector(sector: string) {
    setFilters((f) => ({
      ...f,
      sectors: f.sectors.includes(sector)
        ? f.sectors.filter((s) => s !== sector)
        : [...f.sectors, sector],
    }));
  }

  return (
    <div className="screener-panel">
      <div className="screener-section">
        <div className="screener-section-title">筛选条件</div>
        <div className="screener-filters">
          <button
            className={`filter-chip ${filters.limitUp ? 'active' : ''}`}
            onClick={() => setFilters((f) => ({ ...f, limitUp: !f.limitUp, limitDown: false }))}
            style={filters.limitUp ? { borderColor: 'var(--chart-red)', color: 'var(--chart-red)' } : {}}
          >
            🔴 涨停
          </button>
          <button
            className={`filter-chip ${filters.limitDown ? 'active' : ''}`}
            onClick={() => setFilters((f) => ({ ...f, limitDown: !f.limitDown, limitUp: false }))}
            style={filters.limitDown ? { borderColor: 'var(--chart-green)', color: 'var(--chart-green)' } : {}}
          >
            🟢 跌停
          </button>
        </div>
      </div>

      <div className="screener-section">
        <div className="screener-section-title">行业板块</div>
        <div className="screener-filters">
          {SECTORS.map((s) => (
            <button
              key={s}
              className={`filter-chip ${filters.sectors.includes(s) ? 'active' : ''}`}
              onClick={() => toggleSector(s)}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <button
        style={{
          marginBottom: 12,
          padding: '8px 16px',
          fontSize: 13,
          borderRadius: 8,
          background: 'rgba(88,166,255,0.15)',
          border: '1px solid var(--accent-blue)',
          color: 'var(--accent-blue)',
          fontWeight: 600,
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.6 : 1,
        }}
        onClick={runScreener}
        disabled={loading}
      >
        {loading ? '🔍 查询中...' : '🔍 查询'}
      </button>

      <div className="screener-section">
        <div className="screener-section-title">查询结果 ({results.length})</div>
        {results.length === 0 && !loading && (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
            点击上方「查询」按钮获取结果
          </div>
        )}
        {results.map((stock) => (
          <div key={stock.symbol} className="screener-stock">
            <div className="screener-stock-left">
              <span className="screener-stock-symbol">
                {stock.symbol}
                {stock.limit_up ? <span className="limit-up-badge">涨停</span> : null}
                {stock.limit_down ? <span className="limit-down-badge">跌停</span> : null}
              </span>
              <span className="screener-stock-name">{stock.name || stock.sector || ''}</span>
            </div>
            <div className="screener-stock-right">
              <div className="screener-stock-price">
                ¥{(stock.close || 0).toFixed(2)}
              </div>
              <div className={`screener-stock-change ${(stock.change_pct || 0) >= 0 ? 'up' : 'down'}`}>
                {(stock.change_pct || 0) >= 0 ? '+' : ''}{(stock.change_pct || 0).toFixed(2)}%
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
