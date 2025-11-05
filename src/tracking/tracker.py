"""
多目标追踪模块
用于土豆跨视野追踪，支持SORT算法和位置预测
"""
import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from scipy.optimize import linear_sum_assignment
from filterpy.kalman import KalmanFilter

from ..utils.logger import get_logger
from ..utils.config_loader import get_config


logger = get_logger("tracking")


@dataclass
class Detection:
    """检测结果数据类"""
    bbox: np.ndarray  # [x1, y1, x2, y2]
    confidence: float
    class_id: int = 0
    features: Optional[np.ndarray] = None


@dataclass
class Track:
    """追踪轨迹数据类"""
    track_id: int
    bbox: np.ndarray  # 当前位置 [x1, y1, x2, y2]
    hits: int = 0  # 命中次数
    age: int = 0  # 年龄（总帧数）
    time_since_update: int = 0  # 自上次更新以来的帧数
    state: str = "tentative"  # tentative/confirmed/deleted
    
    # 检测结果
    grade: Optional[int] = None
    defects: Optional[List[str]] = None
    is_ng: bool = False
    
    # 预测位置
    predicted_bbox: Optional[np.ndarray] = None


def bbox_iou(bbox1: np.ndarray, bbox2: np.ndarray) -> float:
    """
    计算两个边界框的IoU
    
    Args:
        bbox1: [x1, y1, x2, y2]
        bbox2: [x1, y1, x2, y2]
        
    Returns:
        IoU值
    """
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])
    
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    
    area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
    union = area1 + area2 - intersection
    
    if union <= 0:
        return 0.0
    
    return intersection / union


def bbox_to_xyah(bbox: np.ndarray) -> np.ndarray:
    """
    将bbox转换为[center_x, center_y, aspect_ratio, height]格式
    
    Args:
        bbox: [x1, y1, x2, y2]
        
    Returns:
        [center_x, center_y, aspect_ratio, height]
    """
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = bbox[0] + w / 2
    y = bbox[1] + h / 2
    a = w / (h + 1e-6)
    return np.array([x, y, a, h])


def xyah_to_bbox(xyah: np.ndarray) -> np.ndarray:
    """
    将[center_x, center_y, aspect_ratio, height]转换为bbox
    
    Args:
        xyah: [center_x, center_y, aspect_ratio, height]
        
    Returns:
        [x1, y1, x2, y2]
    """
    w = xyah[2] * xyah[3]
    h = xyah[3]
    x1 = xyah[0] - w / 2
    y1 = xyah[1] - h / 2
    x2 = xyah[0] + w / 2
    y2 = xyah[1] + h / 2
    return np.array([x1, y1, x2, y2])


class KalmanBoxTracker:
    """使用卡尔曼滤波的边界框追踪器"""
    
    count = 0
    
    def __init__(self, bbox: np.ndarray):
        """
        初始化卡尔曼追踪器
        
        Args:
            bbox: 初始边界框 [x1, y1, x2, y2]
        """
        # 定义卡尔曼滤波器
        # 状态: [center_x, center_y, aspect_ratio, height, vx, vy, va, vh]
        self.kf = KalmanFilter(dim_x=8, dim_z=4)
        
        # 状态转移矩阵
        self.kf.F = np.array([
            [1, 0, 0, 0, 1, 0, 0, 0],  # x = x + vx
            [0, 1, 0, 0, 0, 1, 0, 0],  # y = y + vy
            [0, 0, 1, 0, 0, 0, 1, 0],  # a = a + va
            [0, 0, 0, 1, 0, 0, 0, 1],  # h = h + vh
            [0, 0, 0, 0, 1, 0, 0, 0],  # vx = vx
            [0, 0, 0, 0, 0, 1, 0, 0],  # vy = vy
            [0, 0, 0, 0, 0, 0, 1, 0],  # va = va
            [0, 0, 0, 0, 0, 0, 0, 1],  # vh = vh
        ])
        
        # 测量矩阵
        self.kf.H = np.array([
            [1, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0, 0],
        ])
        
        # 测量噪声
        self.kf.R[2:, 2:] *= 10
        
        # 过程噪声
        self.kf.P[4:, 4:] *= 1000  # 速度不确定性
        self.kf.P *= 10
        
        # 过程协方差
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01
        
        # 初始化状态
        self.kf.x[:4] = bbox_to_xyah(bbox)
        
        self.time_since_update = 0
        self.id = KalmanBoxTracker.count
        KalmanBoxTracker.count += 1
        self.history = []
        self.hits = 0
        self.hit_streak = 0
        self.age = 0
    
    def update(self, bbox: np.ndarray):
        """
        更新追踪器
        
        Args:
            bbox: 新的检测框 [x1, y1, x2, y2]
        """
        self.time_since_update = 0
        self.history = []
        self.hits += 1
        self.hit_streak += 1
        self.kf.update(bbox_to_xyah(bbox))
    
    def predict(self) -> np.ndarray:
        """
        预测下一帧位置
        
        Returns:
            预测的边界框 [x1, y1, x2, y2]
        """
        # 防止高度为负
        if self.kf.x[3] + self.kf.x[7] <= 0:
            self.kf.x[7] *= 0.0
        
        self.kf.predict()
        self.age += 1
        
        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1
        
        self.history.append(xyah_to_bbox(self.kf.x[:4]))
        return self.history[-1]
    
    def get_state(self) -> np.ndarray:
        """
        获取当前状态
        
        Returns:
            当前边界框 [x1, y1, x2, y2]
        """
        return xyah_to_bbox(self.kf.x[:4])


class SORTTracker:
    """SORT (Simple Online and Realtime Tracking) 追踪器"""
    
    def __init__(self, max_age: int = 30, min_hits: int = 3, iou_threshold: float = 0.3):
        """
        初始化SORT追踪器
        
        Args:
            max_age: 最大失踪帧数
            min_hits: 最小命中次数（确认追踪）
            iou_threshold: IoU匹配阈值
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        
        self.trackers: List[KalmanBoxTracker] = []
        self.tracks: Dict[int, Track] = {}
        self.frame_count = 0
        
        logger.info(f"SORT追踪器初始化: max_age={max_age}, min_hits={min_hits}, iou={iou_threshold}")
    
    def update(self, detections: List[Detection]) -> List[Track]:
        """
        更新追踪器
        
        Args:
            detections: 检测结果列表
            
        Returns:
            活跃的追踪列表
        """
        self.frame_count += 1
        
        # 预测所有追踪器的位置
        trks = np.zeros((len(self.trackers), 5))
        to_del = []
        for t, trk in enumerate(trks):
            pos = self.trackers[t].predict()
            trk[:] = [pos[0], pos[1], pos[2], pos[3], 0]
            if np.any(np.isnan(pos)):
                to_del.append(t)
        
        trks = np.ma.compress_rows(np.ma.masked_invalid(trks))
        for t in reversed(to_del):
            self.trackers.pop(t)
        
        # 关联检测与追踪
        dets = np.array([det.bbox for det in detections]) if detections else np.empty((0, 4))
        matched, unmatched_dets, unmatched_trks = self._associate_detections_to_trackers(dets, trks)
        
        # 更新匹配的追踪
        for m in matched:
            self.trackers[m[1]].update(dets[m[0]])
        
        # 为未匹配的检测创建新追踪
        for i in unmatched_dets:
            trk = KalmanBoxTracker(dets[i])
            self.trackers.append(trk)
        
        # 收集活跃追踪
        active_tracks = []
        for trk in reversed(self.trackers):
            d = trk.get_state()
            
            # 删除太久未更新的追踪
            if trk.time_since_update > self.max_age:
                self.trackers.remove(trk)
                if trk.id in self.tracks:
                    del self.tracks[trk.id]
                continue
            
            # 只返回确认的追踪（命中次数足够）
            if trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits:
                if trk.id not in self.tracks:
                    self.tracks[trk.id] = Track(
                        track_id=trk.id,
                        bbox=d,
                        hits=trk.hits,
                        age=trk.age,
                        time_since_update=trk.time_since_update,
                        state="confirmed"
                    )
                else:
                    track = self.tracks[trk.id]
                    track.bbox = d
                    track.hits = trk.hits
                    track.age = trk.age
                    track.time_since_update = trk.time_since_update
                
                active_tracks.append(self.tracks[trk.id])
        
        return active_tracks
    
    def _associate_detections_to_trackers(
        self, detections: np.ndarray, trackers: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        关联检测与追踪
        
        Args:
            detections: 检测框数组 [N, 4]
            trackers: 追踪框数组 [M, 5]
            
        Returns:
            (匹配对, 未匹配的检测, 未匹配的追踪)
        """
        if len(trackers) == 0:
            return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty((0,), dtype=int)
        
        # 计算IoU矩阵
        iou_matrix = np.zeros((len(detections), len(trackers)), dtype=np.float32)
        for d, det in enumerate(detections):
            for t, trk in enumerate(trackers):
                iou_matrix[d, t] = bbox_iou(det, trk[:4])
        
        # 匈牙利算法匹配
        if min(iou_matrix.shape) > 0:
            a = (iou_matrix > self.iou_threshold).astype(np.int32)
            if a.sum(1).max() == 1 and a.sum(0).max() == 1:
                matched_indices = np.stack(np.where(a), axis=1)
            else:
                row_ind, col_ind = linear_sum_assignment(-iou_matrix)
                matched_indices = np.array(list(zip(row_ind, col_ind)))
        else:
            matched_indices = np.empty((0, 2), dtype=int)
        
        # 过滤低IoU匹配
        matches = []
        for m in matched_indices:
            if iou_matrix[m[0], m[1]] < self.iou_threshold:
                pass
            else:
                matches.append(m.reshape(1, 2))
        
        if len(matches) == 0:
            matches = np.empty((0, 2), dtype=int)
        else:
            matches = np.concatenate(matches, axis=0)
        
        # 未匹配的检测和追踪
        unmatched_detections = []
        for d in range(len(detections)):
            if d not in matches[:, 0]:
                unmatched_detections.append(d)
        
        unmatched_trackers = []
        for t in range(len(trackers)):
            if t not in matches[:, 1]:
                unmatched_trackers.append(t)
        
        return matches, np.array(unmatched_detections), np.array(unmatched_trackers)
    
    def get_track(self, track_id: int) -> Optional[Track]:
        """
        获取指定ID的追踪
        
        Args:
            track_id: 追踪ID
            
        Returns:
            Track对象，不存在返回None
        """
        return self.tracks.get(track_id)
    
    def update_track_result(self, track_id: int, grade: int, defects: List[str], is_ng: bool):
        """
        更新追踪的检测结果
        
        Args:
            track_id: 追踪ID
            grade: 分级等级
            defects: 缺陷列表
            is_ng: 是否为NG品
        """
        if track_id in self.tracks:
            track = self.tracks[track_id]
            track.grade = grade
            track.defects = defects
            track.is_ng = is_ng
            logger.debug(f"更新追踪 {track_id}: grade={grade}, NG={is_ng}")


class TrackerManager:
    """追踪管理器"""
    
    def __init__(self, config_loader=None):
        """
        初始化追踪管理器
        
        Args:
            config_loader: 配置加载器
        """
        self.config = config_loader or get_config()
        
        # 加载追踪配置
        max_age = self.config.get("tracking.max_age", 30)
        min_hits = self.config.get("tracking.min_hits", 3)
        iou_threshold = self.config.get("tracking.iou_threshold", 0.3)
        
        self.tracker = SORTTracker(max_age, min_hits, iou_threshold)
        
        logger.info("追踪管理器初始化完成")
    
    def update(self, detections: List[Detection]) -> List[Track]:
        """
        更新追踪
        
        Args:
            detections: 检测结果列表
            
        Returns:
            活跃追踪列表
        """
        return self.tracker.update(detections)
    
    def get_track(self, track_id: int) -> Optional[Track]:
        """获取追踪"""
        return self.tracker.get_track(track_id)
    
    def update_track_result(self, track_id: int, grade: int, defects: List[str], is_ng: bool):
        """更新追踪结果"""
        self.tracker.update_track_result(track_id, grade, defects, is_ng)

