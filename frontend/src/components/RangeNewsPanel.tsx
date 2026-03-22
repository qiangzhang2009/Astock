import { useState, useEffect } from 'react';
import axios from 'axios';

interface Props {
  symbol: string;
  startDate: string;
  endDate: string;
  priceChange?: number;
  onClose: () => void;
  onAskAI?: (question: string) => void;
}

interface RangeAnalysisData {
  price_change_pct: number;
  news_count: number;
  analysis: string;
  prices: any[];
  news: any[];
}

export default function RangeNewsPanel({ symbol, startDate, endDate, priceChange, onClose }: Props) {
  const [data, setData] = useState<RangeAnalysisData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    axios.get(`/api/news/${symbol}/range?start=${startDate}&end=${endDate}`)
      .then((r) => setData(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [symbol, startDate, endDate]);

  const change = data?.price_change_pct ?? priceChange ?? 0;

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
            {startDate} ~ {endDate}
          </div>
          <div style={{ fontSize: 12, color: change >= 0 ? 'var(--chart-green)' : 'var(--chart-red)', fontWeight: 700, fontFamily: 'Menlo, monospace' }}>
            {change >= 0 ? '+' : ''}{change.toFixed(2)}%
          </div>
        </div>
        <button
          onClick={onClose}
          style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: 16, cursor: 'pointer' }}
        >×</button>
      </div>

      {loading ? (
        <div className="loading-spinner"><div className="spinner" />加载中</div>
      ) : data ? (
        <>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
            共 {data.news_count} 条新闻
          </div>
          {data.news?.slice(0, 10).map((n: any) => (
            <div key={n.news_id} style={{ padding: '8px 0', borderBottom: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, fontFamily: 'Menlo, monospace' }}>
                {n.trade_date} {n.source}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 4, lineHeight: 1.4 }}>
                {n.title}
              </div>
              {n.sentiment && (
                <span className={`sentiment-badge ${n.sentiment}`}>
                  {n.sentiment_cn || n.sentiment}
                </span>
              )}
              {n.ret_t1 != null && (
                <span style={{ marginLeft: 8, fontSize: 11, fontFamily: 'Menlo, monospace', color: n.ret_t1 >= 0 ? 'var(--chart-green)' : 'var(--chart-red)' }}>
                  T+1: {n.ret_t1 >= 0 ? '+' : ''}{n.ret_t1.toFixed(2)}%
                </span>
              )}
            </div>
          ))}
        </>
      ) : (
        <div className="empty-state">
          <div className="empty-state-icon">📰</div>
          <div>暂无新闻数据</div>
        </div>
      )}
    </div>
  );
}
