import { useState, useEffect } from 'react';
import axios from 'axios';
import type { NewsCategory } from '../types';

interface Props {
  symbol: string;
  activeCategory: string | null;
  onCategoryChange: (category: string | null, articleIds: string[], color?: string) => void;
}

export default function NewsCategoryPanel({ symbol, activeCategory, onCategoryChange }: Props) {
  const [categories, setCategories] = useState<NewsCategory[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!symbol) return;
    setLoading(true);
    axios.get(`/api/news/${symbol}/categories`)
      .then((r) => setCategories(r.data))
      .catch(() => setCategories([]))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading || categories.length === 0) {
    return <div className="category-panel" style={{ color: 'var(--text-muted)', fontSize: 12, padding: 8 }}>暂无分类</div>;
  }

  function handleClick(cat: NewsCategory) {
    if (activeCategory === cat.category) {
      onCategoryChange(null, [], undefined);
    } else {
      // Fetch articles for this category and extract IDs
      axios.get(`/api/news/${symbol}?date=`)
        .then((r) => {
          const allNews = r.data as any[];
          const ids = allNews
            .filter((n) => {
              const t = n.title || '';
              switch (cat.category) {
                case '政策': return /政策|监管|央行|发改委|财政部/.test(t);
                case '业绩': return /业绩|财报|季报|净利润|营收/.test(t);
                case '概念': return /概念|题材|板块|AI|新能源/.test(t);
                case '公告': return /公告|证监会|问询/.test(t);
                case '市场': return /大盘|指数|上证|北向|外资/.test(t);
                default: return true;
              }
            })
            .map((n: any) => n.news_id);
          onCategoryChange(cat.category, ids, cat.color);
        })
        .catch(() => {});
    }
  }

  return (
    <div className="category-panel">
      <button
        className={`category-chip ${!activeCategory ? 'active' : ''}`}
        onClick={() => onCategoryChange(null, [], undefined)}
        style={{ color: !activeCategory ? 'var(--text-primary)' : undefined }}
      >
        全部
      </button>
      {categories.map((cat) => (
        <button
          key={cat.category}
          className={`category-chip ${activeCategory === cat.category ? 'active' : ''}`}
          style={{
            color: activeCategory === cat.category ? cat.color : undefined,
            borderColor: activeCategory === cat.category ? cat.color : undefined,
          }}
          onClick={() => handleClick(cat)}
        >
          {cat.category}
          <span className="category-count">({cat.count})</span>
        </button>
      ))}
    </div>
  );
}
