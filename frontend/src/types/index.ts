// ─── K 线数据 ───────────────────────────────────────────────────────────────
export interface OHLCRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount?: number;
  change_pct: number;
  limit_up?: number;
  limit_down?: number;
}

// ─── 新闻粒子 (K线图叠加点) ────────────────────────────────────────────────
export interface NewsParticle {
  news_id: string;
  d: string; // date
  s: 'positive' | 'negative' | 'neutral';
  r: 'high' | 'medium' | 'low';
  t: string; // title
  rt1?: number | null; // return T+1
}

// ─── 新闻条目 ──────────────────────────────────────────────────────────────
export interface NewsItem {
  news_id: string;
  title: string;
  content?: string;
  source?: string;
  published_at?: string;
  sentiment?: string;
  sentiment_cn?: string;
  relevance?: string;
  key_discussion?: string;
  reason_growth?: string;
  reason_decrease?: string;
  trade_date?: string;
  ret_t0?: number | null;
  ret_t1?: number | null;
  ret_t3?: number | null;
  ret_t5?: number | null;
  date?: string;
}

// ─── 新闻分类统计 ─────────────────────────────────────────────────────────
export interface NewsCategory {
  id: string;
  label: string;
  color: string;
  count: number;
  positive: number;
  negative: number;
  neutral: number;
}

// ─── 股票信息 ──────────────────────────────────────────────────────────────
export interface StockInfo {
  symbol: string;
  name?: string;
  sector?: string;
  market?: string;
  last_ohlc_fetch?: string | null;
  price?: number;
  change?: number;
  change_pct?: number;
  volume?: number;
  turnover?: number;
  high?: number;
  low?: number;
  open?: number;
  prev_close?: number;
  amplitude?: number;
}

// ─── 择时预测 ──────────────────────────────────────────────────────────────
export interface PredictionForecast {
  symbol: string;
  window_days: number;
  forecast_date: string;
  news_summary: {
    total: number;
    positive: number;
    negative: number;
    neutral: number;
    sentiment_ratio: number;
    top_headlines: { news_id: string; title: string; sentiment: string }[];
    top_impact: {
      news_id: string;
      title: string;
      sentiment: string;
      ret_t1: number;
    }[];
  };
  prediction: {
    direction?: string;
    confidence?: number;
    t1?: { direction: string; confidence: number };
    t3?: { direction: string; confidence: number };
    t5?: { direction: string; confidence: number };
  };
  similar_periods: SimilarPeriod[];
  similar_stats: {
    count: number;
    up_ratio_5d: number;
    up_ratio_10d: number;
    avg_ret_5d: number | null;
    avg_ret_10d: number | null;
  };
  conclusion?: string;
}

export interface SimilarPeriod {
  start_date: string;
  end_date: string;
  similarity: number;
  price_change_pct: number;
  ret_t1?: number | null;
  ret_t3?: number | null;
  ret_t5?: number | null;
}

// ─── 区间分析 ──────────────────────────────────────────────────────────────
export interface RangeAnalysis {
  symbol: string;
  start_date: string;
  end_date: string;
  price_change_pct: number;
  news_count: number;
  analysis: string;
  prices: OHLCRow[];
  news: NewsItem[];
}

// ─── 选股器 ────────────────────────────────────────────────────────────────
export interface ScreenerStock {
  symbol: string;
  name?: string;
  sector?: string;
  market?: string;
  close?: number;
  price?: number;
  change_pct: number;
  volume: number;
  turnover?: number;
  limit_up?: number;
  limit_down?: number;
  amplitude?: number;
  high?: number;
  low?: number;
  open?: number;
}

export interface ScreenerResponse {
  count: number;
  filters: {
    sectors: string[];
    min_change_pct: number | null;
    max_change_pct: number | null;
    limit_up_only: boolean;
    limit_down_only: boolean;
  };
  results: ScreenerStock[];
}

// ─── 深度分析 ─────────────────────────────────────────────────────────────
export interface DeepAnalysis {
  news_id: string;
  title: string;
  content?: string;
  sentiment: string;
  sentiment_cn?: string;
  key_discussion?: string;
  reason_growth?: string;
  reason_decrease?: string;
  returns: {
    t0: number | null;
    t1: number | null;
    t3: number | null;
    t5: number | null;
  };
}
