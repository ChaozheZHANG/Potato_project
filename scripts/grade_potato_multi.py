#!/usr/bin/env python3
"""多土豆分级系统：为每个土豆分配唯一ID并独立分级"""
import argparse
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from ultralytics import YOLO
import cv2
import csv
import time
from datetime import datetime
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
    bit_order = rules["signals"]["bit_order"]
    bits = [0] * len(bit_order)
    if grade in mapping:
        custom = mapping[grade].get("bits")
        if custom:
            return custom
    if grade in bit_order:
        bits[bit_order.index(grade)] = 1
    return bits


def estimate_size_from_area(area_px: float, rules: Dict[str, Any]) -> int:
    """基于面积返回尺寸档位 1-7"""
    cfg = rules.get("size", {})
    thresholds = cfg.get("thresholds_px", [])
    if not thresholds:
        return 1
    for idx, t in enumerate(thresholds, start=1):
        if area_px < t:
            return idx
    return 7


def extract_individual_potatoes(image_path: str) -> List[Tuple[np.ndarray, Dict]]:
    """分割图片中的每个土豆区域，返回[(子图, bbox_info), ...]"""
    img = cv2.imread(image_path)
    if img is None:
        return []
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if th.mean() > 127:
        th = 255 - th
    
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    potatoes = []
    for cnt in cnts:
        area = cv2.contourArea(cnt)
        if area < 10000:  # 过滤小噪点
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        roi = img[y:y+h, x:x+w].copy()
        bbox_info = {
            "x": int(x),
            "y": int(y),
            "width": int(w),
            "height": int(h),
            "area_px": float(area)
        }
        potatoes.append((roi, bbox_info))
    
    return potatoes


def grade_single_potato(
    roi: np.ndarray,
    bbox_info: Dict,
    model: YOLO,
    rules: Dict[str, Any],
    conf: float = 0.25
) -> Tuple[str, Dict[str, int], List[int], int]:
    """对单个土豆ROI进行缺陷检测和分级"""
    # 在ROI上检测缺陷
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
    
    # 判断OK/NG
    if is_ok(counts, rules):
        size_bin = estimate_size_from_area(bbox_info["area_px"], rules)
        grade = f"OK_S{size_bin}"
    else:
        grade = "NG"
    
    signal_bits = to_signal_bits(grade, rules)
    lane = rules["signals"]["mapping"].get(grade, {}).get("lane", 0)
    
    return grade, counts, signal_bits, lane


def draw_potato_label(img: np.ndarray, bbox: Dict, potato_id: str, grade: str) -> np.ndarray:
    """在图片上绘制土豆序号和分级结果"""
    x, y, w, h = bbox["x"], bbox["y"], bbox["width"], bbox["height"]
    
    # 绘制边框
    color = (0, 255, 0) if grade.startswith("OK") else (0, 0, 255)
    cv2.rectangle(img, (x, y), (x+w, y+h), color, 3)
    
    # 绘制ID和等级标签
    label = f"ID:{potato_id} {grade}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    thickness = 2
    
    (label_w, label_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)
    cv2.rectangle(img, (x, y-label_h-10), (x+label_w+10, y), color, -1)
    cv2.putText(img, label, (x+5, y-5), font, font_scale, (255, 255, 255), thickness)
    
    return img


def process_image(
    image_path: str,
    model: YOLO,
    rules: Dict[str, Any],
    id_gen: PotatoIDGenerator,
    out_dir: Path,
    conf: float = 0.25,
    save_viz: bool = True
) -> List[Dict]:
    """处理单张图片，返回所有土豆的分级结果"""
    potatoes = extract_individual_potatoes(image_path)
    
    if not potatoes:
        print(f"警告: {image_path} 未检测到土豆")
        return []
    
    results = []
    img_viz = cv2.imread(image_path) if save_viz else None
    
    for roi, bbox in potatoes:
        potato_id = id_gen.generate()
        grade, counts, signal_bits, lane = grade_single_potato(roi, bbox, model, rules, conf)
        
        result = {
            "potato_id": potato_id,
            "image": image_path,
            "bbox": bbox,
            "counts": counts,
            "grade": grade,
            "signal": {
                "bits": signal_bits,
                "bit_order": rules["signals"]["bit_order"],
                "lane": lane
            }
        }
        results.append(result)
        
        # 在可视化图上标记
        if save_viz and img_viz is not None:
            img_viz = draw_potato_label(img_viz, bbox, potato_id, grade)
    
    # 保存可视化结果
    if save_viz and img_viz is not None:
        viz_dir = out_dir / "visualizations"
        viz_dir.mkdir(exist_ok=True)
        viz_path = viz_dir / f"{Path(image_path).stem}_labeled.jpg"
        cv2.imwrite(str(viz_path), img_viz)
    
    return results


def main():
    parser = argparse.ArgumentParser(description="多土豆分级系统 - 为每个土豆分配唯一ID")
    parser.add_argument("--model", required=True, help="训练好的模型权重")
    parser.add_argument("--source", required=True, help="图片或目录")
    parser.add_argument("--rules", default="/tmp/potato_inspection_system/config/grading_rules.json")
    parser.add_argument("--out", default="/tmp/potato_inspection_system/results/grades_multi")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--no-viz", action="store_true", help="不保存可视化图片")
    args = parser.parse_args()
    
    rules = load_rules(Path(args.rules))
    model = YOLO(args.model)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    id_gen = PotatoIDGenerator()
    
    # 收集所有图片
    source_path = Path(args.source)
    if source_path.is_file():
        images = [str(source_path)]
    else:
        images = [str(p) for p in source_path.rglob("*") if p.suffix.lower() in {'.jpg', '.jpeg', '.png'}]
    
    all_results = []
    
    for img_path in images:
        print(f"处理: {img_path}")
        img_results = process_image(
            img_path, model, rules, id_gen, out_dir, args.conf, not args.no_viz
        )
        all_results.extend(img_results)
    
    # 保存JSONL
    jsonl_path = out_dir / "potatoes.jsonl"
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for res in all_results:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
    
    # 保存CSV
    csv_path = out_dir / "potatoes.csv"
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["potato_id", "image", "bbox_json", "grade", "signal_bits", "lane", "counts_json"])
        for res in all_results:
            writer.writerow([
                res["potato_id"],
                res["image"],
                json.dumps(res["bbox"], ensure_ascii=False),
                res["grade"],
                ''.join(map(str, res["signal"]["bits"])),
                res["signal"]["lane"],
                json.dumps(res["counts"], ensure_ascii=False)
            ])
    
    print(f"\n处理完成:")
    print(f"  - 共处理 {len(images)} 张图片")
    print(f"  - 检测到 {len(all_results)} 个土豆")
    print(f"  - JSONL: {jsonl_path}")
    print(f"  - CSV: {csv_path}")
    if not args.no_viz:
        print(f"  - 可视化: {out_dir / 'visualizations'}/")


if __name__ == '__main__':
    main()

