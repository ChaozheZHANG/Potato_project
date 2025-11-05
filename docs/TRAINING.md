# 模型训练指南

本文档说明如何训练和优化土豆质检分级模型。

## 训练环境准备

### 硬件要求
- GPU: NVIDIA RTX 3060 或更高（12GB+ 显存）
- CPU: 8核以上
- 内存: 32GB+
- 存储: 500GB+ SSD

### 软件环境

```bash
# 创建训练环境
conda create -n potato_training python=3.9
conda activate potato_training

# 安装PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 安装YOLOv8
pip install ultralytics

# 安装其他依赖
pip install opencv-python pillow matplotlib seaborn pandas scikit-learn
pip install labelimg  # 标注工具
```

## 数据准备

### 1. 数据采集

使用系统采集模式：

```python
# scripts/collect_training_data.py
from src.acquisition.camera import CameraManager
import time

camera_mgr = CameraManager()
camera_mgr.initialize()

for i in range(1000):
    image = camera_mgr.capture()
    camera_mgr.save_image(image, "data/raw_images", f"potato_{i:04d}")
    time.sleep(2)  # 每2秒采集一张
```

### 2. 数据标注

**使用LabelImg进行标注：**

```bash
# 启动LabelImg
labelimg data/raw_images data/annotations/classes.txt
```

**类别文件 (classes.txt):**
```
black_spot
pit
residual_peel
green_spot
deformation
```

**标注规范：**
- 标注框紧贴缺陷边界
- 小缺陷也要标注（≥5mm）
- 每张图检查3遍确保无遗漏

### 3. 数据组织

```
data/
├── images/
│   ├── train/
│   │   ├── potato_0001.jpg
│   │   ├── potato_0002.jpg
│   │   └── ...
│   ├── val/
│   └── test/
└── labels/
    ├── train/
    │   ├── potato_0001.txt
    │   ├── potato_0002.txt
    │   └── ...
    ├── val/
    └── test/
```

**YOLO格式标注 (potato_0001.txt):**
```
0 0.5123 0.6234 0.1234 0.0987
1 0.7456 0.3456 0.0654 0.0543
```
格式: `class_id center_x center_y width height` (归一化坐标)

### 4. 数据集配置

创建 `data/potato_data.yaml`:

```yaml
# 数据集路径
path: /path/to/data
train: images/train
val: images/val
test: images/test

# 类别
nc: 5
names: ['black_spot', 'pit', 'residual_peel', 'green_spot', 'deformation']
```

## 缺陷检测模型训练

### 训练脚本

```python
# scripts/train_defect_model.py
from ultralytics import YOLO

# 加载预训练模型
model = YOLO('yolov8m.pt')

# 训练
results = model.train(
    data='data/potato_data.yaml',
    epochs=100,
    imgsz=640,
    batch=16,
    device=0,  # GPU 0
    project='runs/defect_detection',
    name='exp1',
    
    # 优化参数
    optimizer='AdamW',
    lr0=0.01,
    lrf=0.01,
    momentum=0.937,
    weight_decay=0.0005,
    
    # 数据增强
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=10.0,
    translate=0.1,
    scale=0.5,
    shear=0.0,
    perspective=0.0,
    flipud=0.0,
    fliplr=0.5,
    mosaic=1.0,
    mixup=0.1,
    
    # 其他
    save=True,
    save_period=10,
    val=True,
    plots=True,
)

# 评估
metrics = model.val()
print(f"mAP50: {metrics.box.map50}")
print(f"mAP50-95: {metrics.box.map}")

# 导出为ONNX
model.export(format='onnx', dynamic=False, simplify=True)
```

### 运行训练

```bash
cd scripts
python train_defect_model.py
```

### 监控训练

```bash
# 使用TensorBoard
tensorboard --logdir runs/defect_detection
```

## 分级模型训练

### 数据准备

```
data/grading/
├── train/
│   ├── level_1/
│   │   ├── img001.jpg
│   │   └── ...
│   ├── level_2/
│   ├── ...
│   └── level_7/
├── val/
└── test/
```

### 训练脚本

```python
# scripts/train_grading_model.py
from ultralytics import YOLO

# 分类模型
model = YOLO('yolov8m-cls.pt')

results = model.train(
    data='data/grading',
    epochs=100,
    imgsz=224,
    batch=32,
    device=0,
    project='runs/grading',
    name='exp1',
    
    optimizer='AdamW',
    lr0=0.001,
    
    # 数据增强
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    degrees=15.0,
    translate=0.1,
    scale=0.2,
    fliplr=0.5,
)

# 评估
metrics = model.val()
print(f"Top1 Accuracy: {metrics.top1}")
print(f"Top5 Accuracy: {metrics.top5}")

# 导出
model.export(format='onnx')
```

## 高级训练技巧

### 1. 类别不平衡处理

```python
# 计算类别权重
from collections import Counter
import numpy as np

# 统计各类别数量
class_counts = Counter()
for label_file in label_files:
    with open(label_file) as f:
        for line in f:
            class_id = int(line.split()[0])
            class_counts[class_id] += 1

# 计算权重
total = sum(class_counts.values())
class_weights = {k: total / (len(class_counts) * v) for k, v in class_counts.items()}

# 在训练时使用
# model.train(..., class_weights=class_weights)
```

### 2. 难样本挖掘

```python
# 找出模型预测错误的样本
model = YOLO('runs/defect_detection/exp1/weights/best.pt')

errors = []
for img_path in test_images:
    results = model(img_path)
    # 与真实标签比对
    # 如果错误，记录
    if is_wrong_prediction(results, ground_truth):
        errors.append(img_path)

# 增加难样本的训练次数
# 或进行针对性的数据增强
```

### 3. 模型融合

```python
# 训练多个模型并融合
models = [
    YOLO('yolov8m.pt'),
    YOLO('yolov8l.pt'),
    YOLO('yolov8x.pt'),
]

# 集成预测
def ensemble_predict(image, models):
    all_results = []
    for model in models:
        results = model(image)
        all_results.append(results)
    
    # NMS融合
    return weighted_nms(all_results)
```

### 4. 知识蒸馏

```python
# 使用大模型（教师）训练小模型（学生）
teacher = YOLO('yolov8x.pt')  # 大模型
student = YOLO('yolov8n.pt')  # 小模型

# 蒸馏训练（伪代码）
for image, label in dataloader:
    teacher_pred = teacher(image)
    student_pred = student(image)
    
    # 损失 = 真实标签损失 + 蒸馏损失
    loss = criterion(student_pred, label) + \
           kl_divergence(student_pred, teacher_pred)
    
    loss.backward()
    optimizer.step()
```

## 模型优化

### 1. 剪枝

```python
import torch
from torch.nn.utils import prune

model = YOLO('best.pt').model

# 对卷积层进行剪枝
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Conv2d):
        prune.l1_unstructured(module, name='weight', amount=0.3)
        prune.remove(module, 'weight')

# 保存剪枝后的模型
torch.save(model.state_dict(), 'pruned_model.pt')
```

### 2. 量化

```python
# INT8量化
model = YOLO('best.pt')

# 导出量化模型
model.export(
    format='onnx',
    dynamic=False,
    simplify=True,
    int8=True,  # INT8量化
)
```

### 3. TensorRT优化

```bash
# 转换为TensorRT引擎
trtexec --onnx=model.onnx \
        --saveEngine=model.trt \
        --fp16 \
        --workspace=4096
```

## 评估与验证

### 性能评估

```python
# scripts/evaluate_model.py
from ultralytics import YOLO
import numpy as np

model = YOLO('best.pt')

# 在测试集上评估
results = model.val(data='potato_data.yaml', split='test')

print("缺陷检测性能:")
print(f"  mAP@0.5: {results.box.map50:.4f}")
print(f"  mAP@0.5:0.95: {results.box.map:.4f}")
print(f"  Precision: {results.box.p:.4f}")
print(f"  Recall: {results.box.r:.4f}")

# 各类别性能
for i, class_name in enumerate(results.names.values()):
    print(f"\n{class_name}:")
    print(f"  AP: {results.box.ap[i]:.4f}")
    print(f"  Precision: {results.box.p[i]:.4f}")
    print(f"  Recall: {results.box.r[i]:.4f}")
```

### 推理速度测试

```python
import time

model = YOLO('best.pt')
image = cv2.imread('test.jpg')

# 预热
for _ in range(10):
    model(image)

# 测速
times = []
for _ in range(100):
    start = time.time()
    results = model(image)
    elapsed = (time.time() - start) * 1000
    times.append(elapsed)

print(f"平均推理时间: {np.mean(times):.2f}ms")
print(f"最小推理时间: {np.min(times):.2f}ms")
print(f"最大推理时间: {np.max(times):.2f}ms")
print(f"FPS: {1000/np.mean(times):.2f}")
```

### 混淆矩阵分析

```python
from sklearn.metrics import confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt

# 收集预测和真实标签
y_true = []
y_pred = []

for image, label in test_dataset:
    pred = model(image)
    y_true.append(label)
    y_pred.append(pred.argmax())

# 绘制混淆矩阵
cm = confusion_matrix(y_true, y_pred)
plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=class_names,
            yticklabels=class_names)
plt.ylabel('True Label')
plt.xlabel('Predicted Label')
plt.savefig('confusion_matrix.png')
```

## 部署前检查

### 检查清单

- [ ] 训练收敛（loss稳定下降）
- [ ] 验证集性能达标（mAP≥0.95）
- [ ] 测试集性能达标
- [ ] 推理速度满足要求（<300ms）
- [ ] 模型大小合理（<500MB）
- [ ] ONNX导出成功
- [ ] 实际图像测试通过
- [ ] 边缘案例测试通过

### 版本管理

```bash
# 保存模型版本
mkdir -p models/versions
cp runs/defect_detection/exp1/weights/best.pt \
   models/versions/defect_v1.0_$(date +%Y%m%d).pt

# 记录版本信息
echo "v1.0 - $(date)" >> models/VERSION.txt
echo "mAP: 0.956" >> models/VERSION.txt
echo "Training samples: 2000" >> models/VERSION.txt
```

## 持续改进

### 1. 收集生产数据

部署后持续收集问题样本：
- 误检样本
- 漏检样本
- 分级错误样本

### 2. 定期重训练

每收集500-1000新样本后重新训练：

```bash
# 合并新旧数据
cat data/labels/train/* data/new_labels/* > data/labels/train_v2/*

# 重新训练
python scripts/train_defect_model.py --version v2
```

### 3. A/B测试

```python
# 同时部署新旧模型进行对比
model_v1 = YOLO('models/v1.0.pt')
model_v2 = YOLO('models/v2.0.pt')

# 随机选择模型进行预测
if random.random() < 0.5:
    results = model_v1(image)
    log_result(results, version='v1')
else:
    results = model_v2(image)
    log_result(results, version='v2')

# 比较性能
compare_models('v1', 'v2')
```

## 常见问题

**Q: 训练过拟合怎么办？**
A: 增加数据增强、使用Dropout、减小模型大小、增加正则化

**Q: 小目标检测效果差？**
A: 使用多尺度训练、增加小目标样本、调整anchor尺寸

**Q: 类别不平衡？**
A: 使用focal loss、调整类别权重、过采样少数类

**Q: 推理速度慢？**
A: 使用更小的模型、量化、TensorRT加速、减小输入尺寸

