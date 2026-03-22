import { useEffect, useRef, useState, useCallback } from 'react';
import axios from 'axios';
import * as d3 from 'd3';
import type { OHLCRow, NewsParticle } from '../types';

interface Props {
  symbol: string;
  lockedNewsId: string | null;
  highlightedArticleIds: string[] | null;
  highlightColor: string | null;
  onHover: (date: string | null, ohlc?: { date: string; open: number; high: number; low: number; close: number; change: number }) => void;
  onRangeSelect: (range: { startDate: string; endDate: string; priceChange?: number } | null) => void;
  onArticleSelect: (article: { newsId: string; date: string } | null) => void;
  onDayClick: (date: string) => void;
}

export default function CandlestickChart({
  symbol, lockedNewsId, highlightedArticleIds, highlightColor,
  onHover, onRangeSelect, onArticleSelect, onDayClick,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [data, setData] = useState<OHLCRow[]>([]);
  const [particles, setParticles] = useState<NewsParticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [brushExtent, setBrushExtent] = useState<[Date, Date] | null>(null);

  useEffect(() => {
    setLoading(true);
    setError('');
    Promise.all([
      axios.get(`/api/stocks/${symbol}/ohlc?days=365`).then((r) => r.data),
      axios.get(`/api/news/${symbol}/particles?days=365`).then((r) => r.data).catch(() => []),
    ])
      .then(([ohlcData, particleData]) => {
        const parsed: OHLCRow[] = (ohlcData as any[]).map((d) => ({
          ...d,
          open: Number(d.open), high: Number(d.high), low: Number(d.low),
          close: Number(d.close), volume: Number(d.volume),
          change_pct: d.change_pct != null ? Number(d.change_pct) : 0,
          limit_up: d.limit_up ? 1 : 0,
          limit_down: d.limit_down ? 1 : 0,
        })).reverse();
        setData(parsed);
        setParticles((particleData as NewsParticle[]) || []);
      })
      .catch((e) => setError(e.message || '加载失败'))
      .finally(() => setLoading(false));
  }, [symbol]);

  useEffect(() => {
    if (!data.length || !svgRef.current || !containerRef.current) return;
    drawChart();
  }, [data, particles, lockedNewsId, highlightedArticleIds, highlightColor, brushExtent]);

  const drawChart = useCallback(() => {
    const container = containerRef.current!;
    const svg = d3.select(svgRef.current!);
    svg.selectAll('*').remove();

    const width = container.clientWidth;
    const height = container.clientHeight;
    const margin = { top: 20, right: 60, bottom: 30, left: 60 };
    const innerW = width - margin.left - margin.right;
    const innerH = height - margin.top - margin.bottom;

    if (innerW <= 0 || innerH <= 0) return;

    const displayData = data.filter((d) => d.close != null);
    if (!displayData.length) return;

    const parsedDates = displayData.map((d) => new Date(d.date + 'T00:00:00'));

    const xScale = d3.scaleBand()
      .domain(displayData.map((d) => d.date))
      .range([0, innerW])
      .padding(0.2);

    const yMin = d3.min(displayData, (d) => d.low)! * 0.998;
    const yMax = d3.max(displayData, (d) => d.high)! * 1.002;
    const yScale = d3.scaleLinear().domain([yMin, yMax]).range([innerH, 0]);

    const g = svg
      .attr('width', width)
      .attr('height', height)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Grid
    g.append('g')
      .attr('class', 'grid')
      .call(d3.axisLeft(yScale).tickSize(-innerW).tickFormat(() => ''))
      .selectAll('line')
      .style('stroke', '#21262d')
      .style('stroke-dasharray', '2,2');
    g.selectAll('.grid .domain').remove();

    // Y Axis
    g.append('g')
      .call(d3.axisLeft(yScale).ticks(8).tickFormat((d) => `¥${Number(d).toFixed(0)}`))
      .selectAll('text')
      .style('fill', '#8b949e')
      .style('font-size', '11px')
      .style('font-family', 'Menlo, monospace');
    g.selectAll('.domain').style('stroke', '#30363d');
    g.selectAll('.tick line').style('stroke', '#30363d');

    // X Axis (show dates)
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(
        d3.scaleTime().domain(d3.extent(parsedDates) as [Date, Date]).range([0, innerW])
      ).ticks(8).tickFormat(d3.timeFormat('%m/%d') as any))
      .selectAll('text')
      .style('fill', '#8b949e')
      .style('font-size', '10px');
    g.selectAll('.domain').style('stroke', '#30363d');
    g.selectAll('.tick line').style('stroke', '#30363d');

    // Candlesticks
    const candleGroup = g.append('g').attr('class', 'candles');
    displayData.forEach((d, i) => {
      const x = (xScale(d.date) ?? 0) + xScale.bandwidth() / 2;
      const isUp = d.close >= d.open;
      const color = isUp ? '#26a69a' : '#ef5350';

      // Wick
      candleGroup.append('line')
        .attr('x1', x).attr('x2', x)
        .attr('y1', yScale(d.high)).attr('y2', yScale(d.low))
        .style('stroke', color).style('stroke-width', 1);

      // Body
      const bodyTop = yScale(Math.max(d.open, d.close));
      const bodyHeight = Math.max(1, Math.abs(yScale(d.open) - yScale(d.close)));
      candleGroup.append('rect')
        .attr('x', xScale(d.date)!)
        .attr('y', bodyTop)
        .attr('width', xScale.bandwidth())
        .attr('height', bodyHeight)
        .style('fill', color)
        .style('stroke', color)
        .style('stroke-width', 0.5);

      // Limit up/down markers
      if (d.limit_up) {
        candleGroup.append('rect')
          .attr('x', xScale(d.date)!).attr('y', yScale(d.high))
          .attr('width', xScale.bandwidth()).attr('height', yScale(d.low) - yScale(d.high))
          .style('fill', 'rgba(248,81,73,0.06)').style('stroke', 'none');
      }

      // Hover area
      candleGroup.append('rect')
        .attr('class', `hover-area-${i}`)
        .attr('x', xScale(d.date)!)
        .attr('y', 0)
        .attr('width', xScale.bandwidth())
        .attr('height', innerH)
        .style('fill', 'transparent')
        .style('cursor', 'crosshair')
        .on('mouseenter', () => {
          onHover(d.date, { date: d.date, open: d.open, high: d.high, low: d.low, close: d.close, change: d.change_pct ?? 0 });
        })
        .on('mouseleave', () => onHover(null))
        .on('click', () => onDayClick(d.date));
    });

    // News particles
    if (particles.length > 0) {
      const particleGroup = g.append('g').attr('class', 'particles');
      const particleMap = new Map<string, NewsParticle[]>();
      particles.forEach((p) => {
        if (!particleMap.has(p.d)) particleMap.set(p.d, []);
        particleMap.get(p.d)!.push(p);
      });

      displayData.forEach((d) => {
        const ps = particleMap.get(d.date);
        if (!ps) return;
        const x = (xScale(d.date) ?? 0) + xScale.bandwidth() / 2;
        const baseY = yScale(d.high) - 10;

        ps.slice(0, 5).forEach((p, pi) => {
          const sentimentColor = p.s === 'positive' ? '#26a69a' : p.s === 'negative' ? '#ef5350' : '#8b949e';
          const isHighlighted = highlightedArticleIds?.includes(p.news_id);
          const isLocked = lockedNewsId === p.news_id;
          const color = highlightColor || sentimentColor;

          const r = isLocked ? 8 : isHighlighted ? 7 : 5;
          particleGroup.append('circle')
            .attr('cx', x + (pi - ps.length / 2) * 3)
            .attr('cy', baseY - pi * 10)
            .attr('r', r)
            .style('fill', isLocked ? '#58a6ff' : color)
            .style('opacity', isLocked ? 1 : 0.75)
            .style('cursor', 'pointer')
            .style('stroke', isLocked ? '#fff' : 'none')
            .style('stroke-width', isLocked ? 1.5 : 0)
            .on('click', (event: MouseEvent) => {
              event.stopPropagation();
              onArticleSelect({ newsId: p.news_id, date: p.d });
            })
            .on('mouseenter', function() {
              d3.select(this).style('opacity', 1).attr('r', r + 2);
            })
            .on('mouseleave', function() {
              d3.select(this).style('opacity', 0.75).attr('r', r);
            });
        });
      });
    }

    // Brush for range selection
    const brush = d3.brushX()
      .extent([[0, 0], [innerW, innerH]])
      .on('end', (event: d3.D3BrushEvent<unknown>) => {
        if (!event.selection) {
          setBrushExtent(null);
          onRangeSelect(null);
          return;
        }
        const [x0, x1] = event.selection as [number, number];
        const dates = displayData
          .filter((d) => {
            const px = (xScale(d.date) ?? 0);
            return px >= x0 && px + xScale.bandwidth() <= x1;
          })
          .map((d) => d.date);

        if (dates.length >= 2) {
          const firstClose = displayData.find((d) => d.date === dates[0])?.open || 0;
          const lastClose = displayData.find((d) => d.date === dates[dates.length - 1])?.close || 0;
          const priceChange = firstClose ? ((lastClose / firstClose) - 1) * 100 : 0;
          onRangeSelect({ startDate: dates[0], endDate: dates[dates.length - 1], priceChange });
        }
      });

    g.append('g')
      .attr('class', 'brush')
      .call(brush as any);

  }, [data, particles, lockedNewsId, highlightedArticleIds, highlightColor, brushExtent, onHover, onRangeSelect, onArticleSelect, onDayClick]);

  if (loading) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
        <div className="spinner" style={{ marginRight: 8 }} />
        加载 K 线数据...
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-red)', fontSize: 13, flexDirection: 'column', gap: 8 }}>
        <span>加载失败: {error}</span>
        <button className="filter-chip" onClick={() => setLoading(true)}>重试</button>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
      <svg ref={svgRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}
