# 传感器团队快速对接手册

**给谁看**: 传感器/PLC开发人员  
**目的**: 5分钟快速对接分级系统

---

## 你需要知道的3件事

### 1️⃣ 土豆ID格式
```
2025110414320101
│      │ │ │└┴─ 计数01-60（循环）
│      │ │ └──── 秒32
│      │ └────── 分14时
│      └──────── 日04月11
└────────────── 年2025
```

**重点**: 
- 16位数字
- 精确到秒
- 最后2位是计数（01-60循环）

### 2️⃣ 输出数据
**文件**: `potatoes.csv`

**每行一个土豆**，包含：
| 字段 | 示例值 | 说明 |
|------|--------|------|
| potato_id | 2025110414320101 | 唯一ID |
| grade | OK_S3 | 分级结果 |
| signal_bits | 00100000 | 8位信号 |
| lane | 3 | 物理通道号 |

**CSV示例**:
```csv
potato_id,grade,signal_bits,lane
2025110414320101,OK_S3,00100000,3
2025110414320102,NG,00000001,8
2025110414320103,OK_S7,00000010,7
```

### 3️⃣ 信号映射
**8路通道，one-hot编码**:

```
信号位: [L1, L2, L3, L4, L5, L6, L7, NG]
```

| 分级 | 通道 | 8位信号 | 说明 |
|------|------|---------|------|
| OK_S1 | 1 | 10000000 | 最小 |
| OK_S2 | 2 | 01000000 | |
| OK_S3 | 3 | 00100000 | |
| OK_S4 | 4 | 00010000 | |
| OK_S5 | 5 | 00001000 | |
| OK_S6 | 6 | 00000100 | |
| OK_S7 | 7 | 00000010 | 最大 |
| NG | 8 | 00000001 | 筛选 |

---

## 对接代码（Python）

### 读取CSV并控制通道
```python
import csv

with open('potatoes.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        potato_id = row['potato_id']
        lane = int(row['lane'])
        grade = row['grade']
        
        print(f"土豆{potato_id} → 通道{lane} ({grade})")
        
        # 发送到PLC
        activate_channel(lane)
```

### 实时监听JSONL
```python
import json
import time

with open('tracked_potatoes.jsonl', 'r') as f:
    f.seek(0, 2)  # 移到末尾
    while True:
        line = f.readline()
        if line:
            potato = json.loads(line)
            lane = potato['signal']['lane']
            activate_channel(lane)
        else:
            time.sleep(0.01)
```

---

## PLC接口

### Modbus/TCP
- **IP**: 192.168.1.100（可配置）
- **端口**: 502
- **寄存器**: 线圈地址 0-7（可配置）
- **映射**: Bit0→Lane1, Bit1→Lane2, ..., Bit7→NG

### 串口RS232/485
- **端口**: /dev/ttyUSB0 或 COM1
- **波特率**: 9600
- **格式**: ASCII `0,0,1,0,0,0,0,0\n`（对应8位）

---

## 测试结果（新模型）

**测试集**: 12张图片  
**检测土豆**: 19个  
**分级结果**:
- OK_S3: 3个 → Lane 3
- OK_S5: 1个 → Lane 5
- OK_S7: 6个 → Lane 7
- NG: 9个 → Lane 8

**输出位置**:
- `/tmp/potato_inspection_system/results/new_model_test/potatoes.csv`
- `/tmp/potato_inspection_system/results/new_model_test/potatoes.jsonl`
- `/tmp/potato_inspection_system/results/new_model_test/visualizations/`

---

## 检查清单

在系统上线前，请确认：

- [ ] 能正确读取CSV或JSONL文件
- [ ] potato_id格式理解（16位，最后2位是01-60循环）
- [ ] 8路通道物理接线正确（Lane 1-7为OK，Lane 8为NG）
- [ ] PLC通信正常（Modbus或串口）
- [ ] 信号延迟可接受（传送带速度匹配）
- [ ] 查看可视化图片确认检测正确

---

## 联系与支持

**完整文档**:
- 输出格式: `docs/OUTPUT_FORMAT_FINAL.md`
- PLC接口: `docs/PLC_INTERFACE.md`
- 使用指南: `docs/FINAL_USAGE_GUIDE.md`

**配置文件**:
- 分级规则: `config/grading_rules.json`
- 数据配置: `yolo_potato_obb_v2.yaml`

**运行脚本**:
```bash
# 批量处理
python3 scripts/grade_with_obb_labels.py \
  --model runs/yolov8s-obb-potato-v2/weights/best.pt \
  --source 数据目录

# 实时跟踪
python3 scripts/grade_potato_realtime.py \
  --model runs/yolov8s-obb-potato-v2/weights/best.pt \
  --source 0
```

---




