"""
GET /api/predict/{symbol}/forecast        — XGBoost 预测
GET /api/predict/{symbol}/similar-days    — 相似历史区间
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import json
import pandas as pd

from database import get_conn
from ml.inference import generate_forecast, find_similar_periods

router = APIRouter()


@router.get("/{symbol}/forecast")
def get_forecast(symbol: str, window: int = Query(7, ge=7, le=60)):
    """获取股票预测"""
    forecast = generate_forecast(symbol, window_days=window)
    if not forecast:
        return _empty_forecast(symbol, window)
    return forecast


@router.get("/{symbol}/similar-days")
def get_similar_days(symbol: str, date: str = Query(...)):
    """查找历史相似交易日"""
    similar = find_similar_periods(symbol, target_date=date)
    return similar


def _empty_forecast(symbol: str, window: int):
    """返回空预测（当数据不足时）"""
    return {
        "symbol": symbol,
        "window_days": window,
        "forecast_date": "",
        "news_summary": {
            "total": 0, "positive": 0, "negative": 0, "neutral": 0,
            "sentiment_ratio": 0,
            "top_headlines": [],
            "top_impact": [],
        },
        "prediction": {},
        "similar_periods": [],
        "similar_stats": {"count": 0, "up_ratio_5d": 0, "up_ratio_10d": 0,
                          "avg_ret_5d": None, "avg_ret_10d": None},
        "conclusion": f"暂无 {symbol} 的足够历史数据用于预测，建议先同步 K 线数据。",
    }
