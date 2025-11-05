#!/usr/bin/env python3
"""
基于实际检测的土豆尺寸分析脚本
使用OCR识别照片中的尺寸标注，结合计算机视觉检测实际土豆区域
"""

import os
import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import json
import re
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

# 尝试导入OCR库
try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    print("警告: pytesseract未安装，将使用文件名解析作为备选方案")
    OCR_AVAILABLE = False

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class AccuratePotatoAnalyzer:
    """基于实际检测的土豆分析器"""
    
    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
        self.results = {}
        self.image_features = []
        self.ocr_available = OCR_AVAILABLE
        
        # 分级方案定义（基于实际检测结果）
        self.scheme_c = {
            "name": "方案C（50g重量跨度）",
            "levels": {
                "Level 1": {"weight_range": (500, 550), "span": 50},
                "Level 2": {"weight_range": (450, 500), "span": 50},
                "Level 3": {"weight_range": (400, 450), "span": 50},
                "Level 4": {"weight_range": (350, 400), "span": 50},
                "Level 5": {"weight_range": (300, 350), "span": 50},
                "Level 6": {"weight_range": (250, 300), "span": 50},
                "Level 7": {"weight_range": (150, 250), "span": 100},
                "NG": {"weight_range": (0, 150), "span": 150}
            }
        }
    
    def extract_text_from_image(self, image_path: str) -> str:
        """从图像中提取文本（OCR）"""
        if not self.ocr_available:
            return ""
        
        try:
            # 读取图像
            img = cv2.imread(image_path)
            if img is None:
                return ""
            
            # 转换为灰度图
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 图像预处理以提高OCR准确率
            # 1. 高斯模糊去噪
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # 2. 自适应阈值二值化
            thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
            
            # 3. 形态学操作
            kernel = np.ones((2, 2), np.uint8)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # 使用OCR提取文本
            text = pytesseract.image_to_string(thresh, config='--psm 6')
            return text.strip()
            
        except Exception as e:
            print(f"OCR处理失败 {image_path}: {e}")
            return ""
    
    def parse_weight_from_text(self, text: str) -> Optional[float]:
        """从OCR文本中解析重量信息"""
        if not text:
            return None
        
        # 查找重量模式：数字+g, 数字g, 数字克等
        patterns = [
            r'(\d+(?:\.\d+)?)\s*g',  # 数字+g
            r'(\d+(?:\.\d+)?)\s*克',  # 数字+克
            r'(\d+(?:\.\d+)?)\s*gram',  # 数字+gram
            r'(\d+(?:\.\d+)?)\s*G',  # 数字+G
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    weight = float(match.group(1))
                    # 过滤明显不合理的重量值
                    if 10 <= weight <= 1000:  # 合理重量范围
                        return weight
                except ValueError:
                    continue
        
        return None
    
    def parse_weight_from_filename(self, filename: str) -> Optional[float]:
        """从文件名中解析重量信息（备选方案）"""
        # 文件名格式: Pic_2025_10_21_153839_10.jpeg
        # 文件夹名格式: 100-150 OK, 200-250 ng 等
        
        # 从文件夹名解析重量范围
        folder_name = Path(filename).parent.name
        weight_match = re.search(r'(\d+)-(\d+)', folder_name)
        if weight_match:
            min_weight = int(weight_match.group(1))
            max_weight = int(weight_match.group(2))
            # 返回范围中点作为估算重量
            return (min_weight + max_weight) / 2
        
        return None
    
    def detect_potato_regions(self, image_path: str) -> List[Dict]:
        """检测图像中的土豆区域"""
        try:
            # 读取图像
            img = cv2.imread(image_path)
            if img is None:
                return []
            
            # 转换为HSV颜色空间
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # 创建土豆颜色掩码（棕色/黄色范围）
            # 调整颜色范围以更好地检测土豆
            lower_brown1 = np.array([10, 50, 50])
            upper_brown1 = np.array([30, 255, 255])
            lower_brown2 = np.array([0, 30, 30])
            upper_brown2 = np.array([20, 255, 255])
            
            mask1 = cv2.inRange(hsv, lower_brown1, upper_brown1)
            mask2 = cv2.inRange(hsv, lower_brown2, upper_brown2)
            mask = cv2.bitwise_or(mask1, mask2)
            
            # 形态学操作去除噪声
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # 查找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            potato_regions = []
            for contour in contours:
                area = cv2.contourArea(contour)
                # 过滤太小的区域
                if area < 1000:  # 最小面积阈值
                    continue
                
                # 计算轮廓特征
                perimeter = cv2.arcLength(contour, True)
                
                # 拟合椭圆
                if len(contour) >= 5:
                    ellipse = cv2.fitEllipse(contour)
                    (center, axes, angle) = ellipse
                    major_axis = max(axes)
                    minor_axis = min(axes)
                else:
                    major_axis = minor_axis = 0
                
                # 计算圆形度
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                else:
                    circularity = 0
                
                # 计算边界框
                x, y, w, h = cv2.boundingRect(contour)
                
                # 估算体积和重量
                # 假设图像中1像素 = 0.1mm = 0.01cm
                pixel_to_cm = 0.01
                major_axis_cm = major_axis * pixel_to_cm
                minor_axis_cm = minor_axis * pixel_to_cm
                thickness_cm = minor_axis_cm / 2
                
                estimated_volume = (4/3) * np.pi * (major_axis_cm/2) * (minor_axis_cm/2) * thickness_cm
                density = 1.10  # g/cm³
                estimated_weight = estimated_volume * density
                
                potato_regions.append({
                    'area': area,
                    'perimeter': perimeter,
                    'major_axis': major_axis,
                    'minor_axis': minor_axis,
                    'circularity': circularity,
                    'width': w,
                    'height': h,
                    'estimated_volume': estimated_volume,
                    'estimated_weight': estimated_weight,
                    'aspect_ratio': major_axis / minor_axis if minor_axis > 0 else 0,
                    'center': center,
                    'contour': contour
                })
            
            # 按面积排序，返回最大的几个区域
            potato_regions.sort(key=lambda x: x['area'], reverse=True)
            return potato_regions[:3]  # 最多返回3个最大的土豆区域
            
        except Exception as e:
            print(f"土豆检测失败 {image_path}: {e}")
            return []
    
    def analyze_single_image(self, image_path: str) -> Dict:
        """分析单张图像"""
        try:
            # 1. OCR提取文本
            ocr_text = self.extract_text_from_image(image_path)
            ocr_weight = self.parse_weight_from_text(ocr_text)
            
            # 2. 从文件名解析重量（备选方案）
            filename_weight = self.parse_weight_from_filename(image_path)
            
            # 3. 检测土豆区域
            potato_regions = self.detect_potato_regions(image_path)
            
            # 4. 选择最佳重量值
            best_weight = None
            weight_source = "unknown"
            
            if ocr_weight is not None:
                best_weight = ocr_weight
                weight_source = "ocr"
            elif filename_weight is not None:
                best_weight = filename_weight
                weight_source = "filename"
            elif potato_regions:
                # 使用检测到的最大土豆区域的估算重量
                best_weight = potato_regions[0]['estimated_weight']
                weight_source = "detection"
            
            # 5. 解析文件夹信息
            folder_name = Path(image_path).parent.name
            parts = folder_name.split()
            
            if len(parts) >= 2:
                weight_range = parts[0]
                quality = parts[1]
                
                if '-' in weight_range:
                    min_weight, max_weight = map(int, weight_range.split('-'))
                else:
                    min_weight = max_weight = int(weight_range)
            else:
                weight_range = "unknown"
                quality = "unknown"
                min_weight = max_weight = 0
            
            # 6. 计算主要土豆特征（使用最大的土豆区域）
            main_potato = potato_regions[0] if potato_regions else {}
            
            result = {
                'file_path': str(image_path),
                'folder': folder_name,
                'weight_range': weight_range,
                'min_weight': min_weight,
                'max_weight': max_weight,
                'quality': quality,
                'is_ok': quality.upper() == 'OK',
                'ocr_text': ocr_text,
                'ocr_weight': ocr_weight,
                'filename_weight': filename_weight,
                'best_weight': best_weight,
                'weight_source': weight_source,
                'potato_count': len(potato_regions),
                'main_potato': main_potato
            }
            
            # 添加主要土豆的特征
            if main_potato:
                result.update({
                    'area': main_potato['area'],
                    'perimeter': main_potato['perimeter'],
                    'major_axis': main_potato['major_axis'],
                    'minor_axis': main_potato['minor_axis'],
                    'circularity': main_potato['circularity'],
                    'width': main_potato['width'],
                    'height': main_potato['height'],
                    'estimated_volume': main_potato['estimated_volume'],
                    'estimated_weight': main_potato['estimated_weight'],
                    'aspect_ratio': main_potato['aspect_ratio']
                })
            
            return result
            
        except Exception as e:
            print(f"图像分析失败 {image_path}: {e}")
            return None
    
    def load_and_analyze_data(self):
        """加载并分析所有图像数据"""
        print("开始基于实际检测的土豆分析...")
        print(f"OCR可用性: {self.ocr_available}")
        
        all_results = []
        
        for folder in self.data_path.iterdir():
            if folder.is_dir():
                print(f"处理文件夹: {folder.name}")
                
                for img_file in folder.glob("*.jpeg"):
                    result = self.analyze_single_image(str(img_file))
                    if result:
                        all_results.append(result)
        
        print(f"成功分析 {len(all_results)} 张图像")
        return pd.DataFrame(all_results)
    
    def classify_by_scheme_c(self, df: pd.DataFrame) -> pd.DataFrame:
        """使用方案C进行分类"""
        def classify_by_weight(row):
            weight = row['best_weight']
            if weight is None:
                return "Unknown"
            
            if weight >= 500:
                return "Level 1"
            elif weight >= 450:
                return "Level 2"
            elif weight >= 400:
                return "Level 3"
            elif weight >= 350:
                return "Level 4"
            elif weight >= 300:
                return "Level 5"
            elif weight >= 250:
                return "Level 6"
            elif weight >= 150:
                return "Level 7"
            else:
                return "NG"
        
        df['scheme_c_class'] = df.apply(classify_by_weight, axis=1)
        return df
    
    def calculate_accuracy_metrics(self, df: pd.DataFrame) -> Dict:
        """计算准确率指标"""
        # 基于文件夹标签计算准确率
        def get_expected_class(row):
            if row['is_ok']:
                # OK品根据重量范围分类
                avg_weight = (row['min_weight'] + row['max_weight']) / 2
                if avg_weight >= 500:
                    return "Level 1"
                elif avg_weight >= 450:
                    return "Level 2"
                elif avg_weight >= 400:
                    return "Level 3"
                elif avg_weight >= 350:
                    return "Level 4"
                elif avg_weight >= 300:
                    return "Level 5"
                elif avg_weight >= 250:
                    return "Level 6"
                elif avg_weight >= 150:
                    return "Level 7"
                else:
                    return "NG"
            else:
                return "NG"  # NG品统一为NG类
        
        df['expected_class'] = df.apply(get_expected_class, axis=1)
        
        # 计算准确率
        correct_predictions = (df['scheme_c_class'] == df['expected_class']).sum()
        total_predictions = len(df)
        accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
        
        return {
            'accuracy': accuracy,
            'correct_predictions': correct_predictions,
            'total_predictions': total_predictions,
            'confusion_matrix': pd.crosstab(df['expected_class'], df['scheme_c_class'], margins=True)
        }
    
    def generate_visualizations(self, df: pd.DataFrame):
        """生成可视化图表"""
        print("生成可视化图表...")
        
        output_dir = Path("/tmp/potato_inspection_system/results")
        output_dir.mkdir(exist_ok=True)
        
        # 1. 重量来源分布
        plt.figure(figsize=(12, 8))
        weight_sources = df['weight_source'].value_counts()
        plt.pie(weight_sources.values, labels=weight_sources.index, autopct='%1.1f%%')
        plt.title('重量信息来源分布')
        plt.savefig(output_dir / 'weight_source_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. 实际检测重量分布
        plt.figure(figsize=(12, 8))
        valid_weights = df[df['best_weight'].notna()]['best_weight']
        plt.hist(valid_weights, bins=30, alpha=0.7, edgecolor='black')
        plt.xlabel('检测重量 (g)')
        plt.ylabel('样本数量')
        plt.title('实际检测的土豆重量分布')
        plt.grid(True, alpha=0.3)
        plt.savefig(output_dir / 'detected_weight_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. 分类结果对比
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 文件夹标签分布
        folder_dist = df['weight_range'].value_counts().sort_index()
        axes[0, 0].bar(range(len(folder_dist)), folder_dist.values)
        axes[0, 0].set_title('文件夹标签分布')
        axes[0, 0].set_ylabel('样本数量')
        axes[0, 0].set_xticks(range(len(folder_dist)))
        axes[0, 0].set_xticklabels(folder_dist.index, rotation=45)
        
        # 检测分类结果
        class_dist = df['scheme_c_class'].value_counts()
        axes[0, 1].bar(class_dist.index, class_dist.values)
        axes[0, 1].set_title('检测分类结果')
        axes[0, 1].set_ylabel('样本数量')
        axes[0, 1].tick_params(axis='x', rotation=45)
        
        # 重量vs检测重量散点图
        valid_data = df[df['best_weight'].notna()]
        if len(valid_data) > 0:
            folder_avg_weights = valid_data.groupby('weight_range').agg({
                'min_weight': 'mean',
                'max_weight': 'mean'
            })
            folder_avg_weights['avg_weight'] = (folder_avg_weights['min_weight'] + folder_avg_weights['max_weight']) / 2
            
            colors = ['red' if not ok else 'green' for ok in valid_data['is_ok']]
            axes[1, 0].scatter(valid_data['best_weight'], 
                             valid_data['weight_range'].map(folder_avg_weights['avg_weight']), 
                             c=colors, alpha=0.6)
            axes[1, 0].set_xlabel('检测重量 (g)')
            axes[1, 0].set_ylabel('文件夹标签重量 (g)')
            axes[1, 0].set_title('检测重量 vs 标签重量 (红色=NG, 绿色=OK)')
            axes[1, 0].grid(True, alpha=0.3)
        
        # 准确率统计
        accuracy_metrics = self.calculate_accuracy_metrics(df)
        accuracy_data = [accuracy_metrics['accuracy']]
        axes[1, 1].bar(['方案C'], accuracy_data)
        axes[1, 1].set_title('检测准确率')
        axes[1, 1].set_ylabel('准确率')
        axes[1, 1].set_ylim(0, 1)
        
        plt.tight_layout()
        plt.savefig(output_dir / 'accurate_analysis_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"可视化图表已保存到 {output_dir}")
    
    def generate_accurate_report(self, df: pd.DataFrame):
        """生成基于实际检测的准确报告"""
        print("生成准确分析报告...")
        
        # 计算准确率指标
        accuracy_metrics = self.calculate_accuracy_metrics(df)
        
        # 统计重量来源
        weight_source_stats = df['weight_source'].value_counts()
        
        # 统计有效检测
        valid_detections = df[df['best_weight'].notna()]
        detection_rate = len(valid_detections) / len(df) if len(df) > 0 else 0
        
        report = f"""
# 基于实际检测的土豆分级分析报告

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**数据来源**: 1021文件夹土豆照片
**总样本数**: {len(df)}
**有效检测数**: {len(valid_detections)}
**检测成功率**: {detection_rate:.2%}

## 检测方法说明

### 重量信息来源
| 来源 | 样本数 | 占比 |
|------|--------|------|
"""
        
        for source, count in weight_source_stats.items():
            percentage = count / len(df) * 100
            report += f"| {source} | {count} | {percentage:.1f}% |\n"
        
        report += f"""

### 检测技术
1. **OCR文本识别**: 从照片中提取重量标注信息
2. **文件名解析**: 从文件夹名称解析重量范围
3. **计算机视觉检测**: 检测土豆区域并估算重量
4. **多源融合**: 优先使用OCR，备选文件名和视觉检测

## 实际检测结果

### 重量分布统计
"""
        
        if len(valid_detections) > 0:
            weight_stats = valid_detections['best_weight'].describe()
            report += f"""
| 统计量 | 数值 |
|--------|------|
| 平均值 | {weight_stats['mean']:.1f} g |
| 标准差 | {weight_stats['std']:.1f} g |
| 最小值 | {weight_stats['min']:.1f} g |
| 最大值 | {weight_stats['max']:.1f} g |
| 中位数 | {weight_stats['50%']:.1f} g |
"""
        
        report += f"""

### 分类结果
| 等级 | 样本数 | 占比 |
|------|--------|------|
"""
        
        class_dist = df['scheme_c_class'].value_counts()
        for class_name, count in class_dist.items():
            percentage = count / len(df) * 100
            report += f"| {class_name} | {count} | {percentage:.1f}% |\n"
        
        report += f"""

## 准确率分析

### 整体性能
- **检测成功率**: {detection_rate:.2%}
- **分类准确率**: {accuracy_metrics['accuracy']:.2%}
- **正确预测数**: {accuracy_metrics['correct_predictions']}
- **总预测数**: {accuracy_metrics['total_predictions']}

### 混淆矩阵
```
{accuracy_metrics['confusion_matrix']}
```

## 关键发现

### 1. 检测效果
- OCR识别成功率: {weight_source_stats.get('ocr', 0) / len(df) * 100:.1f}%
- 文件名解析成功率: {weight_source_stats.get('filename', 0) / len(df) * 100:.1f}%
- 视觉检测成功率: {weight_source_stats.get('detection', 0) / len(df) * 100:.1f}%

### 2. 重量分布
"""
        
        if len(valid_detections) > 0:
            # 按重量范围统计
            weight_ranges = {
                'Level 1 (500-550g)': len(valid_detections[(valid_detections['best_weight'] >= 500) & (valid_detections['best_weight'] < 550)]),
                'Level 2 (450-500g)': len(valid_detections[(valid_detections['best_weight'] >= 450) & (valid_detections['best_weight'] < 500)]),
                'Level 3 (400-450g)': len(valid_detections[(valid_detections['best_weight'] >= 400) & (valid_detections['best_weight'] < 450)]),
                'Level 4 (350-400g)': len(valid_detections[(valid_detections['best_weight'] >= 350) & (valid_detections['best_weight'] < 400)]),
                'Level 5 (300-350g)': len(valid_detections[(valid_detections['best_weight'] >= 300) & (valid_detections['best_weight'] < 350)]),
                'Level 6 (250-300g)': len(valid_detections[(valid_detections['best_weight'] >= 250) & (valid_detections['best_weight'] < 300)]),
                'Level 7 (150-250g)': len(valid_detections[(valid_detections['best_weight'] >= 150) & (valid_detections['best_weight'] < 250)]),
                'NG (<150g)': len(valid_detections[valid_detections['best_weight'] < 150])
            }
            
            for range_name, count in weight_ranges.items():
                percentage = count / len(valid_detections) * 100
                report += f"- {range_name}: {count} 个样本 ({percentage:.1f}%)\n"
        
        report += f"""

## 改进建议

### 1. OCR优化
- 提高图像预处理质量
- 调整OCR参数配置
- 增加文本区域检测

### 2. 视觉检测优化
- 改进颜色空间和阈值
- 增加形状特征分析
- 优化轮廓检测算法

### 3. 多源融合
- 建立权重分配机制
- 增加置信度评估
- 实现动态阈值调整

## 结论

基于实际检测的分析显示：
1. **检测成功率**: {detection_rate:.2%}
2. **分类准确率**: {accuracy_metrics['accuracy']:.2%}
3. **主要重量来源**: {weight_source_stats.index[0] if len(weight_source_stats) > 0 else 'Unknown'}

建议继续优化检测算法，提高OCR识别准确率，并建立更完善的多源融合机制。

---
*报告由准确土豆分析系统生成*
"""
        
        # 保存报告
        output_dir = Path("/tmp/potato_inspection_system/results")
        output_dir.mkdir(exist_ok=True)
        
        with open(output_dir / 'accurate_analysis_report.md', 'w', encoding='utf-8') as f:
            f.write(report)
        
        # 保存详细数据
        df.to_csv(output_dir / 'accurate_analysis_data.csv', index=False, encoding='utf-8')
        
        # 保存结果JSON
        results_data = {
            'detection_rate': detection_rate,
            'accuracy_metrics': accuracy_metrics,
            'weight_source_stats': weight_source_stats.to_dict(),
            'class_distribution': class_dist.to_dict()
        }
        
        with open(output_dir / 'accurate_analysis_results.json', 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"准确分析报告已保存到 {output_dir}")
        return report
    
    def run_accurate_analysis(self):
        """运行基于实际检测的准确分析"""
        print("开始基于实际检测的土豆分析...")
        
        # 1. 加载并分析数据
        df = self.load_and_analyze_data()
        if df.empty:
            print("错误: 没有找到有效的图像数据")
            return
        
        # 2. 进行分类
        df = self.classify_by_scheme_c(df)
        
        # 3. 生成可视化
        self.generate_visualizations(df)
        
        # 4. 生成报告
        report = self.generate_accurate_report(df)
        
        print("基于实际检测的分析完成！")
        return report

def main():
    """主函数"""
    data_path = "/tmp/potato_inspection_system/data/test/1021"
    
    analyzer = AccuratePotatoAnalyzer(data_path)
    report = analyzer.run_accurate_analysis()
    
    print("\n" + "="*50)
    print("基于实际检测的分析报告摘要:")
    print("="*50)
    print(report)

if __name__ == "__main__":
    main()
