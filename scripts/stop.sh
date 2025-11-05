#!/bin/bash
# 停止土豆质检分级系统

set -e

echo "停止土豆质检分级系统..."

# 查找Python进程
pids=$(pgrep -f "python.*main.py" || true)

if [ -z "$pids" ]; then
    echo "系统未运行"
    exit 0
fi

# 发送SIGTERM信号
echo "发送停止信号到进程: $pids"
for pid in $pids; do
    kill -TERM $pid 2>/dev/null || true
done

# 等待进程退出
echo "等待进程退出..."
sleep 2

# 检查是否还在运行
pids=$(pgrep -f "python.*main.py" || true)
if [ ! -z "$pids" ]; then
    echo "强制终止进程: $pids"
    for pid in $pids; do
        kill -KILL $pid 2>/dev/null || true
    done
fi

echo "系统已停止"

