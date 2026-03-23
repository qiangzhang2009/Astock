import { useState, useEffect, useRef } from 'react';
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
  high?: number;
  low?: number;
  volume?: number;
  turnover?: number;
}

interface BoardItem {
  symbol: string;
  name: string;
  change_pct: number;
  direction: string;
  volume?: number;
  amount?: number;
  lead_flow?: number;
}

interface LimitStock {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  turnover: number;
  amplitude?: number;
  reason?: string;
  high?: number;
  low?: number;
  prev_close?: number;
}

interface HotStock {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  lead_flow: number;
  lead_flow_pct?: number;
}

interface MarketSummary {
  up_count: number;
  down_count: number;
  limit_up_count: number;
  limit_down_count: number;
  total_volume: number;
  total_turnover: number;
  advancing_boards: number;
  declining_boards: number;
}

interface SparklineData {
  date: string;
  close: number;
  change_pct: number;
}

interface StockRow {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  volume: number;
  turnover: number;
  high?: number;
  low?: number;
  open?: number;
  prev_close?: number;
  amplitude?: number;
  market?: string;
  sector?: string;
  lead_flow?: number;
}

function Sparkline({ data, positive }: { data: SparklineData[]; positive: boolean }) {
  const svgRef = useRef<SVGSVGElement>(null);
  useEffect(() => {
    if (!svgRef.current || !data.length) return;
    const w = 60, h = 24;
    const closes = data.map(d => d.close);
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const range = max - min || 1;
    const pts = data.map((d, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((d.close - min) / range) * (h - 4) - 2;
      return `${x},${y}`;
    }).join(' ');
    const color = positive ? '#26a69a' : '#ef5350';
    const svg = svgRef.current;
    svg.innerHTML = '';
    const ns = 'http://www.w3.org/2000/svg';
    const poly = document.createElementNS(ns, 'polygon');
    poly.setAttribute('points', pts);
    poly.setAttribute('fill', color + '22');
    svg.appendChild(poly);
    const line = document.createElementNS(ns, 'polyline');
    line.setAttribute('points', pts);
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', color);
    line.setAttribute('stroke-width', '1.5');
    svg.appendChild(line);
  }, [data, positive]);
  return <svg ref={svgRef} width={60} height={24} style={{ display: 'block' }} />;
}

export default function MarketOverview({ onSelectStock, onSwitchToChart }: Props) {
  const [indices, setIndices] = useState<IndexData[]>([]);
  const [boards, setBoards] = useState<BoardItem[]>([]);
  const [limitUp, setLimitUp] = useState<LimitStock[]>([]);
  const [limitDown, setLimitDown] = useState<LimitStock[]>([]);
  const [hotStocks, setHotStocks] = useState<HotStock[]>([]);
  const [realtimeStocks, setRealtimeStocks] = useState<StockRow[]>([]);
  const [summary, setSummary] = useState<MarketSummary | null>(null);
  const [sparklines, setSparklines] = useState<Record<string, SparklineData[]>>({});
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<'overview' | 'limit' | 'hot' | 'boards' | 'summary'>('overview');
  const [boardDetail, setBoardDetail] = useState<{ code: string; name: string; stocks: StockRow[] } | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([
      axios.get('/api/market/indices'),
      axios.get('/api/market/boards?limit=20'),
      axios.get('/api/market/limit-up?limit=20'),
      axios.get('/api/market/limit-down?limit=20'),
      axios.get('/api/market/hot?limit=15'),
      axios.get('/api/market/realtime?sort_by=change_pct&limit=40'),
      axios.get('/api/market/summary'),
    ]).then((results) => {
      const [idxRes, boardRes, luRes, ldRes, hotRes, rtRes, sumRes] = results;
      if (idxRes.status === 'fulfilled') setIndices(idxRes.value.data || []);
      if (boardRes.status === 'fulfilled') setBoards(boardRes.value.data || []);
      if (luRes.status === 'fulfilled') setLimitUp(luRes.value.data || []);
      if (ldRes.status === 'fulfilled') setLimitDown(ldRes.value.data || []);
      if (hotRes.status === 'fulfilled') setHotStocks(hotRes.value.data || []);
      if (rtRes.status === 'fulfilled') setRealtimeStocks(rtRes.value.data?.results || []);
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value.data || null);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  // Load sparklines for top stocks
  useEffect(() => {
    if (!realtimeStocks.length) return;
    const topSymbols = realtimeStocks.slice(0, 12).map(s => s.symbol);
    Promise.allSettled(
      topSymbols.map(sym =>
        axios.get(`/api/market/sparkline/${sym}`).then(r => ({ sym, data: r.data.data || [] }))
      )
    ).then(results => {
      const map: Record<string, SparklineData[]> = {};
      results.forEach((r) => {
        if (r.status === 'fulfilled') {
          map[r.value.sym] = r.value.data;
        }
      });
      setSparklines(map);
    });
  }, [realtimeStocks]);

  function formatMoney(n: number | undefined) {
    if (!n) return '--';
    if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿';
    if (n >= 1e4) return (n / 1e4).toFixed(2) + '万';
    return n.toFixed(0);
  }

  function formatVol(v: number | undefined) {
    if (!v) return '--';
    if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿';
    if (v >= 1e4) return (v / 1e4).toFixed(0) + '万';
    return v.toFixed(0);
  }

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

  function handleBoardClick(board: BoardItem) {
    setBoardDetail({ code: board.symbol, name: board.name, stocks: [] });
    axios.get(`/api/market/board/${board.symbol}`).then(r => {
      setBoardDetail(prev => prev ? { ...prev, stocks: r.data.results || [] } : null);
    }).catch(() => {
      setBoardDetail(null);
    });
  }

  return (
    <div className="market-overview">
      {/* Market Summary Bar */}
      {summary && (
        <div className="market-summary-bar">
          <div className="summary-item up">
            <span className="summary-label">上涨</span>
            <span className="summary-value">{summary.up_count}</span>
          </div>
          <div className="summary-divider" />
          <div className="summary-item down">
            <span className="summary-label">下跌</span>
            <span className="summary-value">{summary.down_count}</span>
          </div>
          <div className="summary-divider" />
          <div className="summary-item">
            <span className="summary-label">涨停</span>
            <span className="summary-value accent-red">{summary.limit_up_count}</span>
          </div>
          <div className="summary-divider" />
          <div className="summary-item">
            <span className="summary-label">跌停</span>
            <span className="summary-value accent-green">{summary.limit_down_count}</span>
          </div>
          <div className="summary-divider" />
          <div className="summary-item">
            <span className="summary-label">板块上涨</span>
            <span className="summary-value accent-red">{summary.advancing_boards}</span>
          </div>
          <div className="summary-divider" />
          <div className="summary-item">
            <span className="summary-label">板块下跌</span>
            <span className="summary-value accent-green">{summary.declining_boards}</span>
          </div>
        </div>
      )}

      {/* Indices */}
      <div className="market-section">
        <div className="market-section-title">大盘指数</div>
        <div className="indices-grid">
          {indices.map((idx) => (
            <div
              key={idx.symbol}
              className={`index-card ${idx.direction}`}
              onClick={() => {
                const sym = idx.symbol.replace('sh', '').replace('sz', '');
                const mapped = idx.symbol === 'sh000001' ? '000001' :
                  idx.symbol === 'sz399001' ? '399001' :
                  idx.symbol === 'sz399006' ? '399006' :
                  idx.symbol === 'sh000688' ? '000688' : sym;
                onSelectStock(mapped);
                onSwitchToChart();
              }}
              style={{ cursor: 'pointer' }}
            >
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
        {(['overview', 'limit', 'hot', 'boards', 'summary'] as const).map((sec) => (
          <button
            key={sec}
            className={`market-tab ${activeSection === sec ? 'active' : ''}`}
            onClick={() => { setActiveSection(sec); setBoardDetail(null); }}
          >
            {sec === 'overview' ? '涨幅榜' :
             sec === 'limit' ? '涨跌停' :
             sec === 'hot' ? '资金流入' :
             sec === 'boards' ? '板块涨跌' :
             '市场统计'}
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
                  <th>趋势</th>
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
                    <td className="mono">{formatVol(s.volume)}</td>
                    <td className="mono">{formatMoney(s.turnover)}</td>
                    <td>
                      {sparklines[s.symbol] && (
                        <Sparkline data={sparklines[s.symbol]} positive={(s.change_pct || 0) >= 0} />
                      )}
                    </td>
                  </tr>
                ))}
                {realtimeStocks.length === 0 && (
                  <tr><td colSpan={7} className="empty-cell">暂无数据</td></tr>
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
                      {s.reason && <span className="limit-reason-tag">{s.reason}</span>}
                    </div>
                    <div className="limit-item-right">
                      <span className="limit-price mono">¥{s.price}</span>
                      <span className="limit-pct limit-up-pct">+{s.change_pct.toFixed(2)}%</span>
                    </div>
                    <div className="limit-stats">
                      <span>幅: {(s.amplitude || 0).toFixed(1)}%</span>
                      <span>额: {formatMoney(s.turnover)}</span>
                    </div>
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
                    <div className="limit-stats">
                      <span>幅: {(s.amplitude || 0).toFixed(1)}%</span>
                      <span>额: {formatMoney(s.turnover)}</span>
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
                  <th>净流入占比</th>
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
                    <td className="mono">{(s.lead_flow_pct || 0).toFixed(1)}%</td>
                  </tr>
                ))}
                {hotStocks.length === 0 && (
                  <tr><td colSpan={6} className="empty-cell">暂无数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeSection === 'boards' && (
          boardDetail ? (
            <div className="board-detail">
              <div className="board-detail-header">
                <button className="filter-chip" onClick={() => setBoardDetail(null)}>← 返回板块</button>
                <span className="board-detail-name">{boardDetail.name}</span>
                <span className={`board-detail-pct ${boardDetail.stocks.length > 0 && boardDetail.stocks[0]?.change_pct > 0 ? 'up' : 'down'}`}>
                  {boardDetail.stocks.length > 0 ? `${boardDetail.stocks[0].change_pct > 0 ? '+' : ''}${boardDetail.stocks[0].change_pct.toFixed(2)}%` : ''}
                </span>
              </div>
              <div className="market-table-wrapper">
                <table className="market-table">
                  <thead>
                    <tr>
                      <th>代码</th><th>名称</th><th>现价</th><th>涨跌幅</th><th>成交量</th><th>成交额</th>
                    </tr>
                  </thead>
                  <tbody>
                    {boardDetail.stocks.map((s) => (
                      <tr key={s.symbol} onClick={() => { onSelectStock(s.symbol); onSwitchToChart(); }} className="market-row-clickable">
                        <td className="mono">{s.symbol}</td>
                        <td className="name-cell">{s.name}</td>
                        <td className="mono">{s.price > 0 ? '¥' + s.price.toFixed(2) : '--'}</td>
                        <td className={`mono ${s.change_pct >= 0 ? 'up' : 'down'}`}>
                          {s.change_pct >= 0 ? '+' : ''}{s.change_pct.toFixed(2)}%
                        </td>
                        <td className="mono">{formatVol(s.volume)}</td>
                        <td className="mono">{formatMoney(s.turnover)}</td>
                      </tr>
                    ))}
                    {boardDetail.stocks.length === 0 && (
                      <tr><td colSpan={6} className="empty-cell">加载中...</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="boards-grid">
              {boards.map((b) => (
                <div
                  key={b.symbol || b.name}
                  className={`board-card ${b.direction}`}
                  onClick={() => handleBoardClick(b)}
                  style={{ cursor: 'pointer' }}
                >
                  <div className="board-name">{b.name}</div>
                  <div className={`board-pct ${b.direction}`}>
                    {b.change_pct >= 0 ? '+' : ''}{b.change_pct.toFixed(2)}%
                  </div>
                  {b.lead_flow !== undefined && (
                    <div className="board-flow">
                      主力 {b.lead_flow > 0 ? '+' : ''}{formatMoney(b.lead_flow)}
                    </div>
                  )}
                </div>
              ))}
              {boards.length === 0 && <div className="limit-empty">暂无板块数据</div>}
            </div>
          )
        )}

        {activeSection === 'summary' && summary && (
          <div className="market-summary-detail">
            <div className="summary-card">
              <div className="summary-card-title">涨跌统计</div>
              <div className="summary-grid">
                <div className="summary-grid-item">
                  <div className="sgi-label">上涨家数</div>
                  <div className="sgi-value up">{summary.up_count}</div>
                </div>
                <div className="summary-grid-item">
                  <div className="sgi-label">下跌家数</div>
                  <div className="sgi-value down">{summary.down_count}</div>
                </div>
                <div className="summary-grid-item">
                  <div className="sgi-label">涨停家数</div>
                  <div className="sgi-value accent-red">{summary.limit_up_count}</div>
                </div>
                <div className="summary-grid-item">
                  <div className="sgi-label">跌停家数</div>
                  <div className="sgi-value accent-green">{summary.limit_down_count}</div>
                </div>
              </div>
              <div className="summary-bar">
                {summary.up_count + summary.down_count > 0 ? (
                  <div
                    className="summary-bar-fill up"
                    style={{ width: `${(summary.up_count / (summary.up_count + summary.down_count)) * 100}%` }}
                  />
                ) : null}
              </div>
              <div className="summary-bar-labels">
                <span className="up">{summary.up_count} 上涨</span>
                <span className="down">{summary.down_count} 下跌</span>
              </div>
            </div>

            <div className="summary-card">
              <div className="summary-card-title">板块统计</div>
              <div className="summary-grid">
                <div className="summary-grid-item">
                  <div className="sgi-label">上涨板块</div>
                  <div className="sgi-value up">{summary.advancing_boards}</div>
                </div>
                <div className="summary-grid-item">
                  <div className="sgi-label">下跌板块</div>
                  <div className="sgi-value down">{summary.declining_boards}</div>
                </div>
                <div className="summary-grid-item">
                  <div className="sgi-label">平盘</div>
                  <div className="sgi-value">
                    {Math.max(0, 80 - summary.advancing_boards - summary.declining_boards)}
                  </div>
                </div>
              </div>
              {summary.advancing_boards + summary.declining_boards > 0 && (
                <div className="summary-bar">
                  <div
                    className="summary-bar-fill up"
                    style={{ width: `${(summary.advancing_boards / (summary.advancing_boards + summary.declining_boards)) * 100}%` }}
                  />
                </div>
              )}
              <div className="summary-bar-labels">
                <span className="up">{summary.advancing_boards} 上涨</span>
                <span className="down">{summary.declining_boards} 下跌</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
