# 土豆质检分级系统

一个基于机器视觉和深度学习的去皮土豆自动质检分级系统。

## 项目概述

本系统实现了以下核心功能：
- **异常检测**：识别黑点、凹坑、残皮、青斑、畸形等缺陷
- **尺寸分级**：将150-550g的土豆分为7个等级
- **NG处理**：自动识别并分拣不合格产品
- **实时处理**：支持3-5Hz的生产节拍
- **PLC控制**：通过工业协议控制7个OK通道和1个NG通道

## 系统架构

```
土豆质检分级系统
├── 图像采集模块 (acquisition)
│   ├── 工业相机控制
│   ├── 软/硬触发
│   └── 图像存证
├── 推理模块 (inference)
│   ├── 缺陷检测模型
│   └── 尺寸分级模型
├── 追踪模块 (tracking)
│   ├── SORT追踪算法
│   └── 卡尔曼滤波预测
├── PLC通信模块 (plc)
│   ├── Modbus/S7协议
│   └── 分拣信号输出
└── 主控流程
    ├── 多线程流水线
    ├── 性能监控
    └── 异常处理
```

## 技术参数

### 硬件要求
- **相机分辨率**：4096×3000
- **视野范围**：
  - 玻璃板: 38.7×28.35cm (94.5μm/px)
  - 滚轴顶: 56.5×41.4cm (138μm/px)
- **处理器**：建议Intel i5以上或同等性能
- **内存**：8GB以上
- **GPU**：NVIDIA GTX 1060以上（可选，用于加速推理）

### 性能指标
- **目标节拍**：3 Hz
- **最大节拍**：5 Hz
- **平均延迟**：<300ms
- **检测准确率**：≥95%
- **分级准确率**：≥90%
- **NG召回率**：≥98%

### 分级标准
| 等级 | 重量范围 |
|------|----------|
| 1级  | 500-550g |
| 2级  | 450-500g |
| 3级  | 450-450g |
| 4级  | 350-400g |
| 5级  | 300-350g |
| 6级  | 250-300g |
| 7级  | 150-250g |
| NG   | <150g或有缺陷 |

## 快速开始

### 1. 环境配置

```bash
# 克隆项目（或解压部署包）
cd potato_inspection_system

# 运行安装脚本
chmod +x scripts/*.sh
./scripts/setup.sh
```

### 2. 配置系统

编辑配置文件 `configs/system_config.yaml`：

```yaml
# 相机配置
camera:
  model: "industrial"  # 或 "simulated" 用于测试
  exposure:
    default: 5000
  
# PLC配置
plc:
  enable: true
  protocol: "modbus"
  ip: "192.168.1.100"
  port: 502

# 模型配置
model:
  defect_model:
    path: "models/defect_detection.onnx"
  grading_model:
    path: "models/grading_classifier.onnx"
```

### 3. 准备模型

将训练好的模型文件放置到 `models/` 目录：
- `defect_detection.onnx` - 缺陷检测模型
- `grading_classifier.onnx` - 分级分类模型

### 4. 测试组件

```bash
# 测试相机
cd scripts
python test_camera.py

# 测试PLC
python test_plc.py
```

### 5. 启动系统

```bash
# 启动主程序
./scripts/start.sh

# 停止系统
./scripts/stop.sh
```

## 项目结构

```
potato_inspection_system/
├── configs/                  # 配置文件
│   └── system_config.yaml   # 系统主配置
├── src/                     # 源代码
│   ├── acquisition/         # 图像采集模块
│   ├── tracking/            # 追踪模块
│   ├── inference/           # 推理模块
│   ├── plc/                # PLC通信模块
│   ├── utils/              # 工具模块
│   └── main.py             # 主程序
├── scripts/                # 脚本
│   ├── setup.sh           # 安装脚本
│   ├── start.sh           # 启动脚本
│   ├── stop.sh            # 停止脚本
│   ├── test_camera.py     # 相机测试
│   └── test_plc.py        # PLC测试
├── models/                # 模型文件
├── logs/                  # 日志文件
│   ├── system/           # 系统日志
│   ├── acquisition/      # 采集日志
│   ├── inference/        # 推理日志
│   └── plc/             # PLC日志
├── captures/             # 图像存证
│   ├── raw/             # 原始图像
│   └── processed/       # 处理后图像
├── data/                # 数据集
│   ├── train/          # 训练集
│   ├── val/            # 验证集
│   ├── test/           # 测试集
│   └── annotations/    # 标注文件
├── requirements.txt     # Python依赖
└── README.md           # 项目说明
```

## 模型训练

### 数据准备

1. **数据采集**：使用系统采集土豆图像
2. **数据标注**：使用LabelImg/Labelme标注
   - 缺陷类别：black_spot, pit, residual_peel, green_spot, deformation
   - 分级标签：1-7级
3. **数据组织**：
   ```
   data/
   ├── train/
   │   ├── images/
   │   └── labels/
   ├── val/
   │   ├── images/
   │   └── labels/
   └── test/
       ├── images/
       └── labels/
   ```

### 训练流程

```bash
# 安装训练依赖
pip install ultralytics

# 缺陷检测模型训练（YOLOv8）
yolo detect train data=data.yaml model=yolov8m.pt epochs=100 imgsz=640

# 导出为ONNX
yolo export model=runs/detect/train/weights/best.pt format=onnx

# 分级模型训练（分类）
yolo classify train data=data_grading/ model=yolov8m-cls.pt epochs=100

# 导出为ONNX
yolo export model=runs/classify/train/weights/best.pt format=onnx
```

## 配置说明

### 相机参数

```yaml
camera:
  exposure:
    default: 5000      # 默认曝光（μs）
    min: 1000         # 最小曝光
    max: 20000        # 最大曝光
  trigger:
    mode: "software"  # software/hardware/encoder
    delay_ms: 10      # 触发延迟
  light:
    intensity: 80     # 光源强度（0-100）
```

### 检测参数

```yaml
defect_detection:
  confidence_threshold: 0.7  # 置信度阈值
  nms_threshold: 0.45       # NMS阈值
  min_defect_area: 100      # 最小缺陷面积（像素）
```

### 追踪参数

```yaml
tracking:
  max_age: 30          # 最大失踪帧数
  min_hits: 3          # 最小命中次数
  iou_threshold: 0.3   # IoU匹配阈值
```

### PLC参数

```yaml
plc:
  output_channels:
    level_1: 0    # 通道1的PLC地址
    level_2: 1
    ...
    ng: 7
  signal:
    pulse_width_ms: 100  # 脉冲宽度
    sync_delay_ms: 50    # 同步延迟
```

## 运维指南

### 日常维护

1. **日志查看**
   ```bash
   # 系统日志
   tail -f logs/system/$(date +%Y-%m-%d).log
   
   # 错误日志
   tail -f logs/system/error_$(date +%Y-%m-%d).log
   ```

2. **性能监控**
   - FPS（帧率）：目标≥3 Hz
   - 延迟：目标<300ms
   - NG率：根据实际情况

3. **定期清理**
   ```bash
   # 清理旧日志（保留30天）
   find logs/ -name "*.log" -mtime +30 -delete
   
   # 清理旧图像（保留7天）
   find captures/ -name "*.jpg" -mtime +7 -delete
   ```

### 故障排查

1. **相机连接失败**
   - 检查相机电源和网线
   - 检查IP地址配置
   - 运行 `scripts/test_camera.py` 诊断

2. **PLC通信异常**
   - 检查PLC IP和端口
   - 检查网络连通性：`ping PLC_IP`
   - 运行 `scripts/test_plc.py` 诊断

3. **推理速度慢**
   - 检查GPU是否可用：`nvidia-smi`
   - 调整batch_size
   - 考虑模型量化（INT8）

4. **检测准确率低**
   - 检查相机曝光参数
   - 检查模型版本
   - 补充训练数据

## 开发指南

### 添加新的缺陷类型

1. 修改 `src/inference/model.py` 中的 `class_names`
2. 更新配置文件 `configs/system_config.yaml`
3. 标注新数据并重新训练模型
4. 更新NG判定逻辑

### 自定义相机适配

1. 继承 `CameraBase` 类
2. 实现必要的接口方法
3. 在 `CameraManager` 中注册新相机类型

示例：
```python
class MyCamera(CameraBase):
    def connect(self):
        # 实现连接逻辑
        pass
    
    def grab_image(self):
        # 实现图像采集
        pass
```

### 自定义PLC协议

1. 继承 `PLCBase` 类
2. 实现协议接口
3. 在 `PLCManager` 中注册

## FAQ

**Q: 系统支持哪些相机？**
A: 支持Basler、AVT/Allied Vision等GenICam兼容相机，也可以自定义适配。

**Q: 可以不使用GPU吗？**
A: 可以，系统会自动使用CPU推理，但速度会较慢。

**Q: 如何调整分级标准？**
A: 修改 `configs/system_config.yaml` 中的 `grading.levels` 配置。

**Q: 模型需要多少训练数据？**
A: 建议每个类别至少500-1000张标注图像。

**Q: 系统支持多相机吗？**
A: 当前版本为单相机，多相机需要修改代码支持。

## 更新日志

### v1.0.0 (2025-10-22)
- 初始版本发布
- 实现基础的检测、分级、追踪功能
- 支持Modbus PLC通信
- 提供完整的部署和运维工具

## 技术支持

项目负责人：
- **Seven**: 系统集成、相机控制、PLC通信
- **哲豪**: 数据标注、模型训练、算法优化

## 许可证

内部项目，未授权不得外传。

