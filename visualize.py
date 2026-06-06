from __future__ import annotations

import warnings
warnings.filterwarnings("ignore")
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 한글 폰트 설정
matplotlib.rcParams["font.family"] = "NanumGothic"
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyArrowPatch
import matplotlib.dates as mdates
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.models import Sequential

from ml_shared import (
    FEATURES, SEQ_LEN, TARGET,
    inverse_power_kw, load_joined, make_baseline_xy,
    make_sequences, require_rows, split_index, BASELINE_FEATURES,
)

# ── 스타일 ──────────────────────────────────────────────
plt.rcParams.update({
    "figure.facecolor":  "#0d1117",
    "axes.facecolor":    "#161b22",
    "axes.edgecolor":    "#30363d",
    "axes.labelcolor":   "#c9d1d9",
    "axes.titlecolor":   "#e6edf3",
    "text.color":        "#c9d1d9",
    "xtick.color":       "#8b949e",
    "ytick.color":       "#8b949e",
    "grid.color":        "#21262d",
    "grid.linestyle":    "--",
    "grid.alpha":        0.6,
    "legend.facecolor":  "#21262d",
    "legend.edgecolor":  "#30363d",
    "font.size":         9,
})

C_ACTUAL   = "#58a6ff"   # 실제값 (파랑)
C_BASE     = "#3fb950"   # Baseline (초록)
C_LSTM     = "#a371f7"   # LSTM (보라)
C_FUTURE   = "#f0883e"   # 미래 예측 (주황)
C_FILL     = "#e3b341"   # 오차 영역
C_FEATURE  = "#39c5cf"   # feature 색

# ── 데이터 로드 ─────────────────────────────────────────
print("데이터 로드 중...")
df = load_joined()
require_rows(df)
times = df["obs_time"].values

# ── Baseline 학습 ────────────────────────────────────────
print("Baseline 학습 중...")
X_b, y_b = make_baseline_xy(df)
cut_b     = split_index(len(X_b))
model_b   = HistGradientBoostingRegressor(max_depth=6, learning_rate=0.1, random_state=42)
model_b.fit(X_b[:cut_b], y_b[:cut_b])
pred_b    = model_b.predict(X_b[cut_b:])
y_b_test  = y_b[cut_b:]
times_b   = times[cut_b + 1: len(y_b) + 1]   # t+1 에 대응하는 시각
mae_b     = mean_absolute_error(y_b_test, pred_b)

# ── LSTM 학습 ────────────────────────────────────────────
print("LSTM 학습 중...")
X_l, y_l_sc, scaler = make_sequences(df, SEQ_LEN)
cut_l  = split_index(len(X_l))
model_l = Sequential([
    LSTM(64, input_shape=(SEQ_LEN, len(FEATURES))),
    Dense(1),
])
model_l.compile(optimizer="adam", loss="mse")
model_l.fit(X_l[:cut_l], y_l_sc[:cut_l],
            epochs=8, batch_size=32,
            validation_data=(X_l[cut_l:], y_l_sc[cut_l:]),
            verbose=0)
pred_l_sc = model_l.predict(X_l[cut_l:], verbose=0).flatten()
y_l_test  = inverse_power_kw(scaler, y_l_sc[cut_l:])
pred_l    = inverse_power_kw(scaler, pred_l_sc)
times_l   = times[SEQ_LEN + cut_l: SEQ_LEN + len(X_l)]
mae_l     = mean_absolute_error(y_l_test, pred_l)

# ── 미래 24시간 예측 (Baseline) ─────────────────────────
FUTURE_H = 24
last_row  = df[BASELINE_FEATURES].astype(float).values[-1].copy()
future_preds = []
for _ in range(FUTURE_H):
    p = float(model_b.predict([last_row])[0])
    future_preds.append(p)
    last_row = last_row.copy()
    last_row[FEATURES.index("power_kw")] = p

import pandas as pd
last_time = pd.Timestamp(times[-1])
future_times = [last_time + pd.Timedelta(hours=i+1) for i in range(FUTURE_H)]

# ── 그래프 레이아웃 ──────────────────────────────────────
fig = plt.figure(figsize=(18, 14))
fig.suptitle("발전량 예측 시각화  |  Weather-Lab", fontsize=15,
             fontweight="bold", color="#e6edf3", y=0.98)

gs = gridspec.GridSpec(3, 2, figure=fig,
                       hspace=0.42, wspace=0.28,
                       top=0.93, bottom=0.06,
                       left=0.06, right=0.97)

# ────────────────────────────────────────────────────────
# (1) 전체 실제값 + 테스트 구간 예측 (상단 전체)
# ────────────────────────────────────────────────────────
ax1 = fig.add_subplot(gs[0, :])

# 전체 실제 발전량
ax1.plot(times, df["power_kw"].values,
         color=C_ACTUAL, lw=1.0, alpha=0.55, label="실제 발전량")

# Train / Test 구분선
split_time = times[cut_b + 1]
ax1.axvline(x=split_time, color="#8b949e", lw=1, ls="--", alpha=0.7)
ax1.text(split_time, ax1.get_ylim()[1] if ax1.get_ylim()[1] > 0 else 5,
         "  Train | Test", color="#8b949e", fontsize=8, va="top")

# Baseline 예측
ax1.plot(times_b, pred_b,
         color=C_BASE, lw=1.4, alpha=0.85, label=f"Baseline 예측 (MAE {mae_b:.3f} kW)")

# LSTM 예측
ax1.plot(times_l, pred_l,
         color=C_LSTM, lw=1.4, alpha=0.85, label=f"LSTM 예측 (MAE {mae_l:.3f} kW)")

# 미래 예측
ax1.plot(future_times, future_preds,
         color=C_FUTURE, lw=2.0, ls="-", marker="o", ms=3,
         label=f"미래 24시간 예측 (Baseline)")
ax1.axvspan(future_times[0], future_times[-1],
            alpha=0.07, color=C_FUTURE)

ax1.set_title("전체 기간 실제값 vs 예측값  +  미래 24시간", fontsize=10)
ax1.set_ylabel("발전량 (kW)")
ax1.legend(loc="upper left", fontsize=8)
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
ax1.xaxis.set_major_locator(mdates.DayLocator(interval=3))
ax1.grid(True)
plt.setp(ax1.xaxis.get_majorticklabels(), rotation=30, ha="right")

# ────────────────────────────────────────────────────────
# (2) 테스트 구간 확대: 실제 vs Baseline vs LSTM
# ────────────────────────────────────────────────────────
ax2 = fig.add_subplot(gs[1, 0])

# 공통 시간 범위 (마지막 72시간)
n_show = min(72, len(times_b), len(times_l))
ax2.plot(times_b[-n_show:], y_b_test[-n_show:],
         color=C_ACTUAL, lw=1.5, label="실제값")
ax2.plot(times_b[-n_show:], pred_b[-n_show:],
         color=C_BASE, lw=1.5, ls="--", label=f"Baseline")
ax2.plot(times_l[-n_show:], pred_l[-n_show:],
         color=C_LSTM, lw=1.5, ls="-.", label=f"LSTM")

# 오차 영역
ax2.fill_between(times_b[-n_show:], y_b_test[-n_show:], pred_b[-n_show:],
                 alpha=0.15, color=C_BASE)
ax2.set_title("테스트 구간 확대 (최근 72시간)", fontsize=10)
ax2.set_ylabel("발전량 (kW)")
ax2.legend(fontsize=8)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %Hh"))
ax2.xaxis.set_major_locator(mdates.HourLocator(interval=12))
ax2.grid(True)
plt.setp(ax2.xaxis.get_majorticklabels(), rotation=30, ha="right")

# ────────────────────────────────────────────────────────
# (3) 미래 24시간 예측 상세
# ────────────────────────────────────────────────────────
ax3 = fig.add_subplot(gs[1, 1])

# 직전 48시간 실제값
past_n = 48
ax3.plot(times[-past_n:], df["power_kw"].values[-past_n:],
         color=C_ACTUAL, lw=1.5, label="과거 실제값 (48h)")

# 연결선
ax3.plot([times[-1], future_times[0]],
         [df["power_kw"].values[-1], future_preds[0]],
         color=C_FUTURE, lw=1.5, ls=":")

# 미래 예측
ax3.plot(future_times, future_preds,
         color=C_FUTURE, lw=2.2, marker="o", ms=5,
         label="미래 24시간 예측")

# 불확실성 표현 (±MAE)
fp = np.array(future_preds)
ax3.fill_between(future_times,
                 fp - mae_b * np.linspace(1, 2, FUTURE_H),
                 fp + mae_b * np.linspace(1, 2, FUTURE_H),
                 alpha=0.15, color=C_FUTURE, label=f"불확실성 범위 (±MAE)")

ax3.axvline(x=future_times[0], color="#8b949e", lw=1, ls="--", alpha=0.7)
ax3.text(future_times[0], ax3.get_ylim()[0] if ax3.get_ylim()[0] > 0 else 0,
         " 예측 시작", color="#8b949e", fontsize=8)
ax3.set_title("미래 24시간 발전량 예측 (Baseline)", fontsize=10)
ax3.set_ylabel("발전량 (kW)")
ax3.legend(fontsize=8)
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %Hh"))
ax3.xaxis.set_major_locator(mdates.HourLocator(interval=6))
ax3.grid(True)
plt.setp(ax3.xaxis.get_majorticklabels(), rotation=30, ha="right")

# ────────────────────────────────────────────────────────
# (4) 오차 분포 비교 (Baseline vs LSTM)
# ────────────────────────────────────────────────────────
ax4 = fig.add_subplot(gs[2, 0])

err_b = pred_b - y_b_test
# LSTM 오차: 공통 인덱스 맞춤
min_len = min(len(pred_l), len(y_l_test))
err_l = pred_l[:min_len] - y_l_test[:min_len]

bins = np.linspace(-2, 2, 50)
ax4.hist(err_b, bins=bins, alpha=0.6, color=C_BASE,
         label=f"Baseline  MAE={mae_b:.3f}")
ax4.hist(err_l, bins=bins, alpha=0.6, color=C_LSTM,
         label=f"LSTM  MAE={mae_l:.3f}")
ax4.axvline(0, color="#e6edf3", lw=1, ls="--")
ax4.set_title("예측 오차 분포 (실제 − 예측)", fontsize=10)
ax4.set_xlabel("오차 (kW)")
ax4.set_ylabel("빈도")
ax4.legend(fontsize=8)
ax4.grid(True)

# ────────────────────────────────────────────────────────
# (5) Feature vs Power 상관 (기상 4개)
# ────────────────────────────────────────────────────────
ax5 = fig.add_subplot(gs[2, 1])

feat_labels = ["기온(°C)", "습도(%)", "풍속(m/s)", "일사(W/m²)", "강수(mm)"]
feat_keys   = ["temperature", "humidity", "wind_speed", "solar_radiation", "precipitation"]
corrs = [abs(df[k].corr(df["power_kw"])) for k in feat_keys]
colors_bar = [C_FEATURE if c == max(corrs) else "#30363d" for c in corrs]

bars = ax5.barh(feat_labels, corrs, color=colors_bar, edgecolor="#21262d", height=0.5)
for bar, v in zip(bars, corrs):
    ax5.text(v + 0.005, bar.get_y() + bar.get_height()/2,
             f"{v:.3f}", va="center", fontsize=8, color="#e6edf3")

ax5.set_xlim(0, 1.0)
ax5.set_title("기상 Feature ↔ 발전량 상관계수 (절댓값)", fontsize=10)
ax5.set_xlabel("Pearson |r|")
ax5.grid(True, axis="x")

print(f"\n[OK] 그래프 출력")
print(f"     Baseline MAE: {mae_b:.4f} kW")
print(f"     LSTM     MAE: {mae_l:.4f} kW")
print(f"     미래 24h 예측: {future_preds[0]:.2f} → {future_preds[-1]:.2f} kW")

plt.show()
