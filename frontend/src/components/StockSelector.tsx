import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

interface StockInfo {
  symbol: string;
  name?: string;
  sector?: string;
  market?: string;
  last_ohlc_fetch?: string | null;
}

interface Props {
  activeTickers: string[];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
  onAdd: (symbol: string) => void;
}

export default function StockSelector({ activeTickers, selectedSymbol, onSelect, onAdd }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<StockInfo[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setSearchQuery('');
        setSearchResults([]);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Search stocks
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await axios.get(`/api/stocks/search?q=${encodeURIComponent(searchQuery)}`);
        setSearchResults(res.data || []);
      } catch {
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  function handleSelect(symbol: string) {
    onSelect(symbol);
    setIsOpen(false);
    setSearchQuery('');
    setSearchResults([]);
  }

  function handleAddFromSearch(item: StockInfo) {
    onAdd(item.symbol);
    onSelect(item.symbol);
    setIsOpen(false);
    setSearchQuery('');
    setSearchResults([]);
  }

  return (
    <div className="stock-selector" ref={wrapperRef}>
      {/* Current ticker dropdown */}
      <div
        className="ticker-dropdown-wrapper"
        style={{ position: 'relative' }}
      >
        <button
          className={`ticker-current ${isOpen ? 'open' : ''}`}
          onClick={() => {
            setIsOpen(!isOpen);
            if (!isOpen) searchRef.current?.focus();
          }}
        >
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
            {selectedSymbol || '选择股票'}
          </span>
          <span className={`ticker-arrow ${isOpen ? 'open' : ''}`}>▼</span>
        </button>

        {/* Dropdown panel */}
        {isOpen && (
          <div className="ticker-panel" style={{ minWidth: 220 }}>
            {/* Active tickers */}
            {activeTickers.length > 0 && (
              <div className="ticker-panel-group">
                <div className="ticker-panel-group-label">已跟踪</div>
                <div className="ticker-panel-group-items">
                  {activeTickers.map(sym => (
                    <button
                      key={sym}
                      className={`ticker-panel-item ${sym === selectedSymbol ? 'active' : ''}`}
                      onClick={() => handleSelect(sym)}
                    >
                      {sym}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Search */}
            <div className="ticker-panel-group" style={{ padding: '8px 8px 4px' }}>
              <div className="search-wrapper" style={{ position: 'relative' }}>
                <input
                  ref={searchRef}
                  type="text"
                  placeholder="搜索股票代码或名称..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  style={{
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 6,
                    padding: '6px 10px',
                    color: 'var(--text-primary)',
                    fontSize: 12,
                    width: '100%',
                  }}
                />
              </div>

              {/* Search results */}
              {(searchResults.length > 0 || isSearching) && (
                <div style={{
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-color)',
                  borderRadius: 8,
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
                  marginTop: 4,
                  maxHeight: 260,
                  overflowY: 'auto',
                }}>
                  {isSearching && (
                    <div style={{ padding: '12px 12px', color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>
                      搜索中...
                    </div>
                  )}
                  {searchResults.map(item => {
                    const isActive = activeTickers.includes(item.symbol);
                    return (
                      <div
                        key={item.symbol}
                        style={{
                          padding: '8px 12px',
                          borderBottom: '1px solid var(--border-color)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          cursor: 'pointer',
                          transition: 'background 0.1s',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
                        onMouseLeave={e => (e.currentTarget.style.background = '')}
                        onClick={() => isActive ? handleSelect(item.symbol) : handleAddFromSearch(item)}
                      >
                        <span style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: 12,
                          color: 'var(--accent-blue)',
                          fontWeight: 600,
                          minWidth: 60,
                        }}>
                          {item.symbol}
                        </span>
                        <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.name || item.symbol}
                        </span>
                        {item.sector && (
                          <span style={{ fontSize: 10, color: 'var(--text-muted)', flexShrink: 0 }}>
                            {item.sector}
                          </span>
                        )}
                        {isActive && (
                          <span style={{
                            fontSize: 10,
                            color: 'var(--chart-green)',
                            background: 'rgba(63,185,80,0.1)',
                            padding: '1px 5px',
                            borderRadius: 4,
                            flexShrink: 0,
                          }}>
                            已跟踪
                          </span>
                        )}
                      </div>
                    );
                  })}
                  {searchResults.length === 0 && !isSearching && searchQuery && (
                    <div style={{ padding: '12px 12px', color: 'var(--text-muted)', fontSize: 12, textAlign: 'center' }}>
                      未找到匹配的股票
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
