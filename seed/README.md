# power_realtime 시드 (30일 × 24시간)

LSTM·join용 **720시간** 발전 데이터를 미리 넣는다.  
RP2040를 며칠 동안 돌리지 않아도 `power_hourly`와 join까지 진행할 수 있다.

## 파일

| 파일 | 설명 |
|------|------|
| `power_realtime_seed.sql` | SQL import용 (720행, 재실행 시 UPSERT) |
| `generate_power_seed.py` | 기간·종료일 변경 후 재생성 |

## 적용 방법

**전제:** `실습매뉴얼` 4절까지 완료(Docker MySQL, 테이블 생성).

### A — SQL import (권장)

```powershell
docker exec -i weather-mysql mysql -u weather -pweatherpass weather < "$HOME\Projects\weather-rp2040-lab-materials\seed\power_realtime_seed.sql"
```

경로는 `power_realtime_seed.sql` 이 있는 위치로 바꾼다.

### B — Python으로 DB 적재

```powershell
cd $HOME\Projects\weather-rp2040-lab-materials
uv add pymysql python-dotenv
uv run python seed/generate_power_seed.py --import-db
```

## 확인

```sql
USE weather;
SELECT COUNT(*) FROM power_hourly WHERE device_id = 'RP2040-EMU-01';
-- 기대: 720
```

## 참고

- `.env`의 `DEVICE_ID`는 **`RP2040-EMU-01`** (시드와 동일해야 join 됨).
- `collect_rp2040_modbus.py`는 **실시간 데모**용이며, 시드를 대체하지 않는다.
- 기상 backfill 종료일을 바꿨다면:  
  `uv run python generate_power_seed.py --end YYYY-MM-DD --sql power_realtime_seed.sql`
