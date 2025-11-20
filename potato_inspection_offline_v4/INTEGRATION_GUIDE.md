# 生产环境集成指南

本指南说明如何将检测模型与现有的 `cam_plc_capture.py` 和 `plc_dummy_loop.py` 集成。

---

## 系统架构

系统由三个独立进程组成：

1. **`cam_plc_capture.py`** - 拍照存图（不改动）
   - 从相机拍照
   - 保存到 `F:/data/camera/YYYYMMDD/CH{CC}_{YYYYMMDD}_{HHMMSS}-{N}.jpg`
   - 写入PLC寄存器（目前用随机数，第277行TODO）

2. **`plc_dummy_loop.py`** - 监测状态（不改动）
   - 监测PLC状态变化
   - 维持心跳

3. **`detect_and_write_plc.py`** - 检测服务（新增）
   - 监控相机目录的新图片
   - 对图片进行检测和分级
   - 将结果写入PLC的 `attrs_base(channel)` 寄存器

---

## 文件结构

生产环境的目录结构：

```
F:\seven\seven_plc_vision_app\
├── app\                          # 原有目录（已有）
│   ├── cam_plc_capture.py        # 原有文件（不改动）
│   └── plc_dummy_loop.py         # 原有文件（不改动）
├── plc\                          # 新增目录
│   └── registers.py              # 寄存器定义（新增）
├── scripts\                      # 新增目录
│   └── detect_and_write_plc.py   # 检测服务（新增）
├── models\                       # 新增目录（如果还没有）
│   └── yolov8s-obb-potato-v22_best.pt
├── config\                       # 新增目录（如果还没有）
│   └── grading_rules.json
├── venv\                         # Python虚拟环境（如果还没有）
└── run_detection_service.ps1     # Windows启动脚本（新增）
```

**重要**：`app/` 目录已经存在，包含 `cam_plc_capture.py` 和 `plc_dummy_loop.py`，不需要改动。

---

## 部署步骤

### 1. 复制文件到生产环境

将以下文件复制到 `F:\seven\seven_plc_vision_app\`：

- `plc/registers.py` - PLC寄存器定义
- `scripts/detect_and_write_plc.py` - 检测服务脚本
- `run_detection_service.ps1` - Windows启动脚本
- `models/yolov8s-obb-potato-v22_best.pt` - 模型文件
- `config/grading_rules.json` - 分级规则

### 2. 安装依赖

如果生产环境还没有安装依赖，运行：

```powershell
cd F:\seven\seven_plc_vision_app
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install ultralytics opencv-python numpy
```

### 3. 运行三个服务

#### 服务1：拍照存图（原有，不改动）

```powershell
python -m app.cam_plc_capture `
    --fps 5 `
    --threshold 10 `
    --dim-n 1 `
    --tcp 192.168.10.7:10000 `
    --raw-file config\light_on.txt `
    --read-reply `
    --plc-ip 192.168.1.1 `
    --plc-port 502 `
    --channels 1,2,3,4 `
    --addr-base 0 `
    --out F:/data/camera
```

#### 服务2：监测状态（原有，不改动）

```powershell
python -m app.plc_dummy_loop `
    --ip 192.168.1.1 `
    --port 502 `
    --channels 1,2,3,4
```

#### 服务3：检测服务（新增）

```powershell
.\run_detection_service.ps1 `
    -CameraDir "F:\data\camera" `
    -PLCIp "192.168.1.1" `
    -PLCPort 502 `
    -Channels "1,2,3,4" `
    -AddrBase 0
```

或者直接使用Python：

```powershell
python scripts\detect_and_write_plc.py `
    --camera_dir F:/data/camera `
    --model models/yolov8s-obb-potato-v22_best.pt `
    --rules config/grading_rules.json `
    --plc_ip 192.168.1.1 `
    --plc_port 502 `
    --channels 1,2,3,4 `
    --addr_base 0
```

---

## 工作原理

### 数据流

1. **拍照** → `cam_plc_capture.py` 拍照并保存图片
2. **检测** → `detect_and_write_plc.py` 检测新图片
3. **写入PLC** → 检测结果写入 `attrs_base(channel)` 寄存器
4. **监测** → `plc_dummy_loop.py` 监测PLC状态

### PLC寄存器映射

检测服务将分级结果写入到每个通道的 `attrs_base(channel)` 寄存器：

- `OK_S1` → 值 `1`
- `OK_S2` → 值 `2`
- `OK_S3` → 值 `3`
- `OK_S4` → 值 `4`
- `OK_S5` → 值 `5`
- `OK_S6` → 值 `6`
- `OK_S7` → 值 `7`
- `NG` → 值 `8`

### 文件命名格式

检测服务识别以下格式的图片文件：
```
CH{CC}_{YYYYMMDD}_{HHMMSS}-{N}.jpg
```

示例：
- `CH01_20251112_121608-001.jpg`
- `CH02_20251112_121610-001.jpg`

---

## 配置说明

### 检测服务参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--camera_dir` | 相机图片存储根目录 | `F:/data/camera` |
| `--model` | 模型文件路径 | 必需 |
| `--rules` | 分级规则文件 | `config/grading_rules.json` |
| `--plc_ip` | PLC IP地址 | `192.168.1.1` |
| `--plc_port` | PLC端口 | `502` |
| `--channels` | 通道列表 | `1,2,3,4` |
| `--addr_base` | 地址基准（0或1） | `0` |
| `--conf` | 检测置信度 | `0.25` |
| `--scan_interval` | 扫描间隔（秒） | `0.5` |

---

## 注意事项

1. **不改动原有代码**：`cam_plc_capture.py` 和 `plc_dummy_loop.py` 保持原样

2. **PLC寄存器冲突**：
   - `cam_plc_capture.py` 在第280-293行也会写入 `attrs_base(channel)`
   - 检测服务会覆盖这个值（这是期望的行为）
   - 如果不想冲突，可以修改检测服务写入不同的寄存器

3. **文件处理顺序**：
   - 检测服务会跳过已处理的文件
   - 如果图片正在写入，可能会读取到不完整的文件
   - 建议扫描间隔不要太短（默认0.5秒）

4. **多进程运行**：
   - 三个服务可以同时运行
   - 它们通过文件系统和PLC寄存器通信
   - 确保PLC地址不冲突

---

## 故障排查

### 问题1：检测服务未检测到图片

**检查**：
- 图片文件命名格式是否正确
- 相机目录路径是否正确
- 文件是否完整写入（等待几秒再检测）

### 问题2：PLC写入失败

**检查**：
- PLC IP和端口是否正确
- 网络连接是否正常
- 寄存器地址是否正确（检查 `plc/registers.py`）

### 问题3：检测结果不准确

**调整**：
- 修改 `--conf` 参数调整置信度阈值
- 检查 `config/grading_rules.json` 中的分级规则

---

## 测试建议

1. **单独测试检测服务**：
   ```powershell
   # 先停止 cam_plc_capture.py
   # 手动复制几张测试图片到相机目录
   # 运行检测服务，查看是否能正确检测和写入PLC
   ```

2. **集成测试**：
   - 同时运行三个服务
   - 观察检测服务是否能及时处理新图片
   - 检查PLC寄存器值是否正确

3. **性能测试**：
   - 调整 `--scan_interval` 参数
   - 监控CPU和内存使用
   - 确保检测速度跟得上拍照速度

---

## 技术支持

如有问题，请检查：
- `plc/registers.py` - 寄存器地址定义
- `scripts/detect_and_write_plc.py` - 检测服务代码
- PLC连接日志

