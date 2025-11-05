#!/usr/bin/env python3
from ultralytics import YOLO


def main():
    # Choose a model size: yolov8n-obb.pt, yolov8s-obb.pt, etc.
    model = YOLO('yolov8n-obb.pt')
    model.train(
        task='obb',
        data='/tmp/potato_inspection_system/yolo_potato_obb.yaml',
        imgsz=640,
        epochs=100,
        batch=16,
        device=0,
        project='/tmp/potato_inspection_system/runs',
        name='yolov8n-obb-potato'
    )


if __name__ == '__main__':
    main()


