#!/usr/bin/env python3
"""
实时监控相机目录并自动检测和跟踪
监控路径格式: F:/data/camera/YYYYMMDD/ch{CC}_{HHMMSS}-{NNN}.jpg
"""
import argparse
import json
import time
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from collections import defaultdict
import threading
import queue
import cv2
import numpy as np
from ultralytics import YOLO

# 导入PLC输出模块
try:
    # 尝试从上级目录导入
    import sys
    parent_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(parent_dir))
    from scripts.plc_output import PLCModbusTCP, PLCSerial, send_to_plc
except ImportError:
    # 如果plc_output不在，使用内置简化版本
    class PLCModbusTCP:
        def __init__(self, host="192.168.1.100", port=502, unit_id=1):
            self.host = host
            self.port = port
            self.unit_id = unit_id
            self.client = None
            try:
                from pymodbus.client import ModbusTcpClient
                self.client = ModbusTcpClient(host, port)
                self.client.connect()
                print(f"Connected to Modbus TCP {host}:{port}")
            except ImportError:
                print("Warning: pymodbus not installed. Install: pip install pymodbus")
            except Exception as e:
                print(f"Modbus connection failed: {e}")
        
        def write_bits(self, address: int, bits: List[int]) -> bool:
            if not self.client or not self.client.is_socket_open():
                return False
            try:
                values = [bool(b) for b in bits]
                result = self.client.write_coils(address, values, unit=self.unit_id)
                return not result.isError()
            except Exception as e:
                print(f"Modbus write failed: {e}")
                return False
        
        def close(self):
            if self.client:
                self.client.close()


class PotatoIDGenerator:
    """生成唯一土豆ID：年月日时分秒+60进制计数(01-60循环)"""
    def __init__(self):
        self.counter = 1
        self.last_second = ""
    
    def generate(self) -> str:
        now = datetime.now()
        ts_second = now.strftime("%Y%m%d%H%M%S")
        
        if ts_second != self.last_second:
            self.counter = 1
            self.last_second = ts_second
        
        potato_id = f"{ts_second}{self.counter:02d}"
        self.counter += 1
        if self.counter > 60:
            self.counter = 1
        
        return potato_id


class PotatoTracker:
    """土豆目标跟踪器 - 为每个土豆分配持久ID"""
    def __init__(self, id_generator: PotatoIDGenerator, channel: str = "ch01"):
        self.id_gen = id_generator
        self.channel = channel
        self.tracked_potatoes = {}  # track_id -> track_info
        self.next_track_id = 1
        self.max_disappeared = 5  # 最多消失帧数（图片模式减少）
    
    def update(self, detections: List[Dict]) -> Dict[int, Dict]:
        """更新跟踪器"""
        if not detections:
            self._cleanup_disappeared()
            return self.tracked_potatoes
        
        active_tracks = {}
        
        for det in detections:
            best_match_id = None
            best_iou = 0.3
            
            for track_id, tracked in self.tracked_potatoes.items():
                if tracked.get("disappeared", 0) > 0:
                    continue
                iou = self._calculate_iou(det["bbox"], tracked["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_match_id = track_id
            
            if best_match_id is not None:
                self.tracked_potatoes[best_match_id]["bbox"] = det["bbox"]
                self.tracked_potatoes[best_match_id]["area"] = det["area"]
                self.tracked_potatoes[best_match_id]["history"].append(det["bbox"][:2])
                self.tracked_potatoes[best_match_id]["disappeared"] = 0
                self.tracked_potatoes[best_match_id]["last_seen"] = time.time()
                active_tracks[best_match_id] = self.tracked_potatoes[best_match_id]
            else:
                new_id = self.next_track_id
                self.next_track_id += 1
                potato_id = self.id_gen.generate()
                self.tracked_potatoes[new_id] = {
                    "potato_id": potato_id,
                    "bbox": det["bbox"],
                    "area": det["area"],
                    "history": [det["bbox"][:2]],
                    "disappeared": 0,
                    "last_seen": time.time(),
                    "graded": False,
                    "grade": None,
                    "counts": {},
                    "signal": {},
                    "channel": self.channel
                }
                active_tracks[new_id] = self.tracked_potatoes[new_id]
        
        for track_id in self.tracked_potatoes:
            if track_id not in active_tracks:
                self.tracked_potatoes[track_id]["disappeared"] = \
                    self.tracked_potatoes[track_id].get("disappeared", 0) + 1
        
        return self.tracked_potatoes
    
    def _calculate_iou(self, bbox1, bbox2):
        """计算两个bbox的IoU"""
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        xi1 = max(x1, x2)
        yi1 = max(y1, y2)
        xi2 = min(x1 + w1, x2 + w2)
        yi2 = min(y1 + h1, y2 + h2)
        
        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        box1_area = w1 * h1
        box2_area = w2 * h2
        union_area = box1_area + box2_area - inter_area
        
        return inter_area / union_area if union_area > 0 else 0
    
    def _cleanup_disappeared(self):
        """清理消失过久的目标"""
        to_remove = [tid for tid, tracked in self.tracked_potatoes.items()
                    if tracked.get("disappeared", 0) > self.max_disappeared]
        for tid in to_remove:
            del self.tracked_potatoes[tid]


def load_rules(path: Path) -> Dict[str, Any]:
    """加载分级规则"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def is_ok(counts: Dict[str, int], rules: Dict[str, Any]) -> bool:
    """判断是否为OK品"""
    rule = rules["ok_rules"]
    for forb in rule.get("forbid", []):
        if counts.get(forb, 0) > 0:
            return False
    max_counts = rule.get("max_counts", {})
    for cls, limit in max_counts.items():
        if counts.get(cls, 0) > limit:
            return False
    return True


def to_signal_bits(grade: str, rules: Dict[str, Any]) -> List[int]:
    """转换为信号位"""
    mapping = rules["signals"]["mapping"]
    if grade in mapping:
        return mapping[grade].get("bits", [0]*8)
    return [0] * 8


def estimate_size_from_area(area_px: float, rules: Dict[str, Any]) -> int:
    """根据面积估算尺寸等级"""
    cfg = rules.get("size", {})
    thresholds = cfg.get("thresholds_px", [])
    if not thresholds:
        return 1
    for idx, t in enumerate(thresholds, start=1):
        if area_px < t:
            return idx
    return 7


def extract_potatoes_from_image(image: np.ndarray) -> List[Dict]:
    """从图像中提取所有土豆区域"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if th.mean() > 127:
        th = 255 - th
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)
    
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    potatoes = []
    for cnt in cnts:
        area = cv2.contourArea(cnt)
        if area < 50000:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        potatoes.append({
            "bbox": [x, y, w, h],
            "area": float(area)
        })
    
    return potatoes


def grade_potato_roi(
    image: np.ndarray,
    bbox: List[int],
    model: YOLO,
    rules: Dict[str, Any],
    conf: float = 0.25
) -> tuple:
    """对单个土豆ROI进行缺陷检测和分级"""
    x, y, w, h = bbox
    roi = image[y:y+h, x:x+w].copy()
    
    results = model.predict(
        task='obb', source=roi, imgsz=640, conf=conf,
        save=False, device='cpu', verbose=False
    )
    
    counts: Dict[str, int] = {}
    if results:
        r = results[0]
        names = r.names
        if getattr(r, 'obb', None) is not None:
            clses = r.obb.cls.cpu().numpy().tolist()
            confs = r.obb.conf.cpu().numpy().tolist()
            for ci, cfv in zip(clses, confs):
                name = names[int(ci)]
                if cfv >= conf:
                    counts[name] = counts.get(name, 0) + 1
    
    area_px = float(w * h)
    
    if is_ok(counts, rules):
        size_bin = estimate_size_from_area(area_px, rules)
        grade = f"OK_S{size_bin}"
    else:
        grade = "NG"
    
    signal_bits = to_signal_bits(grade, rules)
    lane = rules["signals"]["mapping"].get(grade, {}).get("lane", 0)
    
    return grade, counts, signal_bits, lane, area_px


class CameraDirectoryMonitor:
    """监控相机目录，自动处理新图片"""
    
    def __init__(
        self,
        base_dir: str,
        model: YOLO,
        rules: Dict[str, Any],
        plc_client: Optional[PLCModbusTCP] = None,
        plc_address: int = 0,
        conf: float = 0.25,
        output_dir: Optional[Path] = None
    ):
        self.base_dir = Path(base_dir)
        self.model = model
        self.rules = rules
        self.plc_client = plc_client
        self.plc_address = plc_address
        self.conf = conf
        self.output_dir = output_dir or Path("results/realtime_monitor")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 每个通道一个跟踪器
        self.trackers: Dict[str, PotatoTracker] = {}
        self.id_generators: Dict[str, PotatoIDGenerator] = {}
        
        # 已处理的文件集合
        self.processed_files: Set[Path] = set()
        
        # 结果队列
        self.result_queue = queue.Queue()
        
        # 运行标志
        self.running = True
        
        # 统计信息
        self.stats = {
            "total_images": 0,
            "total_potatoes": 0,
            "by_channel": defaultdict(int),
            "by_grade": defaultdict(int)
        }
    
    def _get_channel_from_path(self, path: Path) -> Optional[str]:
        """从路径提取通道号"""
        # 匹配 ch{CC}_ 格式
        match = re.search(r'ch(\d+)_', path.name)
        if match:
            return f"ch{match.group(1).zfill(2)}"
        return None
    
    def _get_tracker(self, channel: str) -> PotatoTracker:
        """获取或创建通道跟踪器"""
        if channel not in self.trackers:
            if channel not in self.id_generators:
                self.id_generators[channel] = PotatoIDGenerator()
            self.trackers[channel] = PotatoTracker(
                self.id_generators[channel],
                channel=channel
            )
        return self.trackers[channel]
    
    def _process_image(self, image_path: Path):
        """处理单张图片"""
        if image_path in self.processed_files:
            return
        
        try:
            image = cv2.imread(str(image_path))
            if image is None:
                print(f"Failed to read image: {image_path}")
                return
            
            channel = self._get_channel_from_path(image_path)
            if not channel:
                print(f"Could not extract channel from: {image_path}")
                return
            
            tracker = self._get_tracker(channel)
            
            # 提取土豆
            detections = extract_potatoes_from_image(image)
            
            # 更新跟踪器
            tracked = tracker.update(detections)
            
            # 对每个跟踪到的土豆进行分级
            for track_id, track_info in tracked.items():
                if track_info.get("disappeared", 0) > 0:
                    continue
                
                potato_id = track_info["potato_id"]
                
                # 如果还未分级，进行分级
                if not track_info.get("graded", False):
                    grade, counts, signal_bits, lane, area = grade_potato_roi(
                        image, track_info["bbox"], self.model, self.rules, self.conf
                    )
                    track_info["grade"] = grade
                    track_info["counts"] = counts
                    track_info["signal"] = {
                        "bits": signal_bits,
                        "bit_order": self.rules["signals"]["bit_order"],
                        "lane": lane
                    }
                    track_info["graded"] = True
                    track_info["area_px"] = area
                    track_info["image_path"] = str(image_path)
                    track_info["timestamp"] = time.time()
                    
                    # 发送PLC信号
                    if self.plc_client:
                        success = self.plc_client.write_bits(self.plc_address, signal_bits)
                        if success:
                            print(f"[{potato_id}] {grade} -> PLC signal sent (Lane {lane})")
                        else:
                            print(f"[{potato_id}] {grade} -> PLC signal failed")
                    else:
                        print(f"[{potato_id}] {grade} (Lane {lane}) - No PLC client")
                    
                    # 保存结果
                    self._save_result(track_info)
                    
                    # 更新统计
                    self.stats["total_potatoes"] += 1
                    self.stats["by_channel"][channel] += 1
                    self.stats["by_grade"][grade] += 1
            
            self.processed_files.add(image_path)
            self.stats["total_images"] += 1
            
            print(f"Processed: {image_path.name} | Channel: {channel} | "
                  f"Potatoes: {len([t for t in tracked.values() if t.get('disappeared', 0) == 0])}")
        
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            import traceback
            traceback.print_exc()
    
    def _save_result(self, track_info: Dict):
        """保存检测结果"""
        timestamp = datetime.now().strftime("%Y%m%d")
        jsonl_path = self.output_dir / f"results_{timestamp}.jsonl"
        csv_path = self.output_dir / f"results_{timestamp}.csv"
        
        # 追加JSONL
        with open(jsonl_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(track_info, ensure_ascii=False) + "\n")
        
        # 追加CSV（如果文件不存在，写入表头）
        import csv as csv_module
        file_exists = csv_path.exists()
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv_module.writer(f)
            if not file_exists:
                writer.writerow([
                    "potato_id", "channel", "grade", "lane", "signal_bits",
                    "counts", "bbox", "area_px", "image_path", "timestamp"
                ])
            writer.writerow([
                track_info["potato_id"],
                track_info.get("channel", "unknown"),
                track_info["grade"],
                track_info["signal"].get("lane", 0),
                ''.join(map(str, track_info["signal"].get("bits", []))),
                json.dumps(track_info["counts"], ensure_ascii=False),
                json.dumps(track_info["bbox"], ensure_ascii=False),
                track_info.get("area_px", 0),
                track_info.get("image_path", ""),
                track_info.get("timestamp", 0)
            ])
    
    def scan_directory(self):
        """扫描目录查找新图片"""
        today = datetime.now().strftime("%Y%m%d")
        today_dir = self.base_dir / today
        
        if not today_dir.exists():
            return
        
        # 查找所有匹配的图片文件
        pattern = re.compile(r'ch\d+_\d+-\d+\.jpg$', re.IGNORECASE)
        for img_path in today_dir.rglob("*.jpg"):
            if pattern.match(img_path.name) and img_path not in self.processed_files:
                self._process_image(img_path)
    
    def run(self, scan_interval: float = 0.5):
        """运行监控循环"""
        print(f"Starting camera directory monitor...")
        print(f"Base directory: {self.base_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"PLC client: {'Connected' if self.plc_client else 'Disabled'}")
        print(f"Scan interval: {scan_interval}s")
        print("-" * 60)
        
        try:
            while self.running:
                self.scan_directory()
                time.sleep(scan_interval)
                
                # 每100张图片打印统计
                if self.stats["total_images"] % 100 == 0 and self.stats["total_images"] > 0:
                    print(f"\n=== Statistics ===")
                    print(f"Total images: {self.stats['total_images']}")
                    print(f"Total potatoes: {self.stats['total_potatoes']}")
                    print(f"By channel: {dict(self.stats['by_channel'])}")
                    print(f"By grade: {dict(self.stats['by_grade'])}")
                    print("-" * 60)
        
        except KeyboardInterrupt:
            print("\nStopping monitor...")
        finally:
            if self.plc_client:
                self.plc_client.close()
            print(f"\nFinal statistics:")
            print(f"Total images processed: {self.stats['total_images']}")
            print(f"Total potatoes detected: {self.stats['total_potatoes']}")


def main():
    parser = argparse.ArgumentParser(
        description="实时监控相机目录并自动检测和跟踪"
    )
    parser.add_argument(
        "--camera_dir",
        default="F:/data/camera",
        help="相机图片存储根目录 (默认: F:/data/camera)"
    )
    parser.add_argument(
        "--model",
        required=True,
        help="模型权重文件路径"
    )
    parser.add_argument(
        "--rules",
        default="config/grading_rules.json",
        help="分级规则文件路径"
    )
    parser.add_argument(
        "--plc_enable",
        action="store_true",
        help="启用PLC输出"
    )
    parser.add_argument(
        "--plc_host",
        default="192.168.1.100",
        help="PLC IP地址 (默认: 192.168.1.100)"
    )
    parser.add_argument(
        "--plc_port",
        type=int,
        default=502,
        help="PLC端口 (默认: 502)"
    )
    parser.add_argument(
        "--plc_address",
        type=int,
        default=0,
        help="PLC起始地址 (默认: 0)"
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="检测置信度阈值 (默认: 0.25)"
    )
    parser.add_argument(
        "--output",
        default="results/realtime_monitor",
        help="结果输出目录"
    )
    parser.add_argument(
        "--scan_interval",
        type=float,
        default=0.5,
        help="扫描间隔（秒）(默认: 0.5)"
    )
    
    args = parser.parse_args()
    
    # 加载模型和规则
    print("Loading model...")
    model = YOLO(args.model)
    
    print("Loading rules...")
    rules_path = Path(args.rules)
    if not rules_path.is_absolute():
        rules_path = Path(__file__).parent.parent / rules_path
    rules = load_rules(rules_path)
    
    # 创建PLC客户端
    plc_client = None
    if args.plc_enable:
        print(f"Connecting to PLC at {args.plc_host}:{args.plc_port}...")
        plc_client = PLCModbusTCP(args.plc_host, args.plc_port)
    
    # 创建监控器
    monitor = CameraDirectoryMonitor(
        base_dir=args.camera_dir,
        model=model,
        rules=rules,
        plc_client=plc_client,
        plc_address=args.plc_address,
        conf=args.conf,
        output_dir=Path(args.output)
    )
    
    # 运行监控
    monitor.run(scan_interval=args.scan_interval)


if __name__ == '__main__':
    main()

