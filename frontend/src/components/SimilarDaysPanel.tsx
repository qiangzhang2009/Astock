import { useState, useEffect } from 'react';
import axios from 'axios';

interface Props {
  symbol: string;
  date: string;
  onClose: () => void;
}

export default function SimilarDaysPanel({ symbol, date, onClose }: Props) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    axios.get(`/api/predict/${symbol}/similar-days?date=${date}`)
      .then((r) => setData(r.data || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [symbol, date]);

  return (
    <div className="similar-panel">
      <div className="similar-header">
        <div className="similar-title">
          相似历史区间
          <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            ({data.length} 个相似区间)
          </span>
        </div>
        <button className="similar-close" onClick={onClose}>×</button>
      </div>

      {loading ? (
        <div className="loading-spinner"><div className="spinner" />加载中</div>
      ) : data.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📊</div>
          <div>暂无相似历史区间</div>
        </div>
      ) : (
        data.map((p, i) => (
          <div key={i} className="fc-period-card">
            <div className="fc-period-header">
              <span className="fc-period-dates">{p.period_start} ~ {p.period_end}</span>
              <span className="fc-period-sim">{(p.similarity * 100).toFixed(0)}% 相似</span>
            </div>
            <div className="fc-period-detail">
              <span>{p.n_articles} 条新闻</span>
              {p.ret_after_5d != null && (
                <span className={p.ret_after_5d >= 0 ? 'up' : 'down'}>
                  5日: {p.ret_after_5d >= 0 ? '+' : ''}{p.ret_after_5d.toFixed(1)}%
                </span>
              )}
              {p.ret_after_10d != null && (
                <span className={p.ret_after_10d >= 0 ? 'up' : 'down'}>
                  10日: {p.ret_after_10d >= 0 ? '+' : ''}{p.ret_after_10d.toFixed(1)}%
                </span>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
