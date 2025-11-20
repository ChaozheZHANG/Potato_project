# 快速开始指南（5分钟上手）

---

## 🚀 三步开始使用

### 第1步: 部署（首次）
```bash
cd potato_inspection_offline_v4
./deploy.sh
```
等待2-5分钟，自动安装完成。

### 第2步: 检测
```bash
./detect.sh test_images/
```

### 第3步: 查看结果
```bash
# 查看CSV
cat results/*/potatoes.csv | head -10

# 查看可视化图片
ls results/*/visualizations/
```

---

## 📊 输出结果说明

### CSV格式（给传感器团队）
```csv
potato_id,grade,signal_bits,lane
2025110513591101,OK_S7,00000010,7
2025110513591104,NG,00000001,8
```

**字段含义**:
- `potato_id`: 土豆唯一ID（16位）
- `grade`: 分级（OK_S1-S7 或 NG）
- `signal_bits`: 8位信号（控制8路通道）
- `lane`: 物理通道号（1-8）

### 可视化图片
- 每个土豆用旋转框标出
- 显示ID、分级、通道号
- 缺陷用不同颜色标注

---

## 💡 常用命令

```bash
# 检测单张图片
./detect.sh image.jpg

# 检测整个目录
./detect.sh /path/to/images/

# 调整检测灵敏度（降低阈值）
./detect.sh images/ 0.2

# 查看帮助
cat README.md
```

---

## 🎯 ID格式说明

```
2025110513591101
│      │ │ │└┴─ 计数01-60（循环）
│      │ │ └──── 秒59
│      │ └────── 分13时
│      └──────── 日05月11
└────────────── 年2025
```

**示例**:
- `2025110513591101` → 第1个土豆
- `2025110513591160` → 第60个土豆
- `2025110513591101` → 第61个（循环）
- `2025110513591201` → 下一秒第1个

---

## 📞 需要帮助？

- **部署问题**: 查看 `OFFLINE_DEPLOYMENT_GUIDE.md`
- **使用示例**: 查看 `USAGE_EXAMPLES.md`
- **传感器对接**: 查看 `docs/SENSOR_TEAM_QUICK_GUIDE.md`

---

**开始使用吧！** 🎉

