#!/bin/bash
set -e

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$DEPLOY_DIR/venv"

echo "========================================="
echo "马铃薯分级系统 - 自动部署"
echo "========================================="

echo "[1/4] 创建Python虚拟环境..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo "[2/4] 安装依赖..."
pip install -r "$DEPLOY_DIR/requirements.txt"

echo "[3/4] 创建输出目录..."
mkdir -p "$DEPLOY_DIR/results"

echo "[4/4] 验证模型..."
if [ ! -f "$DEPLOY_DIR/models/yolov8s-obb-potato-v22_best.pt" ]; then
    echo "错误: 模型文件不存在！"
    exit 1
fi

echo ""
echo "========================================="
echo "部署完成！"
echo "========================================="
echo ""
echo "使用方法:"
echo "  1. 激活环境: source venv/bin/activate"
echo "  2. 运行检测: ./detect.sh 图片目录"
echo ""
