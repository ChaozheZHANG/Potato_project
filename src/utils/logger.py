"""
日志管理模块
统一的日志配置和管理
"""
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger


class LoggerManager:
    """日志管理器"""
    
    def __init__(self, log_dir: str = "logs", level: str = "INFO"):
        """
        初始化日志管理器
        
        Args:
            log_dir: 日志目录
            level: 日志级别
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.level = level
        
        # 移除默认处理器
        logger.remove()
        
        # 添加控制台输出
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>",
            level=level,
            colorize=True
        )
        
        # 添加系统日志文件
        logger.add(
            self.log_dir / "system" / "{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level=level,
            rotation="00:00",  # 每天午夜轮转
            retention="30 days",  # 保留30天
            compression="zip",  # 压缩
            encoding="utf-8"
        )
        
        # 添加错误日志文件
        logger.add(
            self.log_dir / "system" / "error_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
            level="ERROR",
            rotation="00:00",
            retention="90 days",
            compression="zip",
            encoding="utf-8"
        )
        
    def get_module_logger(self, module_name: str):
        """
        获取模块专用日志器
        
        Args:
            module_name: 模块名称
            
        Returns:
            logger实例
        """
        # 为特定模块添加专用日志文件
        module_log_path = self.log_dir / module_name / "{time:YYYY-MM-DD}.log"
        
        logger.add(
            module_log_path,
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}",
            level=self.level,
            rotation="00:00",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
            filter=lambda record: record["extra"].get("module") == module_name
        )
        
        return logger.bind(module=module_name)


# 全局日志管理器实例
_logger_manager = None


def init_logger(log_dir: str = "logs", level: str = "INFO") -> LoggerManager:
    """
    初始化全局日志管理器
    
    Args:
        log_dir: 日志目录
        level: 日志级别
        
    Returns:
        LoggerManager实例
    """
    global _logger_manager
    _logger_manager = LoggerManager(log_dir, level)
    return _logger_manager


def get_logger(module_name: str = None):
    """
    获取日志器
    
    Args:
        module_name: 模块名称，如果为None则返回通用logger
        
    Returns:
        logger实例
    """
    global _logger_manager
    if _logger_manager is None:
        _logger_manager = LoggerManager()
    
    if module_name:
        return _logger_manager.get_module_logger(module_name)
    return logger

