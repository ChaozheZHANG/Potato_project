"""
土豆质检分级系统主程序
集成采集、检测、追踪、分级和PLC控制
"""
import time
import signal
import sys
from pathlib import Path
from threading import Thread, Event
from queue import Queue, Empty
from typing import Optional
import cv2
import numpy as np

from utils.logger import init_logger, get_logger
from utils.config_loader import init_config, get_config
from utils.metrics import MetricsCollector, Timer

from acquisition.camera import CameraManager
from tracking.tracker import TrackerManager, Detection
from inference.model import InferenceManager
from plc.communication import PLCManager


# 初始化日志和配置
init_logger(log_dir="logs", level="INFO")
logger = get_logger()

init_config("configs/system_config.yaml")
config = get_config()


class InspectionPipeline:
    """质检流水线"""
    
    def __init__(self):
        """初始化质检流水线"""
        logger.info("=" * 80)
        logger.info("土豆质检分级系统启动")
        logger.info("=" * 80)
        
        # 系统组件
        self.camera_mgr = CameraManager(config)
        self.tracker_mgr = TrackerManager(config)
        self.inference_mgr = InferenceManager(config)
        self.plc_mgr = PLCManager(config)
        
        # 性能指标
        self.metrics = MetricsCollector(window_size=100)
        
        # 控制标志
        self.running = Event()
        self.paused = Event()
        
        # 工作队列
        self.image_queue = Queue(maxsize=10)
        self.result_queue = Queue(maxsize=10)
        
        # 工作线程
        self.capture_thread: Optional[Thread] = None
        self.process_thread: Optional[Thread] = None
        self.output_thread: Optional[Thread] = None
        
        # 配置
        self.save_images = config.get("storage.save_images", True)
        self.save_ng_only = config.get("storage.save_ng_only", False)
        self.debug_mode = config.get("debug.enable", False)
        self.visualize = config.get("debug.visualize", True)
        
        logger.info("质检流水线初始化完成")
    
    def initialize(self) -> bool:
        """
        初始化所有组件
        
        Returns:
            是否成功
        """
        logger.info("初始化系统组件...")
        
        # 初始化相机
        if not self.camera_mgr.initialize():
            logger.error("相机初始化失败")
            return False
        
        # 初始化推理模型
        if not self.inference_mgr.initialize():
            logger.error("推理模型初始化失败")
            return False
        
        # 初始化PLC
        if not self.plc_mgr.initialize():
            logger.warning("PLC初始化失败，将在模拟模式下运行")
        
        logger.info("系统组件初始化成功")
        return True
    
    def start(self):
        """启动流水线"""
        logger.info("启动质检流水线...")
        
        self.running.set()
        
        # 启动采集线程
        self.capture_thread = Thread(target=self._capture_worker, name="CaptureWorker")
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
        # 启动处理线程
        self.process_thread = Thread(target=self._process_worker, name="ProcessWorker")
        self.process_thread.daemon = True
        self.process_thread.start()
        
        # 启动输出线程
        self.output_thread = Thread(target=self._output_worker, name="OutputWorker")
        self.output_thread.daemon = True
        self.output_thread.start()
        
        logger.info("质检流水线已启动")
    
    def stop(self):
        """停止流水线"""
        logger.info("停止质检流水线...")
        
        self.running.clear()
        
        # 等待线程结束
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.process_thread:
            self.process_thread.join(timeout=2)
        if self.output_thread:
            self.output_thread.join(timeout=2)
        
        logger.info("质检流水线已停止")
    
    def shutdown(self):
        """关闭系统"""
        logger.info("关闭系统...")
        
        self.stop()
        
        # 关闭各组件
        self.camera_mgr.shutdown()
        self.plc_mgr.shutdown()
        
        # 打印最终统计
        metrics = self.metrics.get_metrics()
        logger.info("=" * 80)
        logger.info("最终统计:")
        logger.info(f"  总处理数: {metrics.total_processed}")
        logger.info(f"  OK品: {metrics.total_ok}")
        logger.info(f"  NG品: {metrics.total_ng}")
        logger.info(f"  NG率: {metrics.total_ng / max(1, metrics.total_processed) * 100:.2f}%")
        logger.info(f"  平均FPS: {metrics.fps:.2f}")
        logger.info(f"  平均延迟: {metrics.avg_latency_ms:.2f}ms")
        logger.info(f"  运行时长: {self.metrics.get_session_duration():.2f}秒")
        logger.info("=" * 80)
        
        logger.info("系统已关闭")
    
    def _capture_worker(self):
        """采集工作线程"""
        logger.info("采集线程启动")
        
        target_interval = 1.0 / config.get("production.target_frequency", 3)
        
        while self.running.is_set():
            if self.paused.is_set():
                time.sleep(0.1)
                continue
            
            try:
                start_time = time.time()
                
                # 采集图像
                image = self.camera_mgr.capture()
                
                if image is None:
                    logger.warning("采集图像失败")
                    time.sleep(0.1)
                    continue
                
                # 放入队列
                try:
                    self.image_queue.put({
                        "image": image,
                        "timestamp": time.time()
                    }, timeout=1)
                except:
                    logger.warning("图像队列已满，丢弃帧")
                
                # 控制采集频率
                elapsed = time.time() - start_time
                sleep_time = max(0, target_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"采集线程异常: {e}", exc_info=True)
                time.sleep(0.5)
        
        logger.info("采集线程结束")
    
    def _process_worker(self):
        """处理工作线程"""
        logger.info("处理线程启动")
        
        while self.running.is_set():
            try:
                # 从队列获取图像
                try:
                    item = self.image_queue.get(timeout=0.5)
                except Empty:
                    continue
                
                image = item["image"]
                capture_time = item["timestamp"]
                
                # 计时
                with Timer() as timer:
                    # 推理（检测+分级）
                    detections, results = self.inference_mgr.process(image)
                    
                    # 追踪更新
                    tracks = self.tracker_mgr.update(detections)
                    
                    # 匹配追踪与检测结果
                    for i, result in enumerate(results):
                        if i < len(tracks):
                            track = tracks[i]
                            self.tracker_mgr.update_track_result(
                                track.track_id,
                                result["grade"],
                                [self.inference_mgr.defect_model.class_names[result["class_id"]]],
                                result["is_ng"]
                            )
                
                # 记录指标
                latency = timer.get_elapsed_ms()
                self.metrics.record_frame(latency)
                
                # 放入结果队列
                try:
                    self.result_queue.put({
                        "image": image,
                        "tracks": tracks,
                        "results": results,
                        "latency_ms": latency,
                        "capture_time": capture_time
                    }, timeout=1)
                except:
                    logger.warning("结果队列已满")
                
            except Exception as e:
                logger.error(f"处理线程异常: {e}", exc_info=True)
        
        logger.info("处理线程结束")
    
    def _output_worker(self):
        """输出工作线程（PLC控制+存证）"""
        logger.info("输出线程启动")
        
        while self.running.is_set():
            try:
                # 从队列获取结果
                try:
                    item = self.result_queue.get(timeout=0.5)
                except Empty:
                    continue
                
                image = item["image"]
                tracks = item["tracks"]
                results = item["results"]
                
                # 处理每个追踪结果
                for track in tracks:
                    if track.grade is None:
                        continue
                    
                    # 记录统计
                    self.metrics.record_result(
                        is_ng=track.is_ng,
                        grade=track.grade,
                        defects=track.defects
                    )
                    
                    # 发送PLC信号
                    success = self.plc_mgr.send_to_channel(track.grade, track.is_ng)
                    
                    if success:
                        channel = "NG" if track.is_ng else f"L{track.grade}"
                        logger.info(f"土豆 #{track.track_id} -> {channel} "
                                  f"(等级:{track.grade}, NG:{track.is_ng})")
                    
                    # 保存图像（可选）
                    if self.save_images and (not self.save_ng_only or track.is_ng):
                        prefix = f"ng_{track.track_id}" if track.is_ng else f"ok_l{track.grade}_{track.track_id}"
                        
                        # 可视化（可选）
                        if self.visualize:
                            vis_image = self._visualize_result(image, track, results)
                            self.camera_mgr.save_image(vis_image, "captures/processed", prefix)
                        else:
                            self.camera_mgr.save_image(image, "captures/raw", prefix)
                
                # 定期打印性能指标
                if int(time.time()) % 10 == 0:
                    metrics = self.metrics.get_metrics()
                    logger.info(f"性能指标: {metrics}")
                
            except Exception as e:
                logger.error(f"输出线程异常: {e}", exc_info=True)
        
        logger.info("输出线程结束")
    
    def _visualize_result(self, image: np.ndarray, track, results) -> np.ndarray:
        """
        可视化检测结果
        
        Args:
            image: 原始图像
            track: 追踪对象
            results: 检测结果
            
        Returns:
            可视化图像
        """
        # 转为BGR（如果是灰度图）
        if len(image.shape) == 2:
            vis_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            vis_image = image.copy()
        
        # 绘制边界框
        x1, y1, x2, y2 = track.bbox.astype(int)
        
        # 根据NG状态选择颜色
        color = (0, 0, 255) if track.is_ng else (0, 255, 0)
        
        cv2.rectangle(vis_image, (x1, y1), (x2, y2), color, 3)
        
        # 绘制标签
        label = f"ID:{track.track_id} L{track.grade}"
        if track.is_ng:
            label += " [NG]"
        
        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.rectangle(vis_image, (x1, y1 - label_h - 10), (x1 + label_w, y1), color, -1)
        cv2.putText(vis_image, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        return vis_image
    
    def pause(self):
        """暂停流水线"""
        self.paused.set()
        logger.info("流水线已暂停")
    
    def resume(self):
        """恢复流水线"""
        self.paused.clear()
        logger.info("流水线已恢复")


def signal_handler(sig, frame):
    """信号处理器（Ctrl+C）"""
    logger.info("接收到中断信号，准备关闭...")
    if 'pipeline' in globals():
        pipeline.shutdown()
    sys.exit(0)


def main():
    """主函数"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建流水线
    global pipeline
    pipeline = InspectionPipeline()
    
    # 初始化
    if not pipeline.initialize():
        logger.error("系统初始化失败，退出")
        return 1
    
    # 启动
    pipeline.start()
    
    try:
        # 主循环（保持运行）
        logger.info("系统运行中... (按 Ctrl+C 停止)")
        while True:
            time.sleep(1)
            
            # 健康检查
            if not pipeline.camera_mgr.camera.is_connected():
                logger.error("相机断开连接！")
                # 尝试重连
                logger.info("尝试重连相机...")
                if pipeline.camera_mgr.camera.connect():
                    logger.info("相机重连成功")
                else:
                    logger.error("相机重连失败")
            
            # PLC健康检查
            if not pipeline.plc_mgr.heartbeat():
                logger.warning("PLC连接异常")
    
    except KeyboardInterrupt:
        logger.info("接收到键盘中断")
    finally:
        pipeline.shutdown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

