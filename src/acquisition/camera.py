"""
相机控制模块
支持工业相机的图像采集、触发控制和参数配置
"""
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Callable
from datetime import datetime
import numpy as np
import cv2

from ..utils.logger import get_logger
from ..utils.config_loader import get_config


logger = get_logger("acquisition")


class CameraBase(ABC):
    """相机基类（抽象接口）"""
    
    @abstractmethod
    def connect(self) -> bool:
        """连接相机"""
        pass
    
    @abstractmethod
    def disconnect(self):
        """断开相机连接"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """检查是否已连接"""
        pass
    
    @abstractmethod
    def set_exposure(self, exposure_us: int):
        """设置曝光时间（微秒）"""
        pass
    
    @abstractmethod
    def set_gain(self, gain: float):
        """设置增益"""
        pass
    
    @abstractmethod
    def trigger(self) -> bool:
        """触发采集"""
        pass
    
    @abstractmethod
    def grab_image(self) -> Optional[np.ndarray]:
        """抓取图像"""
        pass
    
    @abstractmethod
    def get_frame_rate(self) -> float:
        """获取帧率"""
        pass


class SimulatedCamera(CameraBase):
    """模拟相机（用于测试和开发）"""
    
    def __init__(self, width: int = 4096, height: int = 3000):
        """
        初始化模拟相机
        
        Args:
            width: 图像宽度
            height: 图像高度
        """
        self.width = width
        self.height = height
        self.connected = False
        self.exposure_us = 5000
        self.gain = 0.0
        self.frame_count = 0
        self.last_grab_time = 0
        
        logger.info(f"模拟相机初始化: {width}x{height}")
    
    def connect(self) -> bool:
        """连接相机"""
        logger.info("模拟相机连接成功")
        self.connected = True
        return True
    
    def disconnect(self):
        """断开连接"""
        logger.info("模拟相机断开连接")
        self.connected = False
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.connected
    
    def set_exposure(self, exposure_us: int):
        """设置曝光时间"""
        self.exposure_us = exposure_us
        logger.debug(f"设置曝光时间: {exposure_us} μs")
    
    def set_gain(self, gain: float):
        """设置增益"""
        self.gain = gain
        logger.debug(f"设置增益: {gain}")
    
    def trigger(self) -> bool:
        """触发采集"""
        if not self.connected:
            return False
        self.frame_count += 1
        return True
    
    def grab_image(self) -> Optional[np.ndarray]:
        """
        抓取图像（生成模拟图像）
        
        Returns:
            模拟的灰度图像
        """
        if not self.connected:
            return None
        
        # 生成模拟图像（灰度噪声 + 椭圆形物体模拟土豆）
        image = np.random.randint(100, 150, (self.height, self.width), dtype=np.uint8)
        
        # 添加一个或多个椭圆形物体
        num_potatoes = np.random.randint(1, 3)
        for _ in range(num_potatoes):
            center_x = np.random.randint(self.width // 4, 3 * self.width // 4)
            center_y = np.random.randint(self.height // 4, 3 * self.height // 4)
            axes_x = np.random.randint(200, 400)
            axes_y = np.random.randint(150, 350)
            
            cv2.ellipse(image, (center_x, center_y), (axes_x, axes_y), 
                       np.random.randint(0, 180), 0, 360, 
                       int(np.random.randint(180, 240)), -1)
            
            # 随机添加缺陷（黑点）
            if np.random.random() < 0.3:
                for _ in range(np.random.randint(1, 4)):
                    defect_x = center_x + np.random.randint(-axes_x, axes_x)
                    defect_y = center_y + np.random.randint(-axes_y, axes_y)
                    defect_radius = np.random.randint(5, 20)
                    cv2.circle(image, (defect_x, defect_y), defect_radius, 50, -1)
        
        self.last_grab_time = time.time()
        logger.debug(f"抓取图像 #{self.frame_count}")
        
        return image
    
    def get_frame_rate(self) -> float:
        """获取帧率"""
        return 3.0  # 模拟3Hz


class IndustrialCamera(CameraBase):
    """
    工业相机接口
    需要根据实际使用的相机SDK进行适配
    支持的相机品牌: Basler (pypylon), AVT/Allied Vision (vimba), 其他GenICam兼容相机
    """
    
    def __init__(self, camera_index: int = 0):
        """
        初始化工业相机
        
        Args:
            camera_index: 相机索引
        """
        self.camera_index = camera_index
        self.camera = None
        self.connected = False
        
        logger.info(f"工业相机初始化: Index={camera_index}")
        
        # TODO: 根据实际相机SDK初始化
        # 示例: Basler相机
        # try:
        #     import pypylon.pylon as pylon
        #     self.camera = pylon.InstantCamera(
        #         pylon.TlFactory.GetInstance().CreateDevice(
        #             pylon.TlFactory.GetInstance().EnumerateDevices()[camera_index]
        #         )
        #     )
        # except ImportError:
        #     logger.warning("pypylon未安装，使用模拟相机")
        #     self.camera = None
        
    def connect(self) -> bool:
        """连接相机"""
        try:
            if self.camera is None:
                logger.error("相机对象未初始化")
                return False
            
            # TODO: 实际连接逻辑
            # self.camera.Open()
            # self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            
            self.connected = True
            logger.info("工业相机连接成功")
            return True
        except Exception as e:
            logger.error(f"相机连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        try:
            if self.camera and self.connected:
                # TODO: 实际断开逻辑
                # self.camera.StopGrabbing()
                # self.camera.Close()
                
                self.connected = False
                logger.info("工业相机断开连接")
        except Exception as e:
            logger.error(f"相机断开失败: {e}")
    
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self.connected
    
    def set_exposure(self, exposure_us: int):
        """设置曝光时间"""
        if not self.connected:
            return
        
        try:
            # TODO: 实际设置逻辑
            # self.camera.ExposureTime.SetValue(exposure_us)
            logger.debug(f"设置曝光时间: {exposure_us} μs")
        except Exception as e:
            logger.error(f"设置曝光失败: {e}")
    
    def set_gain(self, gain: float):
        """设置增益"""
        if not self.connected:
            return
        
        try:
            # TODO: 实际设置逻辑
            # self.camera.Gain.SetValue(gain)
            logger.debug(f"设置增益: {gain}")
        except Exception as e:
            logger.error(f"设置增益失败: {e}")
    
    def trigger(self) -> bool:
        """触发采集"""
        if not self.connected:
            return False
        
        try:
            # TODO: 实际触发逻辑
            # self.camera.ExecuteSoftwareTrigger()
            return True
        except Exception as e:
            logger.error(f"触发失败: {e}")
            return False
    
    def grab_image(self) -> Optional[np.ndarray]:
        """抓取图像"""
        if not self.connected:
            return None
        
        try:
            # TODO: 实际抓取逻辑
            # grab_result = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
            # if grab_result.GrabSucceeded():
            #     image = grab_result.Array
            #     grab_result.Release()
            #     return image
            
            return None
        except Exception as e:
            logger.error(f"抓取图像失败: {e}")
            return None
    
    def get_frame_rate(self) -> float:
        """获取帧率"""
        if not self.connected:
            return 0.0
        
        try:
            # TODO: 实际获取帧率逻辑
            # return self.camera.ResultingFrameRate.GetValue()
            return 0.0
        except Exception as e:
            logger.error(f"获取帧率失败: {e}")
            return 0.0


class CameraManager:
    """相机管理器"""
    
    def __init__(self, config_loader=None):
        """
        初始化相机管理器
        
        Args:
            config_loader: 配置加载器
        """
        self.config = config_loader or get_config()
        self.camera: Optional[CameraBase] = None
        self.trigger_callback: Optional[Callable] = None
        
        # 加载配置
        camera_model = self.config.get("camera.model", "industrial")
        
        # 创建相机实例
        if camera_model == "simulated":
            width = self.config.get("camera.resolution.width", 4096)
            height = self.config.get("camera.resolution.height", 3000)
            self.camera = SimulatedCamera(width, height)
        else:
            self.camera = IndustrialCamera()
        
        logger.info(f"相机管理器初始化: 模式={camera_model}")
    
    def initialize(self) -> bool:
        """
        初始化相机
        
        Returns:
            是否成功
        """
        if not self.camera.connect():
            logger.error("相机连接失败")
            return False
        
        # 设置参数
        exposure = self.config.get("camera.exposure.default", 5000)
        gain = self.config.get("camera.gain.default", 0)
        
        self.camera.set_exposure(exposure)
        self.camera.set_gain(gain)
        
        logger.info(f"相机初始化成功: 曝光={exposure}μs, 增益={gain}")
        return True
    
    def shutdown(self):
        """关闭相机"""
        if self.camera:
            self.camera.disconnect()
            logger.info("相机已关闭")
    
    def capture(self) -> Optional[np.ndarray]:
        """
        采集一帧图像
        
        Returns:
            图像数组，失败返回None
        """
        if not self.camera or not self.camera.is_connected():
            logger.error("相机未连接")
            return None
        
        # 触发采集
        if not self.camera.trigger():
            logger.error("触发失败")
            return None
        
        # 等待触发延迟
        trigger_delay = self.config.get("camera.trigger.delay_ms", 10)
        time.sleep(trigger_delay / 1000.0)
        
        # 抓取图像
        image = self.camera.grab_image()
        
        if image is None:
            logger.error("抓取图像失败")
            return None
        
        logger.debug(f"采集图像成功: shape={image.shape}")
        return image
    
    def save_image(self, image: np.ndarray, save_dir: str, 
                   prefix: str = "capture", metadata: dict = None) -> str:
        """
        保存图像
        
        Args:
            image: 图像数组
            save_dir: 保存目录
            prefix: 文件名前缀
            metadata: 元数据（可选）
            
        Returns:
            保存的文件路径
        """
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{prefix}_{timestamp}.jpg"
        filepath = save_path / filename
        
        # 保存图像
        quality = self.config.get("storage.image_quality", 85)
        cv2.imwrite(str(filepath), image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        
        logger.debug(f"图像已保存: {filepath}")
        return str(filepath)
    
    def set_trigger_callback(self, callback: Callable):
        """
        设置触发回调函数
        
        Args:
            callback: 回调函数
        """
        self.trigger_callback = callback
        logger.info("触发回调已设置")

