# API文档

## 模块接口说明

### 1. 相机模块 (acquisition.camera)

#### CameraManager

**初始化**
```python
from acquisition.camera import CameraManager
camera_mgr = CameraManager(config_loader=None)
```

**主要方法**

- `initialize() -> bool`
  - 初始化相机连接
  - 返回：是否成功

- `capture() -> Optional[np.ndarray]`
  - 采集一帧图像
  - 返回：图像数组，失败返回None

- `save_image(image, save_dir, prefix, metadata) -> str`
  - 保存图像到文件
  - 参数：
    - `image`: 图像数组
    - `save_dir`: 保存目录
    - `prefix`: 文件名前缀
    - `metadata`: 元数据（可选）
  - 返回：保存的文件路径

- `shutdown()`
  - 关闭相机

**示例**
```python
camera_mgr = CameraManager()
if camera_mgr.initialize():
    image = camera_mgr.capture()
    filepath = camera_mgr.save_image(image, "captures", "test")
    camera_mgr.shutdown()
```

---

### 2. 推理模块 (inference.model)

#### InferenceManager

**初始化**
```python
from inference.model import InferenceManager
inference_mgr = InferenceManager(config_loader=None)
```

**主要方法**

- `initialize() -> bool`
  - 加载模型
  - 返回：是否成功

- `process(image) -> Tuple[List[Detection], List[Dict]]`
  - 处理图像（检测+分级）
  - 参数：`image` - 输入图像
  - 返回：(检测结果列表, 分级结果列表)

**返回格式**
```python
detections = [Detection(bbox, confidence, class_id), ...]
results = [
    {
        "bbox": [x1, y1, x2, y2],
        "confidence": 0.85,
        "grade": 3,
        "grade_confidence": 0.92,
        "is_ng": False,
        "ng_reason": "",
        "class_id": 0
    },
    ...
]
```

**示例**
```python
inference_mgr = InferenceManager()
if inference_mgr.initialize():
    detections, results = inference_mgr.process(image)
    for result in results:
        print(f"等级: {result['grade']}, NG: {result['is_ng']}")
```

---

### 3. 追踪模块 (tracking.tracker)

#### TrackerManager

**初始化**
```python
from tracking.tracker import TrackerManager
tracker_mgr = TrackerManager(config_loader=None)
```

**主要方法**

- `update(detections) -> List[Track]`
  - 更新追踪
  - 参数：`detections` - 检测结果列表
  - 返回：活跃追踪列表

- `get_track(track_id) -> Optional[Track]`
  - 获取指定ID的追踪
  - 参数：`track_id` - 追踪ID
  - 返回：Track对象

- `update_track_result(track_id, grade, defects, is_ng)`
  - 更新追踪的检测结果
  - 参数：
    - `track_id`: 追踪ID
    - `grade`: 分级等级
    - `defects`: 缺陷列表
    - `is_ng`: 是否为NG品

**Track对象属性**
```python
track.track_id       # 追踪ID
track.bbox           # 边界框 [x1, y1, x2, y2]
track.grade          # 分级等级
track.defects        # 缺陷列表
track.is_ng          # 是否NG
track.state          # 状态：tentative/confirmed/deleted
```

**示例**
```python
tracker_mgr = TrackerManager()
tracks = tracker_mgr.update(detections)
for track in tracks:
    if track.state == "confirmed":
        tracker_mgr.update_track_result(
            track.track_id, grade=3, defects=[], is_ng=False
        )
```

---

### 4. PLC模块 (plc.communication)

#### PLCManager

**初始化**
```python
from plc.communication import PLCManager
plc_mgr = PLCManager(config_loader=None)
```

**主要方法**

- `initialize() -> bool`
  - 初始化PLC连接
  - 返回：是否成功

- `send_to_channel(grade, is_ng) -> bool`
  - 发送分拣信号
  - 参数：
    - `grade`: 分级等级（1-7）
    - `is_ng`: 是否为NG品
  - 返回：是否成功

- `heartbeat() -> bool`
  - 心跳检测
  - 返回：PLC是否在线

- `emergency_stop()`
  - 紧急停止（关闭所有输出）

- `shutdown()`
  - 关闭PLC连接

**通道枚举**
```python
from plc.communication import Channel

Channel.LEVEL_1  # 一级通道（500-550g）
Channel.LEVEL_2  # 二级通道（450-500g）
...
Channel.LEVEL_7  # 七级通道（150-250g）
Channel.NG       # NG通道
```

**示例**
```python
plc_mgr = PLCManager()
if plc_mgr.initialize():
    # 发送到3级通道
    plc_mgr.send_to_channel(grade=3, is_ng=False)
    
    # 发送到NG通道
    plc_mgr.send_to_channel(grade=0, is_ng=True)
    
    plc_mgr.shutdown()
```

---

### 5. 工具模块 (utils)

#### 配置管理 (config_loader)

```python
from utils.config_loader import init_config, get_config

# 初始化配置
init_config("configs/system_config.yaml")

# 获取配置
config = get_config()

# 读取配置值
exposure = config.get("camera.exposure.default", 5000)
plc_ip = config.get("plc.ip", "192.168.1.100")

# 设置配置值
config.set("camera.exposure.default", 6000)

# 保存配置
config.save()
```

#### 日志管理 (logger)

```python
from utils.logger import init_logger, get_logger

# 初始化日志
init_logger(log_dir="logs", level="INFO")

# 获取日志器
logger = get_logger()
logger_module = get_logger("my_module")

# 记录日志
logger.info("信息日志")
logger.warning("警告日志")
logger.error("错误日志")
logger.debug("调试日志")
```

#### 性能指标 (metrics)

```python
from utils.metrics import MetricsCollector, Timer

# 创建收集器
metrics = MetricsCollector(window_size=100)

# 记录帧处理
with Timer() as timer:
    # 处理逻辑
    process_image()

metrics.record_frame(timer.get_elapsed_ms())

# 记录结果
metrics.record_result(is_ng=False, grade=3, defects=[])

# 获取指标
perf = metrics.get_metrics()
print(f"FPS: {perf.fps:.2f}")
print(f"延迟: {perf.avg_latency_ms:.2f}ms")
print(f"总处理: {perf.total_processed}")
```

---

## 完整示例

### 基础使用

```python
from utils.logger import init_logger, get_logger
from utils.config_loader import init_config
from acquisition.camera import CameraManager
from inference.model import InferenceManager
from tracking.tracker import TrackerManager
from plc.communication import PLCManager

# 初始化
init_logger()
init_config("configs/system_config.yaml")
logger = get_logger()

# 创建组件
camera_mgr = CameraManager()
inference_mgr = InferenceManager()
tracker_mgr = TrackerManager()
plc_mgr = PLCManager()

# 初始化组件
camera_mgr.initialize()
inference_mgr.initialize()
plc_mgr.initialize()

# 主循环
while True:
    # 采集图像
    image = camera_mgr.capture()
    if image is None:
        continue
    
    # 推理
    detections, results = inference_mgr.process(image)
    
    # 追踪
    tracks = tracker_mgr.update(detections)
    
    # 更新追踪结果并发送PLC信号
    for i, track in enumerate(tracks):
        if i < len(results):
            result = results[i]
            tracker_mgr.update_track_result(
                track.track_id,
                result["grade"],
                [inference_mgr.defect_model.class_names[result["class_id"]]],
                result["is_ng"]
            )
            
            # 发送PLC信号
            plc_mgr.send_to_channel(result["grade"], result["is_ng"])
            
            logger.info(f"土豆 #{track.track_id}: 等级={result['grade']}, NG={result['is_ng']}")

# 关闭
camera_mgr.shutdown()
plc_mgr.shutdown()
```

### 自定义处理流程

```python
import cv2
from utils.metrics import Timer

# 自定义处理函数
def custom_process_pipeline(image):
    results = {}
    
    # 预处理
    with Timer() as t_preprocess:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    results['preprocess_ms'] = t_preprocess.get_elapsed_ms()
    
    # 推理
    with Timer() as t_inference:
        detections, grades = inference_mgr.process(blurred)
    results['inference_ms'] = t_inference.get_elapsed_ms()
    
    # 后处理
    with Timer() as t_postprocess:
        # 自定义后处理逻辑
        filtered = [d for d in detections if d.confidence > 0.8]
    results['postprocess_ms'] = t_postprocess.get_elapsed_ms()
    
    results['total_ms'] = sum([
        results['preprocess_ms'],
        results['inference_ms'],
        results['postprocess_ms']
    ])
    
    return filtered, results

# 使用
image = camera_mgr.capture()
detections, timing = custom_process_pipeline(image)
print(f"总耗时: {timing['total_ms']:.2f}ms")
```

## 错误处理

所有模块都使用异常处理和日志记录：

```python
try:
    image = camera_mgr.capture()
    if image is None:
        logger.error("采集失败")
        # 处理错误
except Exception as e:
    logger.error(f"异常: {e}", exc_info=True)
    # 异常处理
```

## 线程安全

- `MetricsCollector` 使用锁保护共享数据
- PLC通信建议单线程调用
- 相机采集建议在专用线程中运行

