#!/usr/bin/env python3
"""用连续图片模拟视频流测试跟踪系统"""
import sys
import os
sys.path.insert(0, '/tmp/potato_inspection_system/scripts')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from grade_potato_realtime import *
from pathlib import Path
import cv2
import time

def simulate_video_from_images(image_dir: str, fps: int = 5):
    """将图片目录转换为视频流模拟器"""
    images = sorted(Path(image_dir).glob("*.jpg")) + sorted(Path(image_dir).glob("*.jpeg"))
    
    print(f"找到 {len(images)} 张图片")
    
    for img_path in images:
        frame = cv2.imread(str(img_path))
        if frame is not None:
            yield frame
            time.sleep(1.0 / fps)  # 控制帧率

def main():
    model_path = "/tmp/potato_inspection_system/runs/yolov8s-obb-potato/weights/best.pt"
    image_dir = "/tmp/potato_inspection_system/data/test/project-3-at-2025-10-30-19-49-55a1bb93(1)/images/test"
    rules_path = "/tmp/potato_inspection_system/config/grading_rules.json"
    out_dir = Path("/tmp/potato_inspection_system/results/tracking_test")
    
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print("加载模型...")
    model = YOLO(model_path)
    rules = load_rules(Path(rules_path))
    
    id_gen = PotatoIDGenerator()
    tracker = PotatoTracker(id_gen)
    
    jsonl_path = out_dir / "tracked_potatoes.jsonl"
    csv_path = out_dir / "tracked_potatoes.csv"
    
    # 视频录制
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_video = None
    
    frame_idx = 0
    graded_potatoes = set()
    
    print("\n开始处理图片流...\n")
    
    with open(jsonl_path, 'w', encoding='utf-8') as jf, \
         open(csv_path, 'w', newline='', encoding='utf-8') as cf:
        
        csv_writer = csv.writer(cf)
        csv_writer.writerow(["potato_id", "frame", "bbox_json", "grade", "signal_bits", "lane", "counts_json", "timestamp"])
        
        for frame in simulate_video_from_images(image_dir, fps=2):
            if out_video is None:
                h, w = frame.shape[:2]
                out_video = cv2.VideoWriter(
                    str(out_dir / "tracked_output.mp4"),
                    fourcc, 2.0, (w, h)
                )
            
            # 提取土豆
            detections = extract_potatoes_from_frame(frame)
            
            # 更新跟踪器
            tracked = tracker.update(detections)
            
            # 对每个跟踪到的土豆进行分级
            for track_id, track_info in tracked.items():
                if track_info.get("disappeared", 0) > 0:
                    continue
                
                potato_id = track_info["potato_id"]
                
                # 如果还未分级，进行分级
                if not track_info.get("graded", False):
                    grade, counts, signal_bits, lane, area = grade_potato_roi(
                        frame, track_info["bbox"], model, rules, 0.25
                    )
                    track_info["grade"] = grade
                    track_info["counts"] = counts
                    track_info["signal"] = {
                        "bits": signal_bits,
                        "bit_order": rules["signals"]["bit_order"],
                        "lane": lane
                    }
                    track_info["graded"] = True
                    track_info["area_px"] = area
                    
                    # 写入结果
                    if potato_id not in graded_potatoes:
                        record = {
                            "potato_id": potato_id,
                            "frame": frame_idx,
                            "bbox": track_info["bbox"],
                            "counts": counts,
                            "grade": grade,
                            "signal": track_info["signal"],
                            "timestamp": time.time()
                        }
                        jf.write(json.dumps(record, ensure_ascii=False) + "\n")
                        jf.flush()
                        
                        csv_writer.writerow([
                            potato_id,
                            frame_idx,
                            json.dumps(track_info["bbox"]),
                            grade,
                            ''.join(map(str, signal_bits)),
                            lane,
                            json.dumps(counts, ensure_ascii=False),
                            time.time()
                        ])
                        
                        graded_potatoes.add(potato_id)
                        print(f"✓ [{potato_id}] {grade:8s} Lane:{lane} - 缺陷:{counts}")
                
                # 绘制跟踪结果
                frame = draw_tracked_potato(frame, track_info, show_trail=True)
            
            # 显示帧信息
            active_count = len([t for t in tracked.values() if t.get('disappeared', 0) == 0])
            info_text = f"Frame: {frame_idx} | Tracked: {active_count} | Total Graded: {len(graded_potatoes)}"
            cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            
            # 保存（无显示模式）
            if out_video:
                out_video.write(frame)
            
            # 保存每10帧的快照
            if frame_idx % 3 == 0:
                snapshot_path = out_dir / f"frame_{frame_idx:04d}.jpg"
                cv2.imwrite(str(snapshot_path), frame)
            
            frame_idx += 1
    
    if out_video:
        out_video.release()
    cv2.destroyAllWindows()
    
    print(f"\n{'='*60}")
    print(f"处理完成!")
    print(f"{'='*60}")
    print(f"  总帧数(图片): {frame_idx}")
    print(f"  检测到土豆: {len(graded_potatoes)} 个")
    print(f"  输出目录: {out_dir}")
    print(f"  - JSONL: {jsonl_path}")
    print(f"  - CSV: {csv_path}")
    print(f"  - 视频: {out_dir / 'tracked_output.mp4'}")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()

