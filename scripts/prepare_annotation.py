#!/usr/bin/env python3
"""
数据标注准备脚本
用于组织图像、创建标注任务、管理标注进度

作者: 哲豪
日期: 2025-10-22
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict
import json
from datetime import datetime
import yaml


class AnnotationManager:
    """标注任务管理器"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.data_dir = self.project_root / "data"
        self.annotation_dir = self.data_dir / "annotations"
        self.config_dir = self.project_root / "configs"
        
        # 加载标注规范
        self.load_annotation_guideline()
        
        # 标注进度文件
        self.progress_file = self.annotation_dir / "annotation_progress.json"
        self.progress = self.load_progress()
    
    def load_annotation_guideline(self):
        """加载标注规范"""
        guideline_path = self.config_dir / "annotation_guideline.yaml"
        try:
            with open(guideline_path, 'r', encoding='utf-8') as f:
                self.guideline = yaml.safe_load(f)
            print(f"✓ 标注规范加载成功")
        except FileNotFoundError:
            print(f"⚠ 未找到标注规范: {guideline_path}")
            self.guideline = {}
    
    def load_progress(self) -> Dict:
        """加载标注进度"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                "week1_target": 200,
                "week2_target": 500,
                "week3_target": 1000,
                "final_target": 2000,
                "current_annotated": 0,
                "batches": []
            }
    
    def save_progress(self):
        """保存标注进度"""
        self.annotation_dir.mkdir(parents=True, exist_ok=True)
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=2)
    
    def organize_images(self, source_dir: str, target_type: str = "raw"):
        """
        组织图像文件
        
        Args:
            source_dir: 原始图像目录
            target_type: 目标类型 (raw/defects/grading)
        """
        source_path = Path(source_dir)
        if not source_path.exists():
            print(f"❌ 源目录不存在: {source_dir}")
            return
        
        target_dir = self.data_dir / "raw_images" / target_type
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # 支持的图像格式
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        images = []
        for ext in image_extensions:
            images.extend(source_path.glob(f'*{ext}'))
            images.extend(source_path.glob(f'*{ext.upper()}'))
        
        print(f"\n📂 从 {source_dir} 组织图像...")
        print(f"   找到 {len(images)} 张图像")
        
        copied = 0
        for img_path in images:
            target_path = target_dir / img_path.name
            if not target_path.exists():
                shutil.copy2(img_path, target_path)
                copied += 1
        
        print(f"✓ 复制了 {copied} 张新图像到 {target_dir}")
        return copied
    
    def create_annotation_batch(self, batch_name: str, image_dir: str, 
                                batch_size: int = 100) -> Dict:
        """
        创建标注批次
        
        Args:
            batch_name: 批次名称 (如 "week1_batch1")
            image_dir: 图像目录
            batch_size: 批次大小
        
        Returns:
            批次信息字典
        """
        image_path = Path(image_dir)
        if not image_path.exists():
            print(f"❌ 图像目录不存在: {image_dir}")
            return {}
        
        # 获取所有图像
        images = list(image_path.glob('*.jpg')) + list(image_path.glob('*.png'))
        
        # 检查已标注的图像
        annotated_images = self._get_annotated_images()
        unannotated = [img for img in images if img.name not in annotated_images]
        
        print(f"\n📦 创建标注批次: {batch_name}")
        print(f"   总图像数: {len(images)}")
        print(f"   已标注: {len(annotated_images)}")
        print(f"   待标注: {len(unannotated)}")
        
        # 选择批次图像
        batch_images = unannotated[:batch_size]
        
        # 创建批次目录
        batch_dir = self.annotation_dir / batch_name
        batch_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建批次配置
        batch_info = {
            "batch_name": batch_name,
            "created_date": datetime.now().strftime("%Y-%m-%d"),
            "image_count": len(batch_images),
            "images": [img.name for img in batch_images],
            "annotation_tool": "LabelImg",
            "status": "pending",
            "annotator": "哲豪",
            "priority": self._determine_priority(batch_name)
        }
        
        # 保存批次信息
        batch_config_path = batch_dir / "batch_config.json"
        with open(batch_config_path, 'w', encoding='utf-8') as f:
            json.dump(batch_info, f, ensure_ascii=False, indent=2)
        
        # 创建图像列表文件
        image_list_path = batch_dir / "image_list.txt"
        with open(image_list_path, 'w', encoding='utf-8') as f:
            for img in batch_images:
                f.write(f"{img.resolve()}\n")
        
        # 更新进度
        self.progress["batches"].append(batch_info)
        self.save_progress()
        
        print(f"✓ 批次创建成功: {batch_dir}")
        print(f"   包含 {len(batch_images)} 张图像")
        print(f"\n📝 开始标注:")
        print(f"   labelimg {image_dir} {self.config_dir}/classes.txt")
        
        return batch_info
    
    def _determine_priority(self, batch_name: str) -> str:
        """确定批次优先级"""
        if "week1" in batch_name or "urgent" in batch_name:
            return "high"
        elif "boundary" in batch_name or "critical" in batch_name:
            return "high"
        elif "defect" in batch_name:
            return "medium"
        else:
            return "normal"
    
    def _get_annotated_images(self) -> List[str]:
        """获取已标注图像列表"""
        annotated = []
        
        # 检查各个标注目录
        label_dirs = [
            self.data_dir / "train" / "labels",
            self.data_dir / "val" / "labels",
            self.annotation_dir
        ]
        
        for label_dir in label_dirs:
            if label_dir.exists():
                for label_file in label_dir.glob('*.txt'):
                    # 假设图像文件与标注文件同名
                    image_name = label_file.stem + '.jpg'
                    annotated.append(image_name)
        
        return set(annotated)
    
    def create_classes_file(self):
        """创建类别文件（用于LabelImg）"""
        if not self.guideline:
            print("⚠ 未加载标注规范")
            return
        
        classes_path = self.config_dir / "classes.txt"
        
        # 从规范中提取缺陷类别
        defect_classes = self.guideline.get('annotation', {}).get('defect_classes', {})
        class_names = list(defect_classes.keys())
        
        with open(classes_path, 'w', encoding='utf-8') as f:
            for class_name in class_names:
                f.write(f"{class_name}\n")
        
        print(f"✓ 类别文件已创建: {classes_path}")
        print(f"   包含 {len(class_names)} 个缺陷类别:")
        for i, name in enumerate(class_names, 1):
            display_name = defect_classes[name].get('name', name)
            print(f"     {i}. {name} ({display_name})")
    
    def generate_annotation_checklist(self) -> str:
        """生成标注检查清单"""
        checklist = """
# 🥔 土豆质检标注检查清单

## Week 1 目标: 100-200张（优先典型缺陷）

### 标注前准备
- [ ] 安装LabelImg: `pip install labelimg`
- [ ] 熟悉标注规范: `configs/annotation_guideline.yaml`
- [ ] 准备类别文件: `configs/classes.txt`
- [ ] 理解缺陷判定标准

### 缺陷类别标注要求

#### 1. black_spot (黑点)
- [ ] 直径 > 5mm
- [ ] 颜色明显深于周围
- [ ] 边界清晰
- [ ] 每个黑点独立标注

#### 2. pit (凹坑)
- [ ] 深度 > 2mm (阴影可见)
- [ ] 面积 > 100mm²
- [ ] 标注框包含完整凹陷区域

#### 3. residual_peel (残皮)
- [ ] 面积 > 50mm²
- [ ] 颜色明显不同（褐色/黄色）
- [ ] 标注紧贴残皮边界

#### 4. green_spot (青斑) ⚠️ 直接NG
- [ ] 任何可见的绿色都要标注
- [ ] 特别注意浅绿色
- [ ] 芽眼周围重点检查

#### 5. deformation (畸形) ⚠️ 直接NG
- [ ] 长宽比 > 3:1 或 < 1:3
- [ ] 有突出尖角
- [ ] 多分叉、严重弯曲
- [ ] 标注整个土豆轮廓

### 标注质量检查
- [ ] 标注框紧贴缺陷边界（不过大或过小）
- [ ] 类别选择正确
- [ ] 无遗漏缺陷（每张图检查3遍）
- [ ] 小缺陷也要标注（≥5mm）
- [ ] 边界案例标注并备注

### 优先级样本（Week 1重点）
- [ ] 典型黑点样本: 20-30张
- [ ] 典型凹坑样本: 20-30张
- [ ] 典型残皮样本: 20-30张
- [ ] 青斑样本: 10-15张（全部标注）
- [ ] 畸形样本: 10-15张（含9@150+）
- [ ] 多缺陷样本: 20-30张（真实场景）
- [ ] 干净OK品: 20-30张（各级别）

### 边界案例（Week 1开始收集）
- [ ] 轻微黑点（4-6mm）
- [ ] 浅凹坑（1-3mm）
- [ ] 小面积残皮（30-60mm²）
- [ ] 浅色红斑（非青斑）
- [ ] 临界畸形（长宽比2.5-3.5）

### 分级标注（配合重量数据）
- [ ] Level 1 (500-550g): ≥15张
- [ ] Level 2 (450-500g): ≥15张
- [ ] Level 3 (400-450g): ≥15张
- [ ] Level 4 (350-400g): ≥15张
- [ ] Level 5 (300-350g): ≥15张
- [ ] Level 6 (250-300g): ≥15张
- [ ] Level 7 (150-250g): ≥15张
- [ ] NG品: ≥20张

### 标注流程
1. 启动LabelImg:
   ```bash
   labelimg data/raw_images configs/classes.txt
   ```

2. 快捷键:
   - `W`: 创建标注框
   - `D`: 下一张图
   - `A`: 上一张图
   - `Ctrl+S`: 保存
   - `Del`: 删除标注框

3. 保存格式: YOLO格式 (自动归一化)

4. 标注文件命名: 与图像同名 (.txt)

### 每日目标
- 第1天 (10/22): 30-40张（熟悉工具+典型样本）
- 第2天 (10/23): 40-50张（各类缺陷）
- 第3天 (10/24): 40-50张（边界样本+复杂场景）
- 第4天 (10/25): 30-40张（查漏补缺）
- 第5天 (10/26): 质量检查+整理

### 注意事项
⚠️ 标注时参考实物照片和Excel重量数据
⚠️ 遇到不确定的样本拍照记录，留待讨论
⚠️ 每标注50张休息10分钟（避免疲劳误判）
⚠️ 每天结束时更新标注进度

### 完成标志
- [ ] 达到Week 1目标（100-200张）
- [ ] 覆盖所有5类缺陷
- [ ] 覆盖所有7个尺寸级
- [ ] 质量检查通过（2人交叉验证）
- [ ] 标注文件格式正确
- [ ] 更新标注进度JSON

---
**更新日期**: 2025-10-22
**当前进度**: 0 / 200 (Week 1目标)
"""
        
        checklist_path = self.annotation_dir / "ANNOTATION_CHECKLIST.md"
        with open(checklist_path, 'w', encoding='utf-8') as f:
            f.write(checklist)
        
        print(f"✓ 标注检查清单已生成: {checklist_path}")
        return checklist
    
    def update_progress(self, batch_name: str, annotated_count: int, status: str = "in_progress"):
        """更新标注进度"""
        # 找到对应批次
        for batch in self.progress["batches"]:
            if batch["batch_name"] == batch_name:
                batch["annotated_count"] = annotated_count
                batch["status"] = status
                batch["updated_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        
        # 更新总进度
        total_annotated = sum(b.get("annotated_count", 0) for b in self.progress["batches"])
        self.progress["current_annotated"] = total_annotated
        
        self.save_progress()
        
        # 打印进度
        week1_target = self.progress["week1_target"]
        week1_progress = (total_annotated / week1_target) * 100 if week1_target > 0 else 0
        
        print(f"\n📊 标注进度更新")
        print(f"   批次: {batch_name}")
        print(f"   本批次: {annotated_count}")
        print(f"   总进度: {total_annotated} / {week1_target} ({week1_progress:.1f}%)")
        
        if week1_progress >= 100:
            print(f"   🎉 Week 1 目标达成!")
        elif week1_progress >= 75:
            print(f"   💪 快完成了，加油!")
        elif week1_progress >= 50:
            print(f"   ⚡ 进度过半，保持节奏!")
        
    def generate_progress_report(self) -> str:
        """生成进度报告"""
        total = self.progress["current_annotated"]
        week1_target = self.progress["week1_target"]
        
        report = f"""
# 🥔 标注进度报告

**更新时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 总体进度
- Week 1 目标: {week1_target}张
- 当前完成: {total}张
- 完成率: {(total/week1_target*100):.1f}%
- 剩余: {week1_target - total}张

## 批次详情
"""
        
        for i, batch in enumerate(self.progress["batches"], 1):
            status_icon = {
                "pending": "⏳",
                "in_progress": "🔄",
                "completed": "✅",
                "review": "🔍"
            }.get(batch.get("status", "pending"), "❓")
            
            report += f"""
### 批次 {i}: {batch['batch_name']}
- 状态: {status_icon} {batch.get('status', 'pending')}
- 图像数: {batch.get('image_count', 0)}
- 已标注: {batch.get('annotated_count', 0)}
- 创建日期: {batch.get('created_date', 'N/A')}
- 优先级: {batch.get('priority', 'normal')}
"""
        
        # 保存报告
        report_path = self.annotation_dir / "progress_report.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(report)
        print(f"\n✓ 进度报告已保存: {report_path}")
        
        return report


def main():
    """主函数"""
    print("🥔 土豆质检数据标注管理工具")
    print("作者: 哲豪 | 日期: 2025-10-22")
    print("="*60 + "\n")
    
    # 创建管理器
    manager = AnnotationManager()
    
    # 创建必要目录
    print("📁 初始化标注工作环境...")
    dirs_to_create = [
        "data/raw_images/defects",
        "data/raw_images/grading", 
        "data/raw_images/boundary_cases",
        "data/annotations",
        "data/train/images",
        "data/train/labels",
        "data/val/images",
        "data/val/labels",
        "data/test/images",
        "data/test/labels"
    ]
    
    for dir_path in dirs_to_create:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    print("✓ 目录结构创建完成\n")
    
    # 创建类别文件
    print("📝 创建标注类别文件...")
    manager.create_classes_file()
    print()
    
    # 生成标注检查清单
    print("📋 生成标注检查清单...")
    manager.generate_annotation_checklist()
    print()
    
    # 生成进度报告
    print("📊 生成标注进度报告...")
    manager.generate_progress_report()
    print()
    
    print("="*60)
    print("✅ 标注准备工作完成!")
    print("="*60)
    
    print("\n🎯 接下来的步骤:")
    print("  1. 查看标注规范: configs/annotation_guideline.yaml")
    print("  2. 查看检查清单: data/annotations/ANNOTATION_CHECKLIST.md")
    print("  3. 采集或准备图像数据")
    print("  4. 创建第一个标注批次:")
    print("     python scripts/prepare_annotation.py --create-batch week1_batch1")
    print("  5. 开始标注:")
    print("     labelimg data/raw_images configs/classes.txt")
    
    print("\n📌 Week 1 关键目标 (10/20-10/26):")
    print("  - 标注 100-200 张图像")
    print("  - 覆盖所有5类缺陷")
    print("  - 优先标注典型缺陷样本")
    print("  - 准备10/24客户会议材料")


if __name__ == '__main__':
    main()

