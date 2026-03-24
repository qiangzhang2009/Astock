import { useState, useEffect } from 'react';
import axios from 'axios';
import type { RangeAnalysis } from '../types';

interface Props {
  symbol: string;
  startDate: string;
  endDate: string;
  question: string;
  onClear: () => void;
}

export default function RangeAnalysisPanel({ symbol, startDate, endDate, question, onClear }: Props) {
  const [analysis, setAnalysis] = useState<RangeAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!symbol || !startDate || !endDate) return;
    setLoading(true);
    setError('');
    axios.post('/api/analysis/range', {
      symbol,
      start_date: startDate,
      end_date: endDate,
      question,
    })
      .then(res => setAnalysis(res.data || null))
      .catch(e => setError(e.response?.data?.detail || 'AI 分析失败'))
      .finally(() => setLoading(false));
  }, [symbol, startDate, endDate, question]);

  function renderMarkdown(text: string) {
    // Simple markdown renderer: **bold**, *italic*, ▲/▼ bullets, up/down classes
    const lines = text.split('\n');
    return lines.map((line, i) => {
      // Replace **text** with <strong>
      let html = line
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/▲/g, '<span style="color:var(--chart-green);font-weight:700">▲</span>')
        .replace(/▼/g, '<span style="color:var(--chart-red);font-weight:700">▼</span>')
        .replace(/\+\d+\.\d+%/g, m => `<span class="up">${m}</span>`)
        .replace(/-\d+\.\d+%/g, m => `<span class="down">${m}</span>`)
        .replace(/^\s*-\s+(.+)/, (_, content) => `<span style="color:var(--text-secondary)">• ${content}</span>`);

      if (!line.trim()) return <br key={i} />;

      return (
        <div
          key={i}
          style={{ marginBottom: 4, fontSize: 13, lineHeight: 1.6 }}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      );
    });
  }

  const changePct = analysis?.price_change_pct ?? 0;
  const isUp = changePct >= 0;

  return (
    <div className="range-analysis">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>区间 AI 分析</div>
          <div className="range-analysis-title">
            {symbol} · {startDate} ~ {endDate}
            <span className={`range-analysis-change ${isUp ? 'up' : 'down'}`} style={{ marginLeft: 8 }}>
              {isUp ? '▲' : '▼'} {isUp ? '+' : ''}{changePct.toFixed(2)}%
            </span>
          </div>
        </div>
        <button
          className="filter-chip"
          onClick={onClear}
          style={{ fontSize: 10, padding: '2px 8px' }}
        >
          关闭
        </button>
      </div>

      {/* Question */}
      {question && (
        <div style={{
          fontSize: 12,
          color: 'var(--accent-blue)',
          background: 'rgba(88,166,255,0.08)',
          border: '1px solid rgba(88,166,255,0.2)',
          borderRadius: 6,
          padding: '6px 10px',
          marginBottom: 10,
          fontStyle: 'italic',
        }}>
          Q: {question}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="loading-spinner" style={{ flexDirection: 'column', gap: 12, padding: 32 }}>
          <div className="spinner" style={{ width: 24, height: 24, borderWidth: 3 }} />
          <span>AI 正在分析区间...</span>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div style={{
          padding: '12px 16px',
          background: 'rgba(248,81,73,0.08)',
          border: '1px solid rgba(248,81,73,0.2)',
          borderRadius: 8,
          fontSize: 13,
          color: 'var(--chart-red)',
        }}>
          {error}
        </div>
      )}

      {/* Analysis content */}
      {analysis && !loading && (
        <div>
          {/* Summary bar */}
          <div style={{
            display: 'flex',
            gap: 12,
            padding: '8px 12px',
            background: 'var(--bg-secondary)',
            borderRadius: 8,
            marginBottom: 12,
            fontSize: 12,
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: isUp ? 'var(--chart-green)' : 'var(--chart-red)', fontFamily: 'var(--font-mono)' }}>
                {isUp ? '+' : ''}{changePct.toFixed(2)}%
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>区间涨跌</span>
            </div>
            <div style={{ width: 1, background: 'var(--border-color)' }} />
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                {analysis.news_count}
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>相关新闻</span>
            </div>
          </div>

          {/* AI Analysis text */}
          {analysis.analysis && (
            <div className="range-analysis-content">
              {renderMarkdown(analysis.analysis)}
            </div>
          )}

          {/* Price summary */}
          {analysis.prices && analysis.prices.length > 0 && (
            <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--bg-tertiary)', borderRadius: 8 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6, fontWeight: 600 }}>
                价格区间
              </div>
              <div style={{ display: 'flex', gap: 12, fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>起始 </span>
                  <span style={{ color: 'var(--text-primary)' }}>¥{analysis.prices[0].open.toFixed(2)}</span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>最高 </span>
                  <span style={{ color: 'var(--chart-green)' }}>¥{Math.max(...analysis.prices.map(p => p.high)).toFixed(2)}</span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>最低 </span>
                  <span style={{ color: 'var(--chart-red)' }}>¥{Math.min(...analysis.prices.map(p => p.low)).toFixed(2)}</span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)' }}>收盘 </span>
                  <span style={{ color: 'var(--text-primary)' }}>¥{analysis.prices[analysis.prices.length - 1].close.toFixed(2)}</span>
                </div>
              </div>
            </div>
          )}

          {/* Top news in range */}
          {analysis.news && analysis.news.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8, fontWeight: 600 }}>
                重要新闻 ({analysis.news.length})
              </div>
              {analysis.news.slice(0, 5).map(item => {
                const sentiment = item.sentiment || 'neutral';
                const sentimentLabel = item.sentiment_cn ||
                  (sentiment === 'positive' ? '利好' : sentiment === 'negative' ? '利空' : '中性');
                return (
                  <div key={item.news_id} style={{
                    padding: '8px 10px',
                    borderBottom: '1px solid var(--border-color)',
                    background: 'var(--bg-tertiary)',
                    borderRadius: 6,
                    marginBottom: 4,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                      <span className={`sentiment-badge ${sentiment}`}>{sentimentLabel}</span>
                      {item.date && (
                        <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {item.date.slice(0, 10).replace(/-/g, '/')}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.4 }}>
                      {item.title}
                    </div>
                    {(item.reason_growth || item.reason_decrease) && (
                      <div style={{ marginTop: 3, fontSize: 11 }}>
                        {item.reason_growth && (
                          <div style={{ color: 'var(--chart-green)' }}>
                            ▲ {item.reason_growth}
                          </div>
                        )}
                        {item.reason_decrease && (
                          <div style={{ color: 'var(--chart-red)' }}>
                            ▼ {item.reason_decrease}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
