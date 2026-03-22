import { useState, useEffect } from 'react';
import axios from 'axios';
import type { NewsItem } from '../types';

interface Props {
  symbol: string;
  hoveredDate: string | null;
  highlightedNewsId: string | null;
  isLocked: boolean;
  onFindSimilar?: (newsId: string) => void;
  onUnlock: () => void;
  highlightedCategoryIds?: string[];
}

export default function NewsPanel({
  symbol, hoveredDate, highlightedNewsId, isLocked,
  onUnlock, highlightedCategoryIds,
}: Props) {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!hoveredDate) { setNews([]); return; }
    setLoading(true);
    axios.get(`/api/news/${symbol}?date=${hoveredDate}`)
      .then((r) => setNews(r.data))
      .catch(() => setNews([]))
      .finally(() => setLoading(false));
  }, [symbol, hoveredDate]);

  if (!hoveredDate) {
    return (
      <div className="news-panel">
        <div className="news-panel-header">
          <span>新闻</span>
        </div>
        <div className="news-empty">将鼠标移到 K 线查看当日新闻</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="news-panel">
        <div className="news-panel-header">
          <span>{hoveredDate} 新闻</span>
          <div className="loading-spinner"><div className="spinner" />加载中</div>
        </div>
      </div>
    );
  }

  return (
    <div className="news-panel">
      <div className="news-panel-header">
        <span>{hoveredDate} 新闻</span>
        {isLocked && (
          <button
            onClick={onUnlock}
            style={{ background: 'transparent', border: 'none', color: 'var(--accent-blue)', fontSize: 11, cursor: 'pointer', padding: 0 }}
          >
            解除锁定
          </button>
        )}
      </div>
      <div className="news-panel-content">
        {news.length === 0 ? (
          <div className="news-empty">该日暂无新闻数据</div>
        ) : news.map((item) => {
          const isHighlighted = highlightedCategoryIds?.includes(item.news_id);
          const isSelected = highlightedNewsId === item.news_id;
          const cardClass = [
            'news-card',
            isHighlighted ? 'highlighted' : '',
            isSelected ? 'locked' : '',
          ].filter(Boolean).join(' ');

          return (
            <div key={item.news_id} className={cardClass}>
              <div className="news-card-header">
                <span className="news-date">{item.published_at?.slice(11, 16) || ''}</span>
                {item.sentiment && (
                  <span className={`sentiment-badge ${item.sentiment}`}>
                    {item.sentiment_cn || item.sentiment}
                  </span>
                )}
                {item.relevance === 'high' && <span className="relevance-badge">高相关</span>}
                {item.ret_t0 != null && (
                  <span className={`news-ret ${item.ret_t0 >= 0 ? 'up' : 'down'}`}>
                    当日 {item.ret_t0 >= 0 ? '+' : ''}{item.ret_t0?.toFixed(2)}%
                  </span>
                )}
              </div>
              <div className="news-title">{item.title}</div>
              <div className="news-source">{item.source}</div>
              {item.key_discussion && (
                <div className="news-key-discussion">{item.key_discussion}</div>
              )}
              {item.reason_growth && (
                <div style={{ fontSize: 11, color: 'var(--chart-green)', marginTop: 4, padding: '4px 6px', background: 'rgba(63,185,80,0.08)', borderRadius: 4, borderLeft: '2px solid var(--chart-green)' }}>
                  ▲ {item.reason_growth}
                </div>
              )}
              {item.reason_decrease && (
                <div style={{ fontSize: 11, color: 'var(--chart-red)', marginTop: 4, padding: '4px 6px', background: 'rgba(248,81,73,0.08)', borderRadius: 4, borderLeft: '2px solid var(--chart-red)' }}>
                  ▼ {item.reason_decrease}
                </div>
              )}
              {item.ret_t1 != null && (
                <div className="news-ret">
                  <span>T+1:</span>
                  <span className={item.ret_t1 >= 0 ? 'up' : 'down'}>
                    {item.ret_t1 >= 0 ? '+' : ''}{item.ret_t1.toFixed(2)}%
                  </span>
                  {item.ret_t3 != null && <>
                    <span style={{ marginLeft: 8 }}>T+3:</span>
                    <span className={item.ret_t3 >= 0 ? 'up' : 'down'}>
                      {item.ret_t3 >= 0 ? '+' : ''}{item.ret_t3.toFixed(2)}%
                    </span>
                  </>}
                  {item.ret_t5 != null && <>
                    <span style={{ marginLeft: 8 }}>T+5:</span>
                    <span className={item.ret_t5 >= 0 ? 'up' : 'down'}>
                      {item.ret_t5 >= 0 ? '+' : ''}{item.ret_t5.toFixed(2)}%
                    </span>
                  </>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
