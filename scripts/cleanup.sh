#!/bin/bash
# 清理脚本 - 清理旧日志和图像文件

set -e

echo "================================"
echo "系统清理工具"
echo "================================"

# 清理参数
LOG_RETENTION_DAYS=30
IMAGE_RETENTION_DAYS=7

# 清理日志
echo "清理 ${LOG_RETENTION_DAYS} 天前的日志文件..."
find logs/ -name "*.log" -mtime +${LOG_RETENTION_DAYS} -type f -delete 2>/dev/null || true
find logs/ -name "*.log.zip" -mtime +${LOG_RETENTION_DAYS} -type f -delete 2>/dev/null || true

deleted_logs=$(find logs/ -name "*.log" -mtime +${LOG_RETENTION_DAYS} -type f 2>/dev/null | wc -l)
echo "已删除 ${deleted_logs} 个旧日志文件"

# 清理图像
echo "清理 ${IMAGE_RETENTION_DAYS} 天前的图像文件..."
find captures/ -name "*.jpg" -mtime +${IMAGE_RETENTION_DAYS} -type f -delete 2>/dev/null || true
find captures/ -name "*.png" -mtime +${IMAGE_RETENTION_DAYS} -type f -delete 2>/dev/null || true

deleted_images=$(find captures/ -name "*.jpg" -mtime +${IMAGE_RETENTION_DAYS} -type f 2>/dev/null | wc -l)
echo "已删除 ${deleted_images} 个旧图像文件"

# 清理空目录
echo "清理空目录..."
find logs/ -type d -empty -delete 2>/dev/null || true
find captures/ -type d -empty -delete 2>/dev/null || true

# 显示磁盘使用情况
echo ""
echo "当前磁盘使用情况:"
du -sh logs/ captures/ 2>/dev/null || true

echo ""
echo "清理完成！"

