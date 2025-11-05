#!/usr/bin/env python3
"""
PLC通信测试脚本
用于测试PLC连接和信号发送
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
from utils.logger import init_logger, get_logger
from utils.config_loader import init_config
from plc.communication import PLCManager

# 初始化
init_logger(log_dir="../logs", level="INFO")
logger = get_logger()

init_config("../configs/system_config.yaml")

def test_plc():
    """测试PLC"""
    logger.info("=" * 60)
    logger.info("PLC通信测试")
    logger.info("=" * 60)
    
    # 创建PLC管理器
    plc_mgr = PLCManager()
    
    # 初始化
    if not plc_mgr.initialize():
        logger.error("PLC初始化失败")
        return False
    
    logger.info("PLC初始化成功，开始测试...")
    
    # 测试每个通道
    for grade in range(1, 8):
        logger.info(f"测试通道 L{grade}...")
        success = plc_mgr.send_to_channel(grade, is_ng=False)
        
        if success:
            logger.info(f"通道 L{grade} 测试成功")
        else:
            logger.error(f"通道 L{grade} 测试失败")
        
        time.sleep(0.5)
    
    # 测试NG通道
    logger.info("测试NG通道...")
    success = plc_mgr.send_to_channel(0, is_ng=True)
    
    if success:
        logger.info("NG通道测试成功")
    else:
        logger.error("NG通道测试失败")
    
    # 心跳检测
    logger.info("心跳检测...")
    is_alive = plc_mgr.heartbeat()
    logger.info(f"PLC状态: {'在线' if is_alive else '离线'}")
    
    # 关闭
    plc_mgr.shutdown()
    
    logger.info("=" * 60)
    logger.info("PLC通信测试完成")
    logger.info("=" * 60)
    
    return True

if __name__ == "__main__":
    success = test_plc()
    sys.exit(0 if success else 1)

