// A-Stock type definitions

export interface OHLCRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  turnover?: number;
  change_pct?: number;
  limit_up?: number;
  limit_down?: number;
  amplitude?: number;
}

export interface StockInfo {
  symbol: string;
  name?: string;
  sector?: string;
  market?: string;
  last_ohlc_fetch?: string;
  price?: number;
  change_pct?: number;
  volume?: number;
}

export interface NewsItem {
  news_id: string;
  title: string;
  content?: string;
  source?: string;
  published_at?: string;
  sentiment?: 'positive' | 'negative' | 'neutral' | null;
  sentiment_cn?: string | null;
  relevance?: string | null;
  key_discussion?: string | null;
  reason_growth?: string | null;
  reason_decrease?: string | null;
  trade_date?: string;
  ret_t0?: number | null;
  ret_t1?: number | null;
  ret_t3?: number | null;
  ret_t5?: number | null;
}

export interface NewsParticle {
  news_id: string;
  d: string;
  s: string | null;
  r: string | null;
  t: string;
  rt1: number | null;
}

export interface NewsCategory {
  category: string;
  label: string;
  color: string;
  count: number;
  positive: number;
  negative: number;
  neutral: number;
}

export interface Prediction {
  direction: 'up' | 'down';
  confidence: number;
  top_drivers: Driver[];
  model_accuracy?: number | null;
  baseline_accuracy?: number | null;
}

export interface Driver {
  name: string;
  value: number;
  importance: number;
  z_score: number;
  contribution: number;
}

export interface NewsSummary {
  total: number;
  positive: number;
  negative: number;
  neutral: number;
  sentiment_ratio: number;
  top_headlines: Headline[];
  top_impact: ImpactArticle[];
}

export interface Headline {
  date: string;
  title: string;
  sentiment: string;
  summary: string;
}

export interface ImpactArticle {
  news_id: string;
  date: string;
  title: string;
  sentiment: string;
  relevance: string | null;
  key_discussion: string;
  ret_t0: number | null;
  ret_t1: number | null;
}

export interface SimilarStats {
  count: number;
  up_ratio_5d: number;
  up_ratio_10d: number;
  avg_ret_5d: number | null;
  avg_ret_10d: number | null;
}

export interface SimilarPeriod {
  period_start: string;
  period_end: string;
  similarity: number;
  avg_sentiment: number;
  n_articles: number;
  ret_after_5d: number | null;
  ret_after_10d: number | null;
}

export interface Forecast {
  symbol: string;
  window_days: number;
  forecast_date: string;
  news_summary: NewsSummary;
  prediction: Record<string, Prediction>;
  similar_periods: SimilarPeriod[];
  similar_stats: SimilarStats;
  conclusion: string;
}

export interface ScreenerResult {
  symbol: string;
  name?: string;
  sector?: string;
  market?: string;
  close?: number;
  change_pct?: number;
  volume?: number;
  turnover?: number;
  limit_up?: number;
  limit_down?: number;
  amplitude?: number;
}

export interface RangeSelection {
  startDate: string;
  endDate: string;
  priceChange?: number;
  popupX?: number;
  popupY?: number;
}

export interface ArticleSelection {
  newsId: string;
  date: string;
}

export interface DeepAnalysis {
  news_id: string;
  discussion: string;
  growth_reasons: string;
  decrease_reasons: string;
}
