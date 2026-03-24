import { useState } from 'react';

interface RangeSelection {
  startDate: string;
  endDate: string;
  priceChange?: number;
  popupX?: number;
  popupY?: number;
}

interface Props {
  range: RangeSelection;
  onAsk: (question: string) => void;
  onClose: () => void;
}

export default function RangeQueryPopup({ range, onAsk, onClose }: Props) {
  const [question, setQuestion] = useState('');

  function handleAsk() {
    if (!question.trim()) return;
    onAsk(question.trim());
  }

  function handlePresetAsk(text: string) {
    onAsk(text);
  }

  const presets = [
    { label: '这段区间发生了什么？', text: '这段区间发生了什么？' },
    { label: '涨跌原因是什么？', text: '涨跌原因是什么？' },
    { label: '有哪些重大新闻？', text: '有哪些重大新闻影响了股价？' },
    { label: '后续怎么看？', text: '对后续走势有何判断？' },
  ];

  const changePct = range.priceChange ?? 0;
  const isUp = changePct >= 0;

  return (
    <div className="range-popup-overlay">
      <div className="range-popup">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div className="range-popup-title" style={{ marginBottom: 0 }}>
            区间: {range.startDate} ~ {range.endDate}
            <span style={{
              marginLeft: 8,
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              fontWeight: 700,
              color: isUp ? 'var(--chart-green)' : 'var(--chart-red)',
            }}>
              {isUp ? '+' : ''}{changePct.toFixed(2)}%
            </span>
          </div>
          <button className="range-popup-close" onClick={onClose}>×</button>
        </div>

        {/* Quick question buttons */}
        <div className="range-popup-buttons">
          {presets.map(p => (
            <button
              key={p.label}
              className="range-btn"
              onClick={() => handlePresetAsk(p.text)}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Custom question input */}
        <input
          type="text"
          className="range-question-input"
          placeholder="向 AI 询问这个区间..."
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') handleAsk();
            if (e.key === 'Escape') onClose();
          }}
        />
      </div>
    </div>
  );
}
