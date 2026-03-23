import { useState, useEffect } from 'react';
import axios from 'axios';

interface Props {
  onSelectStock: (symbol: string) => void;
  onSwitchToChart: () => void;
}

interface IndexData {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
  direction: string;
}

interface BoardItem {
  symbol: string;
  name: string;
  change_pct: number;
  direction: string;
}

interface LimitStock {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  turnover: number;
  reason?: string;
}

interface HotStock {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  lead_flow: number;
}

export default function MarketOverview({ onSelectStock, onSwitchToChart }: Props) {
  const [indices, setIndices] = useState<IndexData[]>([]);
  const [boards, setBoards] = useState<BoardItem[]>([]);
  const [limitUp, setLimitUp] = useState<LimitStock[]>([]);
  const [limitDown, setLimitDown] = useState<LimitStock[]>([]);
  const [hotStocks, setHotStocks] = useState<HotStock[]>([]);
  const [realtimeStocks, setRealtimeStocks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<'overview' | 'limit' | 'hot' | 'boards'>('overview');

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([
      axios.get('/api/market/indices'),
      axios.get('/api/market/boards?limit=15'),
      axios.get('/api/market/limit-up?limit=20'),
      axios.get('/api/market/limit-down?limit=20'),
      axios.get('/api/market/hot?limit=15'),
      axios.get('/api/market/realtime?sort_by=change_pct&limit=30'),
    ]).then((results) => {
      const [idxRes, boardRes, luRes, ldRes, hotRes, rtRes] = results;
      if (idxRes.status === 'fulfilled') setIndices(idxRes.value.data || []);
      if (boardRes.status === 'fulfilled') setBoards(boardRes.value.data || []);
      if (luRes.status === 'fulfilled') setLimitUp(luRes.value.data || []);
      if (ldRes.status === 'fulfilled') setLimitDown(ldRes.value.data || []);
      if (hotRes.status === 'fulfilled') setHotStocks(hotRes.value.data || []);
      if (rtRes.status === 'fulfilled') setRealtimeStocks(rtRes.value.data?.results || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="market-overview">
        <div className="market-loading">
          <div className="spinner" />
          <span>加载市场数据中...</span>
        </div>
      </div>
    );
  }

  function formatMoney(n: number) {
    if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿';
    if (n >= 1e4) return (n / 1e4).toFixed(2) + '万';
    return n.toFixed(2);
  }

  return (
    <div className="market-overview">
      {/* Indices */}
      <div className="market-section">
        <div className="market-section-title">大盘指数</div>
        <div className="indices-grid">
          {indices.map((idx) => (
            <div key={idx.symbol} className={`index-card ${idx.direction}`}>
              <div className="index-name">{idx.name}</div>
              <div className="index-price">{idx.price > 0 ? idx.price.toFixed(2) : '--'}</div>
              <div className={`index-change ${idx.direction}`}>
                {idx.change > 0 ? '▲' : idx.change < 0 ? '▼' : '—'}
                {' '}
                {idx.change_pct >= 0 ? '+' : ''}{idx.change_pct.toFixed(2)}%
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Section tabs */}
      <div className="market-tabs">
        {(['overview', 'limit', 'hot', 'boards'] as const).map((sec) => (
          <button
            key={sec}
            className={`market-tab ${activeSection === sec ? 'active' : ''}`}
            onClick={() => setActiveSection(sec)}
          >
            {sec === 'overview' ? '涨幅榜' :
             sec === 'limit' ? '涨跌停' :
             sec === 'hot' ? '资金流入' :
             '板块涨跌'}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="market-content">
        {activeSection === 'overview' && (
          <div className="market-table-wrapper">
            <table className="market-table">
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>现价</th>
                  <th>涨跌幅</th>
                  <th>成交量</th>
                  <th>成交额</th>
                </tr>
              </thead>
              <tbody>
                {realtimeStocks.map((s) => (
                  <tr key={s.symbol} onClick={() => { onSelectStock(s.symbol); onSwitchToChart(); }} className="market-row-clickable">
                    <td className="mono">{s.symbol}</td>
                    <td className="name-cell">{s.name || s.symbol}</td>
                    <td className="mono">{s.price > 0 ? '¥' + s.price.toFixed(2) : '--'}</td>
                    <td className={`mono ${(s.change_pct || 0) >= 0 ? 'up' : 'down'}`}>
                      {(s.change_pct || 0) >= 0 ? '+' : ''}{(s.change_pct || 0).toFixed(2)}%
                    </td>
                    <td className="mono">{formatMoney(s.volume)}</td>
                    <td className="mono">{formatMoney(s.turnover)}</td>
                  </tr>
                ))}
                {realtimeStocks.length === 0 && (
                  <tr><td colSpan={6} className="empty-cell">暂无数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeSection === 'limit' && (
          <div className="limit-section">
            <div className="limit-column">
              <div className="limit-title limit-up-title">🔴 涨停 ({limitUp.length})</div>
              <div className="limit-list">
                {limitUp.map((s, i) => (
                  <div key={i} className="limit-item" onClick={() => { onSelectStock(s.symbol); onSwitchToChart(); }}>
                    <div className="limit-item-left">
                      <span className="limit-symbol mono">{s.symbol}</span>
                      <span className="limit-name">{s.name}</span>
                    </div>
                    <div className="limit-item-right">
                      <span className="limit-price mono">¥{s.price}</span>
                      <span className="limit-pct limit-up-pct">+{s.change_pct.toFixed(2)}%</span>
                    </div>
                    {s.reason && <div className="limit-reason">{s.reason}</div>}
                  </div>
                ))}
                {limitUp.length === 0 && <div className="limit-empty">今日无涨停</div>}
              </div>
            </div>
            <div className="limit-column">
              <div className="limit-title limit-down-title">🟢 跌停 ({limitDown.length})</div>
              <div className="limit-list">
                {limitDown.map((s, i) => (
                  <div key={i} className="limit-item" onClick={() => { onSelectStock(s.symbol); onSwitchToChart(); }}>
                    <div className="limit-item-left">
                      <span className="limit-symbol mono">{s.symbol}</span>
                      <span className="limit-name">{s.name}</span>
                    </div>
                    <div className="limit-item-right">
                      <span className="limit-price mono">¥{s.price}</span>
                      <span className="limit-pct limit-down-pct">{s.change_pct.toFixed(2)}%</span>
                    </div>
                  </div>
                ))}
                {limitDown.length === 0 && <div className="limit-empty">今日无跌停</div>}
              </div>
            </div>
          </div>
        )}

        {activeSection === 'hot' && (
          <div className="market-table-wrapper">
            <table className="market-table">
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>现价</th>
                  <th>涨跌幅</th>
                  <th>主力净流入</th>
                </tr>
              </thead>
              <tbody>
                {hotStocks.map((s) => (
                  <tr key={s.symbol} onClick={() => { onSelectStock(s.symbol); onSwitchToChart(); }} className="market-row-clickable">
                    <td className="mono">{s.symbol}</td>
                    <td className="name-cell">{s.name}</td>
                    <td className="mono">{s.price > 0 ? '¥' + s.price.toFixed(2) : '--'}</td>
                    <td className={`mono ${(s.change_pct || 0) >= 0 ? 'up' : 'down'}`}>
                      {(s.change_pct || 0) >= 0 ? '+' : ''}{(s.change_pct || 0).toFixed(2)}%
                    </td>
                    <td className="mono up">▲ {formatMoney(s.lead_flow)}</td>
                  </tr>
                ))}
                {hotStocks.length === 0 && (
                  <tr><td colSpan={5} className="empty-cell">暂无数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeSection === 'boards' && (
          <div className="boards-grid">
            {boards.map((b) => (
              <div
                key={b.symbol || b.name}
                className={`board-card ${b.direction}`}
                onClick={() => {}}
              >
                <div className="board-name">{b.name}</div>
                <div className={`board-pct ${b.direction}`}>
                  {b.change_pct >= 0 ? '+' : ''}{b.change_pct.toFixed(2)}%
                </div>
              </div>
            ))}
            {boards.length === 0 && <div className="limit-empty">暂无板块数据</div>}
          </div>
        )}
      </div>
    </div>
  );
}
