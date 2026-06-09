from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pymysql
from dotenv import load_dotenv
from sklearn.preprocessing import MinMaxScaler

SEQ_LEN = 35
TEST_RATIO = 0.2
FEATURES = [
    "temperature",
    "humidity",
    "wind_speed",
    "solar_radiation",
    "precipitation",
    "power_kw",
    "panel_temp",
    "panel_humidity",
]
TARGET = "power_kw"
BASELINE_FEATURES = list(FEATURES)
METRICS_PATH = Path(__file__).with_name("metrics_baseline.json")


def load_joined() -> pd.DataFrame:
    load_dotenv()
    conn = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "weather"),
        password=os.getenv("MYSQL_PASSWORD", "weatherpass"),
        database=os.getenv("MYSQL_DATABASE", "weather"),
        charset="utf8mb4",
    )
    sql = """
    SELECT
      w.obs_time,
      w.temperature,
      w.humidity,
      w.wind_speed,
      w.solar_radiation,
      w.precipitation,
      p.power_kw,
      p.temperature AS panel_temp,
      p.humidity AS panel_humidity
    FROM weather_hourly w
    INNER JOIN power_hourly p
      ON p.hour_time = DATE_FORMAT(w.obs_time, '%%Y-%%m-%%d %%H:00:00')
      AND p.device_id = %s
    WHERE w.source = %s
    ORDER BY w.obs_time
    """
    device = os.getenv("DEVICE_ID", "RP2040-EMU-01")
    source = os.getenv("WEATHER_SOURCE", "public")
    df = pd.read_sql(sql, conn, params=(device, source))
    conn.close()
    for col in FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["solar_radiation"] = df["solar_radiation"].fillna(0.0)
    df["precipitation"] = df["precipitation"].fillna(0.0)
    df[FEATURES] = df[FEATURES].ffill().bfill().fillna(0.0)
    return df


def require_rows(df: pd.DataFrame, min_rows: int = 400) -> None:
    if len(df) < min_rows:
        raise RuntimeError(
            f"join 행 수 부족: {len(df)} (기상 backfill 30일 + power 시드 import 확인)"
        )


def split_index(n: int, test_ratio: float = TEST_RATIO) -> int:
    return int(n * (1 - test_ratio))


def make_baseline_xy(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """시각 t 의 BASELINE_FEATURES(8) -> 시각 t+1 power_kw."""
    data = df[BASELINE_FEATURES].astype(float).values
    y = df[TARGET].astype(float).values
    return data[:-1], y[1:]


def make_sequences(df: pd.DataFrame, seq_len: int = SEQ_LEN):
    data = df[FEATURES].astype(float).values
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(data)
    xs, ys = [], []
    target_idx = FEATURES.index(TARGET)
    for i in range(seq_len, len(scaled)):
        xs.append(scaled[i - seq_len : i])
        ys.append(scaled[i, target_idx])
    return np.array(xs), np.array(ys), scaler


def inverse_power_kw(scaler: MinMaxScaler, y_scaled: np.ndarray) -> np.ndarray:
    idx = FEATURES.index(TARGET)
    lo, hi = scaler.data_min_[idx], scaler.data_max_[idx]
    return y_scaled * (hi - lo) + lo


def save_baseline_metrics(mae: float, rmse: float, r2: float) -> None:
    METRICS_PATH.write_text(
        json.dumps({"mae_kw": mae, "rmse_kw": rmse, "r2": r2}, indent=2),
        encoding="utf-8",
    )


def load_baseline_metrics() -> dict | None:
    if not METRICS_PATH.exists():
        return None
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
