#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立的检测服务：监控相机目录，检测图片，将结果写入PLC寄存器
---------------- 第一版最终的 ---------------------

此脚本与 cam_plc_capture.py 和 plc_dummy_loop.py 配合工作：
- cam_plc_capture.py: 负责拍照存图（不改动）
- plc_dummy_loop.py: 负责监测状态（不改动）
- 本脚本: 负责检测图片并写入PLC的attrs_base寄存器

使用方法：
    python scripts/detect_and_write_plc.py \
        --camera_dir F:/data/camera \
        --model models/yolov8s-obb-potato-v22_best.pt \
        --rules config/grading_rules.json \
        --plc_ip 192.168.1.1 \
        --plc_port 502 \
        --channels 1,2,3,4 \
        --addr_base 0
"""

import argparse
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import cv2
import numpy as np
from ultralytics import YOLO
import socket
import struct

# 导入PLC寄存器定义
# 生产环境目录结构：F:\seven\seven_plc_vision_app\
# - app/ (已有)
# - plc/ (新增)
# - scripts/ (新增)
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from plc.registers import attrs_base, now_reg, ready2_reg, wrap60
except ImportError as e:
    # 如果导入失败，尝试其他路径
    print(f"[warning] Failed to import plc.registers: {e}")
    print(f"[info] Project root: {project_root}")
    print(f"[info] Checking for plc/registers.py...")
    plc_registers = project_root / "plc" / "registers.py"
    if plc_registers.exists():
        print(f"[info] Found: {plc_registers}")
        # 确保项目根目录在路径中
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from plc.registers import attrs_base, now_reg, ready2_reg, wrap60
    else:
        print(f"[error] plc/registers.py not found at: {plc_registers}")
        raise


class ModbusTCP:
    """Modbus TCP客户端（与cam_plc_capture.py中的实现保持一致）"""
    def __init__(self, host: str, port: int = 502, timeout: float = 1.0, unit_id: int = 1):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.unit_id = unit_id
        self.tid = 1
        self.sock: Optional[socket.socket] = None

    def connect(self):
        self.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect((self.host, self.port))
        self.sock = s

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.sock = None

    def _next_tid(self) -> int:
        self.tid = (self.tid + 1) & 0xFFFF
        if self.tid == 0:
            self.tid = 1
        return self.tid

    def _recvn(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))  # type: ignore[arg-type]
            if not chunk:
                break
            buf.extend(chunk)
        return bytes(buf)

    def _send_pdu(self, pdu: bytes) -> bytes:
        if not self.sock:
            self.connect()
        tid = self._next_tid()
        mbap = struct.pack(">HHHB", tid, 0, len(pdu) + 1, self.unit_id)
        self.sock.sendall(mbap + pdu)  # type: ignore[arg-type]
        hdr = self._recvn(7)
        if len(hdr) != 7:
            raise IOError("MBAP short")
        r_tid, r_pid, r_len, r_uid = struct.unpack(">HHHB", hdr)
        if r_tid != tid or r_pid != 0 or r_uid != self.unit_id:
            raise IOError("MBAP mismatch")
        payload = self._recvn(r_len - 1)
        if len(payload) != r_len - 1:
            raise IOError("PDU short")
        if payload and (payload[0] & 0x80):
            code = payload[1] if len(payload) > 1 else -1
            raise IOError(f"Modbus exception fc=0x{payload[0]:02X}, code={code}")
        return payload

    def write_single(self, addr: int, value: int) -> bool:
        """写入单个寄存器（功能码0x06）"""
        pdu = struct.pack(">BHH", 0x06, addr, value & 0xFFFF)
        r = self._send_pdu(pdu)
        return (len(r) == 5 and r[0] == 0x06)
    
    def read_single(self, addr: int) -> Optional[int]:
        """读取单个寄存器（功能码0x03）- 参考plc_dummy_loop.py的实现"""
        try:
            pdu = struct.pack(">BHH", 0x03, addr, 1)
            r = self._send_pdu(pdu)
            if len(r) >= 4 and r[0] == 0x03:
                byte_count = r[1]
                if byte_count >= 2:
                    # 从偏移2开始读取2字节（大端序）
                    value = (r[2] << 8) | r[3]
                    return value
        except Exception as e:
            pass
        return None
    
    def read_multiple(self, addr: int, count: int) -> Optional[List[int]]:
        """读取多个连续寄存器（功能码0x03）- 参考plc_dummy_loop.py的实现"""
        try:
            pdu = struct.pack(">BHH", 0x03, addr, count)
            r = self._send_pdu(pdu)
            if len(r) < 2 or r[0] != 0x03:
                return None
            byte_count = r[1]
            if byte_count != count * 2 or len(r) != 2 + byte_count:
                return None
            values = []
            for i in range(count):
                # 从偏移2开始，每个寄存器2字节（大端序）
                value = (r[2 + 2*i] << 8) | r[3 + 2*i]
                values.append(value)
            return values
        except Exception as e:
            pass
        return None


def load_rules(path: Path) -> Dict[str, Any]:
    """加载分级规则"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def is_ok(counts: Dict[str, int], rules: Dict[str, Any]) -> bool:
    """判断是否为OK品"""
    rule = rules["ok_rules"]
    for forb in rule.get("forbid", []):
        if counts.get(forb, 0) > 0:
            return False
    max_counts = rule.get("max_counts", {})
    for cls, limit in max_counts.items():
        if counts.get(cls, 0) > limit:
            return False
    return True


def estimate_size_from_area(area_px: float, rules: Dict[str, Any], area_history: Optional[List[float]] = None) -> int:
    """
    根据面积估算尺寸等级（从大到小：S1最大，S7最小）
    
    参数:
        area_px: 土豆像素面积
        rules: 分级规则配置
        area_history: 历史面积列表（用于动态计算分位数阈值）
    
    返回:
        1-7: 对应OK_S1到OK_S7（S1最大，S7最小）
    """
    # 如果提供了历史面积数据，使用分位数动态计算阈值
    if area_history and len(area_history) >= 7:
        # 使用分位数均匀分配7个等级
        # 从大到小：S1最大(>93.3%), S2(80-93.3%), S3(66.7-80%), S4(53.3-66.7%), 
        #           S5(40-53.3%), S6(26.7-40%), S7最小(<26.7%)
        percentiles = [100 - (i * 100 / 7) for i in range(8)]  # [100, 85.7, 71.4, 57.1, 42.9, 28.6, 14.3, 0]
        percentiles.reverse()  # [0, 14.3, 28.6, 42.9, 57.1, 71.4, 85.7, 100]
        thresholds = [np.percentile(area_history, p) for p in percentiles[1:-1]]  # 6个阈值，分成7段
        thresholds.reverse()  # 从大到小排序
        
        # 根据面积从大到小分配等级（S1最大，S7最小）
        for idx, threshold in enumerate(thresholds, start=1):
            if area_px >= threshold:
                return idx  # S1=1(最大), S2=2, ..., S7=7(最小)
        return 7  # 最小等级
    
    # 如果没有历史数据，使用配置文件中的固定阈值
    # 但需要调整逻辑：从大到小分配（S1最大，S7最小）
    cfg = rules.get("size", {})
    thresholds = cfg.get("thresholds_px", [])
    if not thresholds:
        # 初始阈值：基于实际检测数据（从大到小）
        # 数据来源：30个实际检测的OK土豆面积
        # 面积范围：87606 - 435767 像素²
        # 基于分位数计算的7级阈值（从大到小，S1最大，S7最小）
        # S1: >= 365730, S2: >= 330168, S3: >= 311345, S4: >= 265561, S5: >= 224704, S6: >= 135848, S7: < 135848
        thresholds = [365730, 330168, 311345, 265561, 224704, 135848]
    
    # 阈值应该从大到小排序（S1最大，S7最小）
    thresholds_sorted = sorted(thresholds, reverse=True)
    
    # 根据面积从大到小分配等级
    for idx, threshold in enumerate(thresholds_sorted, start=1):
        if area_px >= threshold:
            return idx  # S1=1(最大), S2=2, ..., S7=7(最小)
    return 7  # 最小等级


def grade_potato_with_defects(
    potato_info: Dict,
    rules: Dict[str, Any],
    area_history: Optional[List[float]] = None
) -> tuple:
    """
    根据土豆信息和关联的缺陷进行分级
    potato_info: 包含bbox, area, defects等信息
    area_history: 历史面积列表（用于动态计算分位数阈值）
    """
    # 统计缺陷数量（从已关联的缺陷中统计）
    counts: Dict[str, int] = {}
    for defect in potato_info.get("defects", []):
        defect_class = defect["class"]
        if defect_class != "potato":  # 排除potato标签本身
            counts[defect_class] = counts.get(defect_class, 0) + 1
    
    area_px = potato_info["area"]
    
    # 根据缺陷判断是否OK
    if is_ok(counts, rules):
        size_bin = estimate_size_from_area(area_px, rules, area_history)
        grade = f"OK_S{size_bin}"
    else:
        grade = "NG"
    
    return grade, counts, area_px


def extract_potatoes_with_defects_from_image(image: np.ndarray, model: YOLO, conf: float = 0.25) -> tuple:
    """
    使用YOLO模型检测所有类别（potato和缺陷）
    返回: (potatoes, all_defects)
    - potatoes: 土豆列表，每个包含bbox和关联的缺陷
    - all_defects: 所有缺陷列表
    """
    # 使用YOLO模型检测所有类别
    # 对potato使用更高的置信度阈值，减少误检
    results = model.predict(
        task='obb', source=image, imgsz=640, conf=conf,
        save=False, device='cpu', verbose=False
    )
    
    if not results or len(results) == 0:
        return [], []
    
    r = results[0]
    potatoes = []
    all_defects = []
    
    # 图像尺寸，用于面积过滤
    img_h, img_w = image.shape[:2]
    img_area = img_w * img_h
    min_potato_area = img_area * 0.01  # 至少占图像1%
    max_potato_area = img_area * 0.5   # 最多占图像50%
    
    # 提取所有检测结果
    if getattr(r, 'obb', None) is not None:
        names = r.names
        obb_data = r.obb
        
        clses = obb_data.cls.cpu().numpy()
        confs = obb_data.conf.cpu().numpy()
        xyxyxyxy = obb_data.xyxyxyxy.cpu().numpy()
        xywhr = obb_data.xywhr.cpu().numpy()
        
        for cls_id, conf_val, points, xywhr_val in zip(clses, confs, xyxyxyxy, xywhr):
            if conf_val < conf:
                continue
            
            class_name = names[int(cls_id)]
            points_int = points.reshape((-1, 2)).astype(np.int32)
            area = cv2.contourArea(points_int)
            cx, cy = float(xywhr_val[0]), float(xywhr_val[1])
            
            if class_name == "potato":
                # 这是土豆个体 - 使用更严格的过滤
                # 1. 提高置信度阈值（potato需要更高的置信度）
                if conf_val < max(conf, 0.3):  # 至少0.3
                    continue
                
                # 2. 面积过滤（太小或太大可能是误检）
                if area < min_potato_area or area > max_potato_area:
                    continue
                
                x, y, w, h = cv2.boundingRect(points_int)
                
                # 3. 尺寸合理性检查（宽高比不能太极端）
                aspect_ratio = max(w, h) / max(min(w, h), 1)
                if aspect_ratio > 5:  # 长宽比超过5:1可能是误检
                    continue
                
                potatoes.append({
                    "bbox": [int(x), int(y), int(w), int(h)],
                    "area": float(area),
                    "confidence": float(conf_val),
                    "obb_points": points,
                    "center": (cx, cy)
                })
            else:
                # 这是缺陷或其他类别
                all_defects.append({
                    "class": class_name,
                    "confidence": float(conf_val),
                    "center": (cx, cy),
                    "obb_points": points,
                    "area": float(area)
                })
    
    # 将缺陷关联到对应的土豆
    for potato in potatoes:
        potato["defects"] = []
        potato_bbox = potato["bbox"]
        px, py, pw, ph = potato_bbox
        
        for defect in all_defects:
            defect_center = defect["center"]
            # 如果缺陷中心在土豆bbox内，则关联
            if (px <= defect_center[0] <= px + pw and 
                py <= defect_center[1] <= py + ph):
                potato["defects"].append(defect)
    
    # NMS去重：移除重叠度高的土豆检测框（提高IoU阈值）
    if len(potatoes) > 1:
        potatoes.sort(key=lambda x: x["confidence"], reverse=True)
        filtered_potatoes = []
        for potato in potatoes:
            is_duplicate = False
            for existing in filtered_potatoes:
                iou = calculate_iou(potato["bbox"], existing["bbox"])
                # 提高IoU阈值到0.6，减少误去重
                if iou > 0.6:
                    is_duplicate = True
                    break
            if not is_duplicate:
                filtered_potatoes.append(potato)
        potatoes = filtered_potatoes
    
    return potatoes, all_defects


def grade_to_plc_value(grade: str) -> int:
    """
    将分级结果转换为PLC寄存器值
    根据PLC规范：
    - 1: 缺省
    - 2-8: 正常土豆对应尺寸类别+1 (OK_S1->2, OK_S2->3, ..., OK_S7->8)
    - 9: 异常土豆 (NG)
    """
    if grade == "NG":
        return 9  # 异常土豆
    elif grade.startswith("OK_S"):
        try:
            size = int(grade.split("_S")[1])
            if 1 <= size <= 7:
                return size + 1  # OK_S1->2, OK_S2->3, ..., OK_S7->8
        except:
            pass
    return 1  # 缺省值


def get_channel_from_filename(filename: str) -> Optional[int]:
    """从文件名提取通道号：CH{CC}_{YYYYMMDD}_{HHMMSS}-{N}.jpg"""
    match = re.search(r'CH(\d+)_', filename.upper())
    if match:
        return int(match.group(1))
    return None


def calculate_iou(bbox1: List[int], bbox2: List[int]) -> float:
    """计算两个bbox的IoU"""
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2
    
    xi1 = max(x1, x2)
    yi1 = max(y1, y2)
    xi2 = min(x1 + w1, x2 + w2)
    yi2 = min(y1 + h1, y2 + h2)
    
    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    box1_area = w1 * h1
    box2_area = w2 * h2
    union_area = box1_area + box2_area - inter_area
    
    return inter_area / union_area if union_area > 0 else 0


class PotatoTracker:
    """土豆追踪器：跨帧追踪同一个土豆，保持ID一致"""
    
    def __init__(self, channel: int):
        self.channel = channel
        self.tracked_potatoes: Dict[int, Dict] = {}  # track_id -> track_info
        self.next_track_id = 1
        self.max_disappeared = 3  # 最多消失帧数（连续3帧未出现则认为离开画面）
        self.iou_threshold = 0.3  # IoU匹配阈值（降低以提高匹配成功率，减少重复计数）
        self.min_track_frames = 2  # 最小追踪帧数（只有追踪超过此帧数的土豆才输出结果，避免单帧误检）
    
    def update(self, detections: List[Dict], image: np.ndarray, model: YOLO, rules: Dict, conf: float, area_history: Optional[List[float]] = None) -> Dict[int, Dict]:
        """
        更新追踪器，对每个检测到的土豆进行分级
        
        Args:
            detections: 检测到的土豆列表 [{"bbox": [x,y,w,h], "area": float, "defects": [...]}, ...]
            image: 图像（用于获取尺寸，判断边缘）
            model: YOLO模型（未使用，保留接口兼容）
            rules: 分级规则
            conf: 置信度阈值（未使用，保留接口兼容）
            area_history: 历史面积列表（用于动态计算分位数阈值）
            
        Returns:
            活跃的追踪字典 {track_id: track_info}
        """
        active_tracks = {}
        
        # 获取图像尺寸，用于边缘检测
        img_h, img_w = image.shape[:2] if image is not None else (1000, 1000)  # 默认值
        edge_threshold = img_h * 0.1  # 边缘阈值：图像高度的10%
        
        # 对每个检测到的土豆进行分级（使用已关联的缺陷）
        graded_detections = []
        for det in detections:
            grade, counts, area = grade_potato_with_defects(det, rules, area_history)
            bbox = det["bbox"]
            # 计算中心点
            cx = bbox[0] + bbox[2] / 2
            cy = bbox[1] + bbox[3] / 2
            graded_detections.append({
                "bbox": bbox,
                "area": det["area"],
                "grade": grade,
                "counts": counts,
                "defects": det.get("defects", []),
                "center": (cx, cy),
                "is_near_top": cy < edge_threshold,  # 靠近顶部
                "is_near_bottom": cy > (img_h - edge_threshold)  # 靠近底部
            })
        
        # 匹配检测结果与已有追踪（使用匈牙利算法风格的匹配）
        # 先计算所有IoU矩阵和中心点距离
        # 考虑活跃的追踪和刚消失的追踪（disappeared <= 1，可能是边缘入画导致的短暂消失）
        iou_matrix = []
        distance_matrix = []
        track_ids_list = []
        for track_id, tracked in self.tracked_potatoes.items():
            disappeared = tracked.get("disappeared", 0)
            # 考虑活跃的追踪和刚消失1帧的追踪（可能是边缘入画导致的短暂消失）
            if disappeared <= 1:
                track_ids_list.append(track_id)
        
        for det in graded_detections:
            iou_row = []
            dist_row = []
            for track_id in track_ids_list:
                tracked = self.tracked_potatoes[track_id]
                iou = calculate_iou(det["bbox"], tracked["bbox"])
                iou_row.append(iou)
                
                # 计算中心点距离（用于边缘匹配）
                tracked_bbox = tracked["bbox"]
                tracked_cx = tracked_bbox[0] + tracked_bbox[2] / 2
                tracked_cy = tracked_bbox[1] + tracked_bbox[3] / 2
                dist = ((det["center"][0] - tracked_cx) ** 2 + (det["center"][1] - tracked_cy) ** 2) ** 0.5
                dist_row.append(dist)
            iou_matrix.append(iou_row)
            distance_matrix.append(dist_row)
        
        # 贪心匹配：按IoU从高到低排序，确保一对一匹配
        # 构建所有可能的匹配对（考虑边缘情况，降低IoU阈值）
        all_matches = []
        for det_idx in range(len(graded_detections)):
            det = graded_detections[det_idx]
            for track_idx, track_id in enumerate(track_ids_list):
                tracked = self.tracked_potatoes[track_id]
                iou = iou_matrix[det_idx][track_idx]
                dist = distance_matrix[det_idx][track_idx]
                
                # 判断追踪是否在边缘附近
                tracked_bbox = tracked["bbox"]
                tracked_cy = tracked_bbox[1] + tracked_bbox[3] / 2
                tracked_is_near_top = tracked_cy < edge_threshold
                tracked_is_near_bottom = tracked_cy > (img_h - edge_threshold)
                
                # 对于边缘附近的追踪，降低IoU阈值或使用中心点距离
                threshold = self.iou_threshold
                if det["is_near_top"] or det["is_near_bottom"] or tracked_is_near_top or tracked_is_near_bottom:
                    # 边缘情况：降低IoU阈值，或使用中心点距离
                    threshold = max(0.15, self.iou_threshold * 0.5)  # 降低到0.15或原阈值的一半
                    # 如果中心点距离很近（小于bbox宽度的2倍），也认为匹配
                    bbox_w = max(det["bbox"][2], tracked_bbox[2])
                    if dist < bbox_w * 2 and iou > 0.1:  # 中心点距离很近，IoU>0.1即可
                        all_matches.append((det_idx, track_id, iou, dist))
                        continue
                
                if iou > threshold:
                    all_matches.append((det_idx, track_id, iou, dist))
        
        # 按IoU从高到低排序
        all_matches.sort(key=lambda x: x[2], reverse=True)
        
        # 一对一匹配：每个检测框和每个追踪只能匹配一次
        matched_tracks = set()
        matched_dets = set()
        matches = []
        
        for det_idx, track_id, iou_val, dist_val in all_matches:
            if det_idx not in matched_dets and track_id not in matched_tracks:
                matches.append((det_idx, track_id, iou_val))
                matched_dets.add(det_idx)
                matched_tracks.add(track_id)
        
        # 处理匹配的检测
        for det_idx, track_id, iou_val in matches:
            det = graded_detections[det_idx]
            track = self.tracked_potatoes[track_id]
            track["bbox"] = det["bbox"]
            track["area"] = det["area"]
            track["disappeared"] = 0
            track["frame_count"] = track.get("frame_count", 0) + 1
            track["grade"] = det["grade"]
            track["counts"] = det["counts"]
            track["grades_history"] = track.get("grades_history", []) + [det["grade"]]
            track["last_seen"] = time.time()
            active_tracks[track_id] = track
        
        # 处理未匹配的检测（创建新追踪）
        for det_idx, det in enumerate(graded_detections):
            if det_idx not in matched_dets:
                track_id = self.next_track_id
                self.next_track_id += 1
                self.tracked_potatoes[track_id] = {
                    "track_id": track_id,
                    "bbox": det["bbox"],
                    "area": det["area"],
                    "grade": det["grade"],
                    "counts": det["counts"],
                    "disappeared": 0,
                    "frame_count": 1,
                    "grades_history": [det["grade"]],
                    "first_seen": time.time(),
                    "last_seen": time.time()
                }
                active_tracks[track_id] = self.tracked_potatoes[track_id]
        
        # 标记消失的目标
        for track_id in self.tracked_potatoes:
            if track_id not in active_tracks:
                self.tracked_potatoes[track_id]["disappeared"] = \
                    self.tracked_potatoes[track_id].get("disappeared", 0) + 1
                self.tracked_potatoes[track_id]["last_seen"] = time.time()
        
        return active_tracks
    
    def get_finished_tracks(self) -> List[Dict]:
        """获取已离开画面的追踪（消失帧数超过阈值，且追踪帧数达到最小值）"""
        finished = []
        to_remove = []
        
        for track_id, track in self.tracked_potatoes.items():
            disappeared = track.get("disappeared", 0)
            frame_count = track.get("frame_count", 0)
            # 只有消失超过阈值 且 追踪帧数达到最小值的土豆才输出结果
            # 这样可以避免单帧误检被当作土豆
            if disappeared >= self.max_disappeared and frame_count >= self.min_track_frames:
                finished.append(track)
                to_remove.append(track_id)
                print(f"[完成] ch{self.channel} | 土豆#{track_id} | 消失{disappeared}帧, 追踪{frame_count}帧 -> 准备输出结果")
            elif disappeared >= self.max_disappeared:
                # 追踪帧数不足，直接删除，不输出结果（可能是误检）
                print(f"[跳过] ch{self.channel} | 土豆#{track_id} | 消失{disappeared}帧但追踪仅{frame_count}帧（不足{self.min_track_frames}帧）-> 删除不输出")
                to_remove.append(track_id)
        
        # 清理已完成的追踪
        for track_id in to_remove:
            del self.tracked_potatoes[track_id]
        
        return finished


class DetectionService:
    """检测服务：监控目录，检测图片，追踪土豆，写入PLC"""
    
    def __init__(
        self,
        camera_dir: str,
        model: YOLO,
        rules: Dict[str, Any],
        plc_client: ModbusTCP,
        channels: List[int],
        addr_base: int,
        conf: float = 0.25
    ):
        self.camera_dir = Path(camera_dir)
        self.model = model
        self.rules = rules
        self.plc_client = plc_client
        self.channels = channels
        self.addr_base = addr_base
        self.conf = conf
        
        # 地址转换函数（与cam_plc_capture.py保持一致）
        self.A = (lambda addr: addr - 1) if addr_base == 1 else (lambda addr: addr)
        
        # 已处理的文件集合
        self.processed_files: Set[Path] = set()
        
        # 启动时间：只处理启动后新创建的图片
        self.start_time = time.time()
        
        # 每个通道一个追踪器
        self.trackers: Dict[int, PotatoTracker] = {
            ch: PotatoTracker(ch) for ch in channels
        }
        
        # 每个通道的最大ID（用于更新READY_2寄存器）
        self.channel_max_id: Dict[int, int] = {ch: 0 for ch in channels}
        
        # 每个通道上次使用的NOW值（用于检测NOW是否更新）
        self.channel_last_now: Dict[int, int] = {ch: 0 for ch in channels}
        
        # 每个通道的面积历史记录（用于动态计算分位数阈值，实现均匀分级）
        self.channel_area_history: Dict[int, List[float]] = {ch: [] for ch in channels}
        self.max_area_history_size = 1000  # 最多保存1000个面积值
        
        # 统计信息（只统计出画面的土豆，避免重复计数）
        self.stats = {
            "total_images": 0,
            "total_potatoes": 0,  # 已完成（出画面）的土豆数量
            "by_channel": {},
            "by_grade": {}
        }
        
        # 日志文件
        self.log_dir = Path("results/realtime_monitor")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"detection_log_{timestamp}.txt"
        self.detail_log_file = self.log_dir / f"detail_log_{timestamp}.jsonl"
        self.plc_write_log_file = self.log_dir / f"plc_write_log_{timestamp}.txt"  # PLC写入详细记录
        
        # 已处理文件记录（持久化，避免重启后重复处理）
        self.processed_file_record = self.log_dir / "processed_files.txt"
        self._load_processed_files()
    
    def _load_processed_files(self):
        """加载已处理的文件列表（从持久化文件）"""
        if self.processed_file_record.exists():
            try:
                with open(self.processed_file_record, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            self.processed_files.add(Path(line))
                print(f"[init] 加载已处理文件记录: {len(self.processed_files)} 个")
            except Exception as e:
                print(f"[init] 加载已处理文件记录失败: {e}")
    
    def _save_processed_file(self, image_path: Path):
        """保存已处理的文件路径（追加到文件）"""
        try:
            with open(self.processed_file_record, 'a', encoding='utf-8') as f:
                f.write(str(image_path) + "\n")
        except Exception as e:
            pass  # 静默失败，不影响主流程
    
    def _is_new_image(self, image_path: Path) -> bool:
        """判断图片是否为新拍摄的（启动后创建或修改的）"""
        if image_path in self.processed_files:
            return False
        
        # 检查文件修改时间（新拍摄的图片应该在启动时间之后）
        try:
            file_mtime = image_path.stat().st_mtime
            # 允许5秒的误差（文件系统时间可能略有偏差）
            return file_mtime >= (self.start_time - 5.0)
        except Exception:
            # 如果无法获取修改时间，检查是否已处理过
            return image_path not in self.processed_files
    
    def process_image(self, image_path: Path):
        """处理单张图片：检测、追踪、分级"""
        # 检查是否已处理过
        if image_path in self.processed_files:
            return
        
        # 检查是否为新图片（启动后新创建的）
        if not self._is_new_image(image_path):
            # 旧图片，标记为已处理但不处理
            self.processed_files.add(image_path)
            self._save_processed_file(image_path)
            return
        
        try:
            # 读取图片
            image = cv2.imread(str(image_path))
            if image is None:
                print(f"[detect] Failed to read: {image_path.name}")
                return
            
            # 提取通道号
            channel = get_channel_from_filename(image_path.name)
            if channel is None or channel not in self.channels:
                print(f"[detect] Invalid channel in filename: {image_path.name}")
                return
            
            # 获取该通道的追踪器
            tracker = self.trackers[channel]
            
            # 使用YOLO模型检测所有类别（potato和缺陷）
            detections, all_defects = extract_potatoes_with_defects_from_image(image, self.model, self.conf)
            
            # 显示检测到的所有类别（用于调试）
            if all_defects:
                defect_classes = {}
                for defect in all_defects:
                    cls = defect["class"]
                    defect_classes[cls] = defect_classes.get(cls, 0) + 1
                if defect_classes:
                    print(f"[检测] ch{channel} | {image_path.name} | 检测到类别: {defect_classes}")
            if not detections:
                # 即使没有检测到，也要标记已有追踪为消失
                for track_id in list(tracker.tracked_potatoes.keys()):
                    tracker.tracked_potatoes[track_id]["disappeared"] = \
                        tracker.tracked_potatoes[track_id].get("disappeared", 0) + 1
                # 检查是否有土豆离开画面
                finished_tracks = tracker.get_finished_tracks()
                for track in finished_tracks:
                    self._output_final_result(channel, track, image_path.name)
                
                # 不显示未检测到信息（减少日志噪音）
                # 如果有正在追踪的土豆，可以显示追踪状态
                active_tracks_count = len([t for t in tracker.tracked_potatoes.values() if t.get("disappeared", 0) == 0])
                if active_tracks_count > 0:
                    # 只在有追踪中的土豆时才显示（可选，如果还是太多可以完全移除）
                    pass  # 暂时不显示任何信息
                
                # 标记为已处理并保存
                self.processed_files.add(image_path)
                self._save_processed_file(image_path)
                return
            
            # 更新追踪器（会对每个土豆进行分级）
            # 获取该通道的面积历史记录（用于动态分位数分级）
            area_history = self.channel_area_history.get(channel, [])
            active_tracks = tracker.update(detections, image, self.model, self.rules, self.conf, area_history)
            
            # 更新面积历史记录（从分级结果中收集OK土豆的面积，用于后续动态调整阈值）
            # 遍历所有检测结果，收集OK土豆的面积
            for det in detections:
                area = det["area"]
                # 使用相同的面积历史记录进行分级（确保一致性）
                grade, _, _ = grade_potato_with_defects(det, self.rules, area_history)
                if grade.startswith("OK_"):
                    area_history.append(area)
                    # 限制历史记录大小，保持最近的数据
                    if len(area_history) > self.max_area_history_size:
                        area_history = area_history[-self.max_area_history_size:]
            self.channel_area_history[channel] = area_history
            
            # 显示检测结果（每张图片都显示，但信息简化）
            # 只显示有活跃追踪的图片（减少日志噪音）
            active_count = len(active_tracks)
            if active_count > 0:
                # 只显示文件名和时间戳，不显示完整路径
                img_name_short = image_path.name
                print(f"[→] ch{channel} | {img_name_short} | 检测:{len(detections)}个 | 追踪:{active_count}个")
            
            # 检查是否有土豆离开画面（消失超过阈值）
            finished_tracks = tracker.get_finished_tracks()
            if finished_tracks:
                print(f"[处理] ch{channel} | 发现{len(finished_tracks)}个土豆离开画面，准备输出结果")
            for track in finished_tracks:
                print(f"[调用] ch{channel} | 调用_output_final_result处理土豆#{track['track_id']}")
                self._output_final_result(channel, track, image_path.name)
            
            # 标记为已处理并保存
            self.processed_files.add(image_path)
            self._save_processed_file(image_path)
            
            self.stats["total_images"] += 1
            # 注意：土豆计数在_output_final_result中完成（当土豆离开画面时），避免重复计数
        
        except Exception as e:
            print(f"[✗] ch{channel} | 处理错误: {e}")
            import traceback
            traceback.print_exc()
    
    def _output_final_result(self, channel: int, track: Dict, image_name: str):
        """输出土豆的最终结果并写入PLC（当土豆离开画面时）"""
        print(f"[开始] ch{channel} | _output_final_result被调用，track_id={track.get('track_id')}")
        grade = track["grade"]
        track_id = track["track_id"]
        frame_count = track.get("frame_count", 1)
        grades_history = track.get("grades_history", [])
        print(f"[信息] ch{channel} | 土豆#{track_id} | grade={grade}, frame_count={frame_count}, history={grades_history}")
        
        # 使用最频繁的分级结果作为最终结果
        if grades_history:
            from collections import Counter
            grade_counts = Counter(grades_history)
            final_grade = grade_counts.most_common(1)[0][0]
        else:
            final_grade = grade
        
        # 根据模型输出转换为PLC值：
        # 1: 缺省
        # 2-8: 正常土豆对应尺寸类别+1 (OK_S1->2, OK_S2->3, ..., OK_S7->8)
        # 9: 异常土豆 (NG)
        plc_value = grade_to_plc_value(final_grade)
        print(f"[转换] ch{channel} | 土豆#{track_id} | 模型输出: {final_grade} -> PLC值: {plc_value}")
        
        # 根据PLC规范写入：
        # 1. 检查READY_1状态（PLC是否就绪）
        # 2. 读取NOW寄存器获取PLC分配的序号（完全依赖PLC，不使用本地slot）
        # 3. 如果NOW值没有变化，说明PLC还没更新，需要等待或重试
        # 4. 写入ATTRS[序号]
        # 5. 更新READY_2为当前最大ID
        try:
            # 检查READY_1状态（PLC是否就绪开始采相）
            from plc.registers import ready1_reg
            ready1_addr = self.A(ready1_reg(channel))
            ready1_value = self.plc_client.read_single(ready1_addr)
            if ready1_value is None:
                print(f"[✗] ch{channel} | 土豆#{track_id} | 无法读取READY_1，跳过写入")
                return
            if ready1_value == 0:
                print(f"[⚠️] ch{channel} | 土豆#{track_id} | READY_1=0（待机状态），PLC可能不会读取ATTRS，但仍尝试写入")
            
            # 读取NOW寄存器（PLC已分配的目标序号）
            now_addr = self.A(now_reg(channel))
            now_value = self.plc_client.read_single(now_addr)
            
            # 完全依赖PLC的NOW寄存器，不使用本地slot
            if now_value is None or now_value == 0:
                print(f"[✗] ch{channel} | 土豆#{track_id} | PLC NOW=0，跳过写入（等待PLC分配序号）")
                return
            
            # 根据plc_dummy_loop的逻辑：读取NOW值，写入到slot = NOW + 1
            # NOW值表示PLC已分配的序号，下一个要写入的slot就是NOW+1
            # 重要：如果NOW值没变化，说明PLC还没读取上一个值，需要等待，避免多个土豆写入同一slot
            last_now = self.channel_last_now.get(channel, 0)
            
            # 如果NOW值没变化且不是第一次写入，说明PLC还没更新，需要等待
            if now_value == last_now and last_now > 0:
                print(f"[等待] ch{channel} | 土豆#{track_id} | NOW值未更新({now_value})，等待PLC更新...")
                import time
                max_retries = 10
                retry_interval = 0.2
                updated = False
                for retry in range(max_retries):
                    time.sleep(retry_interval)
                    new_now_value = self.plc_client.read_single(now_addr)
                    if new_now_value and new_now_value != last_now:
                        now_value = new_now_value
                        updated = True
                        print(f"[更新] ch{channel} | 土豆#{track_id} | NOW更新为{now_value}")
                        break
                
                if not updated:
                    print(f"[✗] ch{channel} | 土豆#{track_id} | NOW值未更新({now_value})，跳过写入（避免覆盖其他土豆结果）")
                    return
            
            slot_id = wrap60(now_value + 1)
            
            # 安全检查：确保slot_id在有效范围内（1-60）
            if slot_id < 1 or slot_id > 60:
                print(f"[✗] ch{channel} | 土豆#{track_id} | 无效的slot_id={slot_id}（NOW={now_value}），跳过写入")
                return
            
            # 特殊检查：如果slot=1且NOW=60，需要特别小心，因为cam_plc_capture.py也在写入slot1
            # 如果slot1的值很大（>9），说明是cam_plc_capture.py写入的随机数，我们可以覆盖
            # 但如果值在2-9范围内，可能是我们之前写入的，需要小心
            if slot_id == 1:
                slot1_value = self.plc_client.read_single(attrs_addr)
                if slot1_value and slot1_value > 9:
                    print(f"[⚠️] ch{channel} | 土豆#{track_id} | 警告：写入slot1（NOW=60），当前值={slot1_value}（可能是cam_plc_capture.py写入），将覆盖")
                elif slot1_value and 2 <= slot1_value <= 9:
                    print(f"[⚠️] ch{channel} | 土豆#{track_id} | 警告：写入slot1（NOW=60），当前值={slot1_value}（可能是之前的检测结果），将覆盖")
            
            # 计算ATTRS数组的地址（参考plc_dummy_loop.py的逻辑）
            # slot 1 -> addr = attrs_base + 0
            # slot 2 -> addr = attrs_base + 1
            # ...
            # slot 60 -> addr = attrs_base + 59
            attrs_base_addr = attrs_base(channel)
            attrs_addr_raw = attrs_base_addr + (slot_id - 1)  # 原始地址（例如：700 + (51-1) = 750）
            attrs_addr = self.A(attrs_addr_raw)  # 应用地址转换（如果addr_base=1，则减1）
            
            # 安全检查：确保计算的地址在ATTRS范围内
            expected_max_addr = attrs_base_addr + 59  # slot60的地址
            if attrs_addr_raw < attrs_base_addr or attrs_addr_raw > expected_max_addr:
                print(f"[✗] ch{channel} | 土豆#{track_id} | 地址超出范围: {attrs_addr_raw} (BASE={attrs_base_addr}, 范围={attrs_base_addr}..{expected_max_addr})")
                return
            
            print(f"[地址] ch{channel} | 通道{channel} ATTRS_BASE={attrs_base_addr}, slot={slot_id}, 原始地址={attrs_addr_raw}, 转换后地址={attrs_addr}, addr_base={self.addr_base}")
            
            # 检查目标slot的当前值（读：清零的位置可以重写）
            current_value = self.plc_client.read_single(attrs_addr)
            print(f"[调试] ch{channel} | 土豆#{track_id} | NOW={now_value} -> slot={slot_id}, 写入地址={attrs_addr}(原始{attrs_addr_raw}), 当前值={current_value}, 准备写入={plc_value}")
            
            # 写入ATTRS数组（根据模型输出：1缺省, 2-8正常土豆尺寸类别+1, 9异常土豆）
            print(f"[写入] ch{channel} | 土豆#{track_id} | 写入: slot={slot_id}, addr={attrs_addr}(原始{attrs_addr_raw}, BASE={attrs_base_addr}), value={plc_value}, NOW={now_value}")
            
            # 记录写入前的状态
            write_timestamp = datetime.now().isoformat()
            write_record = {
                "timestamp": write_timestamp,
                "channel": channel,
                "track_id": track_id,
                "before_write": {
                    "now_value": now_value,
                    "slot_id": slot_id,
                    "attrs_base": attrs_base_addr,
                    "addr_raw": attrs_addr_raw,
                    "addr_actual": attrs_addr,
                    "current_value": current_value,
                    "addr_base": self.addr_base
                },
                "write_data": {
                    "final_grade": final_grade,
                    "plc_value": plc_value,
                    "grades_history": grades_history,
                    "frame_count": frame_count
                }
            }
            
            ok = self.plc_client.write_single(attrs_addr, plc_value)
            
            if ok:
                # 验证写入：立即读取刚写入的值
                verify_value = self.plc_client.read_single(attrs_addr)
                verify_status = "✓" if verify_value == plc_value else f"✗(读回{verify_value})"
                
                # 记录写入后的状态
                write_record["after_write"] = {
                    "write_success": True,
                    "verify_value": verify_value,
                    "verify_status": verify_status,
                    "read_immediately_after_write": verify_value
                }
                
                # 等待一小段时间后再次读取，检查PLC是否读取并清零
                import time
                time.sleep(0.1)  # 等待100ms
                read_after_delay = self.plc_client.read_single(attrs_addr)
                write_record["after_write"]["read_after_100ms"] = read_after_delay
                
                # 记录到PLC写入日志文件（详细格式）
                with open(self.plc_write_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{write_timestamp}] ch{channel} | 土豆#{track_id} | "
                           f"NOW={now_value} -> slot={slot_id} | "
                           f"地址: {attrs_addr}(原始{attrs_addr_raw}, BASE={attrs_base_addr}, addr_base={self.addr_base}) | "
                           f"写入前值={current_value} | "
                           f"写入值={plc_value} | "
                           f"写入后立即读取={verify_value} | "
                           f"100ms后读取={read_after_delay} | "
                           f"验证={verify_status}")
                    if read_after_delay == 0 and verify_value == plc_value:
                        f.write(f" | ⚠️ PLC已读取并清零（正常行为）")
                    elif read_after_delay != plc_value and verify_value == plc_value:
                        f.write(f" | ⚠️ 值被修改（可能被其他程序覆盖）")
                    f.write("\n")
                
                # 同时记录JSON格式的详细日志
                with open(self.plc_write_log_file.with_suffix('.jsonl'), 'a', encoding='utf-8') as f:
                    f.write(json.dumps(write_record, ensure_ascii=False) + "\n")
                
                # 写入成功后，记录使用的NOW值（用于调试，不用于判断是否更新）
                # 注意：写入到slot=NOW+1后，PLC会读取这个值，然后NOW会自动更新为NOW+1
                self.channel_last_now[channel] = now_value
                
                # 更新该通道的最大ID
                self.channel_max_id[channel] = max(self.channel_max_id[channel], slot_id)
                
                # 更新READY_2寄存器（本波可读取的最大ID）
                # 重要：READY_2必须更新，PLC才会知道有多少个结果可以读取
                ready2_addr = self.A(ready2_reg(channel))
                ready2_ok = self.plc_client.write_single(ready2_addr, self.channel_max_id[channel])
                if not ready2_ok:
                    print(f"[✗] ch{channel} | 土豆#{track_id} | READY_2写入失败！PLC可能无法读取结果")
                else:
                    # 验证READY_2写入
                    verify_ready2 = self.plc_client.read_single(ready2_addr)
                    if verify_ready2 != self.channel_max_id[channel]:
                        print(f"[⚠️] ch{channel} | 土豆#{track_id} | READY_2验证失败：写入{self.channel_max_id[channel]}，读回{verify_ready2}")
                
                # 更新统计（只在成功写入PLC时统计，确保每个土豆只统计一次）
                self.stats["total_potatoes"] += 1  # 每个完成的追踪代表一个唯一的土豆
                self.stats["by_channel"][channel] = self.stats["by_channel"].get(channel, 0) + 1
                self.stats["by_grade"][final_grade] = self.stats["by_grade"].get(final_grade, 0) + 1
                
                # 简化终端输出（只显示出画面的土豆）
                status_note = ""
                if read_after_delay == 0 and verify_value == plc_value:
                    status_note = " | PLC已读取并清零（正常）"
                elif read_after_delay != plc_value and verify_value == plc_value:
                    status_note = f" | 值被修改为{read_after_delay}"
                print(f"[✓] ch{channel} | 土豆#{track_id} | {final_grade} | {frame_count}帧 | PLC:{plc_value}@{attrs_addr}(slot{slot_id}) | 验证:{verify_status} | READY_2:{self.channel_max_id[channel]}{'✓' if ready2_ok else '✗'}{status_note}")
                
                # 详细记录保存到文件
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "channel": channel,
                    "track_id": track_id,
                    "final_grade": final_grade,
                    "plc_value": plc_value,
                    "plc_address": attrs_addr,
                    "slot_id": slot_id,
                    "now_value": now_value,
                    "ready2_value": self.channel_max_id[channel],
                    "frame_count": frame_count,
                    "grades_history": grades_history,
                    "area": track.get("area", 0),
                    "counts": track.get("counts", {}),
                    "image": image_name
                }
                
                # 写入详细日志（JSONL格式）
                with open(self.detail_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                
                # 写入文本日志
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{log_entry['timestamp']}] ch{channel} | 土豆#{track_id} | {final_grade} | "
                           f"{frame_count}帧 | PLC:{plc_value}@{attrs_addr}(slot{slot_id}) | 历史:{','.join(grades_history)}\n")
            else:
                # 记录写入失败
                write_record["after_write"] = {
                    "write_success": False,
                    "error": "write_single returned False"
                }
                with open(self.plc_write_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{write_timestamp}] ch{channel} | 土豆#{track_id} | "
                           f"写入失败 | NOW={now_value} -> slot={slot_id} | "
                           f"地址: {attrs_addr}(原始{attrs_addr_raw}) | "
                           f"值={plc_value}({final_grade})\n")
                with open(self.plc_write_log_file.with_suffix('.jsonl'), 'a', encoding='utf-8') as f:
                    f.write(json.dumps(write_record, ensure_ascii=False) + "\n")
                
                print(f"[✗] ch{channel} | 土豆#{track_id} | PLC写入失败 (addr={attrs_addr}, value={plc_value})")
        except Exception as e:
            print(f"[✗] ch{channel} | 土豆#{track_id} | PLC错误: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.plc_client.connect()
                # 重试读取和写入
                now_addr = self.A(now_reg(channel))
                now_value = self.plc_client.read_single(now_addr)
                if now_value and now_value > 0:
                    slot_id = wrap60(now_value)
                    attrs_base_addr = attrs_base(channel)
                    attrs_addr = self.A(attrs_base_addr + slot_id - 1)
                    ok = self.plc_client.write_single(attrs_addr, plc_value)
                    if ok:
                        self.channel_max_id[channel] = max(self.channel_max_id[channel], slot_id)
                        ready2_addr = self.A(ready2_reg(channel))
                        self.plc_client.write_single(ready2_addr, self.channel_max_id[channel])
                        print(f"[✓] ch{channel} | 土豆#{track_id} | 重连后写入成功")
            except Exception as e2:
                print(f"[✗] ch{channel} | 土豆#{track_id} | 重连失败: {e2}")
        
        # 更新统计（只在土豆离开画面时统计一次，避免重复计数）
        # 注意：只有成功写入PLC的土豆才统计（在ok=True的分支中）
        # 这里先不统计，等写入成功后再统计
    
    def _print_plc_registers(self):
        """打印当前PLC寄存器状态（显示详细信息和所有非零值）"""
        try:
            print("\n[PLC寄存器状态]")
            for ch in self.channels:
                # 读取NOW寄存器
                now_addr = self.A(now_reg(ch))
                now_value = self.plc_client.read_single(now_addr)
                
                # 读取READY_2寄存器
                ready2_addr = self.A(ready2_reg(ch))
                ready2_value = self.plc_client.read_single(ready2_addr)
                
                attrs_base_addr = attrs_base(ch)
                
                # 打印基本状态
                print(f"  通道{ch}:")
                print(f"    NOW({now_reg(ch)}): {now_value if now_value is not None else 'N/A'} (实际地址:{now_addr})")
                print(f"    READY_2({ready2_reg(ch)}): {ready2_value if ready2_value is not None else 'N/A'} (实际地址:{ready2_addr})")
                
                # 读取整个ATTRS数组（60个值）
                try:
                    start_addr_actual = self.A(attrs_base_addr)
                    all_values = self.plc_client.read_multiple(start_addr_actual, 60)
                    
                    if all_values:
                        # 找出所有非零值
                        nonzero_slots = {}
                        for i, val in enumerate(all_values):
                            if val != 0:
                                slot = i + 1
                                nonzero_slots[slot] = val
                        
                        # 显示NOW值附近的slot（前后各10个，共21个）
                        if now_value and now_value > 0:
                            center_slot = wrap60(now_value)
                            print(f"    ATTRS[NOW附近, slot{max(1, center_slot-10)}..slot{min(60, center_slot+10)}]:")
                            
                            for slot in range(max(1, center_slot-10), min(61, center_slot+11)):
                                val = all_values[slot - 1]
                                addr = attrs_base_addr + (slot - 1)
                                marker = " <--NOW" if slot == center_slot else ""
                                print(f"      slot{slot:2d} = {val:2d} (addr{addr}){marker}")
                        
                        # 显示所有非零值（如果和上面的范围不同）
                        if nonzero_slots:
                            other_nonzero = {k: v for k, v in nonzero_slots.items() 
                                          if not (now_value and abs(wrap60(k) - wrap60(now_value)) <= 10)}
                            if other_nonzero:
                                print(f"    ATTRS[其他非零值]:")
                                for slot in sorted(other_nonzero.keys()):
                                    val = nonzero_slots[slot]
                                    addr = attrs_base_addr + (slot - 1)
                                    print(f"      slot{slot:2d} = {val:2d} (addr{addr})")
                        else:
                            print(f"    ATTRS: 所有值均为0")
                    else:
                        print(f"    ATTRS: 读取失败")
                except Exception as e:
                    print(f"    ATTRS: 读取错误 - {e}")
        except Exception as e:
            print(f"   [PLC读取错误] {e}")
            import traceback
            traceback.print_exc()
    
    def scan_directory(self):
        """扫描目录查找新图片（只处理启动后新创建的）"""
        today = datetime.now().strftime("%Y%m%d")
        today_dir = self.camera_dir / today
        
        if not today_dir.exists():
            return
        
        # 查找所有匹配的图片文件
        # 支持两种格式：
        # 1. CH01_20251112_121608-001.jpg (cam_plc_capture.py生成)
        # 2. ch01_121608-001.jpg (简化格式)
        pattern1 = re.compile(r'CH\d+_\d{8}_\d{6}-\d+\.jpg$', re.IGNORECASE)
        pattern2 = re.compile(r'ch\d+_\d{6}-\d+\.jpg$', re.IGNORECASE)
        
        new_images = []
        for img_path in today_dir.rglob("*.jpg"):
            if (pattern1.match(img_path.name) or pattern2.match(img_path.name)):
                if self._is_new_image(img_path):
                    new_images.append(img_path)
        
        # 按修改时间排序，先处理最新的
        new_images.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        for img_path in new_images:
            self.process_image(img_path)
    
    def run(self, scan_interval: float = 0.5):
        """运行检测服务"""
        print("=" * 60)
        print("Detection Service Started")
        print("=" * 60)
        print(f"Camera directory: {self.camera_dir}")
        print(f"PLC: {self.plc_client.host}:{self.plc_client.port}")
        print(f"Channels: {self.channels}")
        print(f"Scan interval: {scan_interval}s")
        print(f"Log file: {self.log_file}")
        print(f"Detail log: {self.detail_log_file}")
        print(f"Start time: {datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Processed files record: {self.processed_file_record}")
        print("-" * 60)
        print("Note: Only processing images created/modified after service start.")
        print("Detailed tracking info is saved to log files.")
        print("Terminal only shows summary (detection count and final results).")
        print("-" * 60)
        
        # 连接PLC
        try:
            self.plc_client.connect()
            print(f"[plc] Connected to {self.plc_client.host}:{self.plc_client.port}")
        except Exception as e:
            print(f"[plc] Connection failed: {e}")
            print("[plc] Will retry on first write")
        
        try:
            last_stat_time = time.time()
            last_heartbeat = time.time()
            stat_interval = 5.0  # 每5秒显示一次统计
            heartbeat_interval = 30.0  # 每30秒显示一次心跳（证明系统在运行）
            
            while True:
                self.scan_directory()
                time.sleep(scan_interval)
                
                current_time = time.time()
                
                # 心跳输出（即使没有检测到，也显示系统在运行）
                if current_time - last_heartbeat >= heartbeat_interval:
                    last_heartbeat = current_time
                    # 显示各通道状态
                    status_lines = []
                    for ch in self.channels:
                        active_count = len([t for t in self.trackers[ch].tracked_potatoes.values() 
                                           if t.get("disappeared", 0) == 0])
                        processed = self.stats["by_channel"].get(ch, 0)
                        status_lines.append(f"ch{ch}:追踪{active_count}个/已处理{processed}个")
                    print(f"[心跳] 系统运行中 | {' | '.join(status_lines)}")
                
                # 定期显示统计（每5秒或每30张图片）
                if (current_time - last_stat_time >= stat_interval) or \
                   (self.stats["total_images"] % 30 == 0 and self.stats["total_images"] > 0):
                    last_stat_time = current_time
                    
                    # 显示各通道的活跃追踪数
                    active_by_channel = {}
                    for ch in self.channels:
                        active_count = len([t for t in self.trackers[ch].tracked_potatoes.values() 
                                           if t.get("disappeared", 0) == 0])
                        active_by_channel[ch] = active_count
                    
                    print(f"\n[统计] 已处理: {self.stats['total_images']}张 | "
                          f"已完成: {self.stats['total_potatoes']}个土豆（出画面）")
                    print(f"       各通道追踪中: {active_by_channel}")
                    if self.stats["by_grade"]:
                        print(f"       分级统计: {dict(self.stats['by_grade'])}")
                    
                    # 打印PLC寄存器状态
                    self._print_plc_registers()
                    
                    print("-" * 60)
        
        except KeyboardInterrupt:
            print("\n[detect] Stopping...")
        finally:
            self.plc_client.close()
            print(f"\n[detect] Final statistics:")
            print(f"Total images processed: {self.stats['total_images']}")
            print(f"Total potatoes completed (left frame): {self.stats['total_potatoes']}")


def main():
    parser = argparse.ArgumentParser(
        description="检测服务：监控相机目录，检测图片，写入PLC寄存器"
    )
    parser.add_argument(
        "--camera_dir",
        default="F:/data/camera",
        help="相机图片存储根目录"
    )
    parser.add_argument(
        "--model",
        required=True,
        help="模型权重文件路径"
    )
    parser.add_argument(
        "--rules",
        default="config/grading_rules.json",
        help="分级规则文件路径"
    )
    parser.add_argument(
        "--plc_ip",
        default="192.168.1.1",
        help="PLC IP地址"
    )
    parser.add_argument(
        "--plc_port",
        type=int,
        default=502,
        help="PLC端口"
    )
    parser.add_argument(
        "--channels",
        default="1,2,3,4",
        help="通道列表，例如 1,2,3,4"
    )
    parser.add_argument(
        "--addr_base",
        type=int,
        choices=[0, 1],
        default=0,
        help="PLC地址是否1起始（1则发起始地址-1）"
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="检测置信度阈值"
    )
    parser.add_argument(
        "--scan_interval",
        type=float,
        default=0.5,
        help="扫描间隔（秒）"
    )
    
    args = parser.parse_args()
    
    # 加载模型和规则
    print("[init] Loading model...")
    model = YOLO(args.model)
    
    print("[init] Loading rules...")
    rules_path = Path(args.rules)
    if not rules_path.is_absolute():
        rules_path = Path(__file__).parent.parent / rules_path
    rules = load_rules(rules_path)
    
    # 解析通道列表
    channels = [int(x) for x in args.channels.split(",") if x.strip()]
    
    # 创建PLC客户端
    plc_client = ModbusTCP(args.plc_ip, args.plc_port)
    
    # 创建检测服务
    service = DetectionService(
        camera_dir=args.camera_dir,
        model=model,
        rules=rules,
        plc_client=plc_client,
        channels=channels,
        addr_base=args.addr_base,
        conf=args.conf
    )
    
    # 运行服务
    service.run(scan_interval=args.scan_interval)


if __name__ == '__main__':
    main()








