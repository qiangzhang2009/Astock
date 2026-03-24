import { useState, useEffect } from 'react';
import axios from 'axios';
import type { SimilarPeriod } from '../types';

interface Props {
  symbol: string;
  date: string;
  onClose: () => void;
}

export default function SimilarDaysPanel({ symbol, date, onClose }: Props) {
  const [periods, setPeriods] = useState<SimilarPeriod[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!symbol || !date) return;
    setLoading(true);
    setError('');
    axios.get(`/api/predict/${symbol}/similar-days?date=${date}`)
      .then(res => {
        const data = res.data;
        setPeriods(Array.isArray(data) ? data : (data?.similar_periods || []));
      })
      .catch(() => setError('加载相似历史区间失败'))
      .finally(() => setLoading(false));
  }, [symbol, date]);

  return (
    <div className="similar-panel">
      <div className="similar-header">
        <div className="similar-title">
          与 <span style={{ color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>{date}</span> 相似的历史区间
        </div>
        <button className="similar-close" onClick={onClose}>×</button>
      </div>

      {loading ? (
        <div className="loading-spinner">
          <div className="spinner" />
          <span>寻找相似区间...</span>
        </div>
      ) : error ? (
        <div className="news-empty" style={{ color: 'var(--chart-red)' }}>{error}</div>
      ) : periods.length === 0 ? (
        <div className="news-empty">暂无相似历史区间</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {periods.map((period, i) => {
            const change = period.price_change_pct;
            const isUp = change >= 0;
            const sim = period.similarity;
            return (
              <div
                key={i}
                className="fc-period-card"
                style={{ cursor: 'default' }}
              >
                <div className="fc-period-header">
                  <span className="fc-period-dates">
                    {period.start_date} ~ {period.end_date}
                  </span>
                  <span className="fc-period-sim" style={{ fontSize: 10, color: 'var(--accent-yellow)', fontFamily: 'var(--font-mono)' }}>
                    相似度 {typeof sim === 'number' ? (sim * 100).toFixed(0) : '--'}%
                  </span>
                </div>
                <div className="fc-period-detail">
                  <span>区间涨跌: </span>
                  <span className={isUp ? 'up' : 'down'}>
                    {isUp ? '+' : ''}{change.toFixed(2)}%
                  </span>
                </div>
                {(period.ret_t1 != null || period.ret_t3 != null || period.ret_t5 != null) && (
                  <div style={{ display: 'flex', gap: 8, fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                    {period.ret_t1 != null && (
                      <span>T+1: <span className={period.ret_t1 >= 0 ? 'up' : 'down'}>{period.ret_t1 >= 0 ? '+' : ''}{period.ret_t1.toFixed(2)}%</span></span>
                    )}
                    {period.ret_t3 != null && (
                      <span>T+3: <span className={period.ret_t3 >= 0 ? 'up' : 'down'}>{period.ret_t3 >= 0 ? '+' : ''}{period.ret_t3.toFixed(2)}%</span></span>
                    )}
                    {period.ret_t5 != null && (
                      <span>T+5: <span className={period.ret_t5 >= 0 ? 'up' : 'down'}>{period.ret_t5 >= 0 ? '+' : ''}{period.ret_t5.toFixed(2)}%</span></span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Summary */}
      {periods.length > 0 && (
        <div className="fc-similar-section" style={{ marginTop: 12 }}>
          <div className="fc-section-divider">统计规律</div>
          <div className="fc-similar-stats">
            <div className="fc-stat">
              <span className="fc-stat-label">相似区间数</span>
              <span className="fc-stat-value">{periods.length}</span>
            </div>
            <div className="fc-stat">
              <span className="fc-stat-label">区间平均涨跌</span>
              <span className={`fc-stat-value ${
                (periods.reduce((s, p) => s + p.price_change_pct, 0) / periods.length) >= 0 ? 'up' : 'down'
              }`}>
                {(() => {
                  const avg = periods.reduce((s, p) => s + p.price_change_pct, 0) / periods.length;
                  return `${avg >= 0 ? '+' : ''}${avg.toFixed(2)}%`;
                })()}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
