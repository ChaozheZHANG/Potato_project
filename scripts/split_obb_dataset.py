#!/usr/bin/env python3
import argparse
from pathlib import Path
import random
import shutil


def find_pairs(images_dir: Path, labels_dir: Path):
    image_paths = sorted([p for p in images_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}])
    pairs = []
    for img in image_paths:
        lbl = labels_dir / (img.stem + ".txt")
        if lbl.exists():
            pairs.append((img, lbl))
    return pairs


def split_dataset(root: Path, train_ratio: float = 0.9, val_ratio: float = 0.1, test_ratio: float = 0.0, seed: int = 42):
    images_dir = root / "images"
    labels_dir = root / "labels"
    assert images_dir.exists() and labels_dir.exists(), "images/ and labels/ must exist under root"
    pairs = find_pairs(images_dir, labels_dir)
    n = len(pairs)
    assert abs((train_ratio+val_ratio+test_ratio) - 1.0) < 1e-5, 'train+val+test比例之和须等于1'
    random.Random(seed).shuffle(pairs)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    train_pairs = pairs[:n_train]
    val_pairs = pairs[n_train:n_train+n_val]
    test_pairs = pairs[n_train+n_val:]
    # 输出文件夹
    out_dirs = {
        "train_img": images_dir / "train",
        "val_img": images_dir / "val",
        "test_img": images_dir / "test",
        "train_lbl": labels_dir / "train",
        "val_lbl": labels_dir / "val",
        "test_lbl": labels_dir / "test",
    }
    for d in out_dirs.values():
        d.mkdir(exist_ok=True, parents=True)
    def copy_pairs(pairs_list, img_out_dir, lbl_out_dir):
        for img_p, lbl_p in pairs_list:
            shutil.copy2(img_p, img_out_dir / img_p.name)
            shutil.copy2(lbl_p, lbl_out_dir / lbl_p.name)
    copy_pairs(train_pairs, out_dirs["train_img"], out_dirs["train_lbl"])
    copy_pairs(val_pairs, out_dirs["val_img"], out_dirs["val_lbl"])
    copy_pairs(test_pairs, out_dirs["test_img"], out_dirs["test_lbl"])
    return len(train_pairs), len(val_pairs), len(test_pairs)


def main():
    parser = argparse.ArgumentParser(description="Split YOLO OBB dataset into train/val/test.")
    parser.add_argument("root", type=Path, help="Root folder containing images/ and labels/")
    parser.add_argument("--train_ratio", type=float, default=0.9)
    parser.add_argument("--val_ratio", type=float, default=0.05)
    parser.add_argument("--test_ratio", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    n_tr, n_val, n_ts = split_dataset(args.root, args.train_ratio, args.val_ratio, args.test_ratio, args.seed)
    print(f"Split done. train={n_tr}, val={n_val}, test={n_ts}")


if __name__ == "__main__":
    main()


