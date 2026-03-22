# Astock — A 股事件驱动分析与选股工具

**基于 [PokieTicker](https://github.com/qiangzhang2009/PokieTicker) 架构，针对中国 A 股市场重新构建**

🔗 **在线演示**: [astock.vercel.app](https://astock.vercel.app)

---

## 核心功能

- **K 线 + 新闻叠加** — 在 K 线图上叠加新闻粒子，点击查看当日新闻
- **新闻情感 AI 分析** — DeepSeek 模型分析新闻对股价的影响（利好/利空/中性）
- **选股器** — 按行业板块、涨跌停、涨跌幅筛选 A 股
- **涨跌停追踪** — 实时监控涨停/跌停股池
- **择时信号** — 基于新闻情感 + 技术指标的 T+1/T+3/T+5 预测
- **区间 AI 分析** — 拖拽 K 线区间，AI 生成涨跌原因分析

---

## 技术架构

```
AKShare (免费数据) → SQLite → FastAPI → React + D3.js
                        ↓
                 DeepSeek API (情感分析)
                        ↓
                 XGBoost (涨跌预测)
```

---

## 快速开始

### 前端 + 后端

```bash
# 克隆项目
git clone https://github.com/qiangzhang2009/Astock.git
cd Astock

# 安装前端依赖
cd frontend && npm install && cd ..

# 安装后端依赖
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 同步股票数据
python -c "
from backend.data.akshare_client import sync_all_defaults
sync_all_defaults()
"

# 启动后端
uvicorn backend.api.main:app --reload --port 8000

# 启动前端（新终端）
cd frontend && npm run dev
```

打开: **http://localhost:7777/Astock**

### Docker 部署

```bash
docker build -t astock .
docker run -p 8000:8000 -e DEEPSEEK_API_KEY=your_key astock
```

---

## 环境变量

```bash
cp .env.example .env
# 编辑 .env 填入:
# DEEPSEEK_API_KEY=sk-xxxxx  # DeepSeek API Key
```

---

## 数据说明

| 数据源 | 用途 | 费用 |
|--------|------|------|
| AKShare | K 线数据 | 免费 |
| DeepSeek API | 新闻情感分析 | 低成本 |

> AKShare 数据源存在几秒到几十秒延迟，仅适合学习研究、复盘分析，不建议用于高频实盘交易。

---

## 许可证

MIT
