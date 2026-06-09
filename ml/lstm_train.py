from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.models import Sequential

from ml_shared import (
    FEATURES,
    SEQ_LEN,
    TARGET,
    inverse_power_kw,
    load_baseline_metrics,
    load_joined,
    make_sequences,
    require_rows,
    split_index,
)


def main():
    df = load_joined()
    require_rows(df, min_rows=SEQ_LEN + 50)
    print(f"[INFO] join 행 수: {len(df)}, 기간: {df['obs_time'].min()} ~ {df['obs_time'].max()}")

    X, y_scaled, scaler = make_sequences(df, SEQ_LEN)
    cut = split_index(len(X))
    X_train, X_test = X[:cut], X[cut:]
    y_train, y_test = y_scaled[:cut], y_scaled[cut:]

    model = Sequential(
        [
            LSTM(64, input_shape=(SEQ_LEN, len(FEATURES))),
            Dense(1),
        ]
    )
    model.compile(optimizer="adam", loss="mse")
    model.fit(
        X_train,
        y_train,
        epochs=8,
        batch_size=32,
        validation_data=(X_test, y_test),
        verbose=1,
    )

    pred_scaled = model.predict(X_test, verbose=0).flatten()
    y_test_kw = inverse_power_kw(scaler, y_test)
    pred_kw = inverse_power_kw(scaler, pred_scaled)
    mae = mean_absolute_error(y_test_kw, pred_kw)
    rmse = float(np.sqrt(mean_squared_error(y_test_kw, pred_kw)))

    print("[LSTM] 과거 35시간 × 8 feature → power_kw (베이스라인은 t→t+1 1시간만 사용)")
    print(f"  test MAE  (kW): {mae:.4f}")
    print(f"  test RMSE (kW): {rmse:.4f}")

    base = load_baseline_metrics()
    if base:
        b_mae = base["mae_kw"]
        print("\n[COMPARE] Baseline vs LSTM MAE (kW)")
        print(f"  Baseline: {b_mae:.4f}")
        print(f"  LSTM:     {mae:.4f}")
    else:
        print("\n[HINT] 먼저 15절 train_baseline.py 실행")


if __name__ == "__main__":
    main()
