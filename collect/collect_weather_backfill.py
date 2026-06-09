from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from db import env, save_weather_hourly


def main():
    load_dotenv()
    source = env("WEATHER_SOURCE", "public").lower().strip()

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)

    if source == "public":
        from weather_public import fetch_hourly
    elif source == "openmeteo":
        from weather_openmeteo import fetch_hourly
    else:
        raise ValueError("WEATHER_SOURCE는 public 또는 openmeteo")

    print(f"[INFO] backfill {days}일: {start}~{end}, source={source}")
    rows = fetch_hourly(start, end)
    n = save_weather_hourly(rows)
    print(f"[OK] 저장 {n}건 (목표 약 {days * 24}건)")


if __name__ == "__main__":
    main()
