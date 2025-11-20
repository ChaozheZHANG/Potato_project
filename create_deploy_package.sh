#!/bin/bash
# 创建完整离线部署包

set -e

PACKAGE_NAME="potato_inspection_offline_v4"
PACKAGE_DIR="/tmp/$PACKAGE_NAME"

echo "========================================="
echo "创建部署包: $PACKAGE_NAME"
echo "========================================="

# 1. 创建目录结构
echo "[1/8] 创建目录结构..."
rm -rf "$PACKAGE_DIR"
mkdir -p "$PACKAGE_DIR"/{models,scripts,config,docs,test_images,results}

# 2. 复制模型
echo "[2/8] 复制模型文件..."
cp /tmp/potato_inspection_system/runs/yolov8s-obb-potato-v22/weights/best.pt \
   "$PACKAGE_DIR/models/yolov8s-obb-potato-v22_best.pt"

# 3. 复制脚本
echo "[3/8] 复制检测脚本..."
cp /tmp/potato_inspection_system/scripts/grade_with_potato_label.py "$PACKAGE_DIR/scripts/"
cp /tmp/potato_inspection_system/scripts/grade_potato_realtime.py "$PACKAGE_DIR/scripts/"

# 4. 复制配置
echo "[4/8] 复制配置文件..."
cp /tmp/potato_inspection_system/config/grading_rules.json "$PACKAGE_DIR/config/"

# 5. 复制文档
echo "[5/8] 复制文档..."
cp /tmp/potato_inspection_system/docs/SENSOR_TEAM_QUICK_GUIDE.md "$PACKAGE_DIR/docs/"
cp /tmp/potato_inspection_system/docs/OUTPUT_FORMAT_FINAL.md "$PACKAGE_DIR/docs/"
cp /tmp/potato_inspection_system/OFFLINE_DEPLOYMENT_GUIDE.md "$PACKAGE_DIR/"

# 6. 创建requirements.txt
echo "[6/8] 创建requirements.txt..."
cat > "$PACKAGE_DIR/requirements.txt" << 'EOF'
ultralytics==8.3.222
opencv-python==4.10.0.84
numpy>=1.24.0
Pillow>=10.0.0
EOF

# 7. 创建部署脚本
echo "[7/8] 创建部署脚本..."
cat > "$PACKAGE_DIR/deploy.sh" << 'DEPLOY'
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
DEPLOY

chmod +x "$PACKAGE_DIR/deploy.sh"

# 8. 创建快速检测脚本
cat > "$PACKAGE_DIR/detect.sh" << 'DETECT'
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
DETECT

chmod +x "$PACKAGE_DIR/detect.sh"

# 9. 创建Python示例代码
cat > "$PACKAGE_DIR/example_detect.py" << 'EXAMPLE'
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
EXAMPLE

chmod +x "$PACKAGE_DIR/example_detect.py"

# 10. 复制测试图片
echo "[8/8] 复制测试图片..."
cp /tmp/potato_inspection_system/data/test/project-3-at-2025-11-04-13-44-8dae778d_new/images/test/*.jpeg \
   "$PACKAGE_DIR/test_images/" 2>/dev/null | head -5 || true

# 11. 打包
echo "打包..."
cd /tmp
tar -czf "${PACKAGE_NAME}.tar.gz" "$PACKAGE_NAME/"

echo ""
echo "========================================="
echo "部署包创建完成！"
echo "========================================="
echo "文件: /tmp/${PACKAGE_NAME}.tar.gz"
echo "大小: $(du -h /tmp/${PACKAGE_NAME}.tar.gz | cut -f1)"
echo ""
echo "包含内容:"
echo "  - 模型: yolov8s-obb-potato-v22_best.pt (23MB)"
echo "  - 脚本: grade_with_potato_label.py, grade_potato_realtime.py"
echo "  - 配置: grading_rules.json"
echo "  - 文档: 3份"
echo "  - 测试图片: $(ls $PACKAGE_DIR/test_images/ | wc -l)张"
echo ""
echo "传输到离线机器后："
echo "  tar -xzf ${PACKAGE_NAME}.tar.gz"
echo "  cd ${PACKAGE_NAME}"
echo "  ./deploy.sh"
echo "  ./detect.sh test_images/"
echo ""

