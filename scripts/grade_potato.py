#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List, Any
from ultralytics import YOLO
import cv2
import csv
import time


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
        # bits as defined directly
        custom = mapping[grade].get("bits")
        if custom:
            return custom
    # fallback: one-hot in bit_order
    if grade in bit_order:
        bits[bit_order.index(grade)] = 1
    return bits


def estimate_size_bin_from_img(img, rules: Dict[str, Any]) -> int:
    # Returns 1..7 using contour area thresholds
    cfg = rules.get("size", {})
    thresholds = cfg.get("thresholds_px", [])
    if not thresholds:
        return 1
    if img is None:
        return 1
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Simple background separation via Otsu
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    # Ensure potato is foreground (invert if necessary)
    if th.mean() > 127:
        th = 255 - th
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        area = 0
    else:
        area = max(cv2.contourArea(c) for c in cnts)
    # Map to bin
    for idx, t in enumerate(thresholds, start=1):
        if area < t:
            return idx
    return 7


def estimate_size_bin(image_path: str, rules: Dict[str, Any]) -> int:
    img = cv2.imread(image_path)
    return estimate_size_bin_from_img(img, rules)


def run_infer_and_grade(
    model_path: str,
    source: str,
    rules_path: str,
    out_dir: str,
    conf: float = 0.25,
    plc_method: str = None,
    plc_kwargs: Dict[str, Any] = None,
):
    rules = load_rules(Path(rules_path))
    model = YOLO(model_path)
    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)

    # Check if source is video or image/dir
    source_path = Path(source)
    is_video = (source_path.suffix.lower() in {'.mp4', '.avi', '.mov', '.mkv', '.flv'} or 
                (isinstance(source, str) and source.isdigit()) or '://' in source)

    jsonl_path = out_dir_p / 'grades.jsonl'
    csv_path = out_dir_p / 'grades.csv'

    # Import PLC output if needed
    plc_sender = None
    if plc_method:
        try:
            from plc_output import send_to_plc
            plc_sender = send_to_plc
        except ImportError:
            print("警告: PLC输出模块未找到，跳过实时发送")

    if is_video:
        # Video stream mode
        cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
        frame_idx = 0
        with open(jsonl_path, 'w', encoding='utf-8') as jf, open(csv_path, 'w', newline='', encoding='utf-8') as cf:
            csv_writer = csv.writer(cf)
            csv_writer.writerow(["frame", "grade", "signal_bits", "counts_per_class_json", "timestamp"])
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                # Run inference on frame
                results = model.predict(task='obb', source=frame, imgsz=640, conf=conf, save=False, device='cpu', verbose=False)
                if not results:
                    continue
                r = results[0]
                counts: Dict[str, int] = {}
                names = r.names
                if getattr(r, 'obb', None) is not None:
                    clses = r.obb.cls.cpu().numpy().tolist()
                    confs = r.obb.conf.cpu().numpy().tolist()
                    for ci, cfv in zip(clses, confs):
                        name = names[int(ci)]
                        if cfv >= conf:
                            counts[name] = counts.get(name, 0) + 1
                if is_ok(counts, rules):
                    size_bin = estimate_size_bin_from_img(frame, rules)
                    grade = f"OK_S{size_bin}"
                else:
                    grade = "NG"
                signal_bits = to_signal_bits(grade, rules)
                record = {
                    "frame": frame_idx,
                    "counts": counts,
                    "grade": grade,
                    "signal": {
                        "bits": signal_bits,
                        "bit_order": rules["signals"]["bit_order"],
                        "lane": rules["signals"]["mapping"].get(grade, {}).get("lane")
                    },
                    "timestamp": time.time()
                }
                jf.write(json.dumps(record, ensure_ascii=False) + "\n")
                csv_writer.writerow([frame_idx, grade, ''.join(map(str, signal_bits)), json.dumps(counts, ensure_ascii=False), record["timestamp"]])
                if plc_sender and plc_kwargs:
                    plc_sender(grade, signal_bits, plc_method, **plc_kwargs)
                frame_idx += 1
                if frame_idx % 10 == 0:
                    print(f"处理 {frame_idx} 帧...")
        cap.release()
    else:
        # Image/directory mode
        results = model.predict(task='obb', source=source, imgsz=640, conf=conf, save=False, device='cpu')
        with open(jsonl_path, 'w', encoding='utf-8') as jf, open(csv_path, 'w', newline='', encoding='utf-8') as cf:
            csv_writer = csv.writer(cf)
            csv_writer.writerow(["image", "grade", "signal_bits", "counts_per_class_json"]) 

            for r in results:
                image_path = str(r.path)
                counts: Dict[str, int] = {}
                names = r.names
                if getattr(r, 'obb', None) is not None:
                    clses = r.obb.cls.cpu().numpy().tolist()
                    confs = r.obb.conf.cpu().numpy().tolist()
                    for ci, cfv in zip(clses, confs):
                        name = names[int(ci)]
                        if cfv >= conf:
                            counts[name] = counts.get(name, 0) + 1
                if is_ok(counts, rules):
                    size_bin = estimate_size_bin(image_path, rules)
                    grade = f"OK_S{size_bin}"
                else:
                    grade = "NG"
                signal_bits = to_signal_bits(grade, rules)
                record = {
                    "image": image_path,
                    "counts": counts,
                    "grade": grade,
                    "signal": {
                        "bits": signal_bits,
                        "bit_order": rules["signals"]["bit_order"],
                        "lane": rules["signals"]["mapping"].get(grade, {}).get("lane")
                    }
                }
                jf.write(json.dumps(record, ensure_ascii=False) + "\n")
                csv_writer.writerow([image_path, grade, ''.join(map(str, signal_bits)), json.dumps(counts, ensure_ascii=False)])
                if plc_sender and plc_kwargs:
                    plc_sender(grade, signal_bits, plc_method, **plc_kwargs)

    print(f"Wrote {jsonl_path} and {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Run YOLOv8-OBB inference and output potato grades and signals")
    parser.add_argument("--model", required=True, help="path to trained weights .pt")
    parser.add_argument("--source", required=True, help="image, directory, video file, or camera index (e.g., 0)")
    parser.add_argument("--rules", default="/tmp/potato_inspection_system/config/grading_rules.json")
    parser.add_argument("--out", default="/tmp/potato_inspection_system/results/grades")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--plc", choices=["print", "modbus", "serial"], help="PLC输出方式")
    parser.add_argument("--modbus_host", default="192.168.1.100")
    parser.add_argument("--modbus_port", type=int, default=502)
    parser.add_argument("--modbus_address", type=int, default=0)
    parser.add_argument("--serial_port", default="/dev/ttyUSB0")
    parser.add_argument("--serial_baud", type=int, default=9600)
    args = parser.parse_args()
    
    plc_kwargs = {}
    if args.plc == "modbus":
        plc_kwargs = {"host": args.modbus_host, "port": args.modbus_port, "address": args.modbus_address}
    elif args.plc == "serial":
        plc_kwargs = {"port": args.serial_port, "baudrate": args.serial_baud}
    
    run_infer_and_grade(args.model, args.source, args.rules, args.out, args.conf, args.plc, plc_kwargs)


if __name__ == '__main__':
    main()


