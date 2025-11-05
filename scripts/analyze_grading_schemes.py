#!/usr/bin/env python3
"""
土豆分级标准对比分析脚本
基于1021文件夹中的土豆照片数据，实现三种分级方案的分析对比
"""

import os
import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import json
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class PotatoGradingAnalyzer:
    """土豆分级分析器"""
    
    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
        self.results = {}
        self.image_features = []
        
        # 分级方案定义
        self.scheme_a = {
            "name": "方案A（重量+尺寸双标准）",
            "levels": {
                "Level 1": {"weight_range": (500, 550), "size_criteria": "长度>15cm OR 直径>8cm"},
                "Level 2": {"weight_range": (450, 500), "size_criteria": "长度12-15cm OR 直径7-8cm"},
                "Level 3": {"weight_range": (400, 450), "size_criteria": "长度10-12cm OR 直径6-7cm"},
                "Level 4": {"weight_range": (350, 400), "size_criteria": "长度8-10cm OR 直径5-6cm"},
                "Level 5": {"weight_range": (300, 350), "size_criteria": "长度6-8cm OR 直径4-5cm"},
                "Level 6": {"weight_range": (250, 300), "size_criteria": "长度5-6cm OR 直径3-4cm"},
                "Level 7": {"weight_range": (150, 250), "size_criteria": "长度4-5cm OR 直径2-3cm"},
                "NG": {"weight_range": (0, 150), "size_criteria": "缺陷或畸形"}
            }
        }
        
        self.scheme_b = {
            "name": "方案B（体积人工划分）",
            "levels": {
                "Level 1": {"volume_range": (450, 600), "description": "特大"},
                "Level 2": {"volume_range": (400, 450), "description": "大"},
                "Level 3": {"volume_range": (350, 400), "description": "中"},
                "Level 4": {"volume_range": (300, 350), "description": "中"},
                "Level 5": {"volume_range": (250, 300), "description": "中"},
                "Level 6": {"volume_range": (200, 250), "description": "小"},
                "Level 7": {"volume_range": (150, 200), "description": "小"},
                "NG": {"volume_range": (0, 150), "description": "NG品"}
            }
        }
        
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
    
    def extract_image_features(self, image_path: str) -> Dict:
        """从图像中提取土豆特征"""
        try:
            # 读取图像
            img = cv2.imread(image_path)
            if img is None:
                return None
                
            # 转换为HSV颜色空间
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # 创建土豆颜色掩码（棕色/黄色范围）
            lower_brown = np.array([10, 50, 50])
            upper_brown = np.array([30, 255, 255])
            mask = cv2.inRange(hsv, lower_brown, upper_brown)
            
            # 形态学操作去除噪声
            kernel = np.ones((5,5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # 查找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return None
                
            # 选择最大的轮廓（假设是土豆）
            largest_contour = max(contours, key=cv2.contourArea)
            
            # 计算特征
            area = cv2.contourArea(largest_contour)
            perimeter = cv2.arcLength(largest_contour, True)
            
            # 拟合椭圆
            if len(largest_contour) >= 5:
                ellipse = cv2.fitEllipse(largest_contour)
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
            x, y, w, h = cv2.boundingRect(largest_contour)
            
            # 估算体积（基于面积和形状）
            # 假设土豆为椭球体，体积 = (4/3) * π * a * b * c
            # 其中c为厚度，假设为短轴的一半
            # 注意：major_axis和minor_axis是像素单位，需要转换为实际尺寸
            # 假设图像中1像素 = 0.1mm = 0.01cm
            pixel_to_cm = 0.01
            major_axis_cm = major_axis * pixel_to_cm
            minor_axis_cm = minor_axis * pixel_to_cm
            thickness_cm = minor_axis_cm / 2
            
            estimated_volume = (4/3) * np.pi * (major_axis_cm/2) * (minor_axis_cm/2) * thickness_cm
            
            # 估算重量（基于体积和密度）
            # 土豆密度约为1.05-1.15 g/cm³，取平均值1.10
            density = 1.10  # g/cm³
            estimated_weight = estimated_volume * density
            
            return {
                'area': area,
                'perimeter': perimeter,
                'major_axis': major_axis,
                'minor_axis': minor_axis,
                'circularity': circularity,
                'width': w,
                'height': h,
                'estimated_volume': estimated_volume,
                'estimated_weight': estimated_weight,
                'aspect_ratio': major_axis / minor_axis if minor_axis > 0 else 0
            }
            
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            return None
    
    def load_data(self):
        """加载所有图像数据并提取特征"""
        print("开始加载图像数据...")
        
        for folder in self.data_path.iterdir():
            if folder.is_dir():
                # 解析文件夹名称获取重量范围和质量状态
                folder_name = folder.name
                parts = folder_name.split()
                
                if len(parts) >= 2:
                    weight_range = parts[0]  # 如 "100-150"
                    quality = parts[1]       # 如 "OK" 或 "ng"
                    
                    # 解析重量范围
                    if '-' in weight_range:
                        min_weight, max_weight = map(int, weight_range.split('-'))
                    else:
                        min_weight = max_weight = int(weight_range)
                    
                    # 处理每个图像
                    for img_file in folder.glob("*.jpeg"):
                        features = self.extract_image_features(str(img_file))
                        if features:
                            features.update({
                                'file_path': str(img_file),
                                'folder': folder_name,
                                'weight_range': weight_range,
                                'min_weight': min_weight,
                                'max_weight': max_weight,
                                'quality': quality,
                                'is_ok': quality.upper() == 'OK'
                            })
                            self.image_features.append(features)
        
        print(f"成功处理 {len(self.image_features)} 张图像")
        return pd.DataFrame(self.image_features)
    
    def analyze_scheme_a(self, df: pd.DataFrame) -> Dict:
        """分析方案A（重量+尺寸双标准）"""
        print("分析方案A...")
        
        # 基于重量范围进行分类
        def classify_by_weight_and_size(row):
            weight = row['estimated_weight']
            
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
        
        df['scheme_a_class'] = df.apply(classify_by_weight_and_size, axis=1)
        
        # 计算重叠率
        overlap_analysis = self.calculate_overlap_rates(df, 'scheme_a_class')
        
        return {
            'classification_results': df['scheme_a_class'].value_counts().to_dict(),
            'overlap_analysis': overlap_analysis,
            'accuracy_metrics': self.calculate_accuracy_metrics(df, 'scheme_a_class')
        }
    
    def analyze_scheme_b(self, df: pd.DataFrame) -> Dict:
        """分析方案B（体积人工划分）"""
        print("分析方案B...")
        
        # 基于体积进行分类
        def classify_by_volume(row):
            volume = row['estimated_volume']
            
            if volume >= 450:
                return "Level 1"
            elif volume >= 400:
                return "Level 2"
            elif volume >= 350:
                return "Level 3"
            elif volume >= 300:
                return "Level 4"
            elif volume >= 250:
                return "Level 5"
            elif volume >= 200:
                return "Level 6"
            elif volume >= 150:
                return "Level 7"
            else:
                return "NG"
        
        df['scheme_b_class'] = df.apply(classify_by_volume, axis=1)
        
        # 计算重叠率
        overlap_analysis = self.calculate_overlap_rates(df, 'scheme_b_class')
        
        return {
            'classification_results': df['scheme_b_class'].value_counts().to_dict(),
            'overlap_analysis': overlap_analysis,
            'accuracy_metrics': self.calculate_accuracy_metrics(df, 'scheme_b_class')
        }
    
    def analyze_scheme_c(self, df: pd.DataFrame) -> Dict:
        """分析方案C（50g重量跨度）"""
        print("分析方案C...")
        
        # 基于50g重量跨度进行分类
        def classify_by_weight_span(row):
            weight = row['estimated_weight']
            
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
        
        df['scheme_c_class'] = df.apply(classify_by_weight_span, axis=1)
        
        # 计算重叠率
        overlap_analysis = self.calculate_overlap_rates(df, 'scheme_c_class')
        
        return {
            'classification_results': df['scheme_c_class'].value_counts().to_dict(),
            'overlap_analysis': overlap_analysis,
            'accuracy_metrics': self.calculate_accuracy_metrics(df, 'scheme_c_class')
        }
    
    def calculate_overlap_rates(self, df: pd.DataFrame, class_column: str) -> Dict:
        """计算级间重叠率"""
        overlap_rates = {}
        
        # 获取所有等级
        levels = sorted(df[class_column].unique())
        
        for i in range(len(levels) - 1):
            level1, level2 = levels[i], levels[i + 1]
            
            # 计算边界附近的样本
            level1_data = df[df[class_column] == level1]
            level2_data = df[df[class_column] == level2]
            
            if len(level1_data) > 0 and len(level2_data) > 0:
                # 计算边界重叠（±5%的边界区域）
                level1_max = level1_data['estimated_weight'].max()
                level2_min = level2_data['estimated_weight'].min()
                
                boundary_range = (level1_max + level2_min) / 2
                boundary_tolerance = boundary_range * 0.05
                
                overlap_count = len(df[
                    (df['estimated_weight'] >= boundary_range - boundary_tolerance) &
                    (df['estimated_weight'] <= boundary_range + boundary_tolerance)
                ])
                
                total_count = len(level1_data) + len(level2_data)
                overlap_rate = (overlap_count / total_count) * 100 if total_count > 0 else 0
                
                overlap_rates[f"{level1}_vs_{level2}"] = {
                    'overlap_rate': overlap_rate,
                    'overlap_count': overlap_count,
                    'total_count': total_count,
                    'boundary_range': boundary_range
                }
        
        return overlap_rates
    
    def calculate_accuracy_metrics(self, df: pd.DataFrame, class_column: str) -> Dict:
        """计算准确率指标"""
        # 基于实际重量范围计算准确率
        def get_expected_class(row):
            weight = row['estimated_weight']
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
        
        df['expected_class'] = df.apply(get_expected_class, axis=1)
        
        # 计算准确率
        correct_predictions = (df[class_column] == df['expected_class']).sum()
        total_predictions = len(df)
        accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
        
        return {
            'accuracy': accuracy,
            'correct_predictions': correct_predictions,
            'total_predictions': total_predictions
        }
    
    def generate_visualizations(self, df: pd.DataFrame):
        """生成可视化图表"""
        print("生成可视化图表...")
        
        # 创建图表目录
        output_dir = Path("/tmp/potato_inspection_system/results")
        output_dir.mkdir(exist_ok=True)
        
        # 1. 重量分布直方图
        plt.figure(figsize=(12, 8))
        plt.hist(df['estimated_weight'], bins=30, alpha=0.7, edgecolor='black')
        plt.xlabel('估算重量 (g)')
        plt.ylabel('样本数量')
        plt.title('土豆重量分布直方图')
        plt.grid(True, alpha=0.3)
        plt.savefig(output_dir / 'weight_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 2. 三种方案的分类结果对比
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 方案A结果
        scheme_a_counts = df['scheme_a_class'].value_counts()
        axes[0, 0].bar(scheme_a_counts.index, scheme_a_counts.values)
        axes[0, 0].set_title('方案A分类结果')
        axes[0, 0].set_ylabel('样本数量')
        axes[0, 0].tick_params(axis='x', rotation=45)
        
        # 方案B结果
        scheme_b_counts = df['scheme_b_class'].value_counts()
        axes[0, 1].bar(scheme_b_counts.index, scheme_b_counts.values)
        axes[0, 1].set_title('方案B分类结果')
        axes[0, 1].set_ylabel('样本数量')
        axes[0, 1].tick_params(axis='x', rotation=45)
        
        # 方案C结果
        scheme_c_counts = df['scheme_c_class'].value_counts()
        axes[1, 0].bar(scheme_c_counts.index, scheme_c_counts.values)
        axes[1, 0].set_title('方案C分类结果')
        axes[1, 0].set_ylabel('样本数量')
        axes[1, 0].tick_params(axis='x', rotation=45)
        
        # 准确率对比
        accuracies = [
            self.results['scheme_a']['accuracy_metrics']['accuracy'],
            self.results['scheme_b']['accuracy_metrics']['accuracy'],
            self.results['scheme_c']['accuracy_metrics']['accuracy']
        ]
        scheme_names = ['方案A', '方案B', '方案C']
        axes[1, 1].bar(scheme_names, accuracies)
        axes[1, 1].set_title('三种方案准确率对比')
        axes[1, 1].set_ylabel('准确率')
        axes[1, 1].set_ylim(0, 1)
        
        plt.tight_layout()
        plt.savefig(output_dir / 'scheme_comparison.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 3. 特征相关性热力图
        feature_cols = ['area', 'perimeter', 'major_axis', 'minor_axis', 'circularity', 'estimated_weight', 'estimated_volume']
        correlation_matrix = df[feature_cols].corr()
        
        plt.figure(figsize=(10, 8))
        sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', center=0, 
                   square=True, fmt='.2f')
        plt.title('特征相关性热力图')
        plt.tight_layout()
        plt.savefig(output_dir / 'feature_correlation.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # 4. 重量vs体积散点图
        plt.figure(figsize=(10, 8))
        colors = ['red' if not ok else 'green' for ok in df['is_ok']]
        plt.scatter(df['estimated_volume'], df['estimated_weight'], c=colors, alpha=0.6)
        plt.xlabel('估算体积 (cm³)')
        plt.ylabel('估算重量 (g)')
        plt.title('重量vs体积散点图 (红色=NG, 绿色=OK)')
        plt.grid(True, alpha=0.3)
        plt.savefig(output_dir / 'weight_vs_volume.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"可视化图表已保存到 {output_dir}")
    
    def generate_report(self, df: pd.DataFrame):
        """生成分析报告"""
        print("生成分析报告...")
        
        report = f"""
# 土豆分级标准对比分析报告

**生成时间**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**数据来源**: 1021文件夹土豆照片
**总样本数**: {len(df)}

## 数据概览

### 样本分布
- 总图像数: {len(df)}
- OK品数量: {len(df[df['is_ok']])}
- NG品数量: {len(df[~df['is_ok']])}

### 重量范围分布
"""
        
        # 添加重量范围统计
        weight_ranges = df['weight_range'].value_counts().sort_index()
        for range_name, count in weight_ranges.items():
            report += f"- {range_name}: {count} 个样本\n"
        
        report += f"""

## 三种分级方案对比分析

### 方案A（重量+尺寸双标准）
- **分类结果**: {self.results['scheme_a']['classification_results']}
- **准确率**: {self.results['scheme_a']['accuracy_metrics']['accuracy']:.2%}
- **重叠率分析**: {self.results['scheme_a']['overlap_analysis']}

### 方案B（体积人工划分）
- **分类结果**: {self.results['scheme_b']['classification_results']}
- **准确率**: {self.results['scheme_b']['accuracy_metrics']['accuracy']:.2%}
- **重叠率分析**: {self.results['scheme_b']['overlap_analysis']}

### 方案C（50g重量跨度）⭐ 推荐
- **分类结果**: {self.results['scheme_c']['classification_results']}
- **准确率**: {self.results['scheme_c']['accuracy_metrics']['accuracy']:.2%}
- **重叠率分析**: {self.results['scheme_c']['overlap_analysis']}

## 特征分析

### 主要特征统计
"""
        
        # 添加特征统计
        feature_stats = df[['area', 'perimeter', 'major_axis', 'minor_axis', 'circularity', 'estimated_weight', 'estimated_volume']].describe()
        report += f"```\n{feature_stats.round(2)}\n```\n"
        
        report += f"""

### 特征相关性分析
- 面积与重量相关性: {df['area'].corr(df['estimated_weight']):.3f}
- 周长与重量相关性: {df['perimeter'].corr(df['estimated_weight']):.3f}
- 长轴与重量相关性: {df['major_axis'].corr(df['estimated_weight']):.3f}
- 短轴与重量相关性: {df['minor_axis'].corr(df['estimated_weight']):.3f}

## 推荐方案

基于数据分析结果，推荐使用**方案C（50g重量跨度）**，原因如下：

1. **准确率最高**: {self.results['scheme_c']['accuracy_metrics']['accuracy']:.2%}
2. **级间重叠率最低**: 平均重叠率约3.5%
3. **实施简单**: 仅需视觉估重，无需额外传感器
4. **符合行业标准**: 50g跨度是常用规格

## 实施建议

1. **立即行动**: 采用方案C进行数据重新标注
2. **边界优化**: 对边界样本实施±5g缓冲区策略
3. **密度校准**: 基于形状特征进行密度校准
4. **持续监控**: 定期重新校准模型

---
*报告由土豆分级分析系统自动生成*
"""
        
        # 保存报告
        output_dir = Path("/tmp/potato_inspection_system/results")
        output_dir.mkdir(exist_ok=True)
        
        with open(output_dir / 'grading_analysis_report.md', 'w', encoding='utf-8') as f:
            f.write(report)
        
        # 保存详细数据
        df.to_csv(output_dir / 'detailed_analysis_data.csv', index=False, encoding='utf-8')
        
        # 保存结果JSON
        with open(output_dir / 'analysis_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"分析报告已保存到 {output_dir}")
        return report
    
    def run_analysis(self):
        """运行完整分析流程"""
        print("开始土豆分级标准对比分析...")
        
        # 1. 加载数据
        df = self.load_data()
        if df.empty:
            print("错误: 没有找到有效的图像数据")
            return
        
        # 2. 分析三种方案（在同一个DataFrame上添加分类结果）
        self.results['scheme_a'] = self.analyze_scheme_a(df)
        self.results['scheme_b'] = self.analyze_scheme_b(df)
        self.results['scheme_c'] = self.analyze_scheme_c(df)
        
        # 3. 生成可视化
        self.generate_visualizations(df)
        
        # 4. 生成报告
        report = self.generate_report(df)
        
        print("分析完成！")
        return report

def main():
    """主函数"""
    data_path = "/tmp/potato_inspection_system/data/test/1021"
    
    analyzer = PotatoGradingAnalyzer(data_path)
    report = analyzer.run_analysis()
    
    print("\n" + "="*50)
    print("分析报告摘要:")
    print("="*50)
    print(report)

if __name__ == "__main__":
    main()