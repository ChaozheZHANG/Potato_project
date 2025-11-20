# -*- coding: utf-8 -*-
"""
app/plc_dummy_loop.py

当前行为（精简版）：
- 启动时：对每个通道的60个ATTR写入顺序值（1..9循环，通道之间互不影响）。
  ch1从1开始循环到9再回到1；ch2也独立从1开始，等等。
- 运行时循环：
  * 维持心跳
  * 监测并打印 RUN_STATUS / READY_1 / NOW 的变化
  * 不再做回填：即使某个ATTR后来被PLC/下游清成0，也不会再去写回

运行示例：
  python -m app.plc_dummy_loop --ip 192.168.1.1 --port 502 --channels 1,2,3,4

常用参数：
  --addr-base 0/1   # PLC 地址是否 1 起始（若 PLC 把 500 当第 501 个寄存器，就传 1）
  --interval 0.05   # 轮询间隔秒
  --seed 42         # 兼容旧参数，不再影响写值
"""

from __future__ import annotations
import argparse
import socket
import struct
import time
import random
from typing import Dict, List, Optional

# 你已有的寄存器常量
from plc.registers import (
    REG_HEARTBEAT, REG_RUN_STATUS,
    ready1_reg, ready2_reg, now_reg, attrs_base, wrap60,
)

# ---------------------- 打印工具 ----------------------

def ts() -> str:
    """时间戳字符串"""
    return time.strftime("%H:%M:%S") + f".{int((time.time()%1)*1000):03d}"

def log(msg: str):
    print(f"[{ts()}] {msg}", flush=True)

# ---------------------- 顺序写值分配器（单通道用） ----------------------

class SeqWriter:
    """
    提供依次递增的1..9数值。
    每次调用 next_val() 返回当前值，然后自增，过9回到1。
    这个类的实例是“每个通道一份”。
    """
    def __init__(self, start_val: int = 1):
        if start_val < 1 or start_val > 9:
            start_val = 1
        self.curr = start_val

    def next_val(self) -> int:
        v = self.curr
        self.curr += 1
        if self.curr > 9:
            self.curr = 1
        return v

# ---------------------- Modbus TCP 极简客户端 ----------------------

class ModbusTCP:
    def __init__(self, host: str, port: int = 502, timeout: float = 1.0, unit_id: int = 1):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.unit_id = unit_id
        self.tid = 0
        self.sock: socket.socket | None = None

    def connect(self):
        self.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        log(f"[mb] connect -> {self.host}:{self.port}")
        s.connect((self.host, self.port))
        self.sock = s
        log("[mb] connected")

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None

    def _next_tid(self) -> int:
        self.tid = (self.tid + 1) & 0xFFFF
        if self.tid == 0:
            self.tid = 1
        return self.tid

    def _recvn(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))  # type: ignore[arg-type]
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def _send_pdu(self, pdu: bytes) -> bytes:
        if not self.sock:
            self.connect()
        tid = self._next_tid()
        mbap = struct.pack(">HHHB", tid, 0, len(pdu) + 1, self.unit_id)
        self.sock.sendall(mbap + pdu)  # type: ignore[arg-type]

        hdr = self._recvn(7)
        if len(hdr) != 7:
            raise IOError("MBAP header short")
        r_tid, r_pid, r_len, r_uid = struct.unpack(">HHHB", hdr)
        if r_tid != tid or r_pid != 0 or r_uid != self.unit_id:
            raise IOError("MBAP mismatch")
        payload = self._recvn(r_len - 1)
        if len(payload) != r_len - 1:
            raise IOError("PDU payload short")
        if payload and (payload[0] & 0x80):
            ec = payload[1] if len(payload) > 1 else -1
            raise IOError(f"Modbus exception fc=0x{payload[0]:02X}, code={ec}")
        return payload

    def read_holding(self, addr: int, quantity: int) -> List[int]:
        # 0x03
        pdu = struct.pack(">BHH", 0x03, addr, quantity)
        r = self._send_pdu(pdu)
        if len(r) < 2 or r[0] != 0x03:
            raise IOError("bad read response")
        bc = r[1]
        if bc != quantity * 2 or len(r) != 2 + bc:
            raise IOError("byte count mismatch")
        out = []
        for i in range(quantity):
            out.append((r[2 + 2*i] << 8) | r[3 + 2*i])
        return out

    def write_single(self, addr: int, value: int) -> bool:
        # 0x06
        pdu = struct.pack(">BHH", 0x06, addr, value & 0xFFFF)
        r = self._send_pdu(pdu)
        ok = (len(r) == 5 and r[0] == 0x06)
        return ok

# ---------------------- 启动时铺底（一次性写入） ----------------------

def initial_fill(
    mb: ModbusTCP,
    A,
    channels: List[int],
    seed: Optional[int],
    seq_map: Dict[int, SeqWriter],
):
    """
    对每个通道写入60个ATTR。
    每个通道使用自己独立的SeqWriter，从1开始循环1..9。
    这里只写一次，后续循环不再回填。
    """
    # seed 仅保留接口兼容，现逻辑不使用随机
    if seed is not None:
        random.seed(seed + 10086)

    log("========== 初始铺底：每通道独立顺序发生器，60个ATTR依次写入1..9循环（一次性） ==========")

    for ch in channels:
        base = attrs_base(ch)
        seq = seq_map[ch]  # 该通道自己的发号器
        for k in range(1, 61):
            v = seq.next_val()
            addr = base + (k - 1)
            try:
                ok = mb.write_single(A(addr), v)
                log(f"[init][ch{ch}] REG {addr} (ATTR[{k}]) = {v} -> {'OK' if ok else 'NG'}")
            except Exception as e:
                log(f"[init][ch{ch}] 写 REG {addr} 失败: {e} -> 尝试重连")
                try:
                    mb.connect()
                except Exception as e2:
                    log(f"[mb] reconnect fail: {e2}")

    log("========== 初始铺底完成 ==========")

# ---------------------- 主循环 ----------------------

def run_loop(ip: str, port: int, channels: List[int], addr_base: int, interval: float, seed: Optional[int]):
    # 为每个通道准备一个独立的 SeqWriter
    # 每个通道都从1开始自己的1..9循环
    seq_map: Dict[int, SeqWriter] = {ch: SeqWriter(start_val=1) for ch in channels}

    # 地址基准：PLC 若为 1 起始（常见 40001 那种），我们对外输入 500，但实际要发 499
    def A(x: int) -> int:
        return x - (1 if addr_base == 1 else 0)

    # 启动信息
    log("========== PLC Demo Loop（监测+心跳版，无回填） ==========")
    log(f"PLC = {ip}:{port}, channels = {channels}, addr_base = {addr_base}, interval = {interval}s, seed = {seed}")
    log("规则：启动时每个通道按1..9循环写满60格。之后只打印状态变化，不再把被清零的格子写回。")

    mb = ModbusTCP(ip, port, timeout=1.0, unit_id=1)

    # 状态追踪
    last_run_status: int | None = None
    last_ready1: Dict[int, int] = {ch: -999 for ch in channels}
    last_now:    Dict[int, int] = {ch: -999 for ch in channels}   # 保存“上一帧”的 NOW

    # 心跳
    last_hb_t = 0.0
    hb_bit = 0

    # 尝试连接
    while True:
        try:
            mb.connect()
            break
        except Exception as e:
            log(f"[mb] connect error: {e} -> 2s 后重试")
            time.sleep(2)

    # 启动时铺底（一次性）
    initial_fill(mb, A, channels, seed, seq_map)

    try:
        while True:
            t = time.time()

            # 1) 心跳：每 0.5s 翻转一次（静默，只有失败才打印）
            if t - last_hb_t >= 0.5:
                hb_bit ^= 1
                try:
                    ok = mb.write_single(A(REG_HEARTBEAT), hb_bit)
                    if not ok:
                        log(f"[hb] write REG_HEARTBEAT({REG_HEARTBEAT}) -> NG")
                except Exception as e:
                    log(f"[hb] write fail: {e} -> reconnect")
                    try:
                        mb.connect()
                    except Exception as e2:
                        log(f"[mb] reconnect fail: {e2}")
                last_hb_t = t

            # 2) 运行状态（只打印变化）
            try:
                rs = mb.read_holding(A(REG_RUN_STATUS), 1)[0]
                if rs != last_run_status:
                    last_run_status = rs
                    if rs == 0:
                        log(f"[run] REG_RUN_STATUS({REG_RUN_STATUS})=0 -> 停止/暂停，维持心跳与监测")
                    elif rs == 1:
                        log(f"[run] REG_RUN_STATUS({REG_RUN_STATUS})=1 -> 运行中")
                    elif rs == 2:
                        log(f"[run] REG_RUN_STATUS({REG_RUN_STATUS})=2 -> 重启/清零请求（仅记录，不自动清零）")
                    else:
                        log(f"[run] REG_RUN_STATUS({REG_RUN_STATUS})={rs} -> 未知状态")
            except Exception as e:
                log(f"[run] read run_status fail: {e} -> reconnect")
                try:
                    mb.connect()
                except Exception as e2:
                    log(f"[mb] reconnect fail: {e2}")
                time.sleep(interval)
                continue

            # 3) 各通道轮询（只读+打印，不写）
            for ch in channels:
                try:
                    # READY_1（仅记录变化）
                    try:
                        r1 = mb.read_holding(A(ready1_reg(ch)), 1)[0]
                        if r1 != last_ready1[ch]:
                            last_ready1[ch] = r1
                            log(f"[ch{ch}] READY_1({ready1_reg(ch)}) 变化 -> {r1} "
                                f"{'(待机)' if r1==0 else '(一波就绪,采相开始)'}")
                    except Exception as e:
                        log(f"[ch{ch}] 读 READY_1 失败: {e}")
                        raise

                    # NOW（仅记录变化）
                    try:
                        nowv = mb.read_holding(A(now_reg(ch)), 1)[0]
                        if nowv != last_now[ch]:
                            log(f"[ch{ch}] NOW({now_reg(ch)}) 变化: {last_now[ch]} -> {nowv}")
                            # 更新上一帧 NOW
                            last_now[ch] = nowv
                    except Exception as e:
                        log(f"[ch{ch}] 读 NOW 失败: {e}")
                        raise

                except Exception:
                    # 上面已分别打印细节，这里兜底重连
                    try:
                        mb.connect()
                    except Exception as e2:
                        log(f"[mb] reconnect fail: {e2}")

            time.sleep(interval)

    finally:
        mb.close()
        log("[plc] bye.")

# ---------------------- 入口 ----------------------

def parse_args():
    ap = argparse.ArgumentParser(description="PLC demo loop（一次性铺底+状态监测，无回填）")
    ap.add_argument("--ip", default="192.168.1.1", help="PLC IP")
    ap.add_argument("--port", type=int, default=502, help="PLC Modbus TCP 端口")
    ap.add_argument("--channels", default="1,2,3,4", help="通道列表，例如 1,2 或 1,2,3,4")
    ap.add_argument("--addr-base", type=int, default=0, choices=[0, 1],
                    help="地址是否 1 起始（若 PLC 把 500 当实际偏移499，则传 1）")
    ap.add_argument("--interval", type=float, default=0.05, help="轮询间隔秒")
    ap.add_argument("--seed", type=int, default=None,
                    help="兼容旧参数；现逻辑只在初始铺底写入一次")
    return ap.parse_args()

if __name__ == "__main__":
    args = parse_args()
    chs = [int(x) for x in args.channels.split(",") if x.strip()]
    run_loop(args.ip, args.port, chs, addr_base=args.addr_base, interval=args.interval, seed=args.seed)




