# 马铃薯分级系统 - 离线部署完整指南

**目标**: 在离线工控机/边缘计算卡上部署系统  
**适用**: 无网络环境的产线现场

---

## 📦 部署包清单

### 必需文件
```
potato_inspection_system/
├── models/
│   └── yolov8s-obb-potato-v22_best.pt  (23MB)
├── scripts/
│   └── grade_with_potato_label.py
├── config/
│   └── grading_rules.json
├── requirements.txt
├── deploy.sh
└── README_OFFLINE.md
```

### 可选文件
- 测试图片（用于验证部署）
- PLC对接脚本（如需）

---

## 🚀 快速部署步骤

### 步骤1: 准备部署包（在有网络的机器上）

```bash
# 1. 创建部署目录
mkdir -p potato_deploy
cd potato_deploy

# 2. 复制模型
mkdir -p models
cp /tmp/potato_inspection_system/runs/yolov8s-obb-potato-v22/weights/best.pt \
   models/yolov8s-obb-potato-v22_best.pt

# 3. 复制脚本
mkdir -p scripts
cp /tmp/potato_inspection_system/scripts/grade_with_potato_label.py scripts/

# 4. 复制配置
mkdir -p config
cp /tmp/potato_inspection_system/config/grading_rules.json config/

# 5. 创建requirements.txt
cat > requirements.txt << 'EOF'
ultralytics==8.3.222
opencv-python==4.10.0.84
numpy>=1.24.0
Pillow>=10.0.0
EOF

# 6. 打包
cd ..
tar -czf potato_deploy.tar.gz potato_deploy/
```

### 步骤2: 传输到离线机器

```bash
# 使用U盘、SCP或其他方式传输 potato_deploy.tar.gz
# 假设传输到离线机器的 /opt/ 目录
```

### 步骤3: 离线机器部署

```bash
# 1. 解压
cd /opt
tar -xzf potato_deploy.tar.gz
cd potato_deploy

# 2. 安装Python依赖（需提前准备离线pip包）
# 方式A: 如果有离线pip源
pip install -r requirements.txt --no-index --find-links=/path/to/offline/packages

# 方式B: 使用whl文件
pip install ultralytics-8.3.222-py3-none-any.whl
pip install opencv_python-4.10.0.84-cp312-cp312-linux_x86_64.whl
```

---

## 💻 示例代码

### 1. 单张图片检测
```python
#!/usr/bin/env python3
# detect_single.py
import sys
sys.path.insert(0, '/opt/potato_deploy/scripts')

from grade_with_potato_label import *
from pathlib import Path

# 配置
MODEL_PATH = "/opt/potato_deploy/models/yolov8s-obb-potato-v22_best.pt"
RULES_PATH = "/opt/potato_deploy/config/grading_rules.json"
IMAGE_PATH = "/path/to/potato.jpg"
OUTPUT_DIR = "/opt/potato_deploy/results"

# 加载
model = YOLO(MODEL_PATH)
rules = load_rules(Path(RULES_PATH))
id_gen = PotatoIDGenerator()

# 处理
out_dir = Path(OUTPUT_DIR)
out_dir.mkdir(parents=True, exist_ok=True)

results = process_image_with_potato_detection(
    IMAGE_PATH, model, rules, id_gen, out_dir, conf=0.25, save_viz=True
)

# 输出
for potato in results:
    print(f"ID: {potato['potato_id']}")
    print(f"  分级: {potato['grade']}")
    print(f"  通道: Lane {potato['signal']['lane']}")
    print(f"  缺陷: {potato['defect_counts']}")
    print()
```

### 2. 批量检测
```python
#!/usr/bin/env python3
# detect_batch.py
import sys
sys.path.insert(0, '/opt/potato_deploy/scripts')

from grade_with_potato_label import *
from pathlib import Path
import json

MODEL_PATH = "/opt/potato_deploy/models/yolov8s-obb-potato-v22_best.pt"
RULES_PATH = "/opt/potato_deploy/config/grading_rules.json"
IMAGE_DIR = "/path/to/images"
OUTPUT_DIR = "/opt/potato_deploy/results/batch"

model = YOLO(MODEL_PATH)
rules = load_rules(Path(RULES_PATH))
id_gen = PotatoIDGenerator()
out_dir = Path(OUTPUT_DIR)
out_dir.mkdir(parents=True, exist_ok=True)

# 收集图片
images = sorted(Path(IMAGE_DIR).glob("*.jpg"))
all_potatoes = []

for img_path in images:
    print(f"处理: {img_path.name}")
    results = process_image_with_potato_detection(
        str(img_path), model, rules, id_gen, out_dir, conf=0.25, save_viz=True
    )
    all_potatoes.extend(results)
    for p in results:
        print(f"  └─ {p['potato_id']}: {p['grade']} Lane{p['signal']['lane']}")

# 保存汇总
with open(out_dir / "summary.jsonl", 'w') as f:
    for p in all_potatoes:
        f.write(json.dumps(p, ensure_ascii=False) + "\n")

print(f"\n总计: {len(all_potatoes)}个土豆")
```

### 3. 实时摄像头检测
```python
#!/usr/bin/env python3
# detect_realtime.py
import sys
sys.path.insert(0, '/opt/potato_deploy/scripts')

from grade_potato_realtime import *
from pathlib import Path

MODEL_PATH = "/opt/potato_deploy/models/yolov8s-obb-potato-v22_best.pt"
RULES_PATH = "/opt/potato_deploy/config/grading_rules.json"
CAMERA_ID = 0  # 摄像头编号
OUTPUT_DIR = "/opt/potato_deploy/results/realtime"

model = YOLO(MODEL_PATH)
rules = load_rules(Path(RULES_PATH))
out_dir = Path(OUTPUT_DIR)
out_dir.mkdir(parents=True, exist_ok=True)

# 运行实时检测
process_video_stream(
    source=CAMERA_ID,
    model=model,
    rules=rules,
    out_dir=out_dir,
    conf=0.25,
    display=True  # 设为False则无窗口模式
)
```

### 4. 命令行调用
```bash
#!/bin/bash
# detect.sh

MODEL="/opt/potato_deploy/models/yolov8s-obb-potato-v22_best.pt"
RULES="/opt/potato_deploy/config/grading_rules.json"

# 批量检测
python3 /opt/potato_deploy/scripts/grade_with_potato_label.py \
    --model "$MODEL" \
    --source /path/to/images \
    --rules "$RULES" \
    --out /opt/potato_deploy/results/output \
    --conf 0.25

echo "检测完成，结果保存在 /opt/potato_deploy/results/output/"
```

---

## 🔧 自动化部署脚本

### deploy.sh（一键部署）
```bash
#!/bin/bash
# deploy.sh - 自动部署脚本

set -e

DEPLOY_DIR="/opt/potato_deploy"
VENV_DIR="$DEPLOY_DIR/venv"

echo "========================================="
echo "马铃薯分级系统 - 自动部署"
echo "========================================="

# 1. 创建虚拟环境
echo "[1/5] 创建Python虚拟环境..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# 2. 安装依赖
echo "[2/5] 安装依赖包..."
pip install -r "$DEPLOY_DIR/requirements.txt" --no-cache-dir

# 3. 验证模型文件
echo "[3/5] 验证模型文件..."
if [ ! -f "$DEPLOY_DIR/models/yolov8s-obb-potato-v22_best.pt" ]; then
    echo "错误: 模型文件不存在！"
    exit 1
fi

# 4. 创建输出目录
echo "[4/5] 创建输出目录..."
mkdir -p "$DEPLOY_DIR/results"

# 5. 运行测试
echo "[5/5] 运行测试检测..."
if [ -d "$DEPLOY_DIR/test_images" ]; then
    python3 "$DEPLOY_DIR/scripts/grade_with_potato_label.py" \
        --model "$DEPLOY_DIR/models/yolov8s-obb-potato-v22_best.pt" \
        --source "$DEPLOY_DIR/test_images" \
        --out "$DEPLOY_DIR/results/test" \
        --conf 0.25
    echo "测试完成！查看 $DEPLOY_DIR/results/test/"
else
    echo "跳过测试（无test_images目录）"
fi

echo ""
echo "========================================="
echo "部署完成！"
echo "========================================="
echo "模型路径: $DEPLOY_DIR/models/yolov8s-obb-potato-v22_best.pt"
echo "脚本路径: $DEPLOY_DIR/scripts/"
echo "配置文件: $DEPLOY_DIR/config/grading_rules.json"
echo ""
echo "使用示例:"
echo "  source $VENV_DIR/bin/activate"
echo "  python3 scripts/grade_with_potato_label.py --model models/yolov8s-obb-potato-v22_best.pt --source 图片目录"
echo ""
```

---

## 📝 完整部署包创建脚本

### create_deploy_package.sh
```bash
#!/bin/bash
# 在开发机器上运行，创建完整部署包

PACKAGE_NAME="potato_inspection_offline_v4"
PACKAGE_DIR="/tmp/$PACKAGE_NAME"

echo "创建部署包: $PACKAGE_NAME"

# 1. 创建目录结构
mkdir -p "$PACKAGE_DIR"/{models,scripts,config,docs,test_images}

# 2. 复制模型
echo "复制模型..."
cp /tmp/potato_inspection_system/runs/yolov8s-obb-potato-v22/weights/best.pt \
   "$PACKAGE_DIR/models/yolov8s-obb-potato-v22_best.pt"

# 3. 复制脚本
echo "复制脚本..."
cp /tmp/potato_inspection_system/scripts/grade_with_potato_label.py "$PACKAGE_DIR/scripts/"
cp /tmp/potato_inspection_system/scripts/grade_potato_realtime.py "$PACKAGE_DIR/scripts/"

# 4. 复制配置
echo "复制配置..."
cp /tmp/potato_inspection_system/config/grading_rules.json "$PACKAGE_DIR/config/"

# 5. 复制文档
echo "复制文档..."
cp /tmp/potato_inspection_system/docs/SENSOR_TEAM_QUICK_GUIDE.md "$PACKAGE_DIR/docs/"
cp /tmp/potato_inspection_system/docs/OUTPUT_FORMAT_FINAL.md "$PACKAGE_DIR/docs/"
cp /tmp/potato_inspection_system/OFFLINE_DEPLOYMENT_GUIDE.md "$PACKAGE_DIR/"

# 6. 创建requirements.txt
cat > "$PACKAGE_DIR/requirements.txt" << 'EOF'
ultralytics==8.3.222
opencv-python==4.10.0.84
numpy>=1.24.0
Pillow>=10.0.0
torch>=2.0.0
torchvision>=0.15.0
EOF

# 7. 创建部署脚本
cat > "$PACKAGE_DIR/deploy.sh" << 'DEPLOY_SCRIPT'
#!/bin/bash
set -e

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$DEPLOY_DIR/venv"

echo "========================================="
echo "马铃薯分级系统 - 自动部署"
echo "========================================="

# 创建虚拟环境
echo "[1/4] 创建Python虚拟环境..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# 安装依赖
echo "[2/4] 安装依赖..."
pip install -r "$DEPLOY_DIR/requirements.txt"

# 创建输出目录
echo "[3/4] 创建输出目录..."
mkdir -p "$DEPLOY_DIR/results"

# 测试
echo "[4/4] 测试检测..."
if [ -d "$DEPLOY_DIR/test_images" ] && [ "$(ls -A $DEPLOY_DIR/test_images)" ]; then
    python3 "$DEPLOY_DIR/scripts/grade_with_potato_label.py" \
        --model "$DEPLOY_DIR/models/yolov8s-obb-potato-v22_best.pt" \
        --source "$DEPLOY_DIR/test_images" \
        --out "$DEPLOY_DIR/results/test" \
        --conf 0.25
    echo "测试完成！查看 results/test/"
fi

echo ""
echo "========================================="
echo "部署完成！"
echo "========================================="
echo ""
echo "使用方法:"
echo "  1. 激活环境: source $VENV_DIR/bin/activate"
echo "  2. 运行检测: python3 scripts/grade_with_potato_label.py --model models/yolov8s-obb-potato-v22_best.pt --source 图片目录"
echo ""
DEPLOY_SCRIPT

chmod +x "$PACKAGE_DIR/deploy.sh"

# 8. 创建快速使用脚本
cat > "$PACKAGE_DIR/detect.sh" << 'DETECT_SCRIPT'
#!/bin/bash
# 快速检测脚本

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"

MODEL="$SCRIPT_DIR/models/yolov8s-obb-potato-v22_best.pt"
RULES="$SCRIPT_DIR/config/grading_rules.json"
OUTPUT="$SCRIPT_DIR/results/$(date +%Y%m%d_%H%M%S)"

if [ -z "$1" ]; then
    echo "用法: ./detect.sh <图片目录或图片路径>"
    echo "示例: ./detect.sh /path/to/images"
    exit 1
fi

python3 "$SCRIPT_DIR/scripts/grade_with_potato_label.py" \
    --model "$MODEL" \
    --source "$1" \
    --rules "$RULES" \
    --out "$OUTPUT" \
    --conf 0.25

echo ""
echo "检测完成！结果保存在: $OUTPUT"
echo "  - CSV: $OUTPUT/potatoes.csv"
echo "  - JSONL: $OUTPUT/potatoes.jsonl"
echo "  - 可视化: $OUTPUT/visualizations/"
DETECT_SCRIPT

chmod +x "$PACKAGE_DIR/detect.sh"

# 9. 创建README
cat > "$PACKAGE_DIR/README_OFFLINE.md" << 'README'
# 马铃薯分级系统 - 离线版使用说明

## 快速开始

### 1. 部署（首次）
```bash
cd /opt/potato_deploy
./deploy.sh
```

### 2. 检测图片
```bash
./detect.sh /path/to/images
```

### 3. 查看结果
```bash
# CSV文件
cat results/最新时间戳/potatoes.csv

# 可视化图片
ls results/最新时间戳/visualizations/
```

## 输出格式

### CSV格式
```csv
potato_id,grade,signal_bits,lane
2025110513591101,OK_S7,00000010,7
2025110513591104,NG,00000001,8
```

### 字段说明
- potato_id: 16位唯一ID（年月日时分秒+01-60）
- grade: OK_S1-S7 或 NG
- signal_bits: 8位二进制
- lane: 物理通道1-8

## 高级用法

### Python调用
```python
from grade_with_potato_label import *

model = YOLO("models/yolov8s-obb-potato-v22_best.pt")
rules = load_rules(Path("config/grading_rules.json"))
id_gen = PotatoIDGenerator()

results = process_image_with_potato_detection(
    "image.jpg", model, rules, id_gen, 
    Path("results"), conf=0.25
)

for potato in results:
    print(f"{potato['potato_id']} → Lane {potato['signal']['lane']}")
```

### 调整参数
- 置信度: `--conf 0.3` (默认0.25)
- 不保存图片: `--no-viz`

## 故障排查

### 问题1: 模型加载失败
- 检查模型文件是否存在
- 检查ultralytics是否安装

### 问题2: 检测不到土豆
- 降低置信度: `--conf 0.2`
- 检查图片质量

### 问题3: 依赖安装失败
- 使用离线whl包
- 检查Python版本（需>=3.8）

## 联系支持
查看 docs/ 目录获取完整文档。
README

# 10. 复制测试图片（可选）
if [ -d "/tmp/potato_inspection_system/data/test/project-3-at-2025-11-04-13-44-8dae778d_new/images/test" ]; then
    echo "复制测试图片..."
    cp /tmp/potato_inspection_system/data/test/project-3-at-2025-11-04-13-44-8dae778d_new/images/test/*.jpeg \
       "$PACKAGE_DIR/test_images/" 2>/dev/null || true
fi

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
echo "传输到离线机器后："
echo "  1. tar -xzf ${PACKAGE_NAME}.tar.gz"
echo "  2. cd ${PACKAGE_NAME}"
echo "  3. ./deploy.sh"
echo "  4. ./detect.sh 图片目录"
echo ""
```

---

## 📋 离线pip包准备

### 在有网络的机器上下载
```bash
# 创建离线包目录
mkdir -p offline_packages
cd offline_packages

# 下载所有依赖
pip download ultralytics==8.3.222
pip download opencv-python==4.10.0.84
pip download numpy
pip download Pillow
pip download torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 打包
cd ..
tar -czf offline_pip_packages.tar.gz offline_packages/
```

### 在离线机器上安装
```bash
tar -xzf offline_pip_packages.tar.gz
pip install --no-index --find-links=offline_packages/ -r requirements.txt
```

---

## 🎯 完整部署流程示例

### 在开发机（有网络）
```bash
# 1. 创建部署包
bash create_deploy_package.sh

# 2. 下载离线pip包
mkdir offline_packages && cd offline_packages
pip download ultralytics opencv-python numpy Pillow torch torchvision
cd .. && tar -czf offline_packages.tar.gz offline_packages/

# 3. 传输文件
# - potato_inspection_offline_v4.tar.gz
# - offline_packages.tar.gz
```

### 在离线机（无网络）
```bash
# 1. 解压部署包
tar -xzf potato_inspection_offline_v4.tar.gz
cd potato_inspection_offline_v4

# 2. 解压pip包
tar -xzf ../offline_packages.tar.gz

# 3. 创建虚拟环境并安装
python3 -m venv venv
source venv/bin/activate
pip install --no-index --find-links=offline_packages/ -r requirements.txt

# 4. 运行检测
./detect.sh test_images/

# 5. 查看结果
cat results/*/potatoes.csv
```

---

## 📊 输出示例

运行后会生成：
```
results/20251105_135911/
├── potatoes.jsonl          # 每个土豆一行
├── potatoes.csv            # CSV格式
└── visualizations/         # 带标注的图片
    ├── img1_labeled.jpg
    └── img2_labeled.jpg
```

---

**部署指南结束** - 系统可完全离线运行！

