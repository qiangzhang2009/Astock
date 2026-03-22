import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

interface Ticker {
  symbol: string;
  name?: string;
  sector?: string;
  market?: string;
}

interface Props {
  activeTickers: string[];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
  onAdd: (symbol: string) => void;
}

// A 股默认关注股票池
const A_STOCK_GROUPS: Record<string, Array<{ symbol: string; name: string }>> = {
  '科技/AI': [
    { symbol: '002230', name: '科大讯飞' },
    { symbol: '688981', name: '中芯国际' },
    { symbol: '688256', name: '寒武纪' },
    { symbol: '002049', name: '紫光国微' },
    { symbol: '300496', name: '中科创达' },
    { symbol: '002371', name: '北方华创' },
  ],
  '新能源': [
    { symbol: '300750', name: '宁德时代' },
    { symbol: '002594', name: '比亚迪' },
    { symbol: '300274', name: '阳光电源' },
    { symbol: '601012', name: '隆基绿能' },
    { symbol: '601857', name: '中国石油' },
  ],
  '白酒': [
    { symbol: '600519', name: '贵州茅台' },
    { symbol: '000858', name: '五粮液' },
    { symbol: '600809', name: '山西汾酒' },
    { symbol: '000568', name: '泸州老窖' },
  ],
  '金融': [
    { symbol: '600036', name: '招商银行' },
    { symbol: '601318', name: '中国平安' },
    { symbol: '300059', name: '东方财富' },
    { symbol: '300033', name: '同花顺' },
    { symbol: '000001', name: '平安银行' },
  ],
  '医药': [
    { symbol: '600276', name: '恒瑞医药' },
    { symbol: '603259', name: '药明康德' },
  ],
  '消费电子': [
    { symbol: '002475', name: '立讯精密' },
    { symbol: '000725', name: '京东方A' },
    { symbol: '002415', name: '海康威视' },
  ],
  '通信': [
    { symbol: '600050', name: '中国联通' },
    { symbol: '000063', name: '中兴通讯' },
  ],
  '地产基建': [
    { symbol: '600048', name: '保利发展' },
    { symbol: '601668', name: '中国建筑' },
  ],
  '军工': [
    { symbol: '600893', name: '航发动力' },
  ],
};

export default function StockSelector({ activeTickers, selectedSymbol, onSelect, onAdd }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Ticker[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [showPanel, setShowPanel] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearch(false);
      }
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setShowPanel(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  function handleSearch(q: string) {
    setQuery(q);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (q.length < 1) {
      setResults([]);
      setShowSearch(false);
      return;
    }
    timerRef.current = setTimeout(async () => {
      try {
        const res = await axios.get(`/api/stocks/search?q=${encodeURIComponent(q)}`);
        setResults(res.data);
        setShowSearch(true);
      } catch {
        setResults([]);
      }
    }, 300);
  }

  function handlePick(ticker: Ticker) {
    setQuery('');
    setShowSearch(false);
    setShowPanel(false);
    if (!activeTickers.includes(ticker.symbol)) {
      onAdd(ticker.symbol);
    }
    onSelect(ticker.symbol);
  }

  function handleSelectTicker(sym: string) {
    setShowPanel(false);
    onSelect(sym);
  }

  const activeSet = new Set(activeTickers);

  // 只显示有数据的股票分组
  const renderedGroups = Object.entries(A_STOCK_GROUPS)
    .map(([label, stocks]) => ({
      label,
      stocks: stocks.filter((s) => activeSet.has(s.symbol)),
    }))
    .filter((g) => g.stocks.length > 0);

  const assigned = new Set(renderedGroups.flatMap((g) => g.stocks.map((s) => s.symbol)));
  const ungrouped = activeTickers.filter((s) => !assigned.has(s)).sort();
  if (ungrouped.length > 0) {
    renderedGroups.push({ label: '其他', stocks: ungrouped.map((s) => ({ symbol: s, name: s })) });
  }

  // 找选中股票的名称
  const selectedName = Object.values(A_STOCK_GROUPS).flat().find((s) => s.symbol === selectedSymbol)?.name
    || (selectedSymbol ? selectedSymbol : '---');

  return (
    <div className="stock-selector">
      {/* 当前股票按钮 */}
      <div className="ticker-dropdown-wrapper" ref={panelRef}>
        <button className="ticker-current" onClick={() => setShowPanel((v) => !v)}>
          <span className="ticker-current-symbol">
            {selectedSymbol ? `${selectedSymbol} ${selectedName}` : '---'}
          </span>
          <span className={`ticker-arrow ${showPanel ? 'open' : ''}`}>&#9662;</span>
        </button>

        {showPanel && (
          <div className="ticker-panel">
            {renderedGroups.map((group) => (
              <div className="ticker-panel-group" key={group.label}>
                <div className="ticker-panel-group-label">{group.label}</div>
                <div className="ticker-panel-group-items">
                  {group.stocks.map((s) => (
                    <button
                      key={s.symbol}
                      className={`ticker-panel-item ${s.symbol === selectedSymbol ? 'active' : ''}`}
                      onClick={() => handleSelectTicker(s.symbol)}
                    >
                      {s.name} ({s.symbol})
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 搜索 */}
      <div className="search-wrapper" ref={searchRef}>
        <input
          type="text"
          placeholder="搜索股票代码或名称..."
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => results.length > 0 && setShowSearch(true)}
        />
        {showSearch && results.length > 0 && (
          <ul className="search-dropdown">
            {results.map((t) => (
              <li key={t.symbol} onClick={() => handlePick(t)}>
                <strong>{t.symbol}</strong>
                <span>{t.name || ''}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
