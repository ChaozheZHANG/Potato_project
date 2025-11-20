# -*- coding: utf-8 -*-
"""
app/cam_plc_capture.py  （输出目录规则改版：F:/data/camera/YYYYMMDD/ + 扁平文件）

使用：
  python -m app.cam_plc_capture --fps 5 --threshold 10 --dim-n 1 ^
    --tcp 192.168.10.7:10000 --raw-file config\\light_open.txt --read-reply ^
    --plc-ip 192.168.1.1 --plc-port 502 --channels 1,2,3,4 --addr-base 0 ^
    --out F:/data/camera
"""

import os, sys, time, argparse, random, socket, struct
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional, Dict

import numpy as np
import cv2

# ------- 相机封装（已有） -------
from pkg.camera.calibrate_camera import (
    calibrate_camera_init,
    calibrate_get_frame,
    grabOne,
    closeCamera,
    setSoftTriggerConf,
    setExposureTime,
)

# ------- PLC 寄存器常量（已有） -------
from plc.registers import (
    REG_HEARTBEAT,
    ready1_reg, now_reg, attrs_base
)

# ================= 工具 =================
def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

# // NEW: 当天目录名（YYYYMMDD）
def day_folder_name(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now()
    return dt.strftime("%Y%m%d")

# // NEW: 生成文件名所需的时间片段
def make_time_parts(ts: float) -> Tuple[str, str, str]:
    """
    返回 (YYYYMMDD, HHMMSS, sec_key)
    sec_key 用于“同秒内计数”键
    """
    dt = datetime.fromtimestamp(ts)
    d = dt.strftime("%Y%m%d")
    hms = dt.strftime("%H%M%S")
    sec_key = f"{d}_{hms}"
    return d, hms, sec_key

def hexdump(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)

# ================= 灯控 TCP =================
class LightTCP:
    def __init__(self, host: str, port: int, timeout: float = 1.0):
        self.host = host; self.port = port
        self.s: Optional[socket.socket] = None
        self.timeout = timeout

    def connect(self):
        self.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect((self.host, self.port))
        self.s = s

    def close(self):
        if self.s:
            try: self.s.close()
            except: pass
        self.s = None

    def send(self, b: bytes):
        if not self.s: self.connect()
        self.s.sendall(b)

    def recv_reply(self, timeout: float = 0.3) -> Optional[bytes]:
        if not self.s: return None
        self.s.settimeout(timeout)
        try:
            hdr = self.s.recv(4)
            if len(hdr) < 4: return None
            h0, h1, lenL, lenH = hdr[0], hdr[1], hdr[2], hdr[3]
            total = (lenH << 8) | lenL
            rest = bytearray()
            while len(rest) < total:
                chunk = self.s.recv(total - len(rest))
                if not chunk: break
                rest.extend(chunk)
            return bytes(hdr + rest)
        except Exception:
            return None

def parse_hex_lines_from_file(path: str) -> List[bytes]:
    out: List[bytes] = []
    import string
    hexchars = set(string.hexdigits)
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            cleaned = "".join(c for c in s if c in hexchars)
            if len(cleaned) < 4:
                continue
            if cleaned[:4].upper() == "0606":  # ACK示例，不发
                continue
            if len(cleaned) % 2 != 0:
                continue
            out.append(bytes.fromhex(" ".join(cleaned[i:i+2] for i in range(0, len(cleaned), 2))))
    return out

# ================= Modbus TCP（精简） =================
class ModbusTCP:
    def __init__(self, host: str, port: int = 502, timeout: float = 1.0, unit_id: int = 1):
        self.host = host; self.port = port; self.timeout = timeout
        self.unit_id = unit_id; self.tid = 1
        self.sock: Optional[socket.socket] = None

    def connect(self):
        self.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect((self.host, self.port))
        self.sock = s

    def close(self):
        if self.sock:
            try: self.sock.close()
            except: pass
        self.sock = None

    def _next_tid(self) -> int:
        self.tid = (self.tid + 1) & 0xFFFF
        if self.tid == 0: self.tid = 1
        return self.tid

    def _recvn(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))  # type: ignore[arg-type]
            if not chunk: break
            buf.extend(chunk)
        return bytes(buf)

    def _send_pdu(self, pdu: bytes) -> bytes:
        if not self.sock: self.connect()
        tid = self._next_tid()
        mbap = struct.pack(">HHHB", tid, 0, len(pdu) + 1, self.unit_id)
        self.sock.sendall(mbap + pdu)  # type: ignore[arg-type]
        hdr = self._recvn(7)
        if len(hdr) != 7: raise IOError("MBAP short")
        r_tid, r_pid, r_len, r_uid = struct.unpack(">HHHB", hdr)
        if r_tid != tid or r_pid != 0 or r_uid != self.unit_id:
            raise IOError("MBAP mismatch")
        payload = self._recvn(r_len - 1)
        if len(payload) != r_len - 1:
            raise IOError("PDU short")
        if payload and (payload[0] & 0x80):
            code = payload[1] if len(payload) > 1 else -1
            raise IOError(f"Modbus exception fc=0x{payload[0]:02X}, code={code}")
        return payload

    def write_single(self, addr: int, value: int) -> bool:
        pdu = struct.pack(">BHH", 0x06, addr, value & 0xFFFF)
        r = self._send_pdu(pdu)
        return (len(r) == 5 and r[0] == 0x06)

# ================= 一次运行（可被看门狗反复调用） =================
def run_once(args, out_root: Path):
    # ---------- 灯控 ----------
    tcp_ip, tcp_port = args.tcp.split(":")
    light = LightTCP(tcp_ip.strip(), int(tcp_port), timeout=1.0)
    raw_frames = parse_hex_lines_from_file(args.raw_file)
    if not raw_frames:
        print(f"[light] raw-file={args.raw_file} 未解析出有效命令（须以 05 06 开头）。")
        raise RuntimeError("no raw frames")
    print(f"[light] raw commands loaded: {len(raw_frames)}")

    # ---------- PLC ----------
    mb = ModbusTCP(args.plc_ip, args.plc_port, timeout=1.0, unit_id=1)
    A = (lambda addr: addr - 1) if args.addr_base == 1 else (lambda addr: addr)
    chs = [int(x) for x in args.channels.split(",") if x.strip()]
    try:
        mb.connect()
        print(f"[plc] connected {args.plc_ip}:{args.plc_port}")
    except Exception as e:
        print(f"[plc] connect fail (will retry on write): {e}")

    # ---------- 相机 ----------
    cam, stream = calibrate_camera_init()  # 返回 (camera, stream)
    if cam is None or stream is None:
        raise RuntimeError("camera init failed")
    print("[cam] initialized")

    try:
        setSoftTriggerConf(cam)
    except Exception:
        pass
    try:
        setExposureTime(cam, 6000)  # 6ms
    except Exception:
        pass

    # ---------- 运行循环 ----------
    target_interval = 1.0 / max(0.1, args.fps)
    dim_streak = 0
    hb_bit = 0
    last_shot_t = 0.0
    # // NEW: 每通道、每秒独立计数
    sec_counter: Dict[Tuple[int, str], int] = {}

    print(f"[out] root = {out_root}")
    print("[loop] start... (watchdog active; Ctrl+C to stop)")
    try:
        while True:
            now = time.time()
            if last_shot_t > 0:
                sleep_need = last_shot_t + target_interval - now
                if sleep_need > 0:
                    time.sleep(min(sleep_need, target_interval))

            trig_ts = time.time()
            last_shot_t = trig_ts

            # 软触发
            try:
                grabOne(cam)
            except Exception as e:
                print(f"[trigger] soft trigger err: {e}")

            # 取图
            img = None
            try:
                img = calibrate_get_frame(stream)
            except Exception as e:
                print(f"[get] err: {e}")
                img = None

            # // NEW: 生成当天目录 & 时间片
            day_str, hms_str, sec_key = make_time_parts(trig_ts)
            day_dir = ensure_dir(out_root / day_str)

            if img is None or getattr(img, "size", 0) == 0:
                # 空帧也要生成一次文件名（按 CH 列表存？通常不需要保存空帧；这里只打印日志）
                print(f"[frame] empty -> {day_str} {hms_str}")
                dim_streak += 1
            else:
                mean_val = float(np.mean(img))
                try:
                    # // NEW: 为每个通道各自保存一份（文件名含 CHXX）
                    for ch in chs:
                        key = (ch, sec_key)
                        n = sec_counter.get(key, 0) + 1
                        sec_counter[key] = n
                        fn = f"CH{ch:02d}_{day_str}_{hms_str}-{n}.jpg"
                        fp = day_dir / fn
                        cv2.imwrite(str(fp), img)
                        print(f"[save] mean={mean_val:.1f} -> {fp.name}")
                except Exception as e:
                    print(f"[save] err: {e}")

                # 亮度判断
                if mean_val < args.threshold:
                    dim_streak += 1
                else:
                    dim_streak = 0

                # ====== TODO：算法结果 ======
                res = random.randint(0, 999)  # 先用随机数

                # 写下游寄存器（示例：写到每个通道的 attrs_base(ch)）
                for ch in chs:
                    addr = A(attrs_base(ch))
                    try:
                        ok = mb.write_single(addr, int(res) & 0xFFFF)
                        if not ok:
                            print(f"[plc] ch{ch} write REG {addr}={res} -> NG")
                    except Exception as e:
                        print(f"[plc] ch{ch} write err: {e} -> reconnect")
                        try:
                            mb.connect()
                            mb.write_single(addr, int(res) & 0xFFFF)
                        except Exception as e2:
                            print(f"[plc] reconnect/write fail: {e2}")

            # 低亮开灯
            if dim_streak >= max(1, args.dim_n):
                print(f"[light] dim streak = {dim_streak} -> send OPEN cmds")
                try:
                    light.connect()
                    for idx, frm in enumerate(raw_frames, 1):
                        print(f"[light] TX[{idx}/{len(raw_frames)}]: {hexdump(frm)}")
                        light.send(frm)
                        if args.read_reply:
                            r = light.recv_reply(timeout=0.5)
                            if r: print(f"[light] RX: {hexdump(r)}")
                            else: print("[light] RX: (no data)")
                except Exception as e:
                    print(f"[light] send err: {e}")
                finally:
                    dim_streak = 0  # 重置

            # 心跳（每帧翻转一次）
            hb_bit ^= 1
            try:
                _ = mb.write_single(A(REG_HEARTBEAT), hb_bit)
            except Exception:
                pass

    except KeyboardInterrupt:
        print("\n[loop] KeyboardInterrupt -> stop")
        raise
    finally:
        try: closeCamera(cam)
        except Exception: pass
        try: light.close()
        except Exception: pass
        try: mb.close()
        except Exception: pass
        print("[cleanup] resources closed")

# ================= 入口（看门狗） =================
def parse_args():
    ap = argparse.ArgumentParser(description="Camera + Light + PLC (flat save per day)")
    ap.add_argument("--fps", type=float, default=5.0, help="目标帧率")
    ap.add_argument("--threshold", type=float, default=10.0, help="亮度阈值（均值）")
    ap.add_argument("--dim-n", type=int, default=1, help="低于阈值连续N次则开灯")
    ap.add_argument("--tcp", type=str, required=True, help="灯控 ip:port")
    ap.add_argument("--raw-file", type=str, required=True, help="开灯十六进制帧 txt（每行一条）")
    ap.add_argument("--read-reply", action="store_true", help="发送后尝试读取应答")
    # // NEW: 默认输出根目录为 F:/data/camera
    ap.add_argument("--out", type=str, default="F:/data/camera", help="输出根目录（实际存到 <out>/YYYYMMDD/）")
    # PLC
    ap.add_argument("--plc-ip", type=str, default="192.168.1.1")
    ap.add_argument("--plc-port", type=int, default=502)
    ap.add_argument("--channels", type=str, default="1,2,3,4")
    ap.add_argument("--addr-base", type=int, choices=[0,1], default=0, help="PLC地址是否1起始（1则发起始地址-1）")
    return ap.parse_args()

def main():
    args = parse_args()
    out_root = ensure_dir(Path(args.out))
    print(f"[out] root = {out_root}")

    # 看门狗：除非 Ctrl+C，否则 2s 后自动重启
    while True:
        try:
            run_once(args, out_root)
        except KeyboardInterrupt:
            print("[exit] user interrupt. bye.")
            break
        except Exception as e:
            print(f"[watchdog] run crashed: {e} -> restarting in 2s...")
            time.sleep(2)

if __name__ == "__main__":
    main()


