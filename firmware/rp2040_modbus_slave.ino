// RP2040 Modbus RTU Slave
// - USB Serial (COM11 / /dev/ttyACM0) 사용
// - Slave ID: 1
// - Holding Register 0: power_kw  × 100  (예: 350 → 3.50 kW)
// - Holding Register 1: temperature × 10  (예: 253 → 25.3 °C)
// - Holding Register 2: humidity    × 10  (예: 612 → 61.2 %)

#define SLAVE_ID   1
#define BAUD_RATE  9600
#define FRAME_TIMEOUT_MS 15   // 프레임 간격 (ms)

// --- 레지스터 ---
static uint16_t regs[3] = {
  350,  // power_kw  × 100 → 3.50 kW
  253,  // temp      × 10  → 25.3 °C
  612,  // humidity  × 10  → 61.2 %
};

// --- CRC16 (Modbus) ---
static uint16_t crc16(const uint8_t *buf, uint16_t len) {
  uint16_t crc = 0xFFFF;
  for (uint16_t i = 0; i < len; i++) {
    crc ^= buf[i];
    for (uint8_t b = 0; b < 8; b++) {
      crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : (crc >> 1);
    }
  }
  return crc;
}

// --- 에러 응답 ---
static void sendError(uint8_t fc, uint8_t code) {
  uint8_t buf[5];
  buf[0] = SLAVE_ID;
  buf[1] = fc | 0x80;
  buf[2] = code;
  uint16_t crc = crc16(buf, 3);
  buf[3] = crc & 0xFF;
  buf[4] = (crc >> 8) & 0xFF;
  Serial.write(buf, 5);
}

// --- FC03: Read Holding Registers ---
static void handleFC03(const uint8_t *req) {
  uint16_t start = ((uint16_t)req[2] << 8) | req[3];
  uint16_t count = ((uint16_t)req[4] << 8) | req[5];

  if (count == 0 || count > 3 || start + count > 3) {
    sendError(0x03, 0x02);  // Illegal Data Address
    return;
  }

  // 응답: [slave, fc, byte_count, data..., crc_lo, crc_hi]
  uint8_t resp[9];  // 최대 3 레지스터 = 3 + 6 + 2 - 1 = 9 바이트
  resp[0] = SLAVE_ID;
  resp[1] = 0x03;
  resp[2] = (uint8_t)(count * 2);
  for (uint16_t i = 0; i < count; i++) {
    resp[3 + i * 2] = (regs[start + i] >> 8) & 0xFF;
    resp[4 + i * 2] =  regs[start + i]        & 0xFF;
  }
  uint8_t body_len = 3 + count * 2;
  uint16_t crc = crc16(resp, body_len);
  resp[body_len]     = crc & 0xFF;
  resp[body_len + 1] = (crc >> 8) & 0xFF;
  Serial.write(resp, body_len + 2);
}

// --- 센서값 시뮬레이션 (1초마다 갱신) ---
static void updateSensors() {
  float t = millis() / 1000.0f;
  float power = 2.5f + 2.4f * sin(t * 0.008f);          // 0.1 ~ 4.9 kW
  float temp  = 27.0f + 6.0f * sin(t * 0.005f);          // 21 ~ 33 °C
  float hum   = 60.0f + 15.0f * cos(t * 0.006f);         // 45 ~ 75 %

  regs[0] = (uint16_t)(power * 100.0f + 0.5f);
  regs[1] = (uint16_t)(temp  * 10.0f  + 0.5f);
  regs[2] = (uint16_t)(hum   * 10.0f  + 0.5f);
}

// --- 수신 버퍼 ---
static uint8_t rxBuf[64];
static uint8_t rxLen = 0;
static unsigned long lastByteMs = 0;

void setup() {
  Serial.begin(BAUD_RATE);
  // USB CDC가 연결될 때까지 최대 3초 대기
  unsigned long t0 = millis();
  while (!Serial && millis() - t0 < 3000);
}

void loop() {
  // 센서값 1초마다 갱신
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate >= 1000) {
    updateSensors();
    lastUpdate = millis();
  }

  // 바이트 수신
  while (Serial.available()) {
    if (rxLen < sizeof(rxBuf)) {
      rxBuf[rxLen++] = (uint8_t)Serial.read();
    } else {
      Serial.read();  // 버퍼 넘치면 버림
      rxLen = 0;
    }
    lastByteMs = millis();
  }

  // 프레임 타임아웃 → 처리
  if (rxLen >= 8 && millis() - lastByteMs >= FRAME_TIMEOUT_MS) {
    if (rxBuf[0] == SLAVE_ID) {
      uint16_t crc = crc16(rxBuf, rxLen - 2);
      uint16_t rxCrc = (uint16_t)rxBuf[rxLen - 1] << 8 | rxBuf[rxLen - 2];
      if (crc == rxCrc) {
        switch (rxBuf[1]) {
          case 0x03: handleFC03(rxBuf); break;
          default:   sendError(rxBuf[1], 0x01); break;  // Illegal Function
        }
      }
    }
    rxLen = 0;
  }

  // 타임아웃인데 너무 짧으면 버퍼 초기화
  if (rxLen > 0 && millis() - lastByteMs >= 100) {
    rxLen = 0;
  }
}
