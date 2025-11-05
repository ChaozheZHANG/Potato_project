#!/usr/bin/env python3
"""PLC输出模块：支持Modbus/TCP和串口RS232/485"""
import argparse
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import time


class PLCModbusTCP:
    """Modbus/TCP输出（需要安装 pymodbus：pip install pymodbus）"""
    def __init__(self, host: str = "192.168.1.100", port: int = 502, unit_id: int = 1):
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.client = None
        try:
            from pymodbus.client import ModbusTcpClient
            self.client = ModbusTcpClient(host, port)
            self.client.connect()
        except ImportError:
            print("警告: 未安装 pymodbus，Modbus/TCP功能不可用。安装: pip install pymodbus")
        except Exception as e:
            print(f"Modbus连接失败: {e}")

    def write_bits(self, address: int, bits: List[int]) -> bool:
        """写入线圈（单个位）"""
        if not self.client or not self.client.is_socket_open():
            return False
        try:
            # 假设前8位写入地址0-7（或按PLC地址映射表）
            values = [bool(b) for b in bits]
            result = self.client.write_coils(address, values, unit=self.unit_id)
            return not result.isError()
        except Exception as e:
            print(f"Modbus写入失败: {e}")
            return False

    def close(self):
        if self.client:
            self.client.close()


class PLCSerial:
    """串口输出（需要安装 pyserial：pip install pyserial）"""
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 9600, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        try:
            import serial
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
        except ImportError:
            print("警告: 未安装 pyserial，串口功能不可用。安装: pip install pyserial")
        except Exception as e:
            print(f"串口打开失败: {e}")

    def write_bits(self, bits: List[int]) -> bool:
        """发送8位数据：格式为 '<grade>,[bit1],[bit2],...,[bit8]\\n'"""
        if not self.ser or not self.ser.is_open:
            return False
        try:
            # 简单协议：8字节二进制或ASCII格式
            # 选项1：ASCII文本 "NG,0,0,0,0,0,0,0,1\n"
            # 选项2：二进制 0x01 (仅最后一位)
            # 这里用ASCII方便调试
            bit_str = ','.join(map(str, bits))
            cmd = f"{bit_str}\n"
            self.ser.write(cmd.encode('ascii'))
            return True
        except Exception as e:
            print(f"串口写入失败: {e}")
            return False

    def close(self):
        if self.ser:
            self.ser.close()


def send_to_plc(grade: str, bits: List[int], method: str = "print", **kwargs) -> bool:
    """发送信号到PLC"""
    if method == "modbus":
        plc = PLCModbusTCP(kwargs.get("host", "192.168.1.100"), 
                          kwargs.get("port", 502),
                          kwargs.get("unit_id", 1))
        success = plc.write_bits(kwargs.get("address", 0), bits)
        plc.close()
        return success
    elif method == "serial":
        plc = PLCSerial(kwargs.get("port", "/dev/ttyUSB0"),
                       kwargs.get("baudrate", 9600))
        success = plc.write_bits(bits)
        plc.close()
        return success
    else:
        # print模式：仅输出到控制台（调试用）
        print(f"[PLC输出] Grade={grade}, Bits={bits}, Lane={kwargs.get('lane', 'N/A')}")
        return True


def main():
    parser = argparse.ArgumentParser(description="从分级结果JSONL读取并发送PLC信号")
    parser.add_argument("--input", required=True, help="grades.jsonl路径")
    parser.add_argument("--method", choices=["print", "modbus", "serial"], default="print")
    parser.add_argument("--modbus_host", default="192.168.1.100")
    parser.add_argument("--modbus_port", type=int, default=502)
    parser.add_argument("--modbus_address", type=int, default=0)
    parser.add_argument("--serial_port", default="/dev/ttyUSB0")
    parser.add_argument("--serial_baud", type=int, default=9600)
    parser.add_argument("--delay", type=float, default=0.1, help="发送间隔（秒）")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"文件不存在: {input_path}")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            rec = json.loads(line)
            grade = rec.get("grade", "NG")
            signal = rec.get("signal", {})
            bits = signal.get("bits", [0] * 8)
            lane = signal.get("lane", 0)

            kwargs = {
                "lane": lane,
                "host": args.modbus_host,
                "port": args.modbus_port,
                "address": args.modbus_address,
                "port": args.serial_port,
                "baudrate": args.serial_baud
            }
            send_to_plc(grade, bits, args.method, **kwargs)
            time.sleep(args.delay)


if __name__ == '__main__':
    main()

