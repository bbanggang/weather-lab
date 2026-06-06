from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from db import env


def main():
    load_dotenv()
    source = env("WEATHER_SOURCE", "public").lower().strip()
    target = date.today() - timedelta(days=1)

    if source == "public":
        from weather_public import fetch_api_json
    elif source == "openmeteo":
        from weather_openmeteo import fetch_api_json
    else:
        raise ValueError("WEATHER_SOURCE는 public 또는 openmeteo")

    print(f"[INFO] source={source}, 날짜={target}")
    payload = fetch_api_json(target)
    out = Path(f"weather_api_{source}_{target.isoformat()}.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 저장 → {out.resolve()}")


if __name__ == "__main__":
    main()
