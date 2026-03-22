# Astock — A 股市场事件驱动分析与选股工具

> 基于 [PokieTicker](https://github.com/qiangzhang2009/PokieTicker) 架构，针对中国 A 股市场重新构建

## 产品定位

**"理解每一次涨跌背后的故事"** — 为 A 股散户投资者提供事件驱动思维框架：
- K 线图叠加新闻事件，理解"为什么"涨/跌
- 新闻情感 AI 分析，判断市场情绪
- 选股筛选 + 择时信号

## 技术栈

| 层级 | 技术选型 | 理由 |
|------|---------|------|
| 前端 | React + TypeScript + Vite + D3.js | 与 PokieTicker 相同架构，可复用组件 |
| 后端 | FastAPI + SQLite (WAL) | 高性能、易部署 |
| 数据源 | AKShare (免费，无需 Key) | A 股数据全覆盖，无需注册 |
| AI 情感分析 | DeepSeek API (sk-c0f9cb94bb0c42d38a43c9e9df97d31c) | 低成本，中文理解强 |
| 机器学习 | XGBoost + A 股特征工程 | 预测涨跌方向 |
| 新闻源 | 东方财富网爬虫 + AKShare 新闻接口 | 中文财经新闻全覆盖 |
| 部署 | Docker + Railway/Render | 快速上线，无需服务器 |

## 数据架构

```
AKShare (免费数据)
    │
    ├── stock_zh_a_hist() → 日线 OHLCV (K 线)
    ├── stock_zh_a_spot_em() → 实时行情
    ├── stock_info_a_code_name() → 股票列表
    └── akshare 新闻接口 / 东方财富爬虫 → 新闻
           ↓
    SQLite 数据库 (9张表)
           ↓
    AI Layer (DeepSeek)
    ├── Layer 1: 情感分类 (利好/利空/中性) + 原因摘要
    └── Layer 2: 深度分析 (按需)
           ↓
    ML Layer (XGBoost)
    ├── 特征工程 (31个特征)
    └── 预测: T+1/T+3/T+5 涨跌方向
           ↓
    FastAPI REST API
           ↓
    前端 React + D3.js
```

## 数据库 Schema (SQLite)

| 表名 | 用途 | 字段 |
|------|------|------|
| `stocks` | 股票白名单 | symbol, name, sector, market, last_fetch |
| `ohlc` | 日线 OHLCV | symbol, date, open, high, low, close, volume, turnover |
| `news_raw` | 原始新闻 | id, title, content, source, published_at |
| `news_aligned` | 对齐到交易日 | news_id, symbol, trade_date, ret_t0/t1/t3/t5 |
| `layer1_results` | AI 情感结果 | news_id, symbol, sentiment, reason, summary |
| `predictions` | XGBoost 预测 | symbol, date, window, direction, confidence |
| `weekly_log` | 数据更新日志 | id, action, tickers_updated, created_at |

## 股票代码格式

```
上交所: 600xxx, 601xxx, 688xxx (科创板)
深交所: 000xxx (主板), 001xxx (主板), 002xxx (中小板), 003xxx (主板), 300xxx (创业板)
北交所: 8xxxxx
```

## 机器学习特征 (A 股定制, 33个)

**新闻特征 (12个)**
- n_articles, sentiment_score, positive_ratio, negative_ratio
- 3/5/10 日滚动均值, 情感动量

**技术指标 (18个)**
- 收益率: ret_1/3/5/10d (shift 防止泄露)
- 波动率: volatility_5/10d
- 成交量比: volume_ratio_5d
- RSI-14, 均线交叉: MA5/MA20
- 涨跌停标记 (A 股特有)
- 换手率, 主力净流入 (需 AKShare)
- MACD, BOLL 布林带
- 日涨幅, 日跌幅, 振幅

**市场特征 (3个)**
- 上证/深证指数收益率 (大盘联动)
- 行业板块涨跌 (板块轮动)
- 北向资金 (沪深港通)

## A 股特有功能

### 1. 选股器
- 按行业板块筛选
- 按市值、PE、换手率筛选
- 按近期涨跌幅排序
- 按新闻情感排序

### 2. 涨跌停追踪
- 涨停股池 / 跌停股池
- 炸板预警 (涨停打开)
- 强势股 / 弱势股

### 3. 板块轮动
- 行业板块热力图
- 概念板块异动
- 每日主线题材

### 4. 择时信号
- AI 综合信号: 强烈买入/买入/中性/卖出/强烈卖出
- 大盘环境判断 (上证指数状态)
- 情绪周期判断

## API 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/stocks` | GET | 获取股票列表 |
| `/api/stocks/search?q=` | GET | 搜索股票 |
| `/api/stocks/{symbol}/ohlc` | GET | 获取 K 线数据 |
| `/api/news/{symbol}/particles` | GET | 获取新闻粒子(图表用) |
| `/api/news/{symbol}?date=` | GET | 获取当日新闻 |
| `/api/news/{symbol}/categories` | GET | 获取新闻分类 |
| `/api/news/{symbol}/range` | GET | 获取区间新闻 |
| `/api/predict/{symbol}/forecast` | GET | 获取 AI 预测 |
| `/api/predict/{symbol}/similar` | GET | 相似历史区间 |
| `/api/sector/board` | GET | 板块行情 |
| `/api/sector/limit-up` | GET | 涨停股池 |
| `/api/screener` | POST | 选股筛选 |
| `/api/analysis/range` | POST | 区间 AI 分析 |
| `/api/analysis/deep` | POST | 新闻深度分析 |

## 部署架构

```
GitHub (qiangzhang2009/Astock)
    │
    ├── Railway.app (或 Render)
    │   ├── Backend: FastAPI (Python)
    │   └── Frontend: Nginx (静态文件)
    │
    └── Vercel (可选)
        └── Frontend: Vite build
```

## 阶段规划

### Phase 1: 基础框架 (当前)
- [x] 项目架构设计
- [ ] 数据层: AKShare → SQLite
- [ ] API 层: FastAPI 路由
- [ ] 前端: React + D3 K 线 + 新闻粒子
- [ ] DeepSeek 情感分析
- [ ] 选股器基础功能

### Phase 2: 高级功能
- [ ] XGBoost 预测模型
- [ ] 涨跌停追踪
- [ ] 板块轮动热力图
- [ ] 择时信号面板

### Phase 3: 数据增强
- [ ] 实时行情 (WebSocket)
- [ ] 东方财富新闻深度爬虫
- [ ] 机构持仓数据
- [ ] 北向资金追踪
