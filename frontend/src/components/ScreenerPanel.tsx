import { useState } from 'react';
import axios from 'axios';
import type { ScreenerResponse, ScreenerStock } from '../types';

const SECTORS = ['半导体', '新能源', 'AI', '医药', '消费', '军工', '金融', '地产', '汽车', '电力'];

const PRESET_FILTERS = [
  { label: '涨停股', filters: { limit_up_only: true } },
  { label: '跌停股', filters: { limit_down_only: true } },
  { label: '涨幅 >5%', filters: { min_change_pct: 5.0 } },
  { label: '跌幅 >5%', filters: { max_change_pct: -5.0 } },
  { label: '强势股', filters: { min_change_pct: 3.0 } },
];

interface ActiveFilters {
  sectors: string[];
  min_change_pct: number | null;
  max_change_pct: number | null;
  limit_up_only: boolean;
  limit_down_only: boolean;
}

export default function ScreenerPanel() {
  const [results, setResults] = useState<ScreenerStock[]>([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState<ActiveFilters>({
    sectors: [],
    min_change_pct: null,
    max_change_pct: null,
    limit_up_only: false,
    limit_down_only: false,
  });
  const [activePreset, setActivePreset] = useState<string | null>(null);

  async function doSearch(overrideFilters?: Partial<ActiveFilters>) {
    const reqFilters = { ...filters, ...overrideFilters };
    setLoading(true);
    setError('');
    try {
      const res = await axios.post<ScreenerResponse>('/api/screener', {
        sectors: reqFilters.sectors,
        min_change_pct: reqFilters.min_change_pct,
        max_change_pct: reqFilters.max_change_pct,
        limit_up_only: reqFilters.limit_up_only,
        limit_down_only: reqFilters.limit_down_only,
        sort_by: 'change_pct',
        sort_order: 'desc',
        limit: 30,
      });
      setResults(res.data.results || []);
      setCount(res.data.count || 0);
    } catch {
      setError('筛选失败');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  function toggleSector(sector: string) {
    const next = filters.sectors.includes(sector)
      ? filters.sectors.filter(s => s !== sector)
      : [...filters.sectors, sector];
    setFilters(f => ({ ...f, sectors: next }));
    setActivePreset(null);
  }

  function applyPreset(preset: typeof PRESET_FILTERS[0]) {
    const newFilters: ActiveFilters = {
      sectors: [],
      min_change_pct: null,
      max_change_pct: null,
      limit_up_only: false,
      limit_down_only: false,
      ...preset.filters,
    };
    setFilters(newFilters);
    setActivePreset(preset.label);
    doSearch(newFilters);
  }

  return (
    <div className="screener-panel">
      {/* Header */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>选股器</div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          找到 <span style={{ color: 'var(--accent-blue)', fontWeight: 600 }}>{count}</span> 只符合条件的股票
        </div>
      </div>

      {/* Preset quick filters */}
      <div className="screener-section">
        <div className="screener-section-title">快捷筛选</div>
        <div className="screener-filters">
          {PRESET_FILTERS.map(preset => (
            <button
              key={preset.label}
              className={`filter-chip ${activePreset === preset.label ? 'active' : ''}`}
              onClick={() => applyPreset(preset)}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* Sector chips */}
      <div className="screener-section">
        <div className="screener-section-title">行业板块</div>
        <div className="screener-filters">
          {SECTORS.map(sector => (
            <button
              key={sector}
              className={`filter-chip ${filters.sectors.includes(sector) ? 'active' : ''}`}
              onClick={() => toggleSector(sector)}
            >
              {sector}
            </button>
          ))}
        </div>
      </div>

      {/* Custom filters */}
      <div className="screener-section">
        <div className="screener-section-title">涨跌幅范围</div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>最小</span>
            <input
              type="number"
              placeholder="-10"
              value={filters.min_change_pct ?? ''}
              onChange={e => setFilters(f => ({
                ...f,
                min_change_pct: e.target.value ? parseFloat(e.target.value) : null,
              }))}
              style={{
                background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)',
                borderRadius: 6, padding: '4px 8px', color: 'var(--text-primary)',
                fontSize: 12, width: 64, fontFamily: 'var(--font-mono)',
              }}
            />
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>%</span>
          </div>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>~</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>最大</span>
            <input
              type="number"
              placeholder="10"
              value={filters.max_change_pct ?? ''}
              onChange={e => setFilters(f => ({
                ...f,
                max_change_pct: e.target.value ? parseFloat(e.target.value) : null,
              }))}
              style={{
                background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)',
                borderRadius: 6, padding: '4px 8px', color: 'var(--text-primary)',
                fontSize: 12, width: 64, fontFamily: 'var(--font-mono)',
              }}
            />
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>%</span>
          </div>
        </div>
      </div>

      {/* Search button */}
      <div style={{ marginBottom: 12 }}>
        <button
          className="filter-chip active"
          onClick={() => doSearch()}
          disabled={loading}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          {loading ? '筛选中...' : '🔍 执行筛选'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{ padding: '8px 12px', background: 'rgba(248,81,73,0.1)', borderRadius: 6, marginBottom: 8, fontSize: 12, color: 'var(--chart-red)' }}>
          {error}
        </div>
      )}

      {/* Results */}
      <div className="screener-results">
        <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6, fontWeight: 600 }}>
          筛选结果 ({count})
        </div>

        {loading ? (
          <div className="loading-spinner">
            <div className="spinner" />
            <span>筛选中...</span>
          </div>
        ) : results.length === 0 ? (
          <div className="news-empty" style={{ padding: 16 }}>
            暂无符合条件的股票
          </div>
        ) : (
          results.map((stock, i) => {
            const changePct = stock.change_pct ?? 0;
            const isUp = changePct >= 0;
            const isLimitUp = stock.limit_up === 1;
            const isLimitDown = stock.limit_down === 1;
            const price = stock.price ?? stock.close;

            return (
              <div
                key={`${stock.symbol}-${i}`}
                className="screener-stock"
                onClick={() => {
                  window.dispatchEvent(new CustomEvent('astock:navigate', { detail: { symbol: stock.symbol } }));
                }}
              >
                <div className="screener-stock-left">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span className="screener-stock-symbol">{stock.symbol}</span>
                    {isLimitUp && <span className="limit-up-badge">涨停</span>}
                    {isLimitDown && <span className="limit-down-badge">跌停</span>}
                  </div>
                  <span className="screener-stock-name">
                    {stock.name || stock.symbol}
                    {stock.sector && <span style={{ color: 'var(--text-muted)', marginLeft: 4, fontSize: 10 }}>{stock.sector}</span>}
                  </span>
                </div>
                <div className="screener-stock-right">
                  <div className="screener-stock-price">
                    {price && price > 0 ? `¥${price.toFixed(2)}` : '--'}
                  </div>
                  <div className={`screener-stock-change ${isUp ? 'up' : 'down'}`}>
                    {isUp ? '+' : ''}{changePct.toFixed(2)}%
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
