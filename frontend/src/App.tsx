import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'https://astock-api.onrender.com';
axios.defaults.baseURL = API_BASE;
import StockSelector from './components/StockSelector';
import CandlestickChart from './components/CandlestickChart';
import NewsPanel from './components/NewsPanel';
import NewsCategoryPanel from './components/NewsCategoryPanel';
import RangeAnalysisPanel from './components/RangeAnalysisPanel';
import RangeQueryPopup from './components/RangeQueryPopup';
import RangeNewsPanel from './components/RangeNewsPanel';
import SimilarDaysPanel from './components/SimilarDaysPanel';
import PredictionPanel from './components/PredictionPanel';
import ScreenerPanel from './components/ScreenerPanel';
import './App.css';

interface RangeSelection {
  startDate: string;
  endDate: string;
  priceChange?: number;
  popupX?: number;
  popupY?: number;
}

interface ArticleSelection {
  newsId: string;
  date: string;
}

type RightPanelType = 'news' | 'range-analysis' | 'similar' | 'screener';

function App() {
  const [activeTickers, setActiveTickers] = useState<string[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [hoveredDate, setHoveredDate] = useState<string | null>(null);
  const [hoveredOhlc, setHoveredOhlc] = useState<{
    date: string; open: number; high: number; low: number; close: number; change: number;
  } | null>(null);
  const [selectedRange, setSelectedRange] = useState<RangeSelection | null>(null);
  const [rangeQuestion, setRangeQuestion] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [selectedArticle, setSelectedArticle] = useState<ArticleSelection | null>(null);
  const [lockedArticle, setLockedArticle] = useState<ArticleSelection | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [activeCategoryIds, setActiveCategoryIds] = useState<string[]>([]);
  const [activeCategoryColor, setActiveCategoryColor] = useState<string | null>(null);
  const [rightPanel, setRightPanel] = useState<RightPanelType>('news');
  const chartAreaRef = useRef<HTMLDivElement>(null);
  const [chartRect, setChartRect] = useState<DOMRect | undefined>(undefined);

  useEffect(() => {
    axios.get('/api/stocks')
      .then((res) => {
        const tickers = res.data
          .filter((t: any) => t.last_ohlc_fetch)
          .map((t: any) => t.symbol);
        setActiveTickers(tickers);
        if (tickers.length > 0 && !selectedSymbol) {
          setSelectedSymbol(tickers[0]);
        }
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (selectedRange && chartAreaRef.current) {
      setChartRect(chartAreaRef.current.getBoundingClientRect());
    }
  }, [selectedRange]);

  const handleHover = useCallback(
    (date: string | null, ohlc?: { date: string; open: number; high: number; low: number; close: number; change: number }) => {
      if (!lockedArticle) setHoveredDate(date);
      setHoveredOhlc(ohlc || null);
    },
    [lockedArticle]
  );

  const handleRangeSelect = useCallback((range: RangeSelection | null) => {
    setSelectedRange(range);
    setRangeQuestion(null);
    setRightPanel('news');
    if (range) {
      setSelectedDay(null);
      setSelectedArticle(null);
      setLockedArticle(null);
    }
  }, []);

  const handleArticleSelect = useCallback((article: ArticleSelection | null) => {
    if (!article) { setLockedArticle(null); setSelectedArticle(null); return; }
    setLockedArticle((prev) => {
      if (prev?.newsId === article.newsId) { setSelectedArticle(null); return null; }
      setSelectedArticle(article);
      setSelectedRange(null);
      setRangeQuestion(null);
      setSelectedDay(null);
      setHoveredDate(article.date);
      return article;
    });
  }, []);

  const handleDayClick = useCallback((date: string) => {
    setSelectedDay(date);
    setSelectedRange(null);
    setRangeQuestion(null);
    setSelectedArticle(null);
    setLockedArticle(null);
    setRightPanel('news');
  }, []);

  const handleRangeAsk = useCallback((question: string) => {
    setRangeQuestion(question);
    setRightPanel('range-analysis');
  }, []);

  const handleCategoryChange = useCallback((category: string | null, articleIds: string[], color?: string) => {
    setActiveCategory(category);
    setActiveCategoryIds(articleIds);
    setActiveCategoryColor(color ?? null);
  }, []);

  function handleSelectSymbol(symbol: string) {
    setSelectedSymbol(symbol);
    setHoveredDate(null); setHoveredOhlc(null); setSelectedRange(null);
    setRangeQuestion(null); setSelectedDay(null); setSelectedArticle(null);
    setLockedArticle(null); setActiveCategory(null); setActiveCategoryIds([]);
    setActiveCategoryColor(null);
    setRightPanel('news');
  }

  function handleAddTicker(symbol: string) {
    if (!activeTickers.includes(symbol)) {
      setActiveTickers((prev) => [...prev, symbol]);
      axios.post('/api/stocks', { symbol }).catch(console.error);
    }
  }

  const effectiveDate = lockedArticle?.date ?? hoveredDate;
  const isLocked = lockedArticle !== null;

  function renderRightPanel() {
    if (rightPanel === 'screener') {
      return <ScreenerPanel />;
    }
    if (selectedRange && rangeQuestion) {
      return (
        <RangeAnalysisPanel
          symbol={selectedSymbol}
          startDate={selectedRange.startDate}
          endDate={selectedRange.endDate}
          question={rangeQuestion}
          onClear={() => { setSelectedRange(null); setRangeQuestion(null); setRightPanel('news'); }}
        />
      );
    }
    if (selectedRange && !rangeQuestion) {
      return (
        <RangeNewsPanel
          symbol={selectedSymbol}
          startDate={selectedRange.startDate}
          endDate={selectedRange.endDate}
          priceChange={selectedRange.priceChange}
          onClose={() => setSelectedRange(null)}
          onAskAI={handleRangeAsk}
        />
      );
    }
    if (selectedDay) {
      return (
        <SimilarDaysPanel
          symbol={selectedSymbol}
          date={selectedDay}
          onClose={() => setSelectedDay(null)}
        />
      );
    }
    return (
      <NewsPanel
        symbol={selectedSymbol}
        hoveredDate={effectiveDate}
        onFindSimilar={(_newsId: string) => {
          if (effectiveDate) handleDayClick(effectiveDate);
        }}
        highlightedNewsId={selectedArticle?.newsId || null}
        isLocked={isLocked}
        onUnlock={() => { setLockedArticle(null); setSelectedArticle(null); }}
        highlightedCategoryIds={activeCategoryIds.length > 0 ? activeCategoryIds : undefined}
      />
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">
          <span className="logo-text">Astock</span>
          <span className="logo-sub">A股事件驱动分析</span>
        </div>
        <StockSelector
          activeTickers={activeTickers}
          selectedSymbol={selectedSymbol}
          onSelect={handleSelectSymbol}
          onAdd={handleAddTicker}
        />
        {selectedRange ? (
          <div className="header-ohlc">
            <span className="ohlc-date">{selectedRange.startDate} ~ {selectedRange.endDate}</span>
            <span className="range-badge">区间已选</span>
          </div>
        ) : hoveredOhlc ? (
          <div className="header-ohlc">
            <span className="ohlc-date">{hoveredOhlc.date}</span>
            <span className="ohlc-label">开</span>
            <span className="ohlc-val">¥{hoveredOhlc.open.toFixed(2)}</span>
            <span className="ohlc-label">高</span>
            <span className="ohlc-val">¥{hoveredOhlc.high.toFixed(2)}</span>
            <span className="ohlc-label">低</span>
            <span className="ohlc-val">¥{hoveredOhlc.low.toFixed(2)}</span>
            <span className="ohlc-label">收</span>
            <span className="ohlc-val">¥{hoveredOhlc.close.toFixed(2)}</span>
            <span className={`ohlc-change ${hoveredOhlc.change >= 0 ? 'up' : 'down'}`}>
              {hoveredOhlc.change >= 0 ? '+' : ''}{hoveredOhlc.change.toFixed(2)}%
            </span>
          </div>
        ) : null}
        <div className="header-right">
          <button
            className={`filter-chip ${rightPanel === 'screener' ? 'active' : ''}`}
            style={{ fontSize: 12, padding: '4px 10px', borderRadius: 6 }}
            onClick={() => setRightPanel(rightPanel === 'screener' ? 'news' : 'screener')}
          >
            选股器
          </button>
          <a href="https://github.com/qiangzhang2009/Astock" target="_blank" rel="noopener noreferrer" className="header-link header-github">
            <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
            </svg>
            <span className="github-text">GitHub</span>
          </a>
        </div>
      </header>

      <main className="app-main">
        <div className="chart-area" ref={chartAreaRef}>
          {selectedSymbol ? (
            <>
              <CandlestickChart
                symbol={selectedSymbol}
                lockedNewsId={lockedArticle?.newsId ?? null}
                highlightedArticleIds={activeCategoryIds.length > 0 ? activeCategoryIds : null}
                highlightColor={activeCategoryColor}
                onHover={handleHover}
                onRangeSelect={handleRangeSelect}
                onArticleSelect={handleArticleSelect}
                onDayClick={handleDayClick}
              />
              {selectedRange && !rangeQuestion && (
                <RangeQueryPopup
                  range={selectedRange}
                  chartRect={chartRect}
                  onAsk={handleRangeAsk}
                  onClose={() => setSelectedRange(null)}
                />
              )}
            </>
          ) : (
            <div className="chart-placeholder">搜索并选择一只 A 股查看 K 线</div>
          )}
        </div>

        {selectedSymbol && (
          <div className="prediction-area">
            <PredictionPanel symbol={selectedSymbol} />
          </div>
        )}

        <div className="news-area">
          {selectedSymbol && (
            <NewsCategoryPanel
              symbol={selectedSymbol}
              activeCategory={activeCategory}
              onCategoryChange={handleCategoryChange}
            />
          )}
          {renderRightPanel()}
        </div>
      </main>
    </div>
  );
}

export default App;
