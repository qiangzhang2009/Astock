import { useState, useEffect } from 'react';
import axios from 'axios';

interface Props {
  symbol: string;
  startDate: string;
  endDate: string;
  question: string;
  onClear: () => void;
}

export default function RangeAnalysisPanel({ symbol, startDate, endDate, question, onClear }: Props) {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    axios.post('/api/analysis/range', { symbol, start_date: startDate, end_date: endDate, question })
      .then((r) => setResult(r.data))
      .catch((e) => setError(e.message || '分析失败'))
      .finally(() => setLoading(false));
  }, [symbol, startDate, endDate, question]);

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
            AI 区间分析
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 600 }}>
            {startDate} ~ {endDate}
          </div>
        </div>
        <button
          onClick={onClear}
          style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: 18, cursor: 'pointer', lineHeight: 1 }}
        >×</button>
      </div>

      {result?.price_change_pct != null && (
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '6px 12px', borderRadius: 8, marginBottom: 12,
          background: result.price_change_pct >= 0 ? 'rgba(63,185,80,0.1)' : 'rgba(248,81,73,0.1)',
          border: `1px solid ${result.price_change_pct >= 0 ? 'rgba(63,185,80,0.3)' : 'rgba(248,81,73,0.3)'}`,
        }}>
          <span style={{ fontSize: 18, fontWeight: 700, color: result.price_change_pct >= 0 ? 'var(--chart-green)' : 'var(--chart-red)' }}>
            {result.price_change_pct >= 0 ? '↑' : '↓'}
          </span>
          <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'Menlo, monospace', color: result.price_change_pct >= 0 ? 'var(--chart-green)' : 'var(--chart-red)' }}>
            {result.price_change_pct >= 0 ? '+' : ''}{result.price_change_pct.toFixed(2)}%
          </span>
        </div>
      )}

      {loading && <div className="loading-spinner"><div className="spinner" />AI 分析中...</div>}

      {error && <div style={{ color: 'var(--accent-red)', fontSize: 13 }}>{error}</div>}

      {result?.analysis && (
        <div style={{ fontSize: 13, lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          {result.analysis.split('\n').map((line: string, i: number) => {
            if (line.startsWith('**') && line.endsWith('**')) {
              return <div key={i} style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginTop: 8, marginBottom: 4 }}>{line.replace(/\*\*/g, '')}</div>;
            }
            if (line.startsWith('**▲') || line.includes('利好')) {
              return <div key={i} style={{ color: 'var(--chart-green)', fontWeight: 600, marginTop: 6 }}>{line.replace(/\*\*/g, '')}</div>;
            }
            if (line.startsWith('**▼') || line.includes('利空')) {
              return <div key={i} style={{ color: 'var(--chart-red)', fontWeight: 600, marginTop: 6 }}>{line.replace(/\*\*/g, '')}</div>;
            }
            return <div key={i} style={{ marginTop: 2 }}>{line.replace(/\*\*/g, '')}</div>;
          })}
        </div>
      )}

      {!loading && !result && !error && (
        <div className="empty-state">
          <div className="empty-state-icon">🤖</div>
          <div>暂无分析结果</div>
        </div>
      )}
    </div>
  );
}
