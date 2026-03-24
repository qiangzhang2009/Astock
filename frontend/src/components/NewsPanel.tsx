import { useState, useEffect } from 'react';
import axios from 'axios';
import type { NewsItem } from '../types';

interface Props {
  symbol: string;
  hoveredDate: string | null;
  onFindSimilar: (newsId: string) => void;
  highlightedNewsId: string | null;
  isLocked: boolean;
  onUnlock: () => void;
  highlightedCategoryIds?: string[];
}

export default function NewsPanel({
  symbol,
  hoveredDate,
  onFindSimilar,
  highlightedNewsId,
  isLocked,
  onUnlock,
  highlightedCategoryIds,
}: Props) {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError('');
    const url = hoveredDate
      ? `/api/news/${symbol}?date=${hoveredDate}`
      : `/api/news/${symbol}`;
    axios.get(url)
      .then(res => setNews(res.data || []))
      .catch(() => setError('加载新闻失败'))
      .finally(() => setLoading(false));
  }, [symbol, hoveredDate]);

  if (loading) {
    return (
      <div className="news-panel">
        <div className="loading-spinner">
          <div className="spinner" />
          <span>加载新闻...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="news-panel">
        <div className="news-empty" style={{ color: 'var(--chart-red)' }}>{error}</div>
      </div>
    );
  }

  // Filter news to only show highlighted category items if filter is active
  const displayedNews = highlightedCategoryIds && highlightedCategoryIds.length > 0
    ? news.filter(n => highlightedCategoryIds.includes(n.news_id))
    : news;

  return (
    <div className="news-panel">
      {/* Panel header */}
      <div className="news-panel-header">
        <span>
          {hoveredDate ? `${hoveredDate} 新闻` : '最新新闻'}
          <span style={{ fontWeight: 400, marginLeft: 6, color: 'var(--text-muted)', fontSize: 11 }}>
            ({displayedNews.length})
          </span>
        </span>
        {isLocked && (
          <button
            className="filter-chip active"
            onClick={onUnlock}
            style={{ fontSize: 10, padding: '2px 6px' }}
          >
            取消锁定
          </button>
        )}
      </div>

      <div className="news-panel-content">
        {displayedNews.length === 0 ? (
          <div className="news-empty">
            {highlightedCategoryIds && highlightedCategoryIds.length > 0
              ? '该分类下暂无新闻'
              : '暂无新闻数据'}
          </div>
        ) : (
          displayedNews.map(item => {
            const isHighlighted = highlightedNewsId === item.news_id;
            const sentiment = item.sentiment || 'neutral';
            const sentimentLabel = item.sentiment_cn ||
              (sentiment === 'positive' ? '利好' : sentiment === 'negative' ? '利空' : '中性');
            const sentimentClass = sentiment;

            const tradeDate = item.date || item.trade_date;
            const displayDate = tradeDate
              ? tradeDate.slice(0, 10).replace(/-/g, '/')
              : '';

            const relevanceLabel = item.relevance === 'high' ? '强相关' :
              item.relevance === 'low' ? '弱相关' : '中相关';

            return (
              <div
                key={item.news_id}
                className={`news-card ${isHighlighted ? 'highlighted' : ''} ${isHighlighted ? 'locked' : ''}`}
                onClick={() => onFindSimilar(item.news_id)}
              >
                <div className="news-card-header">
                  {displayDate && <span className="news-date">{displayDate}</span>}
                  <span className={`sentiment-badge ${sentimentClass}`}>{sentimentLabel}</span>
                  {item.relevance && (
                    <span className="relevance-badge">{relevanceLabel}</span>
                  )}
                </div>

                <div className="news-title">{item.title}</div>

                {item.source && (
                  <div className="news-source">{item.source}</div>
                )}

                {/* Returns row */}
                {(item.ret_t0 != null || item.ret_t1 != null || item.ret_t3 != null || item.ret_t5 != null) && (
                  <div className="news-ret">
                    {item.ret_t0 != null && (
                      <span>
                        当日: <span className={item.ret_t0 >= 0 ? 'up' : 'down'}>
                          {item.ret_t0 >= 0 ? '+' : ''}{typeof item.ret_t0 === 'number' ? item.ret_t0.toFixed(2) : item.ret_t0}%
                        </span>
                      </span>
                    )}
                    {item.ret_t1 != null && (
                      <span>
                        T+1: <span className={item.ret_t1 >= 0 ? 'up' : 'down'}>
                          {item.ret_t1 >= 0 ? '+' : ''}{typeof item.ret_t1 === 'number' ? item.ret_t1.toFixed(2) : item.ret_t1}%
                        </span>
                      </span>
                    )}
                    {item.ret_t3 != null && (
                      <span>
                        T+3: <span className={item.ret_t3 >= 0 ? 'up' : 'down'}>
                          {item.ret_t3 >= 0 ? '+' : ''}{typeof item.ret_t3 === 'number' ? item.ret_t3.toFixed(2) : item.ret_t3}%
                        </span>
                      </span>
                    )}
                    {item.ret_t5 != null && (
                      <span>
                        T+5: <span className={item.ret_t5 >= 0 ? 'up' : 'down'}>
                          {item.ret_t5 >= 0 ? '+' : ''}{typeof item.ret_t5 === 'number' ? item.ret_t5.toFixed(2) : item.ret_t5}%
                        </span>
                      </span>
                    )}
                  </div>
                )}

                {/* Key discussion (if present) */}
                {item.key_discussion && (
                  <div className="news-key-discussion">{item.key_discussion}</div>
                )}

                {/* Reason tags */}
                {(item.reason_growth || item.reason_decrease) && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 4 }}>
                    {item.reason_growth && (
                      <span style={{
                        fontSize: 10, padding: '1px 6px', borderRadius: 4,
                        background: 'rgba(38,166,154,0.1)', color: 'var(--chart-green)',
                        border: '1px solid rgba(38,166,154,0.2)',
                      }}>
                        ▲ {item.reason_growth.slice(0, 30)}
                      </span>
                    )}
                    {item.reason_decrease && (
                      <span style={{
                        fontSize: 10, padding: '1px 6px', borderRadius: 4,
                        background: 'rgba(239,83,80,0.1)', color: 'var(--chart-red)',
                        border: '1px solid rgba(239,83,80,0.2)',
                      }}>
                        ▼ {item.reason_decrease.slice(0, 30)}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
