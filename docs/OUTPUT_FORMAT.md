# 马铃薯分级系统 - 输出数据格式文档

**版本**: v2.0（多土豆独立标记）  
**日期**: 2025-01-30  
**用途**: 用于与传感器/PLC工作人员对齐数据接口

---

## 重要说明

**新版本特性**：
- ✅ **每个土豆独立标记**：系统自动分割图片中的多个土豆
- ✅ **唯一ID**：每个土豆分配格式为 `年月日时分秒+计数(00-59)` 的唯一序号
- ✅ **边界框坐标**：记录每个土豆在原图中的位置和尺寸
- ✅ **可视化输出**：在图片上标注土豆ID和分级结果

---

## 1. 输出文件格式

### 1.1 JSONL 格式 (`potatoes.jsonl`)

**每行一个土豆**的JSON对象，UTF-8编码。

#### 单个土豆数据结构
```json
{
  "potato_id": "20251104103300",
  "image": "/path/to/image.jpg",
  "bbox": {
    "x": 120,
    "y": 80,
    "width": 250,
    "height": 180,
    "area_px": 35820.5
  },
  "counts": {
    "black_spots": 2,
    "red_spots": 5,
    "scabs": 1
  },
  "grade": "OK_S3",
  "signal": {
    "bits": [0, 0, 1, 0, 0, 0, 0, 0],
    "bit_order": ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "NG"],
    "lane": 3
  }
}
```

#### 同一张图片多个土豆示例
```json
{"potato_id": "20251104103300", "image": "img1.jpg", "bbox": {...}, "grade": "OK_S3", ...}
{"potato_id": "20251104103301", "image": "img1.jpg", "bbox": {...}, "grade": "OK_S5", ...}
{"potato_id": "20251104103302", "image": "img1.jpg", "bbox": {...}, "grade": "NG", ...}
{"potato_id": "20251104103303", "image": "img2.jpg", "bbox": {...}, "grade": "OK_S2", ...}
```

#### 视频流模式字段
```json
{
  "frame": 123,
  "counts": {
    "black_spots": 2,
    "red_spots": 5
  },
  "grade": "NG",
  "signal": {
    "bits": [0, 0, 0, 0, 0, 0, 0, 1],
    "bit_order": ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "NG"],
    "lane": 8
  },
  "timestamp": 1706612345.678
}
```

### 1.2 CSV 格式 (`potatoes.csv`)

表头：`potato_id,image,bbox_json,grade,signal_bits,lane,counts_json`

#### 示例
```csv
potato_id,image,bbox_json,grade,signal_bits,lane,counts_json
20251104103300,img1.jpg,"{""x"":120,""y"":80,""width"":250,""height"":180,""area_px"":35820.5}",OK_S3,00100000,3,"{""black_spots"":2}"
20251104103301,img1.jpg,"{""x"":400,""y"":100,""width"":230,""height"":170,""area_px"":31200.0}",OK_S5,00001000,5,"{""red_spots"":3}"
20251104103302,img1.jpg,"{""x"":650,""y"":90,""width"":240,""height"":185,""area_px"":33500.0}",NG,00000001,8,"{""deformities"":1}"
```

### 1.3 可视化图片 (`visualizations/`)

每张原图生成一张标注后的图片，文件名为 `原图名_labeled.jpg`。

**标注内容**：
- 每个土豆用绿色（OK）或红色（NG）边框标出
- 边框上方显示：`ID:土豆序号 分级结果`
- 示例：`ID:20251104103300 OK_S3`

---

## 2. 字段说明

### 2.1 土豆标识
- **potato_id** (字符串): 唯一土豆序号，格式 `年月日时分秒秒数+计数(00-59)`
  - 示例：`2025110410450101` = 2025年11月4日 10:45:01秒 第01个
  - 格式说明：`YYYYMMDDHHMMSS` + 1位秒数(0-9) + 2位计数(00-59)
  - 秒数精度到0.1秒，计数范围00-59
  - 同一0.1秒内最多标记60个土豆
  - **实时跟踪模式**：每个土豆被首次检测到时分配ID，之后持续跟踪
- **image** (字符串): 图片文件完整路径（批量模式）
- **frame** (整数): 帧序号（实时跟踪模式）

### 2.2 边界框信息 (`bbox`)
记录土豆在原图中的位置和尺寸。

| 字段 | 类型 | 说明 |
|------|------|------|
| `x` | 整数 | 左上角X坐标（像素） |
| `y` | 整数 | 左上角Y坐标（像素） |
| `width` | 整数 | 宽度（像素） |
| `height` | 整数 | 高度（像素） |
| `area_px` | 浮点数 | 轮廓面积（像素²） |

**用途**：
- 传感器团队可根据 `bbox` 定位土豆在传送带上的位置
- `area_px` 用于尺寸分级（S1-S7）

### 2.3 缺陷计数 (`counts`)
字典类型，键为缺陷类别，值为检测到的数量。

#### 支持的缺陷类别
| 类别 | 说明 | 示例值 |
|------|------|--------|
| `OK` | 正常区域 | `1` |
| `black_spots` | 黑斑 | `2` |
| `red_spots` | 红斑 | `5` |
| `scabs` | 疮痂 | `1` |
| `pits` | 坑洼 | `0` |
| `deformities` | 畸形 | `1` |
| `greenish_spots` | 绿斑 | `0` |

**注意**: 未检测到的类别不会出现在字典中。

### 2.4 分级结果 (`grade`)
字符串类型，可能的值：

| 值 | 含义 | 说明 |
|----|------|------|
| `NG` | 不合格 | 存在禁用缺陷或超出允许数量 |
| `OK_S1` | 合格-尺寸1 | 最小尺寸 |
| `OK_S2` | 合格-尺寸2 | |
| `OK_S3` | 合格-尺寸3 | |
| `OK_S4` | 合格-尺寸4 | |
| `OK_S5` | 合格-尺寸5 | |
| `OK_S6` | 合格-尺寸6 | |
| `OK_S7` | 合格-尺寸7 | 最大尺寸 |

### 2.5 信号输出 (`signal`)

#### `bits` (数组，8个整数)
8位二进制信号，每一位对应一个物理通道。

**位顺序**（从左到右，索引0-7）：
```
[L1, L2, L3, L4, L5, L6, L7, NG]
```

**映射关系**：
| 位索引 | 位名 | 对应通道 | 物理含义 |
|--------|------|----------|----------|
| 0 | L1 | 通道1 | OK_S1 出料道 |
| 1 | L2 | 通道2 | OK_S2 出料道 |
| 2 | L3 | 通道3 | OK_S3 出料道 |
| 3 | L4 | 通道4 | OK_S4 出料道 |
| 4 | L5 | 通道5 | OK_S5 出料道 |
| 5 | L6 | 通道6 | OK_S6 出料道 |
| 6 | L7 | 通道7 | OK_S7 出料道 |
| 7 | NG | 通道8 | NG 筛选道 |

**示例**：
- `[1,0,0,0,0,0,0,0]` → 触发通道1（OK_S1）
- `[0,0,1,0,0,0,0,0]` → 触发通道3（OK_S3）
- `[0,0,0,0,0,0,0,1]` → 触发通道8（NG）

#### `bit_order` (数组)
信号的位顺序说明，固定为：`["L1","L2","L3","L4","L5","L6","L7","NG"]`

#### `lane` (整数)
物理通道编号（1-8），对应PLC输出通道。

---

## 3. PLC 接口对接

### 3.1 Modbus/TCP 协议

#### 连接参数
- **IP地址**: 可配置（默认 `192.168.1.100`）
- **端口**: 502
- **功能码**: 05 (写单个线圈) 或 15 (写多个线圈)
- **起始地址**: 可配置（默认 `0`）

#### 数据映射
8位信号对应Modbus线圈地址：
- 位0 (L1) → 地址 `base_address + 0`
- 位1 (L2) → 地址 `base_address + 1`
- ...
- 位7 (NG) → 地址 `base_address + 7`

**示例**：
如果 `base_address = 100`，则：
- `OK_S3` 的 `bits = [0,0,1,0,0,0,0,0]` → 写入地址102为 `ON`，其余为 `OFF`

#### 使用方式
```bash
python3 scripts/plc_output.py \
  --input grades.jsonl \
  --method modbus \
  --modbus_host 192.168.1.100 \
  --modbus_port 502 \
  --modbus_address 100
```

### 3.2 串口 RS232/485 协议

#### 连接参数
- **串口设备**: 可配置（默认 `/dev/ttyUSB0` 或 `COM1`）
- **波特率**: 可配置（默认 `9600`）
- **数据位**: 8
- **停止位**: 1
- **校验**: 无

#### 数据格式
ASCII文本格式，每行一条指令：
```
<bit0>,<bit1>,<bit2>,<bit3>,<bit4>,<bit5>,<bit6>,<bit7>\n
```

**示例**：
- `OK_S3`: `0,0,1,0,0,0,0,0\n`
- `NG`: `0,0,0,0,0,0,0,1\n`

#### 使用方式
```bash
python3 scripts/plc_output.py \
  --input grades.jsonl \
  --method serial \
  --serial_port /dev/ttyUSB0 \
  --serial_baud 9600
```

### 3.3 实时输出模式

在视频流处理时，每检测完一帧自动发送PLC信号：

```bash
python3 scripts/grade_potato.py \
  --model best.pt \
  --source 0 \
  --plc modbus \
  --modbus_host 192.168.1.100
```

---

## 4. 示例数据

### 示例1: 单图多土豆（常见场景）
**原图**: `batch_001.jpg` 包含3个土豆

**输出JSONL**（3行）：
```json
{"potato_id": "20251104103300", "image": "batch_001.jpg", "bbox": {"x": 50, "y": 30, "width": 200, "height": 150, "area_px": 25000}, "counts": {"black_spots": 1}, "grade": "OK_S2", "signal": {"bits": [0,1,0,0,0,0,0,0], "bit_order": ["L1","L2","L3","L4","L5","L6","L7","NG"], "lane": 2}}
{"potato_id": "20251104103301", "image": "batch_001.jpg", "bbox": {"x": 300, "y": 50, "width": 250, "height": 180, "area_px": 38000}, "counts": {"red_spots": 2, "scabs": 1}, "grade": "OK_S4", "signal": {"bits": [0,0,0,1,0,0,0,0], "bit_order": ["L1","L2","L3","L4","L5","L6","L7","NG"], "lane": 4}}
{"potato_id": "20251104103302", "image": "batch_001.jpg", "bbox": {"x": 600, "y": 40, "width": 230, "height": 170, "area_px": 33000}, "counts": {"deformities": 1}, "grade": "NG", "signal": {"bits": [0,0,0,0,0,0,0,1], "bit_order": ["L1","L2","L3","L4","L5","L6","L7","NG"], "lane": 8}}
```

**对应CSV**：
```csv
potato_id,image,bbox_json,grade,signal_bits,lane,counts_json
20251104103300,batch_001.jpg,"{""x"":50,""y"":30,""width"":200,""height"":150,""area_px"":25000}",OK_S2,01000000,2,"{""black_spots"":1}"
20251104103301,batch_001.jpg,"{""x"":300,""y"":50,""width"":250,""height"":180,""area_px"":38000}",OK_S4,00010000,4,"{""red_spots"":2,""scabs"":1}"
20251104103302,batch_001.jpg,"{""x"":600,""y"":40,""width"":230,""height"":170,""area_px"":33000}",NG,00000001,8,"{""deformities"":1}"
```

**可视化图片**: `batch_001_labeled.jpg`
- 3个土豆分别用框标出
- 框上标注：`ID:20251104103300 OK_S2`, `ID:20251104103301 OK_S4`, `ID:20251104103302 NG`

### 示例2: ID格式详解
```
2025110410450101
│││││││││││││└┴─ 计数 01 (00-59)
││││││││││││└──── 秒数 1 (0-9，0.1秒精度)
│││││││││││└───── 秒 01
││││││││││└────── 分 45
│││││││││└─────── 时 10
││││││││└──────── 日 04
│││││││└───────── 月 11
│││││└┴──────────  年 2025
```

**时间进位示例**：
```
2025110410450159  # 01.5秒的第59个
2025110410450200  # 02.0秒的第00个（自动进位）
```

---

## 5. 分级规则说明

### 5.1 OK/NG 判定
- **OK条件**：
  - 无禁用缺陷（`deformities`, `pits`, `greenish_spots`）
  - 允许的缺陷数量未超标
- **NG条件**：
  - 存在禁用缺陷，或
  - 允许缺陷超过阈值

### 5.2 尺寸分级（仅OK时）
基于图像轮廓面积，分为7档：
- S1: 最小
- S2-S6: 中间档
- S7: 最大

阈值可在 `config/grading_rules.json` 中配置。

---

## 6. 使用方法

### 6.1 批量模式（图片处理）
```bash
python3 scripts/grade_potato_multi.py \
  --model runs/yolov8s-obb-potato/weights/best.pt \
  --source data/test/images \
  --out results/grades_multi
```

**输出**：
- `results/grades_multi/potatoes.jsonl` - 每个土豆一行
- `results/grades_multi/potatoes.csv` - 表格格式
- `results/grades_multi/visualizations/*.jpg` - 可视化图片

### 6.2 实时跟踪模式（推荐用于产线）
```bash
# 摄像头输入
python3 scripts/grade_potato_realtime.py \
  --model runs/yolov8s-obb-potato/weights/best.pt \
  --source 0 \
  --out results/realtime_tracking

# 视频文件测试
python3 scripts/grade_potato_realtime.py \
  --model runs/yolov8s-obb-potato/weights/best.pt \
  --source test_video.mp4 \
  --out results/realtime_tracking
```

**实时跟踪特性**：
- ✅ **持续跟踪**：每个土豆从进入画面到离开，持续保持同一ID
- ✅ **轨迹显示**：显示土豆运动轨迹（彩色线条）
- ✅ **实时标注**：每帧显示土豆ID、分级结果、通道号
- ✅ **仅分级一次**：每个土豆仅在首次检测到时分级，避免重复
- ✅ **视频录制**：保存带标注的视频到 `tracked_output.mp4`

**输出**：
- `tracked_potatoes.jsonl` - 每个土豆一行（仅在首次分级时写入）
- `tracked_potatoes.csv` - 表格格式
- `tracked_output.mp4` - 带标注和轨迹的视频

### 与传感器对齐步骤
1. 传感器团队读取 `tracked_potatoes.csv` 或 `potatoes.jsonl`
2. 根据 `potato_id` 唯一标识每个土豆（时间戳+秒数+计数）
3. 根据 `bbox` 定位土豆位置（可选）
4. 根据 `signal.bits` 或 `signal.lane` 控制出料道
5. 实时模式下，查看显示窗口或录制视频确认跟踪正确

## 7. 对接检查清单

- [ ] 确认输出文件路径：`results/grades_multi/potatoes.jsonl` 和 `potatoes.csv`
- [ ] 确认土豆ID格式：`年月日时分秒+计数(00-59)`
- [ ] 确认同一张图多个土豆能正确区分（检查bbox坐标）
- [ ] 确认8位信号位的物理接线顺序（L1-L7为OK通道，NG为筛选通道）
- [ ] 确认PLC通信方式（Modbus/TCP 或 串口）
- [ ] 确认PLC地址映射（起始地址、线圈/寄存器类型）
- [ ] 测试信号发送延迟要求（实时模式 vs 批量模式）
- [ ] 确认数据格式（JSONL vs CSV）
- [ ] 确认可视化图片用于人工审核

---

## 8. 联系方式与更新

如有格式变更，请查看：
- 配置文件：`config/grading_rules.json`
- 脚本：`scripts/grade_potato.py`, `scripts/plc_output.py`
- 完整文档：`README_yolov8_obb.md`

---

**文档结束**

