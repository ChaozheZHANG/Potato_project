#!/usr/bin/env python3
"""分析已分级结果的尺寸分布，自动建议7档阈值"""
import argparse
import json
import cv2
import numpy as np
from pathlib import Path
from typing import List


def extract_contour_area(image_path: str) -> float:
    img = cv2.imread(image_path)
    if img is None:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if th.mean() > 127:
        th = 255 - th
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return 0.0
    return max(cv2.contourArea(c) for c in cnts)


def suggest_thresholds(areas: List[float], n_bins: int = 7) -> List[float]:
    areas = sorted([a for a in areas if a > 0])
    if len(areas) < n_bins:
        # 太少样本，用均匀分位
        return np.linspace(areas[0] if areas else 0, areas[-1] if areas else 1, n_bins + 1)[1:].tolist()
    # 使用分位数方法：将分布分为 n_bins 等份
    percentiles = np.linspace(0, 100, n_bins + 1)[1:-1]
    thresholds = [np.percentile(areas, p) for p in percentiles]
    return thresholds


def main():
    parser = argparse.ArgumentParser(description="分析尺寸分布并建议阈值")
    parser.add_argument("--source", required=True, help="图片目录或JSONL结果文件")
    parser.add_argument("--output", default="/tmp/potato_inspection_system/config/suggested_thresholds.json")
    args = parser.parse_args()

    source = Path(args.source)
    areas = []

    if source.suffix == '.jsonl':
        # 从分级结果JSONL读取图片路径
        with open(source, 'r', encoding='utf-8') as f:
            for line in f:
                rec = json.loads(line)
                img_path = rec.get("image")
                if img_path:
                    area = extract_contour_area(img_path)
                    if area > 0:
                        areas.append(area)
    else:
        # 直接扫描图片目录
        for img_file in source.rglob("*"):
            if img_file.suffix.lower() in {'.jpg', '.jpeg', '.png'}:
                area = extract_contour_area(str(img_file))
                if area > 0:
                    areas.append(area)

    if not areas:
        print("未找到有效图片")
        return

    thresholds = suggest_thresholds(areas, n_bins=7)
    result = {
        "suggested_thresholds_px": [int(t) for t in thresholds],
        "statistics": {
            "count": len(areas),
            "min": float(min(areas)),
            "max": float(max(areas)),
            "mean": float(np.mean(areas)),
            "median": float(np.median(areas)),
            "std": float(np.std(areas))
        },
        "note": "请将 suggested_thresholds_px 复制到 grading_rules.json > size.thresholds_px"
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"建议阈值: {result['suggested_thresholds_px']}")
    print(f"统计: 样本数={result['statistics']['count']}, "
          f"范围=[{result['statistics']['min']:.0f}, {result['statistics']['max']:.0f}], "
          f"均值={result['statistics']['mean']:.0f}")
    print(f"已保存到: {out_path}")


if __name__ == '__main__':
    main()

