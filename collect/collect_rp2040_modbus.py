from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

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
        port = env("MODBUS_PORT", "/dev/ttyACM0")
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
    rr = client.read_holding_registers(0, count=3, device_id=slave_id)
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
