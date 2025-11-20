# 部署到生产环境指南

## 快速部署步骤

### 1. 复制文件到生产环境

将以下文件/目录复制到 `F:\seven\seven_plc_vision_app\`：

```
F:\seven\seven_plc_vision_app\
├── app\                          # 原有目录（已有）
│   ├── cam_plc_capture.py        # 原有文件（不改动）
│   └── plc_dummy_loop.py         # 原有文件（不改动）
├── plc\                          # 新增目录
│   └── registers.py              # 新增：PLC寄存器定义
├── scripts\                      # 新增目录
│   └── detect_and_write_plc.py   # 新增：检测服务
├── models\                       # 新增目录（如果还没有）
│   └── yolov8s-obb-potato-v22_best.pt  # 模型文件
├── config\                       # 新增目录（如果还没有）
│   └── grading_rules.json         # 分级规则
└── run_detection_service.ps1     # 新增：Windows启动脚本
```

**注意**：`app/` 目录已经存在，只需要添加其他新文件。

### 2. 安装Python依赖（如果还没有）

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

---

## 工作原理

1. **`cam_plc_capture.py`** 拍照并保存图片到 `F:/data/camera/YYYYMMDD/CH{CC}_{YYYYMMDD}_{HHMMSS}-{N}.jpg`
2. **`detect_and_write_plc.py`** 监控目录，检测新图片，将结果写入PLC寄存器
3. **`plc_dummy_loop.py`** 监测PLC状态变化

**重要**：检测服务会将分级结果写入到 `attrs_base(channel)` 寄存器，覆盖 `cam_plc_capture.py` 中的随机数（这是期望的行为）。

---

## 检测结果映射

检测服务将分级结果转换为PLC寄存器值：

- `OK_S1` → `1`
- `OK_S2` → `2`
- `OK_S3` → `3`
- `OK_S4` → `4`
- `OK_S5` → `5`
- `OK_S6` → `6`
- `OK_S7` → `7`
- `NG` → `8`

---

## 测试建议

1. **先单独测试检测服务**：
   - 停止 `cam_plc_capture.py`
   - 手动复制几张测试图片到相机目录
   - 运行检测服务，查看是否能正确检测和写入PLC

2. **然后集成测试**：
   - 同时运行三个服务
   - 观察检测服务是否能及时处理新图片

---

## 常见问题

### Q: 检测服务未检测到图片？

A: 检查：
- 图片文件名格式：`CH01_20251112_121608-001.jpg` 或 `ch01_121608-001.jpg`
- 相机目录路径是否正确
- 文件是否完整写入（等待几秒）

### Q: PLC写入失败？

A: 检查：
- PLC IP和端口是否正确
- 网络连接是否正常
- 寄存器地址是否正确

---

## 详细文档

查看 `INTEGRATION_GUIDE.md` 了解更详细的集成说明。

