from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml_shared import (
    BASELINE_FEATURES,
    METRICS_PATH,
    load_joined,
    make_baseline_xy,
    require_rows,
    save_baseline_metrics,
    split_index,
)


def main():
    df = load_joined()
    require_rows(df)
    print(f"[INFO] join 행 수: {len(df)}, 기간: {df['obs_time'].min()} ~ {df['obs_time'].max()}")

    X, y = make_baseline_xy(df)
    cut = split_index(len(X))
    X_train, X_test = X[:cut], X[cut:]
    y_train, y_test = y[:cut], y[cut:]

    model = HistGradientBoostingRegressor(max_depth=6, learning_rate=0.1, random_state=42)
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    mae = mean_absolute_error(y_test, pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
    r2 = r2_score(y_test, pred)
    save_baseline_metrics(mae, rmse, r2)

    n_feat = len(BASELINE_FEATURES)
    print(
        f"[BASELINE] HistGradientBoosting - 시각 t 의 {n_feat} feature "
        f"(power_kw 포함, 직전 시각 값) -> 시각 t+1 power_kw"
    )
    print(f"  test MAE  (kW): {mae:.4f}")
    print(f"  test RMSE (kW): {rmse:.4f}")
    print(f"  test R²:        {r2:.4f}")
    print(f"  (저장) {METRICS_PATH}")


if __name__ == "__main__":
    main()
