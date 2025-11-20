# 马铃薯分级系统 - 输出数据格式文档（最终版）

**版本**: v3.0（传送带实时跟踪版）  
**日期**: 2025-11-04  
**用途**: 用于与传感器/PLC工作人员对齐数据接口

---

## 重要说明

### 系统特性
- ✅ **土豆个体识别**：自动分割图片中的每个土豆
- ✅ **唯一ID**：每个土豆分配 `年月日时分+2位计数(01-60)` 的唯一序号
- ✅ **实时跟踪**：传送带模式下，土豆从入画面到离开保持同一ID
- ✅ **YOLO OBB检测**：使用旋转边界框检测缺陷
- ✅ **缺陷只显示名称**：不为缺陷分配ID，仅显示类别

---

## 1. 土豆ID格式

### 1.1 格式定义
```
202511041132 01
│││││││││││└┴─ 计数01-60（60进制循环）
││││││││││└──── 分32
│││││││││└───── 时11
││││││││└────── 日04
│││││││└─────── 月11
│││││└┴──────── 年2025
```

### 1.2 计数规则
- **范围**: 01-60
- **循环**: 超过60后回到01
- **进位**: 每分钟自动重置为01

### 1.3 示例
```
20251104113201  → 2025年11月4日 11:32 第01个土豆
20251104113259  → 2025年11月4日 11:32 第59个土豆
20251104113260  → 2025年11月4日 11:32 第60个土豆
20251104113201  → 如果还在11:32，第61个会循环回01
20251104113301  → 2025年11月4日 11:33 第01个土豆（自动进位）
```

---

## 2. 输出文件格式

### 2.1 JSONL 格式 (`potatoes.jsonl`)

**每行一个土豆**的JSON对象，UTF-8编码。

#### 批量模式（图片）
```json
{
  "potato_id": "20251104113201",
  "image": "/path/to/image.jpg",
  "bbox": [120, 80, 250, 180],
  "area": 35820.5,
  "total_defects": 3,
  "defect_counts": {
    "scabs": 1,
    "red_spots": 2
  },
  "grade": "OK_S3",
  "signal": {
    "bits": [0, 0, 1, 0, 0, 0, 0, 0],
    "bit_order": ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "NG"],
    "lane": 3
  },
  "defects": [
    {
      "class": "scabs",
      "confidence": 0.85,
      "obb": {
        "xyxyxyxy": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
        "xywhr": [cx, cy, w, h, rotation],
        "area": 1200.5
      }
    },
    {
      "class": "red_spots",
      "confidence": 0.72,
      "obb": {...}
    }
  ]
}
```

#### 实时跟踪模式
```json
{
  "potato_id": "20251104113201",
  "frame": 245,
  "bbox": [120, 80, 250, 180],
  "counts": {"scabs": 1},
  "grade": "OK_S3",
  "signal": {
    "bits": [0, 0, 1, 0, 0, 0, 0, 0],
    "lane": 3
  },
  "timestamp": 1730712301.234
}
```

### 2.2 CSV 格式 (`potatoes.csv`)

#### 批量模式表头
```csv
potato_id,image,bbox_json,area,grade,signal_bits,lane,total_defects,defect_counts_json,defects_json
```

#### 示例行
```csv
20251104113201,img.jpg,"[120,80,250,180]",35820.5,OK_S3,00100000,3,3,"{""scabs"":1,""red_spots"":2}","[{...}]"
20251104113202,img.jpg,"[400,100,230,170]",31200.0,NG,00000001,8,5,"{""deformities"":1}","[{...}]"
```

---

## 3. 字段详解

### 3.1 土豆标识
| 字段 | 类型 | 说明 |
|------|------|------|
| `potato_id` | 字符串 | 唯一土豆ID，格式：`年月日时分+计数(01-60)` |
| `image` | 字符串 | 图片路径（批量模式） |
| `frame` | 整数 | 帧序号（实时模式） |
| `timestamp` | 浮点数 | Unix时间戳（实时模式） |

### 3.2 位置与尺寸
| 字段 | 类型 | 说明 |
|------|------|------|
| `bbox` | 数组 | `[x, y, width, height]` 土豆在图片中的位置 |
| `area` | 浮点数 | 土豆轮廓面积（像素²），用于尺寸分级 |

### 3.3 缺陷信息
| 字段 | 类型 | 说明 |
|------|------|------|
| `total_defects` | 整数 | 检测到的缺陷总数 |
| `defect_counts` | 字典 | 按类别统计，如 `{"scabs": 3}` |
| `defects` | 数组 | 所有缺陷详情列表 |

#### 单个缺陷结构
```json
{
  "class": "scabs",
  "confidence": 0.85,
  "obb": {
    "xyxyxyxy": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
    "xywhr": [center_x, center_y, width, height, rotation_rad],
    "area": 1200.5
  }
}
```

**支持的缺陷类别**：
- `OK` - 正常区域
- `black_spots` - 黑斑
- `red_spots` - 红斑
- `scabs` - 疮痂
- `pits` - 坑洼
- `deformities` - 畸形
- `greenish_spots` - 绿斑

### 3.4 分级与信号
| 字段 | 类型 | 说明 |
|------|------|------|
| `grade` | 字符串 | `NG` 或 `OK_S1`-`OK_S7` |
| `signal.bits` | 数组 | 8位二进制 `[L1,L2,L3,L4,L5,L6,L7,NG]` |
| `signal.lane` | 整数 | 物理通道号（1-8） |

**信号映射**：
- `OK_S1` → Lane 1 → `10000000`
- `OK_S2` → Lane 2 → `01000000`
- ...
- `OK_S7` → Lane 7 → `00000010`
- `NG` → Lane 8 → `00000001`

---

## 4. 使用方法

### 4.1 批量处理（图片）
```bash
python3 scripts/grade_with_obb_labels.py \
  --model runs/yolov8s-obb-potato/weights/best.pt \
  --source data/images \
  --out results/batch_grading
```

**特点**：
- 一张图可能有多个土豆
- 每个土豆分配唯一ID
- 输出JSONL + CSV

### 4.2 实时跟踪（传送带）
```bash
python3 scripts/grade_potato_realtime.py \
  --model runs/yolov8s-obb-potato/weights/best.pt \
  --source 0  # 摄像头
```

**特点**：
- 土豆入画面时分配ID
- 跟踪过程中保持ID不变
- 土豆离开画面后输出结果
- 显示运动轨迹

---

## 5. 实时跟踪流程示意

```
┌──────────────────────────────────────────┐
│  传送带视频流（摄像头）                    │
└──────────────────────────────────────────┘
                   ↓
         ┌─────────┴─────────┐
         │  土豆检测与分割     │
         └─────────┬─────────┘
                   ↓
    ┌──────────────┴──────────────┐
    │  新土豆？                     │
    │  是 → 分配ID: 20251104113201 │
    │  否 → 匹配已有ID             │
    └──────────────┬──────────────┘
                   ↓
         ┌─────────┴─────────┐
         │  YOLO检测缺陷      │
         │  仅首次分级一次     │
         └─────────┬─────────┘
                   ↓
         ┌─────────┴─────────┐
         │  持续跟踪显示       │
         │  ID + Grade + Lane │
         └─────────┬─────────┘
                   ↓
         ┌─────────┴─────────┐
         │  土豆离开画面？     │
         │  是 → 输出结果      │
         │  否 → 继续跟踪      │
         └─────────┬─────────┘
                   ↓
         ┌─────────┴─────────┐
         │  写入JSONL/CSV    │
         │  发送PLC信号       │
         └───────────────────┘
```

---

## 6. 可视化标注说明

### 批量模式
- **土豆边框**：绿色（OK）或红色（NG）矩形
- **土豆ID**：边框上方显示 `ID:20251104113201 OK_S3 L3`
- **缺陷框**：旋转边界框（OBB），不同颜色
- **缺陷标签**：只显示类别名称（scabs、red_spots等）

### 实时跟踪模式
- **土豆边框**：同上
- **运动轨迹**：彩色线条连接历史位置
- **帧信息**：顶部显示帧号、跟踪数、已分级数

---

## 7. 传感器对接要点

### 读取方式

#### 方式A：批量读取CSV
```python
import csv

with open('potatoes.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        potato_id = row['potato_id']
        lane = int(row['lane'])
        grade = row['grade']
        print(f"土豆{potato_id} → 通道{lane} ({grade})")
```

#### 方式B：实时监听JSONL
```python
import json
import time

def tail_jsonl(filepath):
    with open(filepath, 'r') as f:
        f.seek(0, 2)  # 移到文件末尾
        while True:
            line = f.readline()
            if line:
                potato = json.loads(line)
                yield potato
            else:
                time.sleep(0.01)

for potato in tail_jsonl('tracked_potatoes.jsonl'):
    print(f"新土豆: {potato['potato_id']} → Lane {potato['signal']['lane']}")
    # 发送信号到PLC
    send_to_lane(potato['signal']['lane'])
```

### 关键字段
- `potato_id`: 唯一标识（例如 `20251104113201`）
- `signal.lane`: 物理通道（1-8）
- `signal.bits`: 8位控制信号
- `bbox`: 土豆位置（可用于传感器定位）

---

## 8. 注意事项

### 8.1 ID循环
- 同一分钟内，ID从01计数到60，然后循环回01
- 如果每分钟土豆数 > 60，会出现ID重复
- 建议：传送带速度 ≤ 1个/秒

### 8.2 土豆分割
- 使用Otsu二值化 + 形态学处理
- 过滤条件：面积 > 100,000像素，< 整图80%
- 如有漏检，可调整阈值或使用实例分割模型

### 8.3 实时跟踪
- 基于IoU的简单跟踪（生产环境建议用ByteTrack）
- 每个土豆仅分级一次（首次检测时）
- 离开画面后输出最终结果

---

## 9. 文件输出

### 批量模式输出
```
results/batch_grading/
├── potatoes.jsonl          # 每个土豆一行
├── potatoes.csv            # CSV格式
└── visualizations/         # 带标注的图片
    ├── img1_labeled.jpg
    └── img2_labeled.jpg
```

### 实时跟踪模式输出
```
results/realtime_tracking/
├── tracked_potatoes.jsonl  # 每个土豆一行（离开画面时写入）
├── tracked_potatoes.csv    # CSV格式
├── tracked_output.mp4      # 录制的带标注视频
└── frame_XXXX.jpg         # 关键帧快照
```

---

## 10. 对接检查清单

- [ ] 确认土豆ID格式：`年月日时分+计数(01-60)`
- [ ] 确认同一分钟内土豆数 ≤ 60（否则会循环）
- [ ] 确认8位信号位的物理接线顺序
- [ ] 确认PLC通信方式（Modbus/TCP 或 串口）
- [ ] 测试实时模式的跟踪准确性
- [ ] 确认可视化图片中土豆边框正确
- [ ] 确认缺陷OBB框显示正确

---


