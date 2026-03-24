import { useState, useEffect } from 'react';
import axios from 'axios';
import type { PredictionForecast, DeepAnalysis } from '../types';

interface Props {
  symbol: string;
}

export default function PredictionPanel({ symbol }: Props) {
  const [forecast, setForecast] = useState<PredictionForecast | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [deepLoading, setDeepLoading] = useState<string | null>(null);
  const [deepResults, setDeepResults] = useState<Record<string, DeepAnalysis>>({});
  const [error, setError] = useState('');

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError('');
    setForecast(null);
    setExpanded(false);
    setDeepResults({});
    axios.get(`/api/predict/${symbol}/forecast?window=7`)
      .then(res => setForecast(res.data || null))
      .catch(() => setError('预测加载失败'))
      .finally(() => setLoading(false));
  }, [symbol]);

  async function handleDeepAnalysis(newsId: string) {
    if (deepResults[newsId] || deepLoading) return;
    setDeepLoading(newsId);
    try {
      const res = await axios.post('/api/analysis/deep', { news_id: newsId, symbol });
      setDeepResults(prev => ({ ...prev, [newsId]: res.data }));
    } catch {
      // silently fail
    } finally {
      setDeepLoading(null);
    }
  }

  const dir = forecast?.prediction?.direction;
  const conf = forecast?.prediction?.confidence;
  const isUp = dir === 'up';
  const isDown = dir === 'down';

  if (loading) {
    return (
      <div className="pred-panel">
        <div className="pred-header" style={{ cursor: 'default' }}>
          <div className="pred-loading-dot" />
          <span className="pred-loading-text">AI 分析中...</span>
        </div>
      </div>
    );
  }

  if (error || !forecast) {
    return (
      <div className="pred-panel">
        <div className="pred-header" style={{ cursor: 'default' }}>
          <span className="pred-title" style={{ color: 'var(--text-muted)' }}>AI 预测</span>
          <span className="pred-no-model">{error || '暂无数据'}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="pred-panel">
      {/* Collapsed header */}
      <div className="pred-header" onClick={() => setExpanded(v => !v)}>
        <span className="pred-title">AI 预测</span>
        {dir ? (
          <>
            <span className={`pred-arrow ${isUp ? 'up' : isDown ? 'down' : ''}`}>
              {isUp ? '▲' : isDown ? '▼' : '—'}
            </span>
            <span className={`pred-dir ${isUp ? 'up' : isDown ? 'down' : ''}`}>
              {isUp ? '看涨' : isDown ? '看跌' : '中性'}
            </span>
            {conf != null && (
              <div className="pred-conf-bar">
                <div
                  className={`pred-conf-fill ${isUp ? 'up' : 'down'}`}
                  style={{ width: `${Math.min(100, (conf * 100))}%` }}
                />
              </div>
            )}
            {conf != null && (
              <span className="pred-conf-label">{typeof conf === 'number' ? (conf * 100).toFixed(0) : '--'}%</span>
            )}
          </>
        ) : (
          <span className="pred-no-model">{forecast.conclusion?.slice(0, 30) || '数据不足'}</span>
        )}
        <span className="pred-expand-icon">{expanded ? '▲' : '▼'}</span>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="pred-details">
          {/* Conclusion */}
          {forecast.conclusion && (
            <div style={{
              fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5,
              padding: '8px 10px', background: 'var(--bg-tertiary)', borderRadius: 6,
              marginBottom: 10, borderLeft: '3px solid var(--accent-blue)',
            }}>
              {forecast.conclusion}
            </div>
          )}

          {/* Period predictions */}
          {(forecast.prediction?.t1 || forecast.prediction?.t3 || forecast.prediction?.t5) && (
            <div className="fc-predictions">
              {[
                { key: 't1', label: 'T+1', pred: forecast.prediction?.t1 },
                { key: 't3', label: 'T+3', pred: forecast.prediction?.t3 },
                { key: 't5', label: 'T+5', pred: forecast.prediction?.t5 },
              ].filter(p => p.pred).map(p => (
                <div key={p.key} className={`fc-pred-card ${p.pred?.direction === 'up' ? 'up' : 'down'}`}>
                  <div className="fc-pred-header">
                    <span className="fc-pred-label">{p.label}</span>
                    <span className={`fc-pred-dir ${p.pred?.direction === 'up' ? 'up' : 'down'}`}>
                      {p.pred?.direction === 'up' ? '▲' : p.pred?.direction === 'down' ? '▼' : '—'}
                      {' '}{p.pred?.direction === 'up' ? '涨' : p.pred?.direction === 'down' ? '跌' : '中性'}
                    </span>
                    <span className="fc-pred-conf">
                      {typeof p.pred?.confidence === 'number' ? `${(p.pred.confidence * 100).toFixed(0)}%` : '--'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Similar periods */}
          {forecast.similar_periods && forecast.similar_periods.length > 0 && (
            <div className="fc-similar-section">
              <div className="fc-section-divider">相似历史区间</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6 }}>
                共找到 {forecast.similar_periods.length} 个相似区间
              </div>
              {forecast.similar_periods.slice(0, 3).map((period, i) => {
                const chg = period.price_change_pct;
                return (
                  <div key={i} className="fc-period-card">
                    <div className="fc-period-header">
                      <span className="fc-period-dates">{period.start_date} ~ {period.end_date}</span>
                      <span className="fc-period-sim">
                        {typeof period.similarity === 'number' ? `${(period.similarity * 100).toFixed(0)}%` : '--'}
                      </span>
                    </div>
                    <div className="fc-period-detail">
                      <span>涨跌: </span>
                      <span className={chg >= 0 ? 'up' : 'down'}>
                        {chg >= 0 ? '+' : ''}{chg.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Top headlines */}
          {forecast.news_summary && forecast.news_summary.top_headlines?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="fc-section-divider">近期新闻</div>
              <ul className="fc-bullet-list">
                {forecast.news_summary.top_headlines.map((h, i) => (
                  <li key={i} className="fc-bullet-item">
                    <span className={h.sentiment === 'positive' ? 'fc-text-bull' : h.sentiment === 'negative' ? 'fc-text-bear' : ''}>
                      {h.sentiment === 'positive' ? '▲' : h.sentiment === 'negative' ? '▼' : '—'}
                    </span>
                    {' '}{h.title?.slice(0, 60)}{h.title && h.title.length > 60 ? '...' : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Top impact */}
          {forecast.news_summary && forecast.news_summary.top_impact?.length > 0 && (
            <div className="fc-impact-section">
              <div className="fc-section-divider">重大影响新闻</div>
              {forecast.news_summary.top_impact.map((item, i) => (
                <div key={i} className={`fc-impact-card fc-impact-${item.sentiment === 'positive' ? 'up' : 'down'}`}>
                  <div className="fc-impact-header">
                    <span className={`fc-impact-ret ${item.sentiment === 'positive' ? 'up' : 'down'}`}>
                      {item.ret_t1 >= 0 ? '+' : ''}{typeof item.ret_t1 === 'number' ? item.ret_t1.toFixed(2) : '--'}%
                    </span>
                    <span className={`fc-impact-sentiment ${item.sentiment}`}>
                      {item.sentiment === 'positive' ? '利好' : item.sentiment === 'negative' ? '利空' : '中性'}
                    </span>
                    <span className="fc-impact-date">{item.sentiment === 'positive' ? '▲' : '▼'}</span>
                  </div>
                  <div className="fc-impact-title">{item.title?.slice(0, 60)}{item.title && item.title.length > 60 ? '...' : ''}</div>
                </div>
              ))}
            </div>
          )}

          {/* Deep analysis buttons */}
          {forecast.news_summary?.top_headlines?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="fc-section-divider">深度分析</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {forecast.news_summary.top_headlines.slice(0, 3).map((h) => (
                  <button
                    key={h.news_id}
                    className="fc-deep-btn"
                    onClick={() => handleDeepAnalysis(h.news_id)}
                    disabled={!!deepResults[h.news_id] || deepLoading === h.news_id}
                  >
                    {deepLoading === h.news_id ? '分析中...' :
                      deepResults[h.news_id] ? `✓ ${h.title?.slice(0, 30)}...` :
                        `🤖 深度分析: ${h.title?.slice(0, 35)}...`}
                  </button>
                ))}
              </div>

              {/* Deep analysis results */}
              {Object.entries(deepResults).map(([newsId, result]) => (
                <div
                  key={newsId}
                  style={{
                    marginTop: 8, padding: 10, background: 'var(--bg-tertiary)',
                    borderRadius: 6, border: '1px solid var(--border-color)',
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                    {result.title}
                  </div>
                  {result.sentiment_cn && (
                    <div style={{ fontSize: 11, marginBottom: 4 }}>
                      <span style={{
                        padding: '1px 6px', borderRadius: 4,
                        background: result.sentiment === 'positive' ? 'rgba(63,185,80,0.15)' :
                          result.sentiment === 'negative' ? 'rgba(239,83,80,0.15)' : 'rgba(139,148,158,0.1)',
                        color: result.sentiment === 'positive' ? 'var(--chart-green)' :
                          result.sentiment === 'negative' ? 'var(--chart-red)' : 'var(--text-secondary)',
                      }}>
                        {result.sentiment_cn}
                      </span>
                    </div>
                  )}
                  {result.reason_growth && (
                    <div style={{ fontSize: 11, color: 'var(--chart-green)', marginBottom: 2 }}>
                      ▲ {result.reason_growth}
                    </div>
                  )}
                  {result.reason_decrease && (
                    <div style={{ fontSize: 11, color: 'var(--chart-red)', marginBottom: 2 }}>
                      ▼ {result.reason_decrease}
                    </div>
                  )}
                  {result.returns && (
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
                      收益: T0={result.returns.t0 != null ? `${result.returns.t0 >= 0 ? '+' : ''}${result.returns.t0.toFixed(2)}%` : '--'} |{' '}
                      T1={result.returns.t1 != null ? `${result.returns.t1 >= 0 ? '+' : ''}${result.returns.t1.toFixed(2)}%` : '--'} |{' '}
                      T3={result.returns.t3 != null ? `${result.returns.t3 >= 0 ? '+' : ''}${result.returns.t3.toFixed(2)}%` : '--'}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Similar stats */}
          {forecast.similar_stats && forecast.similar_stats.count > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="fc-section-divider">历史统计</div>
              <div className="fc-similar-stats">
                <div className="fc-stat">
                  <span className="fc-stat-label">历史样本</span>
                  <span className="fc-stat-value">{forecast.similar_stats.count}</span>
                </div>
                <div className="fc-stat">
                  <span className="fc-stat-label">5日上涨率</span>
                  <span className={`fc-stat-value ${forecast.similar_stats.up_ratio_5d >= 0.5 ? 'up' : 'down'}`}>
                    {(forecast.similar_stats.up_ratio_5d * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="fc-stat">
                  <span className="fc-stat-label">10日上涨率</span>
                  <span className={`fc-stat-value ${forecast.similar_stats.up_ratio_10d >= 0.5 ? 'up' : 'down'}`}>
                    {(forecast.similar_stats.up_ratio_10d * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="fc-stat">
                  <span className="fc-stat-label">平均5日收益</span>
                  <span className={`fc-stat-value ${(forecast.similar_stats.avg_ret_5d ?? 0) >= 0 ? 'up' : 'down'}`}>
                    {forecast.similar_stats.avg_ret_5d != null
                      ? `${(forecast.similar_stats.avg_ret_5d ?? 0) >= 0 ? '+' : ''}${(forecast.similar_stats.avg_ret_5d ?? 0).toFixed(2)}%`
                      : '--'}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
