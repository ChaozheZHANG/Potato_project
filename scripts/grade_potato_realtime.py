#!/usr/bin/env python3
"""实时视频流土豆跟踪与分级系统 - 为每个土豆分配持久ID并跟踪"""
import argparse
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from ultralytics import YOLO
import cv2
import csv
import time
from datetime import datetime
from collections import defaultdict
import numpy as np


class PotatoIDGenerator:
    """生成唯一土豆ID：年月日时分秒+60进制计数(01-60循环)"""
    def __init__(self):
        self.counter = 1
        self.last_second = ""
    
    def generate(self) -> str:
        now = datetime.now()
        ts_second = now.strftime("%Y%m%d%H%M%S")  # 到秒
        
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
    def __init__(self, id_generator: PotatoIDGenerator):
        self.id_gen = id_generator
        self.tracked_potatoes = {}  # track_id -> {"potato_id": ..., "history": [...], "graded": False, ...}
        self.next_track_id = 1
        self.max_disappeared = 30  # 最多消失帧数
    
    def update(self, detections: List[Dict]) -> Dict[int, Dict]:
        """
        更新跟踪器
        detections: [{"bbox": [x,y,w,h], "area": float, ...}, ...]
        返回: {track_id: {"potato_id": ..., "bbox": ..., ...}}
        """
        if not detections:
            # 清理消失的目标
            self._cleanup_disappeared()
            return self.tracked_potatoes
        
        # 简单的基于IoU的跟踪（生产环境建议用ByteTrack/BoT-SORT）
        active_tracks = {}
        
        for det in detections:
            best_match_id = None
            best_iou = 0.3  # IoU阈值
            
            # 查找最佳匹配
            for track_id, tracked in self.tracked_potatoes.items():
                if tracked.get("disappeared", 0) > 0:
                    continue
                iou = self._calculate_iou(det["bbox"], tracked["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_match_id = track_id
            
            if best_match_id is not None:
                # 更新已有轨迹
                self.tracked_potatoes[best_match_id]["bbox"] = det["bbox"]
                self.tracked_potatoes[best_match_id]["area"] = det["area"]
                self.tracked_potatoes[best_match_id]["history"].append(det["bbox"][:2])
                self.tracked_potatoes[best_match_id]["disappeared"] = 0
                self.tracked_potatoes[best_match_id]["last_seen"] = time.time()
                active_tracks[best_match_id] = self.tracked_potatoes[best_match_id]
            else:
                # 创建新轨迹
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
                    "signal": {}
                }
                active_tracks[new_id] = self.tracked_potatoes[new_id]
        
        # 标记消失的目标
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
        to_remove = []
        for track_id, tracked in self.tracked_potatoes.items():
            if tracked.get("disappeared", 0) > self.max_disappeared:
                to_remove.append(track_id)
        for tid in to_remove:
            del self.tracked_potatoes[tid]


def load_rules(path: Path) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def is_ok(counts: Dict[str, int], rules: Dict[str, Any]) -> bool:
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
    mapping = rules["signals"]["mapping"]
    if grade in mapping:
        return mapping[grade].get("bits", [0]*8)
    return [0] * 8


def estimate_size_from_area(area_px: float, rules: Dict[str, Any]) -> int:
    cfg = rules.get("size", {})
    thresholds = cfg.get("thresholds_px", [])
    if not thresholds:
        return 1
    for idx, t in enumerate(thresholds, start=1):
        if area_px < t:
            return idx
    return 7


def extract_potatoes_from_frame(frame: np.ndarray) -> List[Dict]:
    """从帧中提取所有土豆区域（改进版）"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # 高斯模糊
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Otsu二值化
    _, th = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if th.mean() > 127:
        th = 255 - th
    
    # 形态学处理
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)
    
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    potatoes = []
    for cnt in cnts:
        area = cv2.contourArea(cnt)
        if area < 50000:  # 提高阈值
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        potatoes.append({
            "bbox": [x, y, w, h],
            "area": float(area)
        })
    
    return potatoes


def grade_potato_roi(
    frame: np.ndarray,
    bbox: List[int],
    model: YOLO,
    rules: Dict[str, Any],
    conf: float = 0.25
) -> Tuple[str, Dict[str, int], List[int], int, float]:
    """对单个土豆ROI进行缺陷检测和分级"""
    x, y, w, h = bbox
    roi = frame[y:y+h, x:x+w].copy()
    
    results = model.predict(task='obb', source=roi, imgsz=640, conf=conf, save=False, device='cpu', verbose=False)
    
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


def draw_tracked_potato(
    frame: np.ndarray,
    track_info: Dict,
    show_trail: bool = True
) -> np.ndarray:
    """在帧上绘制跟踪的土豆"""
    bbox = track_info["bbox"]
    x, y, w, h = bbox
    potato_id = track_info["potato_id"]
    grade = track_info.get("grade", "Processing...")
    
    # 颜色
    if grade == "Processing...":
        color = (255, 255, 0)  # 黄色 - 处理中
    elif grade.startswith("OK"):
        color = (0, 255, 0)  # 绿色 - OK
    else:
        color = (0, 0, 255)  # 红色 - NG
    
    # 绘制边框
    cv2.rectangle(frame, (x, y), (x+w, y+h), color, 3)
    
    # 绘制轨迹
    if show_trail and len(track_info.get("history", [])) > 1:
        points = track_info["history"][-20:]  # 最近20个点
        for i in range(1, len(points)):
            pt1 = tuple(map(int, points[i-1]))
            pt2 = tuple(map(int, points[i]))
            cv2.line(frame, pt1, pt2, color, 2)
    
    # 绘制ID和等级标签
    label = f"ID:{potato_id} {grade}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 2
    
    (label_w, label_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)
    cv2.rectangle(frame, (x, y-label_h-10), (x+label_w+10, y), color, -1)
    cv2.putText(frame, label, (x+5, y-5), font, font_scale, (255, 255, 255), thickness)
    
    return frame


def process_video_stream(
    source,
    model: YOLO,
    rules: Dict[str, Any],
    out_dir: Path,
    conf: float = 0.25,
    display: bool = True
):
    """处理视频流并实时跟踪土豆"""
    id_gen = PotatoIDGenerator()
    tracker = PotatoTracker(id_gen)
    
    cap = cv2.VideoCapture(source if isinstance(source, int) else str(source))
    
    jsonl_path = out_dir / "tracked_potatoes.jsonl"
    csv_path = out_dir / "tracked_potatoes.csv"
    
    # 视频录制（可选）
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_video = None
    
    frame_idx = 0
    graded_potatoes = set()  # 已分级的土豆ID
    
    with open(jsonl_path, 'w', encoding='utf-8') as jf, \
         open(csv_path, 'w', newline='', encoding='utf-8') as cf:
        
        csv_writer = csv.writer(cf)
        csv_writer.writerow(["potato_id", "frame", "bbox_json", "grade", "signal_bits", "lane", "counts_json", "timestamp"])
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if out_video is None and display:
                h, w = frame.shape[:2]
                out_video = cv2.VideoWriter(
                    str(out_dir / "tracked_output.mp4"),
                    fourcc, 30.0, (w, h)
                )
            
            # 提取土豆
            detections = extract_potatoes_from_frame(frame)
            
            # 更新跟踪器
            tracked = tracker.update(detections)
            
            # 对每个跟踪到的土豆进行分级（仅分级一次）
            for track_id, track_info in tracked.items():
                if track_info.get("disappeared", 0) > 0:
                    continue
                
                potato_id = track_info["potato_id"]
                
                # 如果还未分级，进行分级
                if not track_info.get("graded", False):
                    grade, counts, signal_bits, lane, area = grade_potato_roi(
                        frame, track_info["bbox"], model, rules, conf
                    )
                    track_info["grade"] = grade
                    track_info["counts"] = counts
                    track_info["signal"] = {
                        "bits": signal_bits,
                        "bit_order": rules["signals"]["bit_order"],
                        "lane": lane
                    }
                    track_info["graded"] = True
                    track_info["area_px"] = area
                    
                    # 写入结果
                    if potato_id not in graded_potatoes:
                        record = {
                            "potato_id": potato_id,
                            "frame": frame_idx,
                            "bbox": track_info["bbox"],
                            "counts": counts,
                            "grade": grade,
                            "signal": track_info["signal"],
                            "timestamp": time.time()
                        }
                        jf.write(json.dumps(record, ensure_ascii=False) + "\n")
                        jf.flush()
                        
                        csv_writer.writerow([
                            potato_id,
                            frame_idx,
                            json.dumps(track_info["bbox"]),
                            grade,
                            ''.join(map(str, signal_bits)),
                            lane,
                            json.dumps(counts, ensure_ascii=False),
                            time.time()
                        ])
                        
                        graded_potatoes.add(potato_id)
                        print(f"[{potato_id}] {grade} - Lane {lane}")
                
                # 绘制跟踪结果
                frame = draw_tracked_potato(frame, track_info, show_trail=True)
            
            # 显示帧信息
            info_text = f"Frame: {frame_idx} | Tracked: {len([t for t in tracked.values() if t.get('disappeared', 0) == 0])}"
            cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            
            # 显示或保存
            if display:
                cv2.imshow("Potato Tracking & Grading", frame)
                if out_video:
                    out_video.write(frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            frame_idx += 1
            if frame_idx % 30 == 0:
                print(f"处理 {frame_idx} 帧, 跟踪 {len(tracked)} 个目标, 已分级 {len(graded_potatoes)} 个土豆")
    
    cap.release()
    if out_video:
        out_video.release()
    cv2.destroyAllWindows()
    
    print(f"\n处理完成:")
    print(f"  - 总帧数: {frame_idx}")
    print(f"  - 总土豆数: {len(graded_potatoes)}")
    print(f"  - JSONL: {jsonl_path}")
    print(f"  - CSV: {csv_path}")
    if out_video:
        print(f"  - 视频: {out_dir / 'tracked_output.mp4'}")


def main():
    parser = argparse.ArgumentParser(description="实时视频流土豆跟踪与分级系统")
    parser.add_argument("--model", required=True, help="训练好的模型权重")
    parser.add_argument("--source", default="0", help="视频源：0(摄像头), 视频文件路径")
    parser.add_argument("--rules", default="/tmp/potato_inspection_system/config/grading_rules.json")
    parser.add_argument("--out", default="/tmp/potato_inspection_system/results/realtime_tracking")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--no-display", action="store_true", help="不显示窗口")
    args = parser.parse_args()
    
    rules = load_rules(Path(args.rules))
    model = YOLO(args.model)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 处理source
    source = int(args.source) if args.source.isdigit() else args.source
    
    process_video_stream(
        source, model, rules, out_dir, args.conf, not args.no_display
    )


if __name__ == '__main__':
    main()

