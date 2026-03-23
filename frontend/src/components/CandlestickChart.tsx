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

// MA line configs
const MA_CONFIGS = [
  { key: 'ma5', label: 'MA5', period: 5, color: '#f0883e' },
  { key: 'ma10', label: 'MA10', period: 10, color: '#58a6ff' },
  { key: 'ma20', label: 'MA20', period: 20, color: '#bc8cff' },
  { key: 'ma60', label: 'MA60', period: 60, color: '#3fb950' },
];

type IndicatorKey = 'ma5' | 'ma10' | 'ma20' | 'ma60' | 'rsi' | 'macd' | 'boll';

function computeMA(data: OHLCRow[], period: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null);
    } else {
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += data[i - j].close;
      }
      result.push(sum / period);
    }
  }
  return result;
}

function computeRSI(data: OHLCRow[], period: number = 14): (number | null)[] {
  const result: (number | null)[] = [];
  if (data.length < period + 1) return data.map(() => null);

  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const change = data[i].close - data[i - 1].close;
    if (change > 0) avgGain += change; else avgLoss -= change;
  }
  avgGain /= period;
  avgLoss /= period;

  for (let i = 0; i < period; i++) result.push(null);

  for (let i = period; i < data.length; i++) {
    if (i > period) {
      const change = data[i].close - data[i - 1].close;
      const gain = change > 0 ? change : 0;
      const loss = change < 0 ? -change : 0;
      avgGain = (avgGain * (period - 1) + gain) / period;
      avgLoss = (avgLoss * (period - 1) + loss) / period;
    }
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    result.push(100 - 100 / (1 + rs));
  }
  return result;
}

interface MACDResult { macd: number; signal: number; histogram: number; }
function computeMACD(data: OHLCRow[], fast = 12, slow = 26, signal = 9): MACDResult[] {
  function calcEma(values: number[], span: number): number[] {
    const k = 2 / (span + 1);
    const result: number[] = [];
    let ema = values[0];
    for (const v of values) {
      ema = v * k + ema * (1 - k);
      result.push(ema);
    }
    return result;
  }
  const closes: number[] = data.map(d => d.close);
  if (closes.length < slow + signal) {
    return data.map(() => ({ macd: 0, signal: 0, histogram: 0 }));
  }
  const fastEma = calcEma(closes, fast);
  const slowEma = calcEma(closes, slow);
  const macdLine: number[] = fastEma.map((v, i) => v - slowEma[i]);
  const sigEma = calcEma(macdLine, signal);
  return data.map((_, i) => ({
    macd: macdLine[i] ?? 0,
    signal: sigEma[i] ?? 0,
    histogram: (macdLine[i] ?? 0) - (sigEma[i] ?? 0),
  }));
}

function computeBOLL(data: OHLCRow[], period = 20, k = 2): { upper: number | null; middle: number | null; lower: number | null }[] {
  const result: { upper: number | null; middle: number | null; lower: number | null }[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push({ upper: null, middle: null, lower: null });
    } else {
      let sum = 0;
      for (let j = 0; j < period; j++) sum += data[i - j].close;
      const mean = sum / period;
      let varSum = 0;
      for (let j = 0; j < period; j++) varSum += Math.pow(data[i - j].close - mean, 2);
      const std = Math.sqrt(varSum / period);
      result.push({ upper: mean + k * std, middle: mean, lower: mean - k * std });
    }
  }
  return result;
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
  const [showIndicators, setShowIndicators] = useState<Record<IndicatorKey, boolean>>({
    ma5: true, ma10: true, ma20: true, ma60: false,
    rsi: true, macd: true, boll: true,
  });
  const [brushExtent, setBrushExtent] = useState<[Date, Date] | null>(null);

  const toggleIndicator = (key: IndicatorKey) => {
    setShowIndicators(prev => ({ ...prev, [key]: !prev[key] }));
  };

  useEffect(() => {
    setLoading(true);
    setError('');
    Promise.all([
      axios.get(`/api/stocks/${symbol}/ohlc?days=730`).then((r) => r.data),
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
  }, [data, particles, lockedNewsId, highlightedArticleIds, highlightColor, brushExtent, showIndicators]);

  const drawChart = useCallback(() => {
    const container = containerRef.current!;
    const svg = d3.select(svgRef.current!);
    svg.selectAll('*').remove();

    const width = container.clientWidth;
    const totalH = container.clientHeight;

    // Panel heights
    const rsiH = showIndicators.rsi ? 70 : 0;
    const macdH = showIndicators.macd ? 75 : 0;
    const priceH = totalH - rsiH - macdH - 10;

    const margin = { top: 10, right: 60, bottom: 5, left: 60 };
    const innerW = width - margin.left - margin.right;

    const showVol = true;
    const volH = 0;
    const priceInnerH = priceH - margin.top - margin.bottom - volH;

    if (innerW <= 0 || priceInnerH <= 0) return;

    const displayData = data.filter((d) => d.close != null);
    if (!displayData.length) return;

    // Compute all indicators
    const maMap: Record<string, (number | null)[]> = {};
    MA_CONFIGS.forEach(({ key, period }) => {
      maMap[key] = computeMA(displayData, period);
    });
    const rsiValues = computeRSI(displayData, 14);
    const macdValues = computeMACD(displayData);
    const bollValues = computeBOLL(displayData);

    const parsedDates = displayData.map((d) => new Date(d.date + 'T00:00:00'));

    const xScale = d3.scaleBand()
      .domain(displayData.map((d) => d.date))
      .range([0, innerW])
      .padding(0.2);

    const yMin = d3.min(displayData, (d) => d.low)! * 0.998;
    const yMax = d3.max(displayData, (d) => d.high)! * 1.002;
    const yScale = d3.scaleLinear().domain([yMin, yMax]).range([priceInnerH, 0]);

    const maxVol = d3.max(displayData, (d) => d.volume) || 1;
    const volScale = d3.scaleLinear().domain([0, maxVol]).range([volH - 5, 0]);
    const volInnerH = volH;

    const rsiScale = d3.scaleLinear().domain([0, 100]).range([rsiH - 20, 5]);
    const macdMax = d3.max(macdValues, (d) => Math.abs(d.histogram)) || 1;
    const macdScale = d3.scaleLinear().domain([-macdMax, macdMax]).range([macdH - 15, 5]);

    const g = svg
      .attr('width', width)
      .attr('height', totalH)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // ─── Price Panel ───────────────────────────────────────────────
    const priceG = g.append('g').attr('class', 'price-panel');

    // Grid
    priceG.append('g')
      .attr('class', 'grid')
      .call(d3.axisLeft(yScale).tickSize(-innerW).tickFormat(() => ''))
      .selectAll('line')
      .style('stroke', '#21262d')
      .style('stroke-dasharray', '2,2');
    priceG.selectAll('.grid .domain').remove();

    // Y Axis
    priceG.append('g')
      .call(d3.axisLeft(yScale).ticks(8).tickFormat((d) => `¥${Number(d).toFixed(0)}`))
      .selectAll('text')
      .style('fill', '#8b949e')
      .style('font-size', '11px')
      .style('font-family', 'Menlo, monospace');
    priceG.selectAll('.domain').style('stroke', '#30363d');
    priceG.selectAll('.tick line').style('stroke', '#30363d');

    // X Axis
    priceG.append('g')
      .attr('transform', `translate(0,${priceInnerH})`)
      .call(d3.axisBottom(
        d3.scaleTime().domain(d3.extent(parsedDates) as [Date, Date]).range([0, innerW])
      ).ticks(8).tickFormat(d3.timeFormat('%m/%d') as any))
      .selectAll('text')
      .style('fill', '#8b949e')
      .style('font-size', '10px');
    priceG.selectAll('.domain').style('stroke', '#30363d');
    priceG.selectAll('.tick line').style('stroke', '#30363d');

    // Bollinger Bands
    if (showIndicators.boll) {
      const bollPath = d3.line<{ x: number; y: number }>()
        .x(d => d.x).y(d => d.y).curve(d3.curveMonotoneX);

      const upperPoints: { x: number; y: number }[] = [];
      const middlePoints: { x: number; y: number }[] = [];
      const lowerPoints: { x: number; y: number }[] = [];

      bollValues.forEach((b, i) => {
        if (b.upper === null) return;
        const x = (xScale(displayData[i].date) ?? 0) + xScale.bandwidth() / 2;
        upperPoints.push({ x, y: yScale(b.upper) });
        middlePoints.push({ x, y: yScale(b.middle!) });
        lowerPoints.push({ x, y: yScale(b.lower!) });
      });

      // Fill between upper and lower
      if (upperPoints.length > 0 && lowerPoints.length > 0) {
        priceG.append('path')
          .datum(upperPoints)
          .attr('d', d3.area<{ x: number; y: number }>()
            .x(d => d.x)
            .y0((_, i) => yScale(bollValues[displayData.findIndex(d => (xScale(d.date) ?? 0) + xScale.bandwidth() / 2 === upperPoints[i]?.x)]?.lower ?? 0))
            .y1(d => d.y)
            .curve(d3.curveMonotoneX)
          )
          .style('fill', 'rgba(96, 125, 139, 0.08)')
          .style('stroke', 'none');
      }

      if (upperPoints.length > 0) {
        priceG.append('path').datum(upperPoints).attr('d', bollPath)
          .style('fill', 'none').style('stroke', 'rgba(96,125,139,0.5)').style('stroke-width', 1).style('stroke-dasharray', '4,2');
        priceG.append('path').datum(middlePoints).attr('d', bollPath)
          .style('fill', 'none').style('stroke', 'rgba(96,125,139,0.4)').style('stroke-width', 1);
        priceG.append('path').datum(lowerPoints).attr('d', bollPath)
          .style('fill', 'none').style('stroke', 'rgba(96,125,139,0.5)').style('stroke-width', 1).style('stroke-dasharray', '4,2');
      }
    }

    // Volume bars
    if (showVol && volH > 0) {
      const volG = priceG.append('g').attr('class', 'volume-bars').attr('transform', `translate(0,${priceInnerH - volH})`);
      displayData.forEach((d) => {
        const x = xScale(d.date)!;
        const barH = volInnerH - volScale(d.volume);
        volG.append('rect')
          .attr('x', x).attr('y', volScale(d.volume))
          .attr('width', xScale.bandwidth())
          .attr('height', Math.max(1, barH))
          .style('fill', (d.change_pct || 0) >= 0 ? 'rgba(38,166,154,0.2)' : 'rgba(239,83,80,0.2)');
      });
    }

    // MA Lines
    MA_CONFIGS.forEach(({ key, color }) => {
      if (!showIndicators[key as keyof typeof showIndicators]) return;
      const maValues = maMap[key];
      const lineGen = d3.line<{ x: number; y: number }>()
        .x((d) => d.x).y((d) => d.y)
        .defined((d) => d.y !== null)
        .curve(d3.curveMonotoneX);

      const points: { x: number; y: number }[] = [];
      maValues.forEach((val, i) => {
        if (val !== null) {
          const x = (xScale(displayData[i].date) ?? 0) + xScale.bandwidth() / 2;
          points.push({ x, y: yScale(val) });
        }
      });

      if (points.length > 0) {
        priceG.append('path')
          .datum(points).attr('class', `ma-line ma-${key}`)
          .attr('d', lineGen)
          .style('fill', 'none').style('stroke', color)
          .style('stroke-width', 1.5).style('opacity', 0.85);
      }
    });

    // Candlesticks
    const candleGroup = priceG.append('g').attr('class', 'candles');
    displayData.forEach((d) => {
      const x = (xScale(d.date) ?? 0) + xScale.bandwidth() / 2;
      const isUp = d.close >= d.open;
      const color = isUp ? '#26a69a' : '#ef5350';

      candleGroup.append('line')
        .attr('x1', x).attr('x2', x)
        .attr('y1', yScale(d.high)).attr('y2', yScale(d.low))
        .style('stroke', color).style('stroke-width', 1);

      const bodyTop = yScale(Math.max(d.open, d.close));
      const bodyHeight = Math.max(1, Math.abs(yScale(d.open) - yScale(d.close)));
      candleGroup.append('rect')
        .attr('x', xScale(d.date)!).attr('y', bodyTop)
        .attr('width', xScale.bandwidth()).attr('height', bodyHeight)
        .style('fill', color).style('stroke', color).style('stroke-width', 0.5);

      if (d.limit_up) {
        candleGroup.append('rect')
          .attr('x', xScale(d.date)!).attr('y', yScale(d.high))
          .attr('width', xScale.bandwidth()).attr('height', yScale(d.low) - yScale(d.high))
          .style('fill', 'rgba(248,81,73,0.06)').style('stroke', 'none');
      }

      candleGroup.append('rect')
        .attr('x', xScale(d.date)!).attr('y', 0)
        .attr('width', xScale.bandwidth()).attr('height', priceInnerH)
        .style('fill', 'transparent').style('cursor', 'crosshair')
        .on('mouseenter', () => {
          onHover(d.date, { date: d.date, open: d.open, high: d.high, low: d.low, close: d.close, change: d.change_pct ?? 0 });
        })
        .on('mouseleave', () => onHover(null))
        .on('click', () => onDayClick(d.date));
    });

    // News particles
    if (particles.length > 0) {
      const particleGroup = priceG.append('g').attr('class', 'particles');
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
            .on('mouseenter', function () {
              d3.select(this).style('opacity', 1).attr('r', r + 2);
            })
            .on('mouseleave', function () {
              d3.select(this).style('opacity', 0.75).attr('r', r);
            });
        });
      });
    }

    // Brush for range selection
    const brush = d3.brushX()
      .extent([[0, 0], [innerW, priceInnerH]])
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

    priceG.append('g').attr('class', 'brush').call(brush as any);

    // MA Legend
    const legendG = priceG.append('g').attr('class', 'ma-legend').attr('transform', `translate(${innerW - 150}, -5)`);
    let legendX = 0;
    MA_CONFIGS.forEach(({ key, label, color }) => {
      if (!showIndicators[key as keyof typeof showIndicators]) return;
      legendG.append('line').attr('x1', legendX).attr('x2', legendX + 12)
        .attr('y1', 5).attr('y2', 5).style('stroke', color).style('stroke-width', 1.5);
      legendG.append('text').attr('x', legendX + 15).attr('y', 9)
        .style('fill', color).style('font-size', '10px')
        .style('font-family', 'Menlo, monospace').text(label);
      legendX += 52;
    });

    // ─── RSI Panel ─────────────────────────────────────────────────
    if (showIndicators.rsi) {
      const rsiG = g.append('g')
        .attr('class', 'rsi-panel')
        .attr('transform', `translate(0,${priceH})`);

      rsiG.append('text').attr('x', 4).attr('y', 12)
        .style('fill', '#6e7681').style('font-size', '10px').style('font-family', 'Menlo, monospace')
        .text('RSI(14)');

      // RSI reference lines
      [30, 50, 70].forEach(level => {
        rsiG.append('line')
          .attr('x1', 0).attr('x2', innerW)
          .attr('y1', rsiScale(level)).attr('y2', rsiScale(level))
          .style('stroke', level === 50 ? '#30363d' : '#21262d')
          .style('stroke-dasharray', level === 50 ? '2,2' : '1,3');
        rsiG.append('text')
          .attr('x', innerW + 2).attr('y', rsiScale(level) + 3)
          .style('fill', '#6e7681').style('font-size', '9px').style('font-family', 'Menlo, monospace')
          .text(level);
      });

      // RSI line
      const rsiPoints: { x: number; y: number }[] = [];
      rsiValues.forEach((v, i) => {
        if (v !== null) {
          const x = (xScale(displayData[i].date) ?? 0) + xScale.bandwidth() / 2;
          rsiPoints.push({ x, y: rsiScale(v) });
        }
      });
      if (rsiPoints.length > 0) {
        rsiG.append('path')
          .datum(rsiPoints)
          .attr('d', d3.line<{ x: number; y: number }>()
            .x(d => d.x).y(d => d.y).curve(d3.curveMonotoneX))
          .style('fill', 'none').style('stroke', '#ce93d8')
          .style('stroke-width', 1.5);
      }

      // RSI X axis
      rsiG.append('g')
        .attr('transform', `translate(0,${rsiH - 15})`)
        .call(d3.axisBottom(
          d3.scaleTime().domain(d3.extent(parsedDates) as [Date, Date]).range([0, innerW])
        ).ticks(4).tickFormat(d3.timeFormat('%m/%d') as any))
        .selectAll('text').style('fill', '#6e7681').style('font-size', '9px');
      rsiG.selectAll('.domain').style('stroke', '#30363d');
      rsiG.selectAll('.tick line').style('stroke', '#30363d');
    }

    // ─── MACD Panel ────────────────────────────────────────────────
    if (showIndicators.macd) {
      const macdG = g.append('g')
        .attr('class', 'macd-panel')
        .attr('transform', `translate(0,${priceH + rsiH})`);

      macdG.append('text').attr('x', 4).attr('y', 12)
        .style('fill', '#6e7681').style('font-size', '10px').style('font-family', 'Menlo, monospace')
        .text('MACD(12,26,9)');

      // MACD zero line
      macdG.append('line')
        .attr('x1', 0).attr('x2', innerW)
        .attr('y1', macdScale(0)).attr('y2', macdScale(0))
        .style('stroke', '#30363d').style('stroke-width', 0.5);

      // MACD Histogram
      macdValues.forEach((m, i) => {
        const x = xScale(displayData[i].date)!;
        const histHeight = Math.abs(macdScale(0) - macdScale(m.histogram));
        macdG.append('rect')
          .attr('x', x).attr('y', m.histogram >= 0 ? macdScale(m.histogram) : macdScale(0))
          .attr('width', xScale.bandwidth())
          .attr('height', Math.max(1, histHeight))
          .style('fill', m.histogram >= 0 ? 'rgba(38,166,154,0.6)' : 'rgba(239,83,80,0.6)');
      });

      // MACD line
      const macdLinePts: { x: number; y: number }[] = [];
      const signalPts: { x: number; y: number }[] = [];
      macdValues.forEach((m, i) => {
        const x = (xScale(displayData[i].date) ?? 0) + xScale.bandwidth() / 2;
        macdLinePts.push({ x, y: macdScale(m.macd) });
        signalPts.push({ x, y: macdScale(m.signal) });
      });
      if (macdLinePts.length > 0) {
        const lineGen = d3.line<{ x: number; y: number }>()
          .x(d => d.x).y(d => d.y).curve(d3.curveMonotoneX);
        macdG.append('path').datum(macdLinePts).attr('d', lineGen)
          .style('fill', 'none').style('stroke', '#42a5f5').style('stroke-width', 1.5);
        macdG.append('path').datum(signalPts).attr('d', lineGen)
          .style('fill', 'none').style('stroke', '#ef5350').style('stroke-width', 1.2);
      }

      // MACD legend
      macdG.append('line').attr('x1', 95).attr('x2', 108).attr('y1', 10).attr('y2', 10)
        .style('stroke', '#42a5f5').style('stroke-width', 1.5);
      macdG.append('text').attr('x', 112).attr('y', 14)
        .style('fill', '#42a5f5').style('font-size', '9px').style('font-family', 'Menlo, monospace').text('DIF');
      macdG.append('line').attr('x1', 145).attr('x2', 158).attr('y1', 10).attr('y2', 10)
        .style('stroke', '#ef5350').style('stroke-width', 1.2);
      macdG.append('text').attr('x', 162).attr('y', 14)
        .style('fill', '#ef5350').style('font-size', '9px').style('font-family', 'Menlo, monospace').text('DEA');

      // MACD X axis
      macdG.append('g')
        .attr('transform', `translate(0,${macdH - 15})`)
        .call(d3.axisBottom(
          d3.scaleTime().domain(d3.extent(parsedDates) as [Date, Date]).range([0, innerW])
        ).ticks(4).tickFormat(d3.timeFormat('%m/%d') as any))
        .selectAll('text').style('fill', '#6e7681').style('font-size', '9px');
      macdG.selectAll('.domain').style('stroke', '#30363d');
      macdG.selectAll('.tick line').style('stroke', '#30363d');
    }

  }, [data, particles, lockedNewsId, highlightedArticleIds, highlightColor, brushExtent, showIndicators, onHover, onRangeSelect, onArticleSelect, onDayClick]);

  const allIndicatorKeys: { key: IndicatorKey; label: string; color: string }[] = [
    { key: 'ma5', label: 'MA5', color: '#f0883e' },
    { key: 'ma10', label: 'MA10', color: '#58a6ff' },
    { key: 'ma20', label: 'MA20', color: '#bc8cff' },
    { key: 'ma60', label: 'MA60', color: '#3fb950' },
    { key: 'boll', label: 'BOLL', color: '#78909c' },
    { key: 'rsi', label: 'RSI', color: '#ce93d8' },
    { key: 'macd', label: 'MACD', color: '#42a5f5' },
  ];

  const loadingControls = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
      {allIndicatorKeys.map(({ key, label, color }) => (
        <button key={key} onClick={() => toggleIndicator(key)}
          style={{
            background: showIndicators[key] ? `${color}22` : 'var(--bg-tertiary)',
            border: `1px solid ${showIndicators[key] ? color : 'var(--border-color)'}`,
            borderRadius: 4, padding: '2px 6px', fontSize: 10,
            color: showIndicators[key] ? color : 'var(--text-muted)',
            cursor: 'pointer',
          }}>
          {label}
        </button>
      ))}
    </div>
  );

  if (loading) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: 13, gap: 12, flexDirection: 'column' }}>
        <div className="spinner" />
        <span>加载 K 线数据...</span>
        {loadingControls}
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
      {/* Indicator toggles */}
      <div style={{
        position: 'absolute', top: 4, right: 68,
        display: 'flex', gap: 4, alignItems: 'center', flexWrap: 'wrap', zIndex: 10, maxWidth: 380,
      }}>
        {allIndicatorKeys.map(({ key, label, color }) => (
          <button key={key} onClick={() => toggleIndicator(key)}
            style={{
              background: showIndicators[key] ? `${color}33` : 'rgba(33,38,45,0.8)',
              border: `1px solid ${showIndicators[key] ? color : '#30363d'}`,
              borderRadius: 4, padding: '2px 6px', fontSize: 10,
              color: showIndicators[key] ? color : '#6e7681',
              cursor: 'pointer',
              fontFamily: 'Menlo, monospace',
            }}>
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
