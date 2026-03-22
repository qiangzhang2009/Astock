import { useState, useEffect } from 'react';
import axios from 'axios';
import type { Forecast } from '../types';

interface Props { symbol: string; }

export default function PredictionPanel({ symbol }: Props) {
  const [forecast7, setForecast7] = useState<Forecast | null>(null);
  const [forecast30, setForecast30] = useState<Forecast | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    setError('');
    Promise.all([
      axios.get(`/api/predict/${symbol}/forecast?window=7`).then((r) => r.data as Forecast).catch(() => null),
      axios.get(`/api/predict/${symbol}/forecast?window=30`).then((r) => r.data as Forecast).catch(() => null),
    ])
      .then(([f7, f30]) => { setForecast7(f7); setForecast30(f30); })
      .catch(() => setError('预测加载失败'))
      .finally(() => setLoading(false));
  }, [symbol]);

  const primaryForecast = forecast7 || forecast30;
  const primary = primaryForecast
    ? (primaryForecast.prediction?.t3 || primaryForecast.prediction?.t1 || primaryForecast.prediction?.t5)
    : null;
  const isUp = primary?.direction === 'up';

  function renderStyledText(text: string): React.ReactNode[] {
    const pattern = /(\[[^\]]+\])|(看涨|看跌|上涨|下跌|利好|利空|偏多|偏空|中性)|([+-]?\d+\.?\d*%)/gi;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0; let key = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(text)) !== null) {
      if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
      const [, , bull, , pct] = match as unknown as string[];
      if (bull) parts.push(<span key={key++} style={{ color: bull.includes('涨') || bull.includes('多') || bull.includes('利') ? 'var(--chart-green)' : 'var(--chart-red)', fontWeight: 600 }}>{match[0]}</span>);
      else if (pct) parts.push(<span key={key++} style={{ color: pct.startsWith('-') ? 'var(--chart-red)' : 'var(--chart-green)', fontWeight: 600, fontFamily: 'Menlo, monospace' }}>{match[0]}</span>);
      lastIndex = match.index + match[0].length;
    }
    if (lastIndex < text.length) parts.push(text.slice(lastIndex));
    return parts;
  }

  if (loading) {
    return (
      <div className="pred-panel">
        <div className="pred-header">
          <span className="pred-title">预测</span>
          <span className="pred-loading-dot" />
          <span className="pred-loading-text">分析中...</span>
        </div>
      </div>
    );
  }

  if (error || (!forecast7 && !forecast30)) {
    return (
      <div className="pred-panel">
        <div className="pred-header">
          <span className="pred-title">预测</span>
          <span className="pred-no-model">{error || '暂无数据'}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`pred-panel ${expanded ? 'pred-expanded' : ''}`}>
      <div className="pred-header" onClick={() => setExpanded(!expanded)}>
        <span className="pred-title">预测</span>
        {primary && (
          <>
            <div className={`pred-arrow ${isUp ? 'up' : 'down'}`}>{isUp ? '↑' : '↓'}</div>
            <span className={`pred-dir ${isUp ? 'up' : 'down'}`}>{isUp ? '看涨' : '看跌'}</span>
            <div className="pred-conf-bar">
              <div className={`pred-conf-fill ${isUp ? 'up' : 'down'}`} style={{ width: `${primary.confidence * 100}%` }} />
              <span className="pred-conf-label">{(primary.confidence * 100).toFixed(0)}%</span>
            </div>
          </>
        )}
        <span className="pred-expand-icon">{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && primaryForecast && (
        <div className="pred-details">
          {/* AI 结论 */}
          {primaryForecast.conclusion && (
            <div className="fc-analysis" style={{ marginBottom: 8 }}>
              <div className="fc-section-title">综合分析</div>
              <div style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--text-secondary)' }}>
                {renderStyledText(primaryForecast.conclusion)}
              </div>
            </div>
          )}

          {/* 预测卡片 */}
          {forecast7 && forecast7.prediction && Object.keys(forecast7.prediction).length > 0 && (
            <div className="fc-section-block">
              <div className="fc-section-divider">7 日窗口预测</div>
              <div className="fc-predictions">
                {(['t1', 't3', 't5'] as const).map((key) => {
                  const pred = forecast7!.prediction[key];
                  if (!pred) return null;
                  const up = pred.direction === 'up';
                  return (
                    <div key={key} className={`fc-pred-card ${up ? 'up' : 'down'}`}>
                      <div className="fc-pred-header">
                        <span className="fc-pred-label">T+{key.slice(1)}</span>
                        <span className={`fc-pred-dir ${up ? 'up' : 'down'}`}>{up ? '↑ 看涨' : '↓ 看跌'}</span>
                        <span className="fc-pred-conf">{(pred.confidence * 100).toFixed(0)}%</span>
                      </div>
                      {pred.model_accuracy != null && (
                        <div className="fc-pred-meta">
                          准确率 {((pred.model_accuracy || 0) * 100).toFixed(1)}% / 基准 {(pred.baseline_accuracy || 0.5) * 100}%
                        </div>
                      )}
                      {pred.top_drivers?.length > 0 && (
                        <div className="fc-drivers">
                          {pred.top_drivers.slice(0, 3).map((d) => (
                            <div key={d.name} className="fc-driver-row">
                              <span className="fc-driver-name">{d.name}</span>
                              <div className="fc-driver-bar-track">
                                <div className={`fc-driver-bar-fill ${d.value >= 0 ? 'up' : 'down'}`} style={{ width: `${Math.min(100, Math.abs(d.contribution) * 200)}%` }} />
                              </div>
                              <span className="fc-driver-val">{d.value.toFixed(2)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 30 日预测摘要 */}
          {forecast30 && (
            <div className="fc-section-block" style={{ marginTop: 8 }}>
              <div className="fc-section-divider">30 日窗口预测</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {forecast30.conclusion ? renderStyledText(forecast30.conclusion) : '暂无 30 日预测数据'}
              </div>
            </div>
          )}

          {/* 说明 */}
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 12, padding: '6px 8px', background: 'var(--bg-tertiary)', borderRadius: 6, lineHeight: 1.5 }}>
            ⚠️ 本工具仅供学习参考，不构成投资建议。股市有风险，投资需谨慎。
          </div>
        </div>
      )}
    </div>
  );
}
