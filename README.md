# Weather-Lab

기상 데이터(Open-Meteo)와 RP2040 Modbus 발전량 데이터를 수집·통합하여  
**다음 시간의 발전량(kW)** 을 예측하는 머신러닝 실습 프로젝트.

---

## 목차

1. [시스템 구성](#1-시스템-구성)
2. [환경](#2-환경)
3. [설치 및 실행](#3-설치-및-실행)
4. [파일 설명](#4-파일-설명)
5. [데이터 파이프라인](#5-데이터-파이프라인)
6. [모델 결과](#6-모델-결과)

---

## 1. 시스템 구성

```
Open-Meteo API ──────────────────→ weather_hourly (MySQL)
                                            │
RP2040 Modbus → power_realtime → power_hourly (뷰)
                                            │
                                    JOIN (시간 매칭)
                                            │
                                   8 feature × 720행
                                       ┌────┴────┐
                                   Baseline    LSTM
                               (t→t+1 예측) (35h→next)
```
---

<video src="https://github.com/user-attachments/assets/32845823-b443-4fad-8923-4dc90e7b1d37" controls autoplay loop muted width="100%"></video>

### 8개 Feature

| # | 컬럼 | 출처 |
|---|------|------|
| 1 | temperature | weather_hourly |
| 2 | humidity | weather_hourly |
| 3 | wind_speed | weather_hourly |
| 4 | solar_radiation | weather_hourly |
| 5 | precipitation | weather_hourly |
| 6 | power_kw | power_hourly |
| 7 | panel_temp | power_hourly |
| 8 | panel_humidity | power_hourly |

---

## 2. 환경

| 항목 | 내용 |
|------|------|
| OS | Windows 11 + WSL2 (Ubuntu 24.04) |
| Python | 3.12 (uv 관리) |
| DB | MySQL 8.4 (Docker, **포트 3307**) |
| 기상 API | Open-Meteo Historical API (키 불필요) |
| 장치 | Arduino Nano RP2040 Connect (COM11 / `/dev/ttyACM0`) |
| Modbus | RTU, 9600 baud, Slave ID 1 |

---

## 3. 설치 및 실행

### 사전 요구사항

- Docker Desktop (실행 상태)
- [uv](https://astral.sh/uv) 패키지 관리자
- Arduino IDE (펌웨어 업로드용)
- [usbipd-win](https://github.com/dorssel/usbipd-win) (WSL2 USB 연결용)

### 최초 설치

```bash
# 1. 저장소 클론
git clone https://github.com/seogilan0/weather-lab.git
cd weather-lab

# 2. Python 환경 구성
uv init
uv python install 3.12
uv add requests pymysql python-dotenv pymodbus pyserial
uv add pandas scikit-learn matplotlib
uv add tensorflow
```

### MySQL 컨테이너 시작

```bash
# 최초 1회
docker run -d --name weather-mysql \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=weather \
  -e MYSQL_USER=weather \
  -e MYSQL_PASSWORD=weatherpass \
  -p 3307:3306 \
  mysql:8.4

# 이후 재시작 시
docker start weather-mysql
```

### DB 초기화 (최초 1회)

```bash
# 테이블·뷰 생성 후 발전량 시드 데이터 (720행) import
docker exec -i weather-mysql mysql -u weather -pweatherpass weather \
  < seed/power_realtime_seed.sql
```

### .env 설정

프로젝트 루트에 `.env` 파일 생성:

```env
WEATHER_SOURCE=openmeteo

LAT=35.95
LON=126.70
LOCATION_KEY=gunsan

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3307
MYSQL_USER=weather
MYSQL_PASSWORD=weatherpass
MYSQL_DATABASE=weather

MODBUS_MODE=rtu
MODBUS_PORT=/dev/ttyACM0
MODBUS_BAUD=9600
MODBUS_SLAVE_ID=1
DEVICE_ID=RP2040-EMU-01
```

### 데이터 수집

```bash
# 기상 데이터 31일 backfill (시드와 날짜 맞춤)
uv run python collect/collect_weather_backfill.py 31

# RP2040 Modbus 실시간 수집 (Ctrl+C로 종료)
uv run python collect/collect_rp2040_modbus.py
```

### 모델 훈련

```bash
uv run python ml/train_baseline.py   # Baseline (HistGradientBoosting)
uv run python ml/lstm_train.py       # LSTM
```

### 시각화

```bash
# 브라우저에서 열기
viz/weather_lab_viz.html
```

---

## 4. 파일 설명

| 파일 | 역할 |
|------|------|
| `db.py` | MySQL 연결 및 weather_hourly 저장 함수 |
| `weather_openmeteo.py` | Open-Meteo API 호출 (기상 데이터) |
| `collect/collect_weather.py` | API JSON 1일치 파일로 저장 (확인용) |
| `collect/collect_weather_backfill.py` | N일치 기상 데이터 수집 → DB 저장 |
| `collect/collect_rp2040_modbus.py` | RP2040 Modbus RTU/TCP 실시간 수집 |
| `ml/ml_shared.py` | DB 로드, feature 생성, 전처리 공통 함수 |
| `ml/train_baseline.py` | HistGradientBoosting 훈련 → metrics_baseline.json |
| `ml/lstm_train.py` | LSTM 훈련 + Baseline 비교 출력 |
| `viz/weather_lab_viz.html` | 파이프라인 4단계 애니메이션 시각화 |
| `firmware/rp2040_modbus_slave.ino` | RP2040 Modbus RTU Slave 펌웨어 |
| `seed/power_realtime_seed.sql` | 발전량 720행 초기 데이터 |
| `seed/README.md` | 시드 데이터 재생성 방법 |

---

## 5. 데이터 파이프라인

### weather_hourly 테이블

- Open-Meteo에서 1시간 단위 기상 데이터 수집
- `source = 'openmeteo'`, `location_key = 'gunsan'`
- 수집 기간: 2026-05-06 ~ 2026-06-05 (744행)

### power_realtime 테이블

- RP2040이 Modbus 레지스터 3개를 1초마다 전송
- `collect_rp2040_modbus.py`가 읽어서 DB 저장
- `power_hourly` 뷰가 시간별로 평균 집계

### RP2040 Modbus 레지스터 구조

| 레지스터 | 값 | Python 변환 |
|---|---|---|
| Reg[0] | power_kw × 100 | `regs[0] / 100.0` |
| Reg[1] | temperature × 10 | `regs[1] / 10.0` |
| Reg[2] | humidity × 10 | `regs[2] / 10.0` |

### JOIN 조건

```sql
weather_hourly w
INNER JOIN power_hourly p
  ON p.hour_time = DATE_FORMAT(w.obs_time, '%Y-%m-%d %H:00:00')
  AND p.device_id = 'RP2040-EMU-01'
WHERE w.source = 'openmeteo'
```

---

## 6. 모델 결과

| 모델 | 입력 | MAE (kW) | RMSE (kW) | R² |
|------|------|----------|-----------|-----|
| **Baseline** (HistGradientBoosting) | 시각 t의 8 feature | **0.1261** | 0.1916 | 0.987 |
| LSTM (64 units, 8 epochs) | 과거 35시간 × 8 feature | 0.2516 | 0.3243 | - |

> Baseline이 더 낮은 이유: 시드 데이터가 규칙적인 사인파 패턴이라  
> 1시간 전 값만으로도 예측이 잘 됨.  
> 실제 발전소 데이터를 장기 수집하면 LSTM이 더 유리해짐.

### 시각화 구성 

1. **전체 기간** — 실제값 vs Baseline vs LSTM + 미래 24시간 예측
2. **테스트 구간 72시간** 확대
3. **미래 24시간** 예측 상세 (불확실성 범위 포함)
4. **오차 분포** 비교 (Baseline vs LSTM)
5. **기상 Feature 상관계수** — 일사량이 발전량과 가장 높은 상관

- 시각화 결과
![시각화 결과](https://github.com/user-attachments/assets/eabcf14a-9174-478b-bea3-091b5fc9487b)


