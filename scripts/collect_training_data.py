#!/usr/bin/env python3
"""
训练数据采集脚本
用于批量采集土豆图像并记录元数据

作者: Seven & 哲豪
日期: 2025-10-22
"""

import cv2
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import time
import argparse


class TrainingDataCollector:
    """训练数据采集器"""
    
    def __init__(self, output_dir: str = "data/raw_images", 
                 use_simulated: bool = False):
        """
        初始化采集器
        
        Args:
            output_dir: 输出目录
            use_simulated: 是否使用模拟相机（用于测试）
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.use_simulated = use_simulated
        self.camera = None
        
        # 元数据存储
        self.metadata_file = self.output_dir / "collection_metadata.json"
        self.metadata = self.load_metadata()
        
        # 采集统计
        self.stats = {
            "session_start": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "images_collected": 0,
            "defect_samples": 0,
            "ok_samples": 0
        }
    
    def load_metadata(self) -> dict:
        """加载现有元数据"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                "collection_sessions": [],
                "images": []
            }
    
    def save_metadata(self):
        """保存元数据"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
    
    def initialize_camera(self):
        """初始化相机"""
        if self.use_simulated:
            print("📹 使用模拟相机（测试模式）")
            self.camera = "simulated"
            return True
        
        try:
            # 尝试连接工业相机
            # 这里应该是实际的相机SDK调用
            # 为了演示，使用OpenCV
            self.camera = cv2.VideoCapture(0)
            if self.camera.isOpened():
                print("📹 相机连接成功")
                # 设置分辨率
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 4096)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 3000)
                return True
            else:
                print("⚠️  无法打开相机，切换到模拟模式")
                self.use_simulated = True
                return True
        except Exception as e:
            print(f"⚠️  相机初始化失败: {e}")
            print("   切换到模拟模式")
            self.use_simulated = True
            return True
    
    def capture_image(self) -> np.ndarray:
        """
        采集一张图像
        
        Returns:
            图像数组
        """
        if self.use_simulated:
            # 生成模拟图像（用于测试）
            return self._generate_simulated_image()
        
        try:
            ret, frame = self.camera.read()
            if ret:
                return frame
            else:
                print("⚠️  采集失败，生成模拟图像")
                return self._generate_simulated_image()
        except Exception as e:
            print(f"⚠️  采集异常: {e}")
            return self._generate_simulated_image()
    
    def _generate_simulated_image(self) -> np.ndarray:
        """生成模拟土豆图像（用于测试）"""
        # 创建灰色背景
        img = np.ones((3000, 4096, 3), dtype=np.uint8) * 128
        
        # 随机生成土豆形状
        center_x = np.random.randint(1500, 2500)
        center_y = np.random.randint(1000, 2000)
        
        # 椭圆形土豆
        axes_x = np.random.randint(300, 600)
        axes_y = np.random.randint(200, 500)
        angle = np.random.randint(0, 180)
        
        # 土豆主体（浅黄色）
        color = (180, 200, 220)  # BGR
        cv2.ellipse(img, (center_x, center_y), (axes_x, axes_y), 
                   angle, 0, 360, color, -1)
        
        # 添加纹理
        noise = np.random.randint(-20, 20, img.shape, dtype=np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        # 随机添加缺陷
        if np.random.random() < 0.3:  # 30%概率有黑点
            num_spots = np.random.randint(1, 4)
            for _ in range(num_spots):
                spot_x = center_x + np.random.randint(-axes_x//2, axes_x//2)
                spot_y = center_y + np.random.randint(-axes_y//2, axes_y//2)
                spot_radius = np.random.randint(5, 15)
                cv2.circle(img, (spot_x, spot_y), spot_radius, (40, 40, 60), -1)
        
        return img
    
    def save_image(self, image: np.ndarray, category: str = "general",
                   weight: float = None, notes: str = "") -> str:
        """
        保存图像及元数据
        
        Args:
            image: 图像数组
            category: 类别 (defect/ok/boundary/grading)
            weight: 重量（克），如果已知
            notes: 备注信息
        
        Returns:
            保存的文件路径
        """
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        image_id = f"{category}_{timestamp}"
        filename = f"{image_id}.jpg"
        
        # 创建分类目录
        category_dir = self.output_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存图像
        filepath = category_dir / filename
        cv2.imwrite(str(filepath), image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        # 记录元数据
        image_meta = {
            "image_id": image_id,
            "filename": filename,
            "category": category,
            "filepath": str(filepath),
            "timestamp": timestamp,
            "weight_g": weight,
            "notes": notes,
            "resolution": f"{image.shape[1]}x{image.shape[0]}",
            "size_bytes": filepath.stat().st_size
        }
        
        self.metadata["images"].append(image_meta)
        
        # 更新统计
        self.stats["images_collected"] += 1
        if category in ["defect", "ng"]:
            self.stats["defect_samples"] += 1
        elif category in ["ok", "grading"]:
            self.stats["ok_samples"] += 1
        
        return str(filepath)
    
    def interactive_collection(self):
        """交互式采集模式"""
        print("\n" + "="*60)
        print("🥔 土豆训练数据交互式采集")
        print("="*60)
        
        print("\n操作说明:")
        print("  [空格] - 采集图像")
        print("  [d] - 标记为缺陷样本")
        print("  [o] - 标记为OK样本")
        print("  [b] - 标记为边界样本")
        print("  [g] - 标记为分级样本（需输入重量）")
        print("  [q] - 退出")
        print("  [s] - 查看统计")
        print()
        
        if not self.initialize_camera():
            print("❌ 相机初始化失败")
            return
        
        # 创建显示窗口
        window_name = "Training Data Collection"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1024, 768)
        
        current_image = None
        current_category = "general"
        
        print("✓ 准备就绪，按空格键采集第一张图像...")
        
        while True:
            # 实时预览
            if current_image is None:
                preview = self.capture_image()
            else:
                preview = current_image.copy()
            
            # 在图像上显示信息
            preview_small = cv2.resize(preview, (1024, 768))
            info_text = f"Collected: {self.stats['images_collected']} | Category: {current_category}"
            cv2.putText(preview_small, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(preview_small, "Press [SPACE] to capture", (10, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
            
            cv2.imshow(window_name, preview_small)
            
            # 处理按键
            key = cv2.waitKey(100) & 0xFF
            
            if key == ord(' '):  # 空格 - 采集
                current_image = self.capture_image()
                print(f"\n📸 图像已采集")
                print("   选择类别: [d]缺陷 [o]OK品 [b]边界 [g]分级")
            
            elif key == ord('d'):  # 缺陷样本
                if current_image is not None:
                    notes = input("   缺陷描述 (黑点/凹坑/残皮/青斑/畸形): ").strip()
                    filepath = self.save_image(current_image, "defect", notes=notes)
                    print(f"   ✓ 缺陷样本已保存: {filepath}")
                    current_image = None
                else:
                    print("   ⚠️  请先采集图像")
            
            elif key == ord('o'):  # OK样本
                if current_image is not None:
                    weight_input = input("   重量(g) [可选]: ").strip()
                    weight = float(weight_input) if weight_input else None
                    filepath = self.save_image(current_image, "ok", weight=weight)
                    print(f"   ✓ OK样本已保存: {filepath}")
                    current_image = None
                else:
                    print("   ⚠️  请先采集图像")
            
            elif key == ord('b'):  # 边界样本
                if current_image is not None:
                    weight_input = input("   重量(g): ").strip()
                    weight = float(weight_input) if weight_input else None
                    notes = input("   边界说明 (如\"249g Level6-7边界\"): ").strip()
                    filepath = self.save_image(current_image, "boundary", 
                                             weight=weight, notes=notes)
                    print(f"   ✓ 边界样本已保存: {filepath}")
                    current_image = None
                else:
                    print("   ⚠️  请先采集图像")
            
            elif key == ord('g'):  # 分级样本
                if current_image is not None:
                    weight = float(input("   重量(g): ").strip())
                    level = self._weight_to_level(weight)
                    notes = f"Level {level}"
                    filepath = self.save_image(current_image, "grading", 
                                             weight=weight, notes=notes)
                    print(f"   ✓ 分级样本已保存 (Level {level}): {filepath}")
                    current_image = None
                else:
                    print("   ⚠️  请先采集图像")
            
            elif key == ord('s'):  # 统计
                self.print_stats()
            
            elif key == ord('q'):  # 退出
                print("\n退出采集...")
                break
        
        # 清理
        if self.camera and not self.use_simulated:
            self.camera.release()
        cv2.destroyAllWindows()
        
        # 保存元数据
        self.save_session_summary()
        self.save_metadata()
        
        print("\n✓ 采集完成！")
        self.print_stats()
    
    def batch_collection(self, count: int, interval: float = 2.0, 
                        category: str = "general"):
        """
        批量自动采集模式
        
        Args:
            count: 采集数量
            interval: 采集间隔（秒）
            category: 类别
        """
        print(f"\n🔄 批量采集模式: {count}张，间隔{interval}秒")
        
        if not self.initialize_camera():
            print("❌ 相机初始化失败")
            return
        
        for i in range(count):
            print(f"采集 {i+1}/{count}...", end=" ")
            
            image = self.capture_image()
            filepath = self.save_image(image, category)
            
            print(f"✓ 已保存: {filepath}")
            
            if i < count - 1:
                time.sleep(interval)
        
        # 清理
        if self.camera and not self.use_simulated:
            self.camera.release()
        
        self.save_session_summary()
        self.save_metadata()
        
        print("\n✓ 批量采集完成！")
        self.print_stats()
    
    def _weight_to_level(self, weight: float) -> int:
        """根据重量判定等级（方案C）"""
        if weight >= 500:
            return 1
        elif weight >= 450:
            return 2
        elif weight >= 400:
            return 3
        elif weight >= 350:
            return 4
        elif weight >= 300:
            return 5
        elif weight >= 250:
            return 6
        elif weight >= 150:
            return 7
        else:
            return 9  # NG
    
    def print_stats(self):
        """打印统计信息"""
        print("\n" + "="*60)
        print("📊 采集统计")
        print("="*60)
        print(f"会话开始时间: {self.stats['session_start']}")
        print(f"总采集数量: {self.stats['images_collected']}")
        print(f"  - 缺陷样本: {self.stats['defect_samples']}")
        print(f"  - OK样本: {self.stats['ok_samples']}")
        print("="*60 + "\n")
    
    def save_session_summary(self):
        """保存会话摘要"""
        session = {
            "start_time": self.stats['session_start'],
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "images_collected": self.stats['images_collected'],
            "defect_samples": self.stats['defect_samples'],
            "ok_samples": self.stats['ok_samples']
        }
        
        self.metadata["collection_sessions"].append(session)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='土豆训练数据采集工具')
    parser.add_argument('--mode', choices=['interactive', 'batch'], 
                       default='interactive',
                       help='采集模式: interactive(交互) 或 batch(批量)')
    parser.add_argument('--count', type=int, default=10,
                       help='批量模式下的采集数量')
    parser.add_argument('--interval', type=float, default=2.0,
                       help='批量模式下的采集间隔（秒）')
    parser.add_argument('--category', type=str, default='general',
                       help='批量模式下的类别')
    parser.add_argument('--output', type=str, default='data/raw_images',
                       help='输出目录')
    parser.add_argument('--simulated', action='store_true',
                       help='使用模拟相机（测试模式）')
    
    args = parser.parse_args()
    
    print("🥔 土豆训练数据采集工具")
    print("作者: Seven & 哲豪 | 日期: 2025-10-22")
    print("="*60 + "\n")
    
    # 创建采集器
    collector = TrainingDataCollector(
        output_dir=args.output,
        use_simulated=args.simulated
    )
    
    # 根据模式执行
    if args.mode == 'interactive':
        collector.interactive_collection()
    else:
        collector.batch_collection(
            count=args.count,
            interval=args.interval,
            category=args.category
        )


if __name__ == '__main__':
    main()

