# 🥔 土豆质检分级系统 - 快速入门指南

**更新时间**: 2025-10-22  
**当前状态**: Week 1 开发中

---

## 📋 当前项目状态

### ✅ 已完成（可以立即使用）
- 系统架构与配置
- 分级标准分析工具
- 数据标注管理系统
- 数据采集工具
- 完整技术文档

### ⏳ 进行中
- 分级标准客户确认
- 训练数据采集与标注
- 模型训练（Week 2-3）

### 📅 计划中
- 系统集成与部署（Week 4-6）

---

## 🚀 5分钟快速上手

### 1. 查看项目文档
```bash
cd /tmp/potato_inspection_system

# 查看主README
cat README.md

# 查看Week 1工作总结
cat docs/WEEK1_SUMMARY.md

# 查看分级标准分析报告
cat docs/GRADING_ANALYSIS.md
```

### 2. 运行分级方案分析
```bash
# 生成三种分级方案对比分析
python scripts/analyze_grading_schemes.py

# 查看生成的图表
ls -lh outputs/grading_analysis/
# - weight_distribution_comparison.png (重量分布对比)
# - analysis_summary.json (分析摘要)
```

### 3. 准备数据标注工作
```bash
# 初始化标注环境
python scripts/prepare_annotation.py

# 查看标注检查清单
cat data/annotations/ANNOTATION_CHECKLIST.md

# 查看标注进度
cat data/annotations/progress_report.md
```

### 4. 数据采集（如果有相机）
```bash
# 交互式采集模式
python scripts/collect_training_data.py --mode interactive

# 批量采集模式（模拟相机）
python scripts/collect_training_data.py --mode batch --count 10 --simulated

# 指定输出目录
python scripts/collect_training_data.py --output data/raw_images/defects --simulated
```

---

## 📁 项目目录结构

```
potato_inspection_system/
├── configs/                      # 配置文件
│   ├── system_config.yaml       # 系统主配置 ⭐
│   ├── annotation_guideline.yaml # 标注规范 ⭐
│   └── classes.txt              # 缺陷类别定义
│
├── docs/                        # 文档
│   ├── WEEK1_SUMMARY.md         # Week 1 工作总结 ⭐
│   ├── GRADING_ANALYSIS.md      # 分级标准分析报告 ⭐
│   ├── CLIENT_PRESENTATION_OUTLINE.md # 客户沟通PPT大纲 ⭐
│   ├── TRAINING.md              # 模型训练指南
│   ├── DEPLOYMENT.md            # 部署指南
│   └── API.md                   # API文档
│
├── scripts/                     # 工具脚本
│   ├── analyze_grading_schemes.py  # 分级方案分析 ⭐
│   ├── prepare_annotation.py       # 标注管理 ⭐
│   ├── collect_training_data.py    # 数据采集 ⭐
│   ├── setup.sh                    # 环境安装
│   ├── start.sh                    # 启动系统
│   └── stop.sh                     # 停止系统
│
├── data/                        # 数据目录
│   ├── raw_images/              # 原始图像
│   ├── annotations/             # 标注文件
│   │   ├── ANNOTATION_CHECKLIST.md  # 标注检查清单 ⭐
│   │   └── progress_report.md       # 标注进度报告
│   ├── train/                   # 训练集
│   ├── val/                     # 验证集
│   └── test/                    # 测试集
│
├── outputs/                     # 输出结果
│   └── grading_analysis/        # 分级分析结果 ⭐
│       ├── weight_distribution_comparison.png
│       └── analysis_summary.json
│
├── src/                         # 源代码
│   ├── acquisition/             # 图像采集模块
│   ├── inference/               # 推理模块
│   ├── tracking/                # 追踪模块
│   ├── plc/                     # PLC通信模块
│   └── main.py                  # 主程序
│
├── models/                      # 模型文件（待训练）
├── logs/                        # 日志文件
├── captures/                    # 图像存证
│
├── README.md                    # 项目说明 ⭐
├── QUICKSTART.md                # 本文件 ⭐
└── requirements.txt             # 依赖包列表
```

**⭐ 标记的文件是当前最重要的文件**

---

## 🎯 Week 1 关键任务（10/20-10/26）

### 已完成 ✅
1. ✅ 系统架构搭建（Seven）
2. ✅ 分级标准分析报告（哲豪）
3. ✅ 数据标注准备工作（哲豪）
4. ✅ 客户沟通PPT大纲（哲豪）
5. ✅ 分析和采集工具开发（哲豪）

### 待完成（需要外部协调）⏳
1. ⏳ 制作正式PPT（10/23）
2. ⏳ 联系毛工取实物样本（10/23）
3. ⏳ 客户确认会议（10/24）
4. ⏳ 采集训练图像（10/25-26）
5. ⏳ 开始数据标注（10/25-26）

---

## 🔧 常用命令

### 查看系统配置
```bash
# 查看完整配置
cat configs/system_config.yaml

# 查看分级标准
grep -A 10 "grading:" configs/system_config.yaml

# 查看缺陷类别
cat configs/classes.txt
```

### 数据管理
```bash
# 查看数据采集元数据
cat data/raw_images/collection_metadata.json

# 查看标注进度
cat data/annotations/progress_report.md

# 统计已标注图像数量
find data/train/labels -name "*.txt" | wc -l
```

### 分析与报告
```bash
# 重新生成分级分析报告
python scripts/analyze_grading_schemes.py

# 更新标注进度报告
python scripts/prepare_annotation.py

# 查看Week 1总结
cat docs/WEEK1_SUMMARY.md
```

---

## 📊 分级标准（推荐方案C）

| 等级 | 重量范围 | 市场规格 | 通道编号 | 备注 |
|------|---------|---------|---------|------|
| Level 1 | 500-550g | 特大 | #1 | 50g跨度 |
| Level 2 | 450-500g | 大 | #2 | 50g跨度 |
| Level 3 | 400-450g | 中大 | #3 | 50g跨度 |
| Level 4 | 350-400g | 中 | #4 | 50g跨度 |
| Level 5 | 300-350g | 中小 | #5 | 50g跨度 |
| Level 6 | 250-300g | 小 | #6 | 50g跨度 |
| Level 7 | 150-250g | 特小 | #7 | 100g跨度 |
| NG | <150g或有缺陷 | 废料 | #8 | 不合格品 |

**方案优势**:
- 级间重叠率仅 3.5%
- 符合行业 50g 标准
- 视觉可区分性好
- 实施成本低

---

## 🏷️ 缺陷类别定义

### 1. black_spot (黑点)
- **判定标准**: 直径 > 5mm，颜色明显深于周围，边界清晰
- **NG阈值**: >3个黑点

### 2. pit (凹坑)
- **判定标准**: 深度 > 2mm，面积 > 100mm²
- **NG阈值**: 凹坑面积比 > 5%

### 3. residual_peel (残皮)
- **判定标准**: 面积 > 50mm²，颜色明显不同
- **NG阈值**: 残皮面积比 > 10%

### 4. green_spot (青斑) ⚠️
- **判定标准**: 任何可见的绿色
- **NG规则**: **直接判NG**（有毒，含龙葵碱）

### 5. deformation (畸形) ⚠️
- **判定标准**: 长宽比 > 3:1 或 < 1:3，有突出尖角
- **NG规则**: **直接判NG**

---

## 💻 开发环境设置

### 安装依赖
```bash
# 基础依赖
pip install numpy opencv-python pillow pyyaml

# 数据分析
pip install pandas matplotlib seaborn

# 深度学习（Week 2需要）
pip install torch torchvision ultralytics

# 完整依赖
pip install -r requirements.txt
```

### 配置系统
```bash
# 复制配置模板
cp configs/system_config.yaml.example configs/system_config.yaml

# 编辑配置（根据实际情况）
vim configs/system_config.yaml
```

---

## 📝 标注工作流程

### Step 1: 准备工作
```bash
# 安装标注工具
pip install labelimg

# 查看标注规范
cat configs/annotation_guideline.yaml

# 查看检查清单
cat data/annotations/ANNOTATION_CHECKLIST.md
```

### Step 2: 开始标注
```bash
# 启动 LabelImg
labelimg data/raw_images/defects configs/classes.txt

# 快捷键:
# W - 创建标注框
# D - 下一张图
# A - 上一张图
# Ctrl+S - 保存
# Del - 删除标注框
```

### Step 3: 质量检查
- 标注框紧贴缺陷边界
- 类别选择正确
- 每张图检查3遍
- 小缺陷也要标注（≥5mm）

### Step 4: 更新进度
```bash
# 更新标注进度
python scripts/prepare_annotation.py
```

---

## 📞 团队协作

### 角色分工

**Seven** (系统集成负责人)
- 相机控制与图像采集
- PLC通信与信号输出
- 系统架构与性能优化
- 现场部署与调试

**哲豪** (算法负责人)
- 数据标注与管理
- 模型训练与优化
- 分级标准分析
- 算法性能评估

### 沟通机制
- 每日同步进度（早会10分钟）
- 问题随时沟通（微信/邮件）
- 每周总结会（周五下午）
- 文档及时更新（Git提交）

---

## 🔍 常见问题

### Q1: 如何查看当前进度？
```bash
# 查看 Week 1 总结
cat docs/WEEK1_SUMMARY.md

# 查看标注进度
cat data/annotations/progress_report.md

# 查看TODO列表
# （在代码仓库的TODO管理中）
```

### Q2: 分级标准还没确认怎么办？
目前推荐方案C，等待客户确认（计划10/24会议）。在此之前：
- 可以先按方案C标注数据
- 如客户要求调整，后续批量更新标注

### Q3: 没有实际图像数据怎么办？
当前可以：
1. 使用模拟模式测试工具：`--simulated`
2. 联系毛工取留存实物拍摄
3. 等待现场采集安排

### Q4: 如何贡献代码和文档？
1. 遵循现有目录结构
2. 更新相关文档
3. 提交前运行测试
4. 编写清晰的注释

---

## 📈 项目里程碑

| 日期 | 里程碑 | 状态 |
|------|--------|------|
| 10/26 | 分级标准确认方案输出 | ✅ 已完成 |
| 11/02 | 客户确认最终分级标准 | ⏳ 准备中 |
| 11/09 | 模型v1.0训练完成 | ⏳ 计划中 |
| 11/16 | 模型v2.0部署就绪 | ⏳ 计划中 |
| 11/23 | 全流程联调通过 | ⏳ 计划中 |
| 11/30 | 现场验收通过 | 🎯 最终目标 |

---

## 🎓 学习资源

### 内部文档
- `docs/TRAINING.md` - 模型训练详细指南
- `docs/DEPLOYMENT.md` - 系统部署手册
- `docs/API.md` - API接口文档

### 外部资源
- YOLOv8官方文档: https://docs.ultralytics.com/
- LabelImg使用教程: https://github.com/tzutalin/labelImg
- OpenCV教程: https://docs.opencv.org/

---

## 🆘 获取帮助

### 问题反馈
1. 查看相关文档（docs/目录）
2. 检查配置文件（configs/目录）
3. 查看日志文件（logs/目录）
4. 联系项目负责人

### 联系方式
- **Seven**: 系统集成、硬件、部署问题
- **哲豪**: 算法、标注、模型问题

---

## 📄 重要文件速查

| 文件 | 用途 | 何时查看 |
|------|------|---------|
| `README.md` | 项目总览 | 首次了解项目 |
| `QUICKSTART.md` | 本文件 | 快速上手 |
| `docs/WEEK1_SUMMARY.md` | Week 1总结 | 了解当前进度 |
| `docs/GRADING_ANALYSIS.md` | 分级分析 | 准备客户会议 |
| `docs/CLIENT_PRESENTATION_OUTLINE.md` | PPT大纲 | 制作演示材料 |
| `configs/system_config.yaml` | 系统配置 | 调整参数 |
| `configs/annotation_guideline.yaml` | 标注规范 | 开始标注前 |
| `data/annotations/ANNOTATION_CHECKLIST.md` | 标注清单 | 标注过程中 |

---

## 🎯 下一步行动

### 立即可做
1. ✅ 熟悉项目结构和文档
2. ✅ 运行分析脚本查看效果
3. ✅ 了解标注规范和流程
4. ⏳ 准备客户会议材料

### 等待协调
1. ⏳ 客户会议时间确认
2. ⏳ 实物样本获取
3. ⏳ 现场数据采集安排

### Week 2准备
1. 📅 模型训练环境搭建
2. 📅 500张标注目标规划
3. 📅 多通道追踪方案设计

---

**祝工作顺利！有问题随时沟通 💪**

---

*最后更新: 2025-10-22 by 哲豪*
