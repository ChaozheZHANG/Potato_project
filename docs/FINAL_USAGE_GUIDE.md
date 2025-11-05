# 马铃薯分级系统 - 最终使用指南

**版本**: v3.0  
**日期**: 2025-11-04  
**适用场景**: 传送带实时分级系统

---

## 系统概述

本系统使用YOLOv8-OBB深度学习模型，实现：
1. **土豆个体识别**：自动识别每个土豆（使用potato标签）
2. **缺陷检测**：检测7类缺陷（黑斑、红斑、疮痂等）
3. **自动分级**：OK（7个尺寸）+ NG
4. **唯一ID追踪**：每个土豆分配唯一ID
5. **PLC信号输出**：8路信号控制出料道

---

## 土豆ID格式（最终版）

### 格式定义
```
20251104143201
│││││││││││└┴─ 计数01-60（60进制循环）
││││││││││└──── 秒32
│││││││││└───── 分14
││││││││└────── 时14
│││││││└─────── 日04
││││││└──────── 月11
│││││└┴─────── 年2025
```

### 示例
```
2025110414320101  → 2025-11-04 14:32:01 第01个土豆
2025110414320159  → 2025-11-04 14:32:01 第59个土豆
2025110414320160  → 2025-11-04 14:32:01 第60个土豆
2025110414320101  → 2025-11-04 14:32:01 第61个（循环回01）
2025110414320201  → 2025-11-04 14:32:02 第01个（下一秒）
```

**容量**: 每秒最多60个土豆，超过则ID循环

---

## 使用方法

### 1. 批量处理模式（图片）

```bash
python3 scripts/grade_with_obb_labels.py \
  --model runs/yolov8s-obb-potato-v2/weights/best.pt \
  --source data/images \
  --out results/batch_grading \
  --conf 0.25
```

**适用场景**: 离线分析、质量检测、数据审核

**输出**:
- `potatoes.jsonl` - 每个土豆一行
- `potatoes.csv` - CSV格式（Excel可打开）
- `visualizations/*.jpg` - 带标注的图片

### 2. 实时跟踪模式（传送带）

```bash
python3 scripts/grade_potato_realtime.py \
  --model runs/yolov8s-obb-potato-v2/weights/best.pt \
  --source 0 \
  --out results/realtime_tracking
```

**适用场景**: 产线实时分级、在线监控

**特性**:
- ✅ 土豆入画面时分配ID
- ✅ 持续跟踪，ID不变
- ✅ 显示运动轨迹
- ✅ 离开画面时输出结果
- ✅ 录制带标注视频

---

## 输出格式说明

### JSONL格式（每个土豆一行）
```json
{
  "potato_id": "2025110414320101",
  "image": "img.jpg",
  "bbox": [120, 80, 250, 180],
  "area": 35820.5,
  "total_defects": 3,
  "defect_counts": {"scabs": 1, "red_spots": 2},
  "grade": "OK_S3",
  "signal": {
    "bits": [0, 0, 1, 0, 0, 0, 0, 0],
    "lane": 3
  },
  "defects": [
    {"class": "scabs", "confidence": 0.85, "obb": {...}},
    {"class": "red_spots", "confidence": 0.72, "obb": {...}}
  ]
}
```

### CSV格式（传感器易读）
```csv
potato_id,image,bbox_json,area,grade,signal_bits,lane,total_defects,defect_counts_json
2025110414320101,img.jpg,"[120,80,250,180]",35820.5,OK_S3,00100000,3,3,"{""scabs"":1,...}"
```

---

## 分级规则

### OK/NG判定
- **NG条件**（筛选通道8）:
  - 存在禁用缺陷: `deformities`, `pits`, `greenish_spots`
  - 允许缺陷超标: `black_spots > 2` 或 `red_spots > 3` 或 `scabs > 1`

- **OK条件**: 无上述问题，按尺寸分7档

### 尺寸分级（OK_S1-S7）
基于土豆轮廓面积：
- S1: 最小（精品小土豆）
- S2-S6: 中间档位
- S7: 最大（大土豆）

**调整**: 修改 `config/grading_rules.json > size.thresholds_px`

---

## 8路信号输出

### 信号映射
| 分级 | 通道 | 信号位 | 说明 |
|------|------|--------|------|
| OK_S1 | Lane 1 | `10000000` | 最小尺寸 |
| OK_S2 | Lane 2 | `01000000` | 尺寸2 |
| OK_S3 | Lane 3 | `00100000` | 尺寸3 |
| OK_S4 | Lane 4 | `00010000` | 尺寸4 |
| OK_S5 | Lane 5 | `00001000` | 尺寸5 |
| OK_S6 | Lane 6 | `00000100` | 尺寸6 |
| OK_S7 | Lane 7 | `00000010` | 最大尺寸 |
| NG | Lane 8 | `00000001` | 不合格筛选 |

---

## 传感器对接

### Python实时读取示例
```python
import json
import time

def monitor_potatoes(jsonl_path):
    """实时监听新土豆"""
    with open(jsonl_path, 'r') as f:
        f.seek(0, 2)  # 移到文件末尾
        while True:
            line = f.readline()
            if line:
                potato = json.loads(line)
                print(f"土豆 {potato['potato_id']} → Lane {potato['signal']['lane']}")
                # 发送到PLC
                send_to_plc(potato['signal']['bits'])
            else:
                time.sleep(0.01)

monitor_potatoes('results/realtime_tracking/tracked_potatoes.jsonl')
```

### 关键字段
- `potato_id`: 唯一标识（16位）
- `signal.lane`: 物理通道（1-8）
- `signal.bits`: 8位控制信号
- `grade`: 分级结果
- `defect_counts`: 缺陷统计

---

## 模型说明

### 当前模型
- **路径**: `runs/yolov8s-obb-potato-v2/weights/best.pt`
- **类别**: 8类（包含potato整体标签）
- **任务**: OBB（旋转边界框检测）

### 模型用途
1. **potato标签**: 用于识别土豆个体（替代传统轮廓分割）
2. **缺陷标签**: 检测具体缺陷位置和类型

### 优势
- ✅ 更准确的土豆个体识别
- ✅ 支持重叠土豆分割
- ✅ 旋转边界框适应任意角度

---

## 配置文件

### 分级规则: `config/grading_rules.json`
```json
{
  "ok_rules": {
    "max_counts": {"black_spots": 2, "red_spots": 3, "scabs": 1},
    "forbid": ["deformities", "pits", "greenish_spots"]
  },
  "size": {
    "thresholds_px": [50000, 90000, 130000, 170000, 210000, 260000, 320000]
  },
  "signals": {
    "mapping": {
      "OK_S1": {"lane": 1, "bits": [1,0,0,0,0,0,0,0]},
      ...
      "NG": {"lane": 8, "bits": [0,0,0,0,0,0,0,1]}
    }
  }
}
```

可根据产线需求调整阈值。

---

## 快速启动

### 步骤1: 运行实时跟踪
```bash
cd /tmp/potato_inspection_system
python3 scripts/grade_potato_realtime.py \
  --model runs/yolov8s-obb-potato-v2/weights/best.pt \
  --source 0
```

### 步骤2: 查看输出
- 实时显示窗口: 每个土豆显示ID、分级、轨迹
- 输出文件: `results/realtime_tracking/tracked_potatoes.jsonl`

### 步骤3: PLC对接
```bash
# 发送信号到PLC（Modbus/TCP）
python3 scripts/plc_output.py \
  --input results/realtime_tracking/tracked_potatoes.jsonl \
  --method modbus \
  --modbus_host 192.168.1.100
```

---

## 关键文档

| 文档 | 用途 |
|------|------|
| `docs/OUTPUT_FORMAT_FINAL.md` | 输出数据格式详解 |
| `docs/PLC_INTERFACE.md` | PLC对接技术文档 |
| `docs/REALTIME_TRACKING_GUIDE.md` | 实时跟踪使用指南 |
| `README_yolov8_obb.md` | YOLOv8训练和使用说明 |

---

## 常见问题

### Q1: ID会重复吗？
A: 同一秒内超过60个土豆时会循环，但实际传送带速度很难达到60个/秒。

### Q2: 如何提高识别准确率？
A: 
- 使用新训练的模型（包含potato标签）
- 调整置信度阈值 `--conf`
- 增加训练数据

### Q3: 如何调整分级规则？
A: 修改 `config/grading_rules.json` 中的阈值和禁用项

### Q4: 支持多摄像头吗？
A: 支持，每个摄像头运行独立的实例即可

---

**文档结束**


