#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate" 2>/dev/null || {
    echo "错误: 请先运行 ./deploy.sh 进行部署"
    exit 1
}

MODEL="$SCRIPT_DIR/models/yolov8s-obb-potato-v22_best.pt"
RULES="$SCRIPT_DIR/config/grading_rules.json"
OUTPUT="$SCRIPT_DIR/results/$(date +%Y%m%d_%H%M%S)"

if [ -z "$1" ]; then
    echo "用法: ./detect.sh <图片目录或图片路径>"
    echo "示例: ./detect.sh test_images/"
    exit 1
fi

echo "开始检测: $1"
echo "输出目录: $OUTPUT"
echo ""

python3 "$SCRIPT_DIR/scripts/grade_with_potato_label.py" \
    --model "$MODEL" \
    --source "$1" \
    --rules "$RULES" \
    --out "$OUTPUT" \
    --conf "${2:-0.25}"

echo ""
echo "========================================="
echo "检测完成！"
echo "========================================="
echo "结果位置: $OUTPUT"
echo "  - CSV: $OUTPUT/potatoes.csv"
echo "  - JSONL: $OUTPUT/potatoes.jsonl"
echo "  - 可视化: $OUTPUT/visualizations/"
echo ""
