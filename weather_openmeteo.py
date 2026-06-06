from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any

import requests

API_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_api_json(day: date) -> dict[str, Any]:
    lat = os.getenv("LAT", "35.95")
    lon = os.getenv("LON", "126.70")
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation,precipitation",
        "timezone": "Asia/Seoul",
    }
    r = requests.get(API_URL, params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_hourly(start: date, end: date) -> list[dict[str, Any]]:
    lat = os.getenv("LAT", "35.95")
    lon = os.getenv("LON", "126.70")
    location_key = os.getenv("LOCATION_KEY", f"{lat},{lon}")
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation,precipitation",
        "timezone": "Asia/Seoul",
    }
    r = requests.get(API_URL, params=params, timeout=60)
    r.raise_for_status()
    payload = r.json()
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    rows: list[dict[str, Any]] = []
    for i, t in enumerate(times):
        obs_time = datetime.fromisoformat(t)
        rows.append(
            {
                "obs_time": obs_time,
                "source": "openmeteo",
                "location_key": location_key,
                "temperature": _at(hourly.get("temperature_2m"), i),
                "humidity": _at(hourly.get("relative_humidity_2m"), i),
                "wind_speed": _at(hourly.get("wind_speed_10m"), i),
                "solar_radiation": _at(hourly.get("shortwave_radiation"), i),
                "precipitation": _at(hourly.get("precipitation"), i),
                "raw_json": json.dumps({"time": t}, ensure_ascii=False),
            }
        )
    return rows


def _at(values, idx):
    if not values or idx >= len(values):
        return None
    v = values[idx]
    return None if v is None else float(v)
