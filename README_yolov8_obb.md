## YOLOv8 OBB 训练说明（马铃薯缺陷检测）

### 1. 环境
```bash
pip install -U ultralytics
```

### 2. 数据集拆分生成
- 已支持 **train/val/test 三分集**，可指定比例
- 运行分割：
```bash
python3 scripts/split_obb_dataset.py \
    /tmp/potato_inspection_system/data/test/project-3-at-2025-10-30-19-49-55a1bb93(1) \
    --train_ratio 0.8 --val_ratio 0.1 --test_ratio 0.1
```
- 输出:
  - `images/train|val|test`、`labels/train|val|test`
- `yolo_potato_obb.yaml` 自动适配此结构

### 3. 一致性检查
> 推荐每次分割/标注后执行，自动发现缺失/空标注
```bash
python3 scripts/check_obb_data_consistency.py \
    /tmp/potato_inspection_system/data/test/project-3-at-2025-10-30-19-49-55a1bb93(1)
```

### 4. 训练
命令行示例：
```bash
yolo task=obb mode=train model=yolov8n-obb.pt \
  data=/tmp/potato_inspection_system/yolo_potato_obb.yaml \
  epochs=100 imgsz=640 batch=16 device=0 \
  project=/tmp/potato_inspection_system/runs name=yolov8n-obb-potato
```
或使用脚本：
```bash
python3 /tmp/potato_inspection_system/scripts/train_yolov8_obb.py
```

### 5. 推理（示例）
```bash
python - << 'PY'
from ultralytics import YOLO
model = YOLO('/tmp/potato_inspection_system/runs/yolov8n-obb-potato/weights/best.pt')
model.predict(task='obb', source='数据集/images/test', imgsz=640, save=True)
PY
```

### 6. 尺寸阈值自动建议
```bash
# 基于已分级结果分析分布
python3 scripts/analyze_size_distribution.py \
  --source /tmp/potato_inspection_system/results/grades/grades.jsonl \
  --output /tmp/potato_inspection_system/config/suggested_thresholds.json

# 或直接从图片目录分析
python3 scripts/analyze_size_distribution.py \
  --source "/tmp/potato_inspection_system/data/test/project-3-at-2025-10-30-19-49-55a1bb93(1)/images/test"
```
生成后，将 `suggested_thresholds_px` 复制到 `grading_rules.json > size.thresholds_px`。

### 7. 分级与信号输出
- 规则文件：`/tmp/potato_inspection_system/config/grading_rules.json`
- 运行分级：
```bash
python3 scripts/grade_potato.py \
  --model /tmp/potato_inspection_system/runs/yolov8s-obb-potato/weights/best.pt \
  --source "/tmp/potato_inspection_system/data/test/project-3-at-2025-10-30-19-49-55a1bb93(1)/images/test" \
  --out /tmp/potato_inspection_system/results/grades
```
- 输出：
  - `results/grades/grades.jsonl` 每行一个样本：`{"image": 路径, "counts": {类别:数量}, "grade": "NG|OK_S1..OK_S7", "signal": {"bits":[8位], "bit_order":["L1".."L7","NG"], "lane":1..8}}`
  - `results/grades/grades.csv` 列：`image, grade, signal_bits(如10000000), counts_per_class_json`
- PLC 对接：8 位信号，前 7 位为 OK 的 7 个大小通道，最后一位为 NG 筛选通道。例：
  - `10000000` -> L1（OK_S1 最小）
  - `00000010` -> L7（OK_S7 最大）
  - `00000001` -> NG 通道
- 尺寸划分基于图像轮廓面积，阈值位于 `grading_rules.json > size.thresholds_px`，请按你的相机标定与目标物距进行调整。
- 支持视频流/摄像头实时处理：
```bash
# 摄像头（索引0）
python3 scripts/grade_potato.py \
  --model /tmp/potato_inspection_system/runs/yolov8s-obb-potato/weights/best.pt \
  --source 0 \
  --plc print

# 视频文件
python3 scripts/grade_potato.py \
  --model .../best.pt \
  --source video.mp4 \
  --plc modbus --modbus_host 192.168.1.100
```

### 8. PLC输出
- 支持三种模式：`print`（调试）、`modbus`（Modbus/TCP）、`serial`（RS232/485）
- 安装依赖（按需）：
```bash
pip install pymodbus  # Modbus/TCP
pip install pyserial   # 串口
```
- 使用示例：
```bash
# 从JSONL批量发送到PLC
python3 scripts/plc_output.py \
  --input /tmp/potato_inspection_system/results/grades/grades.jsonl \
  --method modbus \
  --modbus_host 192.168.1.100 \
  --modbus_port 502 \
  --modbus_address 0

# 串口模式
python3 scripts/plc_output.py \
  --input .../grades.jsonl \
  --method serial \
  --serial_port /dev/ttyUSB0 \
  --serial_baud 9600
```
- 实时模式：在 `grade_potato.py` 中加 `--plc modbus` 或 `--plc serial` 参数，每帧自动发送。

### 9. 注意
- `names` 顺序需与标注阶段一致（已根据 `classes.txt` 设置）
- 需要更大模型可将 `yolov8n-obb.pt` 改为 `yolov8s-obb.pt` 等
 - 可切换 train/val/test 比例并自动适配 YAML 路径


