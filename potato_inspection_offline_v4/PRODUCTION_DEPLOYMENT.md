# 生产环境部署指南

## 实时监控相机目录

本系统支持实时监控相机存储目录，自动检测新拍摄的图片并进行分级，同时可对接PLC输出控制信号。

---

## 快速开始

### 1. 部署系统

```powershell
# 进入部署目录
cd F:\potato_project\potato_inspection_offline_v4

# 运行部署脚本
.\deploy.ps1
```

### 2. 启动实时监控

#### 方式A：不连接PLC（测试模式）

```powershell
.\monitor_realtime.ps1 -CameraDir "F:\data\camera"
```

#### 方式B：连接PLC（生产模式）

```powershell
.\monitor_realtime.ps1 `
    -CameraDir "F:\data\camera" `
    -PLCEnable `
    -PLCHost "192.168.1.100" `
    -PLCPort 502 `
    -PLCAddress 0
```

---

## 配置说明

### 相机目录结构

系统监控的目录结构应为：
```
F:/data/camera/
└── YYYYMMDD/
    ├── ch01_HHMMSS-NNN.jpg
    ├── ch01_HHMMSS-NNN.jpg
    ├── ch02_HHMMSS-NNN.jpg
    └── ch02_HHMMSS-NNN.jpg
```

**路径格式**：`F:/data/camera/YYYYMMDD/ch{CC}_{HHMMSS}-{NNN}.jpg`

- `YYYYMMDD`: 日期（如：20251112）
- `ch{CC}`: 通道号（如：ch01, ch02）
- `HHMMSS`: 时间戳（时:分:秒）
- `NNN`: 序号（如：001, 002）

### PLC配置

#### Modbus TCP 配置

- **协议**: Modbus TCP/IP
- **默认端口**: 502
- **地址映射**: 
  - 地址 0-7 对应 8 个输出通道
  - 通道 1-7: OK产品分级（S1-S7）
  - 通道 8: NG产品筛选

#### 信号格式

系统输出8位数字信号：
- `[1,0,0,0,0,0,0,0]` → OK_S1 (通道1)
- `[0,1,0,0,0,0,0,0]` → OK_S2 (通道2)
- ...
- `[0,0,0,0,0,0,0,1]` → NG (通道8)

---

## 参数说明

### monitor_realtime.ps1 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-CameraDir` | 相机图片存储根目录 | `F:\data\camera` |
| `-Model` | 模型文件路径 | `models\yolov8s-obb-potato-v22_best.pt` |
| `-Rules` | 分级规则文件 | `config\grading_rules.json` |
| `-PLCEnable` | 启用PLC输出 | `false` |
| `-PLCHost` | PLC IP地址 | `192.168.1.100` |
| `-PLCPort` | PLC端口 | `502` |
| `-PLCAddress` | PLC起始地址 | `0` |
| `-Conf` | 检测置信度阈值 | `0.25` |
| `-ScanInterval` | 扫描间隔（秒） | `0.5` |
| `-Output` | 结果输出目录 | `results\realtime_monitor` |

---

## 输出结果

### 结果文件位置

```
results\realtime_monitor\
├── results_20251112.jsonl  # JSON格式（每行一个土豆）
└── results_20251112.csv    # CSV格式（表格数据）
```

### 结果格式

**JSONL格式**（每行一个JSON对象）：
```json
{
  "potato_id": "2025111212160801",
  "channel": "ch01",
  "grade": "OK_S3",
  "lane": 3,
  "signal": {
    "bits": [0,0,1,0,0,0,0,0],
    "lane": 3
  },
  "counts": {"black_spots": 1},
  "bbox": [100, 200, 150, 180],
  "area_px": 27000,
  "image_path": "F:/data/camera/20251112/ch01_121608-001.jpg",
  "timestamp": 1699772168.123
}
```

**CSV格式**：
```csv
potato_id,channel,grade,lane,signal_bits,counts,bbox,area_px,image_path,timestamp
2025111212160801,ch01,OK_S3,3,00100000,"{""black_spots"":1}","[100,200,150,180]",27000,F:/data/camera/20251112/ch01_121608-001.jpg,1699772168.123
```

---

## 运行状态

### 正常运行时输出示例

```
=========================================
Real-time Camera Monitor
=========================================
Camera directory: F:\data\camera
Model: models\yolov8s-obb-potato-v22_best.pt
PLC enabled: True
PLC host: 192.168.1.100
PLC port: 502
PLC address: 0
Scan interval: 0.5 seconds

Loading model...
Loading rules...
Connecting to PLC at 192.168.1.100:502...
Connected to Modbus TCP 192.168.1.100:502
Starting camera directory monitor...
Base directory: F:\data\camera
Output directory: results\realtime_monitor
PLC client: Connected
Scan interval: 0.5s
------------------------------------------------------------
Processed: ch01_121608-001.jpg | Channel: ch01 | Potatoes: 3
[2025111212160801] OK_S3 -> PLC signal sent (Lane 3)
[2025111212160802] OK_S5 -> PLC signal sent (Lane 5)
[2025111212160803] NG -> PLC signal sent (Lane 8)
Processed: ch02_121610-001.jpg | Channel: ch02 | Potatoes: 2
...
```

### 停止监控

按 `Ctrl+C` 停止，系统会显示统计信息：
```
Stopping monitor...

Final statistics:
Total images processed: 150
Total potatoes detected: 450
```

---

## 故障排查

### 问题1: 无法连接到PLC

**检查项**：
1. PLC IP地址和端口是否正确
2. 网络连接是否正常
3. 防火墙是否阻止连接
4. 是否安装了 `pymodbus`：`pip install pymodbus`

**测试连接**：
```powershell
# 测试网络连通性
Test-NetConnection -ComputerName 192.168.1.100 -Port 502
```

### 问题2: 未检测到新图片

**检查项**：
1. 相机目录路径是否正确
2. 图片文件名格式是否符合要求
3. 图片文件是否完整写入（避免读取到未完成的文件）

### 问题3: 检测结果不准确

**调整参数**：
```powershell
# 提高置信度阈值
.\monitor_realtime.ps1 -CameraDir "F:\data\camera" -Conf 0.3

# 或降低阈值
.\monitor_realtime.ps1 -CameraDir "F:\data\camera" -Conf 0.2
```

### 问题4: 处理速度慢

**优化建议**：
1. 增加扫描间隔：`-ScanInterval 1.0`
2. 使用GPU加速（如果支持）
3. 减少图片分辨率

---

## 高级配置

### 修改分级规则

编辑 `config/grading_rules.json` 文件，调整：
- 缺陷判定规则
- 尺寸分级阈值
- 信号映射关系

### 多通道配置

系统自动识别不同通道（ch01, ch02等），每个通道独立跟踪。

### 日志记录

监控过程中的日志会输出到控制台，可以重定向到文件：
```powershell
.\monitor_realtime.ps1 -CameraDir "F:\data\camera" > monitor.log 2>&1
```

---

## 系统要求

- Windows 10/11
- Python 3.8+
- 已部署的虚拟环境（运行 `deploy.ps1` 后）
- 网络连接（如果使用PLC）

---

## 技术支持

如有问题，请检查：
1. `README_WINDOWS.md` - Windows部署说明
2. `docs/PLC_INTERFACE.md` - PLC接口文档
3. `docs/OUTPUT_FORMAT_FINAL.md` - 输出格式说明

