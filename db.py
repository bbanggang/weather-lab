from __future__ import annotations

import json
import os
from typing import Any

import pymysql
from dotenv import load_dotenv


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"{name} 환경변수가 비어 있습니다.")
    return value


def get_conn():
    return pymysql.connect(
        host=env("MYSQL_HOST", "127.0.0.1"),
        port=int(env("MYSQL_PORT", "3306")),
        user=env("MYSQL_USER"),
        password=env("MYSQL_PASSWORD"),
        database=env("MYSQL_DATABASE"),
        charset="utf8mb4",
        autocommit=False,
    )


def save_weather_hourly(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    conn = get_conn()
    saved = 0
    try:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO weather_hourly
                    (obs_time, source, location_key, temperature, humidity,
                     wind_speed, solar_radiation, precipitation, raw_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                      temperature=VALUES(temperature),
                      humidity=VALUES(humidity),
                      wind_speed=VALUES(wind_speed),
                      solar_radiation=VALUES(solar_radiation),
                      precipitation=VALUES(precipitation),
                      raw_json=VALUES(raw_json)
                    """,
                    (
                        row["obs_time"],
                        row["source"],
                        row["location_key"],
                        row.get("temperature"),
                        row.get("humidity"),
                        row.get("wind_speed"),
                        row.get("solar_radiation"),
                        row.get("precipitation"),
                        row.get("raw_json"),
                    ),
                )
                saved += 1
        conn.commit()
    finally:
        conn.close()
    return saved
