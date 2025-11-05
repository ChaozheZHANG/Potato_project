#!/usr/bin/env python3
"""基于YOLO OBB检测结果为每个缺陷标签分配唯一ID并分级"""
import argparse
import json
from pathlib import Path
from typing import Dict, List, Any
from ultralytics import YOLO
import cv2
import csv
import numpy as np
from datetime import datetime
from collections import defaultdict


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


def is_potato_ok(counts: Dict[str, int], rules: Dict[str, Any]) -> bool:
    """根据缺陷计数判断土豆是否OK"""
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


def draw_obb_box(img: np.ndarray, xyxyxyxy: np.ndarray, label: str, color: tuple):
    """绘制旋转边界框（OBB）和标签"""
    # xyxyxyxy: [x1,y1,x2,y2,x3,y3,x4,y4] 四个顶点坐标
    points = xyxyxyxy.reshape((-1, 2)).astype(np.int32)
    
    # 绘制旋转框
    cv2.polylines(img, [points], True, color, 2)
    
    # 计算标签位置（使用第一个顶点）
    x, y = points[0]
    
    # 绘制标签背景和文字（只显示缺陷名称，不显示ID）
    label_text = label
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 2
    
    (label_w, label_h), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)
    cv2.rectangle(img, (x, y-label_h-10), (x+label_w+10, y), color, -1)
    cv2.putText(img, label_text, (x+5, y-5), font, font_scale, (255, 255, 255), thickness)
    
    return img


def extract_individual_potatoes(image: np.ndarray) -> List[Dict]:
    """从图片中分割出每个土豆个体（改进版：多阈值+形态学处理）"""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 高斯模糊降噪
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Otsu二值化
    _, th = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 确保土豆是前景
    if th.mean() > 127:
        th = 255 - th
    
    # 形态学操作去除噪点并填充空洞
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)
    
    # 查找轮廓
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    potatoes = []
    img_area = image.shape[0] * image.shape[1]
    
    for cnt in cnts:
        area = cv2.contourArea(cnt)
        
        # 过滤条件：
        # 1. 太小（噪点）
        # 2. 太大（整张图背景）
        # 3. 太扁（边缘噪声）
        if area < 100000:  # 最小面积阈值
            continue
        if area > img_area * 0.8:  # 排除占满整张图的大框
            continue
        
        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = max(w, h) / (min(w, h) + 1e-6)
        if aspect_ratio > 5:  # 排除太扁的区域
            continue
        
        # 计算最小外接旋转矩形
        rect = cv2.minAreaRect(cnt)
        
        potatoes.append({
            "bbox": [x, y, w, h],
            "area": float(area),
            "contour": cnt,
            "rotated_rect": rect
        })
    
    return potatoes


def process_image_with_obb(
    image_path: str,
    model: YOLO,
    rules: Dict[str, Any],
    id_gen: PotatoIDGenerator,
    out_dir: Path,
    conf: float = 0.25,
    save_viz: bool = True
):
    """处理单张图片，为每个土豆个体分配唯一ID"""
    img = cv2.imread(image_path)
    if img is None:
        return []
    
    # 1. 先分割出每个土豆个体
    potatoes = extract_individual_potatoes(img)
    
    if not potatoes:
        print(f"  警告: 未检测到土豆个体")
        return []
    
    # 2. 运行YOLO检测所有缺陷
    results = model.predict(task='obb', source=image_path, imgsz=640, conf=conf, save=False, device='cpu', verbose=False)
    
    all_defects = []
    if results and len(results) > 0:
        r = results[0]
        if getattr(r, 'obb', None) is not None:
            names = r.names
            obb_data = r.obb
            
            clses = obb_data.cls.cpu().numpy()
            confs = obb_data.conf.cpu().numpy()
            xyxyxyxy = obb_data.xyxyxyxy.cpu().numpy()
            xywhr = obb_data.xywhr.cpu().numpy()
            
            for cls_id, conf_val, points, xywhr_val in zip(clses, confs, xyxyxyxy, xywhr):
                if conf_val < conf:
                    continue
                
                class_name = names[int(cls_id)]
                area = cv2.contourArea(points.reshape((-1, 2)).astype(np.int32))
                
                # 计算缺陷中心点
                cx, cy = xywhr_val[0], xywhr_val[1]
                
                all_defects.append({
                    "class": class_name,
                    "confidence": float(conf_val),
                    "center": (cx, cy),
                    "obb": {
                        "xyxyxyxy": points.tolist(),
                        "xywhr": xywhr_val.tolist(),
                        "area": float(area)
                    }
                })
    
    # 3. 为每个土豆个体分配ID，并关联其缺陷
    potato_records = []
    img_viz = img.copy() if save_viz else None
    
    for potato_info in potatoes:
        potato_id = id_gen.generate()
        bbox = potato_info["bbox"]
        x, y, w, h = bbox
        
        # 找出属于这个土豆的所有缺陷
        potato_defects = []
        potato_counts = defaultdict(int)
        
        for defect in all_defects:
            cx, cy = defect["center"]
            # 判断缺陷中心是否在土豆bbox内
            if x <= cx <= x+w and y <= cy <= y+h:
                potato_defects.append({
                    "class": defect["class"],
                    "confidence": defect["confidence"],
                    "obb": defect["obb"]
                })
                potato_counts[defect["class"]] += 1
                
                # 绘制缺陷OBB
                if img_viz is not None:
                    class_name = defect["class"]
                    if class_name == "OK":
                        color = (0, 255, 0)
                    elif class_name in ["deformities", "pits", "greenish_spots"]:
                        color = (0, 0, 255)
                    else:
                        color = (0, 165, 255)
                    
                    points = np.array(defect["obb"]["xyxyxyxy"])
                    img_viz = draw_obb_box(img_viz, points, class_name, color)
        
        # 分级
        if is_potato_ok(dict(potato_counts), rules):
            size_bin = estimate_size_from_area(potato_info["area"], rules)
            grade = f"OK_S{size_bin}"
        else:
            grade = "NG"
        
        signal_bits = to_signal_bits(grade, rules)
        lane = rules["signals"]["mapping"].get(grade, {}).get("lane", 0)
        
        potato_record = {
            "potato_id": potato_id,
            "image": image_path,
            "bbox": bbox,
            "area": potato_info["area"],
            "total_defects": len(potato_defects),
            "defect_counts": dict(potato_counts),
            "grade": grade,
            "signal": {
                "bits": signal_bits,
                "bit_order": rules["signals"]["bit_order"],
                "lane": lane
            },
            "defects": potato_defects
        }
        potato_records.append(potato_record)
        
        # 在图片上标注每个土豆
        if img_viz is not None:
            # 绘制土豆边框
            grade_color = (0, 255, 0) if grade.startswith("OK") else (0, 0, 255)
            cv2.rectangle(img_viz, (x, y), (x+w, y+h), grade_color, 3)
            
            # 标注土豆ID和分级
            label = f"ID:{potato_id} {grade} L{lane}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.0
            thickness = 2
            
            (label_w, label_h), _ = cv2.getTextSize(label, font, font_scale, thickness)
            cv2.rectangle(img_viz, (x, y-label_h-15), (x+label_w+10, y), grade_color, -1)
            cv2.putText(img_viz, label, (x+5, y-8), font, font_scale, (255, 255, 255), thickness)
    
    # 保存可视化
    if save_viz and img_viz is not None:
        viz_dir = out_dir / "visualizations"
        viz_dir.mkdir(exist_ok=True)
        
        # 在图片顶部显示总计信息
        info_text = f"Image: {Path(image_path).stem} | Total Potatoes: {len(potato_records)}"
        cv2.putText(img_viz, info_text, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 3)
        
        viz_path = viz_dir / f"{Path(image_path).stem}_labeled.jpg"
        cv2.imwrite(str(viz_path), img_viz)
    
    return potato_records


def main():
    parser = argparse.ArgumentParser(description="基于YOLO OBB检测为每个缺陷分配ID并分级")
    parser.add_argument("--model", required=True, help="训练好的模型权重")
    parser.add_argument("--source", required=True, help="图片或目录")
    parser.add_argument("--rules", default="/tmp/potato_inspection_system/config/grading_rules.json")
    parser.add_argument("--out", default="/tmp/potato_inspection_system/results/obb_grading")
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
        images = sorted([str(p) for p in source_path.rglob("*") if p.suffix.lower() in {'.jpg', '.jpeg', '.png'}])
    
    all_potatoes = []
    
    for img_path in images:
        print(f"处理: {Path(img_path).name}")
        potato_records = process_image_with_obb(
            img_path, model, rules, id_gen, out_dir, args.conf, not args.no_viz
        )
        
        if potato_records:
            all_potatoes.extend(potato_records)
            for rec in potato_records:
                print(f"  └─ ID:{rec['potato_id']} | {rec['grade']} | 缺陷:{rec['total_defects']}个")
    
    # 保存土豆记录（每个土豆一行）
    potatoes_jsonl = out_dir / "potatoes.jsonl"
    potatoes_csv = out_dir / "potatoes.csv"
    
    with open(potatoes_jsonl, 'w', encoding='utf-8') as jf, \
         open(potatoes_csv, 'w', newline='', encoding='utf-8') as cf:
        
        csv_writer = csv.writer(cf)
        csv_writer.writerow(["potato_id", "image", "bbox_json", "area", "grade", "signal_bits", "lane", "total_defects", "defect_counts_json", "defects_json"])
        
        for potato in all_potatoes:
            jf.write(json.dumps(potato, ensure_ascii=False) + "\n")
            csv_writer.writerow([
                potato["potato_id"],
                potato["image"],
                json.dumps(potato["bbox"]),
                potato["area"],
                potato["grade"],
                ''.join(map(str, potato["signal"]["bits"])),
                potato["signal"]["lane"],
                potato["total_defects"],
                json.dumps(potato["defect_counts"], ensure_ascii=False),
                json.dumps(potato["defects"], ensure_ascii=False)
            ])
    
    print(f"\n{'='*60}")
    print(f"处理完成!")
    print(f"{'='*60}")
    print(f"  处理土豆: {len(all_potatoes)} 个")
    print(f"  总缺陷数: {sum(p['total_defects'] for p in all_potatoes)} 个")
    print(f"  输出:")
    print(f"    - 土豆记录JSONL: {potatoes_jsonl}")
    print(f"    - 土豆记录CSV: {potatoes_csv}")
    if not args.no_viz:
        print(f"    - 可视化: {out_dir / 'visualizations'}/")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()

