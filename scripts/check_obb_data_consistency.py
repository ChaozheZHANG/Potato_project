#!/usr/bin/env python3
from pathlib import Path
import argparse

def check_consistency(data_root):
    images_dir = Path(data_root) / "images"
    labels_dir = Path(data_root) / "labels"
    report = []
    # 1. Image-label pair check
    images = sorted([p for p in images_dir.glob("*.*") if p.suffix.lower() in {'.jpg', '.jpeg', '.png'}])
    labels = sorted([p for p in labels_dir.glob("*.txt")])
    image_stems = {p.stem for p in images}
    label_stems = {p.stem for p in labels}
    missing_labels = image_stems - label_stems
    missing_images = label_stems - image_stems
    if missing_labels:
        report.append(f"有 {len(missing_labels)} 张图片没有匹配标签: {sorted(missing_labels)}")
    if missing_images:
        report.append(f"有 {len(missing_images)} 个标签没有匹配图片: {sorted(missing_images)}")

    # 2. Check for empty-label files (no valid OBB annotation lines)
    empty_labels = []
    for lbl in labels:
        content = lbl.read_text().strip()
        if not content or all(line.strip() == '' for line in content.splitlines()):
            empty_labels.append(lbl.name)
    if empty_labels:
        report.append(f"有 {len(empty_labels)} 个标签文件是空的: {sorted(empty_labels)}")
    
    # 3. Report summary
    if not report:
        report.append("数据一致性良好，无缺失和空标签。")
    print("\n".join(report))

def main():
    parser = argparse.ArgumentParser(description="检查YOLO OBB数据集 图片/标签一致性与空文件.")
    parser.add_argument("data_root", help="数据集根目录，需包含 images/ labels/")
    args = parser.parse_args()
    check_consistency(args.data_root)

if __name__ == '__main__':
    main()
