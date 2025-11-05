#!/usr/bin/env python3
"""
相机测试脚本
用于测试相机连接和图像采集
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import cv2
import time
from utils.logger import init_logger, get_logger
from utils.config_loader import init_config
from acquisition.camera import CameraManager

# 初始化
init_logger(log_dir="../logs", level="INFO")
logger = get_logger()

init_config("../configs/system_config.yaml")

def test_camera():
    """测试相机"""
    logger.info("=" * 60)
    logger.info("相机测试")
    logger.info("=" * 60)
    
    # 创建相机管理器
    camera_mgr = CameraManager()
    
    # 初始化
    if not camera_mgr.initialize():
        logger.error("相机初始化失败")
        return False
    
    logger.info("相机初始化成功，开始采集测试...")
    
    # 采集10帧
    for i in range(10):
        logger.info(f"采集第 {i+1} 帧...")
        
        start_time = time.time()
        image = camera_mgr.capture()
        elapsed = (time.time() - start_time) * 1000
        
        if image is None:
            logger.error("采集失败")
            continue
        
        logger.info(f"采集成功: shape={image.shape}, 耗时={elapsed:.2f}ms")
        
        # 保存图像
        filepath = camera_mgr.save_image(image, "../captures/test", f"test_{i}")
        logger.info(f"图像已保存: {filepath}")
        
        # 显示图像（可选）
        if os.environ.get('DISPLAY'):
            # 缩放显示
            scale = 0.3
            h, w = image.shape[:2]
            resized = cv2.resize(image, (int(w*scale), int(h*scale)))
            cv2.imshow("Camera Test", resized)
            cv2.waitKey(500)
        
        time.sleep(0.5)
    
    # 关闭
    if os.environ.get('DISPLAY'):
        cv2.destroyAllWindows()
    
    camera_mgr.shutdown()
    
    logger.info("=" * 60)
    logger.info("相机测试完成")
    logger.info("=" * 60)
    
    return True

if __name__ == "__main__":
    success = test_camera()
    sys.exit(0 if success else 1)

