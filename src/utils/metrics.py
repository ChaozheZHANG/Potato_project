"""
性能指标监控模块
用于统计和监控系统性能
"""
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from threading import Lock
import numpy as np


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    fps: float = 0.0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    total_processed: int = 0
    total_ng: int = 0
    total_ok: int = 0
    grade_distribution: Dict[int, int] = field(default_factory=dict)
    defect_distribution: Dict[str, int] = field(default_factory=dict)
    
    def __str__(self):
        return (f"FPS: {self.fps:.2f} | Latency: {self.avg_latency_ms:.2f}ms "
                f"(min:{self.min_latency_ms:.2f}, max:{self.max_latency_ms:.2f}) | "
                f"Processed: {self.total_processed} (OK:{self.total_ok}, NG:{self.total_ng})")


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, window_size: int = 100):
        """
        初始化指标收集器
        
        Args:
            window_size: 滑动窗口大小
        """
        self.window_size = window_size
        self.lock = Lock()
        
        # 时间戳队列（用于计算FPS）
        self.timestamps = deque(maxlen=window_size)
        
        # 延迟队列
        self.latencies = deque(maxlen=window_size)
        
        # 统计计数
        self.total_processed = 0
        self.total_ng = 0
        self.total_ok = 0
        self.grade_distribution: Dict[int, int] = {}
        self.defect_distribution: Dict[str, int] = {}
        
        # 会话开始时间
        self.session_start = time.time()
        
    def record_frame(self, latency_ms: Optional[float] = None):
        """
        记录一帧处理
        
        Args:
            latency_ms: 处理延迟（毫秒）
        """
        with self.lock:
            current_time = time.time()
            self.timestamps.append(current_time)
            
            if latency_ms is not None:
                self.latencies.append(latency_ms)
            
            self.total_processed += 1
    
    def record_result(self, is_ng: bool, grade: Optional[int] = None, 
                      defects: Optional[List[str]] = None):
        """
        记录检测结果
        
        Args:
            is_ng: 是否为NG品
            grade: 分级等级（1-7）
            defects: 缺陷列表
        """
        with self.lock:
            if is_ng:
                self.total_ng += 1
            else:
                self.total_ok += 1
                
            if grade is not None:
                self.grade_distribution[grade] = self.grade_distribution.get(grade, 0) + 1
            
            if defects:
                for defect in defects:
                    self.defect_distribution[defect] = self.defect_distribution.get(defect, 0) + 1
    
    def get_metrics(self) -> PerformanceMetrics:
        """
        获取当前性能指标
        
        Returns:
            PerformanceMetrics对象
        """
        with self.lock:
            metrics = PerformanceMetrics()
            
            # 计算FPS
            if len(self.timestamps) >= 2:
                time_span = self.timestamps[-1] - self.timestamps[0]
                if time_span > 0:
                    metrics.fps = (len(self.timestamps) - 1) / time_span
            
            # 计算延迟统计
            if self.latencies:
                latencies_array = np.array(self.latencies)
                metrics.avg_latency_ms = float(np.mean(latencies_array))
                metrics.max_latency_ms = float(np.max(latencies_array))
                metrics.min_latency_ms = float(np.min(latencies_array))
            
            # 复制统计数据
            metrics.total_processed = self.total_processed
            metrics.total_ng = self.total_ng
            metrics.total_ok = self.total_ok
            metrics.grade_distribution = self.grade_distribution.copy()
            metrics.defect_distribution = self.defect_distribution.copy()
            
            return metrics
    
    def reset(self):
        """重置所有统计"""
        with self.lock:
            self.timestamps.clear()
            self.latencies.clear()
            self.total_processed = 0
            self.total_ng = 0
            self.total_ok = 0
            self.grade_distribution.clear()
            self.defect_distribution.clear()
            self.session_start = time.time()
    
    def get_session_duration(self) -> float:
        """
        获取会话持续时间
        
        Returns:
            会话持续时间（秒）
        """
        return time.time() - self.session_start


class Timer:
    """计时器上下文管理器"""
    
    def __init__(self):
        self.start_time = None
        self.elapsed_ms = 0
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed_ms = (time.perf_counter() - self.start_time) * 1000
        return False
    
    def get_elapsed_ms(self) -> float:
        """获取经过的时间（毫秒）"""
        if self.start_time is None:
            return 0
        return self.elapsed_ms

