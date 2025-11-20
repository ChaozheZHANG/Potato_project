# 马铃薯分级系统 - 离线部署包 v4

**版本**: v4.0  
**模型**: YOLOv8s-OBB-v22（包含potato标签）  
**适用**: 离线工控机/边缘计算设备

---

## 📦 包含内容

```
potato_inspection_offline_v4/
├── models/
│   └── yolov8s-obb-potato-v22_best.pt  (23MB) - 训练好的模型
├── scripts/
│   ├── grade_with_potato_label.py      - 批量检测脚本
│   └── grade_potato_realtime.py        - 实时跟踪脚本
├── config/
│   └── grading_rules.json              - 分级规则配置
├── docs/
│   ├── SENSOR_TEAM_QUICK_GUIDE.md      - 传感器对接手册
│   └── OUTPUT_FORMAT_FINAL.md          - 输出格式文档
├── test_images/                        - 测试图片(12张)
├── requirements.txt                    - Python依赖
├── deploy.sh                           - 自动部署脚本
├── detect.sh                           - 快速检测脚本
├── example_detect.py                   - Python示例代码
└── README.md                           - 本文档
```

---

## 🚀 快速开始（3步）

### 步骤1: 部署（首次运行）
```bash
cd potato_inspection_offline_v4
./deploy.sh
```
这会自动创建虚拟环境并安装依赖。

### 步骤2: 运行检测
```bash
./detect.sh test_images/
```

### 步骤3: 查看结果
```bash
# 结果保存在 results/时间戳/ 目录
ls results/*/potatoes.csv
cat results/*/potatoes.csv | head -5
```

---

## 💻 使用方法

### 方法1: Shell脚本（最简单）
```bash
# 检测单张图片
./detect.sh /path/to/potato.jpg

# 检测整个目录
./detect.sh /path/to/images/

# 调整置信度
./detect.sh /path/to/images/ 0.3
```

### 方法2: Python脚本
```bash
# 激活环境
source venv/bin/activate

# 运行检测
python3 scripts/grade_with_potato_label.py \
    --model models/yolov8s-obb-potato-v22_best.pt \
    --source /path/to/images \
    --out results/my_output \
    --conf 0.25
```

### 方法3: Python代码调用
```python
# 使用 example_detect.py
python3 example_detect.py /path/to/potato.jpg
```

---

## 📊 输出格式

### CSV文件（potatoes.csv）
```csv
potato_id,image,bbox_json,area,grade,signal_bits,lane,total_defects,defect_counts_json
2025110513591101,img.jpg,"[x,y,w,h]",321103,OK_S7,00000010,7,3,"{""black_spots"":2,...}"
```

### 关键字段
- **potato_id**: 16位唯一ID（年月日时分秒+01-60）
- **grade**: OK_S1-S7 或 NG
- **signal_bits**: 8位二进制（控制8路通道）
- **lane**: 物理通道号（1-8）
- **defect_counts_json**: 缺陷统计

### 可视化图片
- 每张图片生成 `*_labeled.jpg`
- 显示土豆ID、分级、缺陷标注

---

## ⚙️ 配置调整

### 修改分级规则
编辑 `config/grading_rules.json`:
```json
{
  "ok_rules": {
    "max_counts": {
      "black_spots": 2,
      "red_spots": 3,
      "scabs": 1
    },
    "forbid": ["deformities", "pits", "greenish_spots"]
  }
}
```

### 调整检测置信度
```bash
# 降低阈值（检测更多，可能误检）
./detect.sh images/ 0.2

# 提高阈值（更准确，可能漏检）
./detect.sh images/ 0.4
```

---

## 🔧 系统要求

### 硬件
- **CPU**: 4核及以上（推荐8核）
- **内存**: 8GB及以上
- **存储**: 500MB可用空间
- **GPU**: 可选（NVIDIA显卡可加速10倍）

### 软件
- **操作系统**: Linux (Ubuntu 18.04+) 或 Windows 10+
- **Python**: 3.8-3.12
- **依赖**: ultralytics, opencv-python, numpy

---

## 📞 故障排查

### 问题1: 模型加载失败
```bash
# 检查模型文件
ls -lh models/yolov8s-obb-potato-v22_best.pt
# 应该显示 23MB
```

### 问题2: 检测不到土豆
```bash
# 降低置信度
./detect.sh images/ 0.15
```

### 问题3: 依赖安装失败
```bash
# 手动安装
source venv/bin/activate
pip install ultralytics opencv-python numpy
```

---

## 📖 完整文档

- `docs/SENSOR_TEAM_QUICK_GUIDE.md` - 传感器对接手册
- `docs/OUTPUT_FORMAT_FINAL.md` - 输出格式详解
- `OFFLINE_DEPLOYMENT_GUIDE.md` - 完整部署指南

---

## ✅ 验证部署

运行测试检测：
```bash
./detect.sh test_images/
```

应该输出：
- 检测到44个土豆
- 生成CSV和JSONL文件
- 生成12张可视化图片

---

**系统已准备就绪，可直接部署到离线设备！** 🎉

