import { useState, useEffect } from 'react';
import axios from 'axios';
import type { NewsItem } from '../types';

interface Props {
  symbol: string;
  startDate: string;
  endDate: string;
  priceChange?: number;
  onClose: () => void;
  onAskAI: (question: string) => void;
}

export default function RangeNewsPanel({
  symbol,
  startDate,
  endDate,
  priceChange,
  onClose,
  onAskAI,
}: Props) {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!symbol || !startDate || !endDate) return;
    setLoading(true);
    setError('');
    axios.get(`/api/news/${symbol}/range?start=${startDate}&end=${endDate}`)
      .then(res => setNews(res.data || []))
      .catch(() => setError('加载区间新闻失败'))
      .finally(() => setLoading(false));
  }, [symbol, startDate, endDate]);

  const changePct = priceChange ?? 0;
  const isUp = changePct >= 0;

  return (
    <div className="news-panel">
      {/* Header */}
      <div className="news-panel-header">
        <span>
          {startDate} ~ {endDate}
          <span style={{
            marginLeft: 6,
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: isUp ? 'var(--chart-green)' : 'var(--chart-red)',
            fontWeight: 700,
          }}>
            {isUp ? '+' : ''}{changePct.toFixed(2)}%
          </span>
        </span>
        <button
          className="filter-chip"
          onClick={onClose}
          style={{ fontSize: 10, padding: '2px 6px' }}
        >
          关闭
        </button>
      </div>

      {/* Summary bar */}
      {news.length > 0 && (
        <div style={{
          padding: '6px 12px',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          gap: 8,
          fontSize: 11,
          background: 'var(--bg-secondary)',
        }}>
          {(() => {
            const positive = news.filter(n => n.sentiment === 'positive').length;
            const negative = news.filter(n => n.sentiment === 'negative').length;
            const neutral = news.filter(n => n.sentiment === 'neutral' || !n.sentiment).length;
            return (
              <>
                <span style={{ color: 'var(--chart-green)' }}>▲ 利好 {positive}</span>
                <span style={{ color: 'var(--chart-red)' }}>▼ 利空 {negative}</span>
                <span style={{ color: 'var(--text-muted)' }}>— 中性 {neutral}</span>
              </>
            );
          })()}
        </div>
      )}

      {/* Ask AI button */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border-color)' }}>
        <button
          className="filter-chip"
          onClick={() => onAskAI('这段区间发生了什么？涨跌原因是什么？有哪些重大新闻？')}
          style={{ width: '100%', justifyContent: 'center', color: 'var(--accent-blue)' }}
        >
          🤖 询问 AI：这个区间发生了什么？
        </button>
      </div>

      {/* News list */}
      <div className="news-panel-content">
        {loading ? (
          <div className="loading-spinner">
            <div className="spinner" />
            <span>加载区间新闻...</span>
          </div>
        ) : error ? (
          <div className="news-empty" style={{ color: 'var(--chart-red)' }}>{error}</div>
        ) : news.length === 0 ? (
          <div className="news-empty">该区间暂无新闻</div>
        ) : (
          news.map(item => {
            const sentiment = item.sentiment || 'neutral';
            const sentimentLabel = item.sentiment_cn ||
              (sentiment === 'positive' ? '利好' : sentiment === 'negative' ? '利空' : '中性');

            return (
              <div key={item.news_id} className="news-card">
                <div className="news-card-header">
                  {item.date && (
                    <span className="news-date">{item.date.slice(0, 10).replace(/-/g, '/')}</span>
                  )}
                  <span className={`sentiment-badge ${sentiment}`}>{sentimentLabel}</span>
                </div>
                <div className="news-title">{item.title}</div>
                {item.source && <div className="news-source">{item.source}</div>}

                {(item.reason_growth || item.reason_decrease) && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 4 }}>
                    {item.reason_growth && (
                      <span style={{
                        fontSize: 11, padding: '2px 6px', borderRadius: 4,
                        background: 'rgba(38,166,154,0.08)', color: 'var(--chart-green)',
                        borderLeft: '2px solid var(--chart-green)',
                      }}>
                        ▲ {item.reason_growth}
                      </span>
                    )}
                    {item.reason_decrease && (
                      <span style={{
                        fontSize: 11, padding: '2px 6px', borderRadius: 4,
                        background: 'rgba(239,83,80,0.08)', color: 'var(--chart-red)',
                        borderLeft: '2px solid var(--chart-red)',
                      }}>
                        ▼ {item.reason_decrease}
                      </span>
                    )}
                  </div>
                )}

                {item.key_discussion && (
                  <div className="news-key-discussion">{item.key_discussion}</div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
