import { useState } from 'react';
import type { RangeSelection } from '../types';

interface Props {
  range: RangeSelection;
  chartRect?: DOMRect;
  onAsk: (question: string) => void;
  onClose: () => void;
}

const PRESET_QUESTIONS = [
  '这段区间为何涨跌？',
  '有什么重大新闻驱动了这段走势？',
  '现在是买入时机吗？',
  '接下来可能怎么走？',
];

export default function RangeQueryPopup({ range, onAsk, onClose }: Props) {
  const [customQ, setCustomQ] = useState('');

  return (
    <div className="range-popup-overlay">
      <div className="range-popup" style={{ position: 'absolute', left: 12, top: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div className="range-popup-title">
            {range.startDate} ~ {range.endDate}
            {range.priceChange != null && (
              <span style={{ marginLeft: 8, color: range.priceChange >= 0 ? 'var(--chart-green)' : 'var(--chart-red)', fontWeight: 700 }}>
                {range.priceChange >= 0 ? '+' : ''}{range.priceChange.toFixed(2)}%
              </span>
            )}
          </div>
          <button className="range-popup-close" onClick={onClose}>×</button>
        </div>
        <div className="range-popup-title">选择分析问题：</div>
        <div className="range-popup-buttons">
          {PRESET_QUESTIONS.map((q) => (
            <button key={q} className="range-btn" onClick={() => onAsk(q)}>
              {q}
            </button>
          ))}
        </div>
        <input
          className="range-question-input"
          placeholder="输入自定义问题..."
          value={customQ}
          onChange={(e) => setCustomQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && customQ.trim()) {
              onAsk(customQ.trim());
              setCustomQ('');
            }
          }}
        />
      </div>
    </div>
  );
}
