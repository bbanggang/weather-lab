# 시간별 기상 · RP2040 · MySQL · LSTM — 따라하기 매뉴얼 (Windows)

PowerShell에서 **위에서 아래 순서대로** 진행한다.  
각 절 끝의 **확인**을 통과한 뒤 다음 절로 넘어간다.

| 문서 | 용도 |
|------|------|
| **이 파일** | 설치·코드·실행·검증 (전체) |
| `seed/README.md` | 발전량 720시간 시드 (5절) |

---

## 목차

0. [한눈에 보기](#0-한눈에-보기) (0.4 GitHub `git clone` 포함)  
1. [준비](#1-준비)  
2. [uv 설치](#2-uv-설치)  
3. [MySQL (Docker)](#3-mysql-docker)  
4. [테이블·뷰 만들기](#4-테이블뷰-만들기)  
5. [발전량 시드 (720시간)](#5-발전량-시드-720시간)  
6. [Python 프로젝트](#6-python-프로젝트)  
7. [환경 변수 `.env`](#7-환경-변수-env)  
8. [`db.py`](#8-dbpy)  
9. [`weather_sources.py`](#9-weather_sourcespy)  
10. [기상 수집 v1 — `collect_weather.py`](#10-기상-수집-v1--collect_weatherpy)  
11. [기상 수집 v2 — 30일 backfill](#11-기상-수집-v2--30일-backfill)  
12. [RP2040 Modbus 저장](#12-rp2040-modbus-저장)  
13. [join으로 데이터 확인](#13-join으로-데이터-확인)  
14. [베이스라인 예측 — `train_baseline.py`](#14-베이스라인-예측--train_baselinepy)  
15. [LSTM — `lstm_train.py`](#15-lstm--lstm_trainpy)  
16. [파일 목록](#16-파일-목록)  
17. [자주 발생하는 문제](#17-자주-발생하는-문제)  

---

## 0. 한눈에 보기

### 0.1 무엇을 만드는지

```text
Open-Meteo(또는 공공 API)  →  weather_hourly   (1시간 1행)
RP2040 Modbus + 시드 SQL  →  power_realtime  →  power_hourly (뷰)
        ↓ join (시간 맞춤)
train_baseline.py  →  발전량 예측 (비교용)
lstm_train.py      →  과거 35시간 × 8 feature → LSTM
```

- **시간 단위** 데이터만 사용한다 (1시간 1행).
- 기본 기상 소스: **`WEATHER_SOURCE=openmeteo`** (API 키 불필요).
- LSTM 입력: **35시간 × 8개 feature**, 데이터 길이 목표 **약 720시간(30일)**.

### 0.2 완료 체크리스트

- [ ] Docker MySQL 실행, 테이블·뷰 생성
- [ ] `power_hourly` ≈ **720**행 (5절 시드)
- [ ] `weather_hourly` ≈ **720**행 (11절 backfill)
- [ ] Modbus 스크립트로 최신 행 1건 이상 (12절)
- [ ] join SQL 결과 ≈ **720**행 (13절)
- [ ] `train_baseline.py` → `metrics_baseline.json`
- [ ] `lstm_train.py` → **`[COMPARE]`** MAE 출력

### 0.3 저장소에 포함된 파일 (GitHub)

`git clone` 후 `weather-rp2040-lab-materials` 폴더에 아래가 있다.

```text
실습매뉴얼_공공데이터_RP2040_MySQL.md
collect_rp2040_modbus.py
ml_shared.py
train_baseline.py
lstm_train.py
seed/power_realtime_seed.sql
seed/README.md
seed/generate_power_seed.py
```

6절에서 이 폴더를 Python 작업 디렉터리로 쓴다. 별도 복사는 필요 없다.

### 0.4 GitHub에서 자료 받기

매뉴얼·`seed/`·Python 스크립트는 아래 **비공개 저장소**에 있다.

- 저장소: https://github.com/seogilan0/weather-rp2040-lab-materials

**처음 받을 때** ([Git](https://git-scm.com/download/win) 설치 후):

```powershell
cd $HOME\Projects
git clone https://github.com/seogilan0/weather-rp2040-lab-materials.git
cd weather-rp2040-lab-materials
```

clone 되면 폴더 `weather-rp2040-lab-materials` 가 생긴다. 아래 명령의 경로는 **이 폴더**를 기준으로 한다.

예 (5절 시드 import):

```powershell
docker exec -i weather-mysql mysql -u weather -pweatherpass weather < "$HOME\Projects\weather-rp2040-lab-materials\seed\power_realtime_seed.sql"
```

**Private 저장소**이므로 clone 전에 GitHub **Settings → Collaborators** 에 해당 계정을 추가해야 한다.  
push·pull 할 때 브라우저 로그인(`seogilan0`) 또는 토큰이 필요할 수 있다.

**이미 받은 폴더를 최신으로:**

```powershell
cd $HOME\Projects\weather-rp2040-lab-materials
git pull
```

이후 작업은 **6절부터 이 clone 폴더 안**에서 진행한다.

---

## 1. 준비

| 항목 | 설명 |
|------|------|
| OS | Windows, PowerShell |
| Git | 0.4절 — `git clone` 으로 자료 받기 |
| Docker Desktop | MySQL 컨테이너용 |
| uv | Python 패키지·실행 |
| RP2040 | Modbus **RTU**(COM) 또는 **TCP** 에뮬레이터 (12절) |
| 기상 | `openmeteo` 권장, 또는 `public` + 공공 API 키 |

---

## 2. uv 설치

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv --version
```

**확인:** 버전 번호가 출력되면 다음 절로.

---

## 3. MySQL (Docker)

[Docker Desktop](https://www.docker.com/products/docker-desktop/) 설치 후 실행한다.

```powershell
docker run -d --name weather-mysql `
  -e MYSQL_ROOT_PASSWORD=rootpass `
  -e MYSQL_DATABASE=weather `
  -e MYSQL_USER=weather `
  -e MYSQL_PASSWORD=weatherpass `
  -p 3306:3306 `
  mysql:8.4

docker ps
```

**확인:** `weather-mysql` 컨테이너가 `Up` 상태.

이미 같은 이름 컨테이너가 있으면 `docker start weather-mysql` 을 사용한다.

### MySQL 접속 (테이블 작업용)

```powershell
docker exec -it weather-mysql mysql -u root -p
```

비밀번호: `rootpass` (입력해도 화면에 안 보일 수 있음)

`mysql>` 프롬프트가 나오면 4절 진행.

---

## 4. 테이블·뷰 만들기

`mysql>` 에서 아래를 **한 블록씩** 실행한다.

```sql
CREATE DATABASE IF NOT EXISTS weather
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE weather;

CREATE TABLE IF NOT EXISTS weather_hourly (
  id               BIGINT AUTO_INCREMENT PRIMARY KEY,
  obs_time         DATETIME NOT NULL COMMENT '관측/예보 시각(시간 단위)',
  source           VARCHAR(20) NOT NULL COMMENT 'openmeteo | public',
  location_key     VARCHAR(50) NOT NULL COMMENT '좌표키 또는 지점번호',
  temperature      DECIMAL(6,2) NULL COMMENT '기온(℃)',
  humidity         DECIMAL(6,2) NULL COMMENT '습도(%)',
  wind_speed       DECIMAL(6,2) NULL COMMENT '풍속(m/s)',
  solar_radiation  DECIMAL(8,2) NULL COMMENT '일사(W/m2)',
  precipitation    DECIMAL(8,2) NULL COMMENT '강수(mm)',
  raw_json         JSON NULL,
  created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_hourly (obs_time, source, location_key)
);

CREATE TABLE IF NOT EXISTS power_realtime (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  measured_at   DATETIME NOT NULL,
  device_id     VARCHAR(50) NOT NULL,
  power_kw      DECIMAL(10,3) NULL,
  temperature   DECIMAL(6,2) NULL,
  humidity      DECIMAL(6,2) NULL,
  raw_payload   TEXT NULL,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_power (measured_at, device_id)
);

CREATE OR REPLACE VIEW power_hourly AS
SELECT
  DATE_FORMAT(measured_at, '%Y-%m-%d %H:00:00') AS hour_time,
  device_id,
  AVG(power_kw)    AS power_kw,
  AVG(temperature) AS temperature,
  AVG(humidity)    AS humidity,
  COUNT(*)         AS sample_count
FROM power_realtime
GROUP BY hour_time, device_id;
```

```sql
exit;
```

**확인:**

```powershell
docker exec -it weather-mysql mysql -u weather -pweatherpass -e "USE weather; SHOW TABLES;"
```

`weather_hourly`, `power_realtime` 가 보이면 5절로.

---

## 5. 발전량 시드 (720시간)

30일치 `power_realtime` 을 넣는다. Modbus를 며칠 돌리지 않아도 LSTM까지 이어진다.

```powershell
docker exec -i weather-mysql mysql -u weather -pweatherpass weather < "$HOME\Projects\weather-rp2040-lab-materials\seed\power_realtime_seed.sql"
```

경로는 `power_realtime_seed.sql` 위치에 맞게 수정한다.  
다른 방법·재생성: `seed/README.md`

**확인:**

```powershell
docker exec -it weather-mysql mysql -u weather -pweatherpass -e "USE weather; SELECT COUNT(*) AS cnt FROM power_hourly WHERE device_id='RP2040-EMU-01';"
```

`cnt` 가 **720** 전후이면 6절로.

---

## 6. Python 프로젝트

0.4절에서 clone 한 폴더에서 패키지를 설정한다.

```powershell
cd $HOME\Projects\weather-rp2040-lab-materials
uv init
uv python install 3.12
uv add requests pymysql python-dotenv pymodbus
```

`uv init` 이 “이미 프로젝트”라고 하면 `pyproject.toml` 이 있는지 보고, 없을 때만 `uv init` 한다.

**확인:** 이 폴더에 `pyproject.toml` 이 있으면 7절로.

---

## 7. 환경 변수 `.env`

프로젝트 루트에 `.env` 파일을 만든다.

**Modbus 연결 방식** — `MODBUS_MODE` 로 선택한다.

| `MODBUS_MODE` | 쓰는 설정 | 안 써도 되는 설정 |
|---------------|-----------|-------------------|
| `rtu` (기본) | `MODBUS_PORT`, `MODBUS_BAUD` | `MODBUS_HOST`, `MODBUS_TCP_PORT` |
| `tcp` | `MODBUS_HOST`, `MODBUS_TCP_PORT` | `MODBUS_PORT`, `MODBUS_BAUD` |

```env
WEATHER_SOURCE=openmeteo

LAT=35.95
LON=126.70
LOCATION_KEY=gunsan

DATA_GO_KR_SERVICE_KEY=여기에_Decoding_키
ASOS_STN_ID=108

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=weather
MYSQL_PASSWORD=weatherpass
MYSQL_DATABASE=weather

# Modbus: rtu | tcp
MODBUS_MODE=rtu
MODBUS_PORT=COM3
MODBUS_BAUD=9600
MODBUS_HOST=127.0.0.1
MODBUS_TCP_PORT=5020
MODBUS_SLAVE_ID=1
DEVICE_ID=RP2040-EMU-01
```

**RTU 예:** `MODBUS_MODE=rtu`, `MODBUS_PORT=COM3` (장치 관리자에서 COM 확인)  
**TCP 예:** `MODBUS_MODE=tcp`, `MODBUS_HOST=127.0.0.1`, `MODBUS_TCP_PORT=5020` (에뮬레이터 Listen 포트와 동일)

**확인:** `WEATHER_SOURCE`, `DEVICE_ID`, `MODBUS_MODE` 와 RTU/TCP에 맞는 항목이 채워져 있는지 본다.

---

## 8. `db.py`

프로젝트 루트에 `db.py` 를 만들고 아래 **전체**를 붙여 넣는다.

```python
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
```

**확인:** 파일 저장 후 9절로.

---

## 9. `weather_sources.py`

`weather_sources.py` 를 만들고 아래 **전체**를 붙여 넣는다.

```python
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from typing import Any

import requests

API_PUBLIC_HOURLY = (
    "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
)
API_OPENMETEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"


def fetch_hourly(source: str, start: date, end: date) -> list[dict[str, Any]]:
    source = source.lower().strip()
    if source == "openmeteo":
        return _fetch_openmeteo(start, end)
    if source == "public":
        return _fetch_public_hourly(start, end)
    raise ValueError(f"지원하지 않는 WEATHER_SOURCE: {source}")


def _fetch_openmeteo(start: date, end: date) -> list[dict[str, Any]]:
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
    r = requests.get(API_OPENMETEO_ARCHIVE, params=params, timeout=60)
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


def _fetch_public_hourly(start: date, end: date) -> list[dict[str, Any]]:
    service_key = os.environ["DATA_GO_KR_SERVICE_KEY"]
    stn_id = os.getenv("ASOS_STN_ID", "108")
    location_key = f"stn:{stn_id}"

    rows: list[dict[str, Any]] = []
    d = start
    while d <= end:
        ymd = d.strftime("%Y%m%d")
        params = {
            "serviceKey": service_key,
            "pageNo": "1",
            "numOfRows": "24",
            "dataType": "JSON",
            "dataCd": "ASOS",
            "dateCd": "HR",
            "startDt": ymd,
            "startHh": "00",
            "endDt": ymd,
            "endHh": "23",
            "stnIds": stn_id,
        }
        r = requests.get(API_PUBLIC_HOURLY, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        header = data.get("response", {}).get("header", {})
        if header.get("resultCode") != "00":
            raise RuntimeError(
                f"공공 API 오류: {header.get('resultCode')} / {header.get('resultMsg')}"
            )

        items = data.get("response", {}).get("body", {}).get("items", {}).get("item")
        if not items:
            d += timedelta(days=1)
            continue
        if not isinstance(items, list):
            items = [items]

        for item in items:
            tm = item.get("tm")
            obs_time = datetime.strptime(tm, "%Y-%m-%d %H:%M")
            rows.append(
                {
                    "obs_time": obs_time,
                    "source": "public",
                    "location_key": location_key,
                    "temperature": _num(item.get("ta")),
                    "humidity": _num(item.get("hm")),
                    "wind_speed": _num(item.get("ws")),
                    "solar_radiation": None,
                    "precipitation": _num(item.get("rn")),
                    "raw_json": json.dumps(item, ensure_ascii=False),
                }
            )
        d += timedelta(days=1)
    return rows


def _at(values, idx):
    if not values or idx >= len(values):
        return None
    v = values[idx]
    return None if v is None else float(v)


def _num(v):
    if v is None or v == "":
        return None
    return float(v)
```

공공 API: [ASOS 시간자료](https://www.data.go.kr/data/15057210/openapi.do) 활용신청·Decoding 키 필요 (`WEATHER_SOURCE=public` 일 때).

**확인:** 파일 저장 후 10절로.

---

## 10. 기상 수집 v1 — `collect_weather.py`

`collect_weather.py` 생성:

```python
from __future__ import annotations

import sys
from datetime import date, timedelta

from dotenv import load_dotenv

from db import env, save_weather_hourly
from weather_sources import fetch_hourly


def main():
    load_dotenv()
    source = env("WEATHER_SOURCE", "openmeteo")

    if len(sys.argv) == 3:
        start = date.fromisoformat(sys.argv[1])
        end = date.fromisoformat(sys.argv[2])
    else:
        end = date.today() - timedelta(days=1)
        start = end

    print(f"[INFO] source={source}, 기간={start}~{end}")
    rows = fetch_hourly(source, start, end)
    n = save_weather_hourly(rows)
    print(f"[OK] weather_hourly 저장 {n}건")


if __name__ == "__main__":
    main()
```

**실행** (기본: 어제 하루 ≈ 24행):

```powershell
cd $HOME\Projects\weather-rp2040-lab-materials
uv run python collect_weather.py
```

날짜 지정:

```powershell
uv run python collect_weather.py 2025-05-01 2025-05-01
```

**확인:**

```powershell
docker exec -it weather-mysql mysql -u weather -pweatherpass -e "USE weather; SELECT COUNT(*) FROM weather_hourly; SELECT * FROM weather_hourly ORDER BY obs_time DESC LIMIT 5;"
```

`COUNT` 가 **24** 전후이면 11절로.

---

## 11. 기상 수집 v2 — 30일 backfill

`collect_weather_backfill.py` 생성:

```python
from __future__ import annotations

import sys
from datetime import date, timedelta

from dotenv import load_dotenv

from db import env, save_weather_hourly
from weather_sources import fetch_hourly


def main():
    load_dotenv()
    source = env("WEATHER_SOURCE", "openmeteo")

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)

    print(f"[INFO] backfill {days}일: {start}~{end}, source={source}")
    rows = fetch_hourly(source, start, end)
    n = save_weather_hourly(rows)
    print(f"[OK] 저장 {n}건 (목표 약 {days * 24}건)")


if __name__ == "__main__":
    main()
```

**실행:**

```powershell
uv run python collect_weather_backfill.py 30
```

**확인:**

```powershell
docker exec -it weather-mysql mysql -u weather -pweatherpass -e "USE weather; SELECT COUNT(*) AS hours FROM weather_hourly;"
```

`hours` 가 **720** 전후이면 12절로.  
(5절 시드와 같이 **어제**를 끝으로 30일이면 join 날짜가 맞기 쉽다.)

---

## 12. RP2040 Modbus 저장 (RTU / TCP)

`.env` 의 `MODBUS_MODE` 로 **시리얼(RTU)** 또는 **TCP** 를 고른다 (7절).

| 모드 | 에뮬레이터 설정 | `.env` |
|------|-----------------|--------|
| `rtu` | COM 포트, 9600 8N1 | `MODBUS_PORT=COM3` |
| `tcp` | Listen IP·포트 (예: 127.0.0.1:5020) | `MODBUS_HOST`, `MODBUS_TCP_PORT` |

`collect_rp2040_modbus.py` — 저장소에 있으면 그대로 쓰고, 없으면 아래 내용으로 파일을 만든다.

```python
from __future__ import annotations

import os
import time
from datetime import datetime

import pymysql
from dotenv import load_dotenv
from pymodbus.client import ModbusSerialClient, ModbusTcpClient


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


def create_modbus_client():
    mode = os.getenv("MODBUS_MODE", "rtu").lower().strip()
    if mode == "rtu":
        port = env("MODBUS_PORT", "COM3")
        baud = int(env("MODBUS_BAUD", "9600"))
        client = ModbusSerialClient(
            port=port,
            baudrate=baud,
            parity="N",
            stopbits=1,
            bytesize=8,
            timeout=1,
        )
        label = f"RTU {port}@{baud}"
    elif mode == "tcp":
        host = env("MODBUS_HOST", "127.0.0.1")
        tcp_port = int(env("MODBUS_TCP_PORT", "5020"))
        client = ModbusTcpClient(host=host, port=tcp_port)
        label = f"TCP {host}:{tcp_port}"
    else:
        raise ValueError(f"MODBUS_MODE는 rtu 또는 tcp: 현재={mode}")
    return client, mode, label


def read_measurements(client, slave_id: int):
    rr = client.read_holding_registers(address=0, count=3, slave=slave_id)
    if rr.isError():
        raise RuntimeError(f"Modbus read error: {rr}")
    regs = rr.registers
    return regs[0] / 100.0, regs[1] / 10.0, regs[2] / 10.0, f"regs={regs}"


def save_row(measured_at, device_id, power_kw, temp, hum, raw):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO power_realtime
                (measured_at, device_id, power_kw, temperature, humidity, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  power_kw=VALUES(power_kw),
                  temperature=VALUES(temperature),
                  humidity=VALUES(humidity),
                  raw_payload=VALUES(raw_payload)
                """,
                (measured_at, device_id, power_kw, temp, hum, raw),
            )
        conn.commit()
        print(f"[OK] power_realtime {measured_at} {power_kw}kW")
    finally:
        conn.close()


def main():
    load_dotenv()
    slave_id = int(env("MODBUS_SLAVE_ID", "1"))
    device_id = env("DEVICE_ID", "RP2040-EMU-01")

    client, mode, label = create_modbus_client()
    if not client.connect():
        raise RuntimeError(f"Modbus 연결 실패 ({mode}): {label}")

    print(f"[INFO] Modbus {label}, slave_id={slave_id}")
    try:
        while True:
            try:
                p, t, h, raw = read_measurements(client, slave_id)
                save_row(
                    datetime.now().replace(microsecond=0), device_id, p, t, h, raw
                )
            except Exception as e:
                print(f"[WARN] {e}")
            time.sleep(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
```

**실행:** 에뮬레이터를 켠 뒤 1~2분 돌리고 `Ctrl+C` 로 종료.

```powershell
uv run python collect_rp2040_modbus.py
```

**확인:** 시드 720행은 유지되고, **최신** `measured_at` 행이 추가되면 13절로.

```powershell
docker exec -it weather-mysql mysql -u weather -pweatherpass -e "USE weather; SELECT * FROM power_realtime ORDER BY measured_at DESC LIMIT 3;"
```

---

## 13. join으로 데이터 확인

### 13.1 feature 8개

| # | 컬럼 | 출처 |
|---|------|------|
| 1 | `temperature` | `weather_hourly` |
| 2 | `humidity` | `weather_hourly` |
| 3 | `wind_speed` | `weather_hourly` |
| 4 | `solar_radiation` | `weather_hourly` |
| 5 | `precipitation` | `weather_hourly` |
| 6 | `power_kw` | `power_hourly` |
| 7 | `panel_temp` | `power_hourly.temperature` |
| 8 | `panel_humidity` | `power_hourly.humidity` |

LSTM: **과거 35시간** × 위 8개 → 다음 `power_kw` 예측.

### 13.2 join SQL

```sql
USE weather;

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
  ON p.hour_time = DATE_FORMAT(w.obs_time, '%Y-%m-%d %H:00:00')
  AND p.device_id = 'RP2040-EMU-01'
WHERE w.source = 'openmeteo'
ORDER BY w.obs_time DESC
LIMIT 10;
```

**확인:** 행이 나오고, `power_kw`·`solar_radiation` 이 대부분 NULL 이 아니면 14절로.  
전체 행 수는 아래로 본다 (≈ **720**).

```sql
SELECT COUNT(*) AS joined_rows
FROM weather_hourly w
INNER JOIN power_hourly p
  ON p.hour_time = DATE_FORMAT(w.obs_time, '%Y-%m-%d %H:00:00')
  AND p.device_id = 'RP2040-EMU-01'
WHERE w.source = 'openmeteo';
```

---

## 14. 베이스라인 예측 — `train_baseline.py`

**패키지** (clone 폴더에서):

```powershell
cd $HOME\Projects\weather-rp2040-lab-materials
uv add pandas scikit-learn
```

**실행:**

```powershell
uv run python train_baseline.py
```

**확인:**

- 콘솔에 `test MAE (kW)`, `R²` 출력
- 프로젝트에 `metrics_baseline.json` 생성

베이스라인은 **현재 시각 8 feature** 만으로 `power_kw` 를 맞춘다. 15절 LSTM과 **MAE 비교**용이다.

---

## 15. LSTM — `lstm_train.py`

`lstm_train.py`, `ml_shared.py` 가 같은 폴더에 있어야 한다.

**패키지:**

```powershell
uv add tensorflow
```

**실행** (`train_baseline.py` **이후** 권장):

```powershell
uv run python lstm_train.py
```

**확인:**

- 학습 로그 후 `test MAE (kW)` 출력
- **`[COMPARE]`** 에 Baseline vs LSTM MAE 가 나옴

**해석:**

- Baseline = 그 시각 feature 만 사용
- LSTM = **지난 35시간** 패턴 사용  
- LSTM MAE가 더 크게 나와도 데이터 양·epoch 부족일 수 있음

7절을 건너뛰면 LSTM만 실행 가능하나 `[COMPARE]` 는 나오지 않는다.

참고 영상: [YouTube](https://www.youtube.com/watch?v=UCqb0VWsa5o)

---

## 16. 파일 목록

```text
weather-rp2040-lab-materials/     ← git clone (GitHub 공유)
  실습매뉴얼_공공데이터_RP2040_MySQL.md
  .env                              ← 각 PC에서 직접 생성 (Git 제외)
  pyproject.toml                    ← 6절 uv
  db.py, weather_sources.py         ← 8~9절
  collect_weather.py
  collect_weather_backfill.py
  collect_rp2040_modbus.py
  ml_shared.py
  train_baseline.py
  lstm_train.py
  metrics_baseline.json             ← 14절 실행 후 (Git 제외)
  seed/power_realtime_seed.sql
  seed/README.md
```

저장소: https://github.com/seogilan0/weather-rp2040-lab-materials

| 파일 | 역할 |
|------|------|
| `weather_sources.py` | Open-Meteo / 공공 **시간별** 수집 |
| `collect_weather.py` | 1일(≈24행) 수집 |
| `collect_weather_backfill.py` | N일(30일≈720행) 수집 |
| `collect_rp2040_modbus.py` | Modbus 실시간 저장 |
| `train_baseline.py` | sklearn 베이스라인 |
| `lstm_train.py` | LSTM + MAE 비교 |

---

## 17. 자주 발생하는 문제

| 증상 | 확인·대응 |
|------|-----------|
| `weather_hourly` 24행 미만 | 기간·`WEATHER_SOURCE`·공공 API 키 |
| Open-Meteo 오류 | `LAT`/`LON`, archive 날짜 범위 |
| 공공 API 오류 | 활용신청, `dateCd=HR`, Decoding 키 |
| `solar_radiation` NULL | `openmeteo` 사용 (`public` 은 일사 없을 수 있음) |
| join 행 적음 | 5절 시드, `DEVICE_ID`, `source` 필터 |
| `power_hourly` ≠ 720 | 5절 SQL import 경로 |
| Modbus 연결 실패 | `MODBUS_MODE`·RTU: COM 번호 / TCP: Host·Port·에뮬 Listen |
| `MODBUS_MODE` 오류 | `rtu` 또는 `tcp` 만 허용 (대소문자 무관) |
| TensorFlow 설치 느림 | 14절은 sklearn만 먼저, 15절 전 설치 |
| `[COMPARE]` 없음 | 14절 `train_baseline.py` 먼저 실행 |
| LSTM 행 수 부족 | 11절 backfill 30 + 5절 시드 |

---

## 전체 순서 요약

1. uv → Docker MySQL → 테이블  
2. **시드** `power_realtime_seed.sql`  
3. 프로젝트 + `.env`  
4. `db.py` → `weather_sources.py` → v1 → v2 (720)  
5. Modbus **짧게** 실행  
6. join 확인  
7. `train_baseline.py` → `lstm_train.py`
