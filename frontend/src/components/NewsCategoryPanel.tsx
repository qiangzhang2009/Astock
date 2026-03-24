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
      .then(res => {
        const cats: NewsCategory[] = Array.isArray(res.data) ? res.data : [];
        setCategories(cats.filter(c => c.count > 0));
      })
      .catch(() => setCategories([]))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) {
    return (
      <div className="category-panel">
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>加载分类...</div>
      </div>
    );
  }

  if (categories.length === 0) {
    return (
      <div className="category-panel">
        <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>暂无新闻分类</div>
      </div>
    );
  }

  function handleClick(cat: NewsCategory) {
    if (activeCategory === cat.id) {
      onCategoryChange(null, [], undefined);
    } else {
      onCategoryChange(cat.id, [], cat.color);
    }
  }

  return (
    <div className="category-panel">
      <button
        className={`category-chip ${!activeCategory ? 'active' : ''}`}
        onClick={() => onCategoryChange(null, [], undefined)}
        style={{ color: !activeCategory ? 'var(--accent-blue)' : undefined }}
      >
        全部
      </button>
      {categories.map(cat => {
        const isActive = activeCategory === cat.id;
        return (
          <button
            key={cat.id}
            className={`category-chip ${isActive ? 'active' : ''}`}
            onClick={() => handleClick(cat)}
            style={{ color: isActive ? cat.color : undefined }}
          >
            {cat.label}
            <span className="category-count">{cat.count}</span>
          </button>
        );
      })}
    </div>
  );
}
