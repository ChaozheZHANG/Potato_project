#!/usr/bin/env python3
"""
离线检测示例代码
"""
import sys
from pathlib import Path

# 添加脚本路径
DEPLOY_DIR = Path(__file__).parent
sys.path.insert(0, str(DEPLOY_DIR / "scripts"))

from grade_with_potato_label import *
import json

def detect_potatoes(image_path, output_dir="results/example"):
    """检测单张或多张图片中的土豆"""
    
    # 配置
    MODEL_PATH = DEPLOY_DIR / "models/yolov8s-obb-potato-v22_best.pt"
    RULES_PATH = DEPLOY_DIR / "config/grading_rules.json"
    
    # 加载模型和规则
    print("加载模型...")
    model = YOLO(str(MODEL_PATH))
    rules = load_rules(RULES_PATH)
    id_gen = PotatoIDGenerator()
    
    # 输出目录
    out_dir = DEPLOY_DIR / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 处理图片
    print(f"处理: {image_path}")
    results = process_image_with_potato_detection(
        str(image_path),
        model,
        rules,
        id_gen,
        out_dir,
        conf=0.25,
        save_viz=True
    )
    
    # 输出结果
    print(f"\n检测到 {len(results)} 个土豆:")
    for potato in results:
        print(f"  ID: {potato['potato_id']}")
        print(f"    分级: {potato['grade']}")
        print(f"    通道: Lane {potato['signal']['lane']}")
        print(f"    信号: {''.join(map(str, potato['signal']['bits']))}")
        print(f"    缺陷: {potato['defect_counts']}")
        print()
    
    # 保存结果
    output_file = out_dir / "result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"结果已保存: {output_file}")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 example_detect.py <图片路径>")
        print("示例: python3 example_detect.py test_images/potato.jpg")
        sys.exit(1)
    
    detect_potatoes(sys.argv[1])
