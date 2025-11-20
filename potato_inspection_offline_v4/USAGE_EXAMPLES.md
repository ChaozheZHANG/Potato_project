# 使用示例代码集合

本文档包含各种使用场景的完整代码示例。

---

## 示例1: 检测单张图片（最简单）

```python
#!/usr/bin/env python3
# example1_single_image.py

import sys
from pathlib import Path

# 添加脚本路径
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from grade_with_potato_label import *

# 配置路径
MODEL = "models/yolov8s-obb-potato-v22_best.pt"
RULES = "config/grading_rules.json"
IMAGE = "test_images/0142ce97-Pic_2025_10_21_154621_149.jpeg"

# 加载
model = YOLO(MODEL)
rules = load_rules(Path(RULES))
id_gen = PotatoIDGenerator()

# 检测
results = process_image_with_potato_detection(
    IMAGE, model, rules, id_gen, 
    Path("results/example1"), 
    conf=0.25, save_viz=True
)

# 输出结果
print(f"检测到 {len(results)} 个土豆:\n")
for potato in results:
    print(f"ID: {potato['potato_id']}")
    print(f"  分级: {potato['grade']}")
    print(f"  通道: Lane {potato['signal']['lane']}")
    print(f"  信号: {''.join(map(str, potato['signal']['bits']))}")
    print(f"  缺陷: {potato['defect_counts']}")
    print()
```

**运行**:
```bash
python3 example1_single_image.py
```

---

## 示例2: 批量检测并生成CSV

```python
#!/usr/bin/env python3
# example2_batch_to_csv.py

import sys
from pathlib import Path
import csv

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from grade_with_potato_label import *

MODEL = "models/yolov8s-obb-potato-v22_best.pt"
RULES = "config/grading_rules.json"
IMAGE_DIR = "test_images"
OUTPUT = "results/batch_output"

# 初始化
model = YOLO(MODEL)
rules = load_rules(Path(RULES))
id_gen = PotatoIDGenerator()
out_dir = Path(OUTPUT)
out_dir.mkdir(parents=True, exist_ok=True)

# 批量处理
images = sorted(Path(IMAGE_DIR).glob("*.jpg")) + sorted(Path(IMAGE_DIR).glob("*.jpeg"))
all_potatoes = []

print(f"开始处理 {len(images)} 张图片...\n")

for img_path in images:
    results = process_image_with_potato_detection(
        str(img_path), model, rules, id_gen, out_dir, conf=0.25, save_viz=True
    )
    all_potatoes.extend(results)
    print(f"✓ {img_path.name}: {len(results)}个土豆")

# 保存简化CSV（给传感器团队）
csv_file = out_dir / "potatoes_simple.csv"
with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["potato_id", "grade", "lane", "signal_bits", "defects"])
    
    for p in all_potatoes:
        writer.writerow([
            p['potato_id'],
            p['grade'],
            p['signal']['lane'],
            ''.join(map(str, p['signal']['bits'])),
            str(p['defect_counts'])
        ])

print(f"\n总计: {len(all_potatoes)}个土豆")
print(f"CSV已保存: {csv_file}")
```

**运行**:
```bash
python3 example2_batch_to_csv.py
```

---

## 示例3: 实时监听并发送信号

```python
#!/usr/bin/env python3
# example3_realtime_monitor.py

import json
import time
from pathlib import Path

JSONL_FILE = "results/realtime/tracked_potatoes.jsonl"

def send_to_plc(potato_id, lane, signal_bits):
    """发送信号到PLC（需根据实际PLC接口实现）"""
    print(f"[PLC] 土豆{potato_id} → 激活通道{lane} (信号:{signal_bits})")
    # TODO: 实际PLC通信代码
    # 例如: modbus_client.write_coils(address, signal_bits)

def monitor_potatoes(jsonl_path):
    """实时监听新土豆并发送信号"""
    print(f"开始监听: {jsonl_path}\n")
    
    with open(jsonl_path, 'r') as f:
        # 移到文件末尾
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            if line:
                potato = json.loads(line)
                send_to_plc(
                    potato['potato_id'],
                    potato['signal']['lane'],
                    ''.join(map(str, potato['signal']['bits']))
                )
            else:
                time.sleep(0.01)  # 等待新数据

if __name__ == "__main__":
    # 确保JSONL文件存在
    if not Path(JSONL_FILE).exists():
        print(f"错误: {JSONL_FILE} 不存在")
        print("请先运行实时检测生成数据")
        exit(1)
    
    monitor_potatoes(JSONL_FILE)
```

**运行**:
```bash
# 终端1: 运行实时检测
python3 scripts/grade_potato_realtime.py --model models/yolov8s-obb-potato-v22_best.pt --source 0

# 终端2: 监听并发送信号
python3 example3_realtime_monitor.py
```

---

## 示例4: 自定义分级规则

```python
#!/usr/bin/env python3
# example4_custom_rules.py

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
from grade_with_potato_label import *

# 自定义规则
custom_rules = {
    "classes": ["OK", "black_spots", "deformities", "greenish_spots", 
                "pits", "potato", "red_spots", "scabs"],
    "ok_rules": {
        "description": "更严格的OK标准",
        "max_counts": {
            "black_spots": 1,  # 只允许1个黑斑
            "red_spots": 2,    # 只允许2个红斑
            "scabs": 0         # 不允许疮痂
        },
        "forbid": ["deformities", "pits", "greenish_spots"],
        "min_conf": 0.25
    },
    "size": {
        "strategy": "contour_area_px",
        "thresholds_px": [100000, 150000, 200000, 250000, 300000, 350000, 400000]
    },
    "signals": {
        "mapping": {
            "NG": {"lane": 8, "bits": [0,0,0,0,0,0,0,1]},
            "OK_S1": {"lane": 1, "bits": [1,0,0,0,0,0,0,0]},
            "OK_S2": {"lane": 2, "bits": [0,1,0,0,0,0,0,0]},
            "OK_S3": {"lane": 3, "bits": [0,0,1,0,0,0,0,0]},
            "OK_S4": {"lane": 4, "bits": [0,0,0,1,0,0,0,0]},
            "OK_S5": {"lane": 5, "bits": [0,0,0,0,1,0,0,0]},
            "OK_S6": {"lane": 6, "bits": [0,0,0,0,0,1,0,0]},
            "OK_S7": {"lane": 7, "bits": [0,0,0,0,0,0,1,0]}
        },
        "bit_order": ["L1","L2","L3","L4","L5","L6","L7","NG"]
    }
}

# 保存自定义规则
with open("config/custom_rules.json", 'w') as f:
    json.dump(custom_rules, f, indent=2, ensure_ascii=False)

# 使用自定义规则检测
model = YOLO("models/yolov8s-obb-potato-v22_best.pt")
id_gen = PotatoIDGenerator()

results = process_image_with_potato_detection(
    "test_images/0142ce97-Pic_2025_10_21_154621_149.jpeg",
    model, custom_rules, id_gen,
    Path("results/custom_rules"),
    conf=0.25, save_viz=True
)

print(f"使用自定义规则检测到 {len(results)} 个土豆")
for p in results:
    print(f"  {p['potato_id']}: {p['grade']}")
```

---

## 示例5: 统计分析

```python
#!/usr/bin/env python3
# example5_statistics.py

import json
from pathlib import Path
from collections import Counter

JSONL_FILE = "results/potato_final_v4/potatoes.jsonl"

# 读取数据
with open(JSONL_FILE, 'r') as f:
    potatoes = [json.loads(line) for line in f]

print("="*60)
print("土豆检测统计分析")
print("="*60)

# 基本统计
total = len(potatoes)
ok_count = sum(1 for p in potatoes if p['grade'].startswith('OK'))
ng_count = total - ok_count

print(f"\n总土豆数: {total}")
print(f"OK土豆: {ok_count} ({ok_count/total*100:.1f}%)")
print(f"NG土豆: {ng_count} ({ng_count/total*100:.1f}%)")

# 分级分布
print("\n分级分布:")
grades = [p['grade'] for p in potatoes]
for grade, count in sorted(Counter(grades).items()):
    print(f"  {grade:8s}: {count:2d}个 ({count/total*100:5.1f}%)")

# 缺陷统计
print("\n缺陷类型统计:")
all_defects = {}
for p in potatoes:
    for defect_type, count in p['defect_counts'].items():
        all_defects[defect_type] = all_defects.get(defect_type, 0) + count

for defect, count in sorted(all_defects.items(), key=lambda x: -x[1]):
    print(f"  {defect:15s}: {count:3d}个")

# NG原因分析
print("\nNG土豆原因:")
ng_potatoes = [p for p in potatoes if p['grade'] == 'NG']
ng_reasons = Counter()
for p in ng_potatoes:
    reasons = []
    counts = p['defect_counts']
    # 检查禁用缺陷
    if 'pits' in counts:
        reasons.append('含pits')
    if 'deformities' in counts:
        reasons.append('含deformities')
    if 'greenish_spots' in counts:
        reasons.append('含greenish_spots')
    # 检查超标
    if counts.get('scabs', 0) > 1:
        reasons.append('scabs超标')
    if counts.get('red_spots', 0) > 3:
        reasons.append('red_spots超标')
    if counts.get('black_spots', 0) > 2:
        reasons.append('black_spots超标')
    
    for reason in reasons:
        ng_reasons[reason] += 1

for reason, count in ng_reasons.most_common():
    print(f"  {reason:20s}: {count}个")

print("\n" + "="*60)
```

**运行**:
```bash
python3 example5_statistics.py
```

---

## 示例6: 导出给传感器的简化格式

```python
#!/usr/bin/env python3
# example6_export_for_sensor.py

import json
import csv
from pathlib import Path

INPUT_JSONL = "results/potato_final_v4/potatoes.jsonl"
OUTPUT_CSV = "results/for_sensor_team.csv"

# 读取数据
with open(INPUT_JSONL, 'r') as f:
    potatoes = [json.loads(line) for line in f]

# 导出简化CSV（只包含传感器需要的字段）
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow([
        "序号", "土豆ID", "分级", "通道", "8位信号", 
        "缺陷总数", "主要缺陷"
    ])
    
    for i, p in enumerate(potatoes, 1):
        # 提取主要缺陷
        main_defects = ', '.join([f"{k}×{v}" for k, v in p['defect_counts'].items()])
        if not main_defects:
            main_defects = "无"
        
        writer.writerow([
            i,
            p['potato_id'],
            p['grade'],
            p['signal']['lane'],
            ''.join(map(str, p['signal']['bits'])),
            p['total_defects'],
            main_defects
        ])

print(f"已导出 {len(potatoes)} 个土豆到: {OUTPUT_CSV}")
print("\n前5行预览:")
with open(OUTPUT_CSV, 'r') as f:
    for i, line in enumerate(f):
        if i < 6:  # 表头+5行
            print(line.strip())
```

**运行**:
```bash
python3 example6_export_for_sensor.py
```

**输出示例**:
```csv
序号,土豆ID,分级,通道,8位信号,缺陷总数,主要缺陷
1,2025110513591101,OK_S7,7,00000010,3,black_spots×2, red_spots×1
2,2025110513591104,NG,8,00000001,7,red_spots×4, black_spots×2, scabs×1
```

---

## 示例7: 命令行工具封装

```bash
#!/bin/bash
# potato_detect_cli.sh - 命令行工具

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"

MODEL="$SCRIPT_DIR/models/yolov8s-obb-potato-v22_best.pt"
RULES="$SCRIPT_DIR/config/grading_rules.json"

# 解析参数
COMMAND="$1"
shift

case "$COMMAND" in
    detect)
        # 检测图片
        SOURCE="$1"
        OUTPUT="${2:-results/$(date +%Y%m%d_%H%M%S)}"
        python3 "$SCRIPT_DIR/scripts/grade_with_potato_label.py" \
            --model "$MODEL" --source "$SOURCE" --out "$OUTPUT" --conf 0.25
        ;;
    
    realtime)
        # 实时检测
        CAMERA="${1:-0}"
        OUTPUT="${2:-results/realtime}"
        python3 "$SCRIPT_DIR/scripts/grade_potato_realtime.py" \
            --model "$MODEL" --source "$CAMERA" --out "$OUTPUT"
        ;;
    
    stats)
        # 统计分析
        JSONL="$1"
        python3 -c "
import json
from collections import Counter
with open('$JSONL') as f:
    data = [json.loads(l) for l in f]
grades = [d['grade'] for d in data]
print(f'总数: {len(data)}')
for g, c in Counter(grades).most_common():
    print(f'  {g}: {c}')
"
        ;;
    
    *)
        echo "用法:"
        echo "  $0 detect <图片目录> [输出目录]     - 批量检测"
        echo "  $0 realtime [摄像头ID] [输出目录]   - 实时检测"
        echo "  $0 stats <jsonl文件>                - 统计分析"
        echo ""
        echo "示例:"
        echo "  $0 detect test_images/"
        echo "  $0 realtime 0"
        echo "  $0 stats results/*/potatoes.jsonl"
        ;;
esac
```

**使用**:
```bash
chmod +x potato_detect_cli.sh

# 检测
./potato_detect_cli.sh detect test_images/

# 实时
./potato_detect_cli.sh realtime 0

# 统计
./potato_detect_cli.sh stats results/*/potatoes.jsonl
```

---

## 完整部署测试流程

```bash
# 1. 解压部署包
tar -xzf potato_inspection_offline_v4.tar.gz
cd potato_inspection_offline_v4

# 2. 部署
./deploy.sh

# 3. 测试检测
./detect.sh test_images/

# 4. 查看结果
ls results/*/
cat results/*/potatoes.csv | head -10

# 5. 查看可视化
ls results/*/visualizations/

# 6. 运行Python示例
python3 example_detect.py test_images/0142ce97-Pic_2025_10_21_154621_149.jpeg

# 7. 统计分析
python3 example5_statistics.py
```

---

**所有示例代码已准备就绪！** 🎉

