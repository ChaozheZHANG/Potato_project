# 部署指南

本文档详细说明土豆质检分级系统的部署流程。

## 部署准备

### 硬件清单

1. **工控机**
   - CPU: Intel i5-10400 或更高
   - 内存: 16GB DDR4
   - 存储: 256GB SSD + 1TB HDD（可选）
   - GPU: NVIDIA GTX 1660 或更高（可选但推荐）
   - 网口: 2个千兆网口（一个连相机，一个连PLC）

2. **工业相机**
   - 型号: Basler acA4096-30um 或同等
   - 分辨率: 4096×3000
   - 接口: GigE
   - 镜头: 根据视野需求配置

3. **光源控制器**
   - 类型: LED条形光源
   - 控制: 支持外部触发
   - 亮度: 可调

4. **PLC**
   - 型号: 支持Modbus TCP或S7协议
   - I/O点数: 至少8个数字输出
   - 网络: 以太网接口

### 软件清单

1. **操作系统**
   - Ubuntu 20.04 LTS 或更高
   - Windows 10/11 专业版（也支持，但推荐Linux）

2. **Python环境**
   - Python 3.8 或更高
   - 虚拟环境管理

3. **相机SDK**
   - Basler pylon SDK（如使用Basler相机）
   - pypylon Python包

4. **NVIDIA驱动**（如使用GPU）
   - CUDA 11.x
   - cuDNN 8.x

## 部署步骤

### 1. 系统安装（Ubuntu）

```bash
# 更新系统
sudo apt update
sudo apt upgrade -y

# 安装基础工具
sudo apt install -y build-essential git vim wget curl

# 安装Python开发环境
sudo apt install -y python3.8 python3.8-dev python3-pip python3-venv

# 安装系统依赖
sudo apt install -y libopencv-dev python3-opencv
sudo apt install -y libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev
```

### 2. GPU驱动安装（可选）

```bash
# 安装NVIDIA驱动
sudo apt install -y nvidia-driver-525

# 安装CUDA Toolkit
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-ubuntu2004.pin
sudo mv cuda-ubuntu2004.pin /etc/apt/preferences.d/cuda-repository-pin-600
sudo apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/3bf863cc.pub
sudo add-apt-repository "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/ /"
sudo apt update
sudo apt install -y cuda-11-8

# 配置环境变量
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

# 验证安装
nvidia-smi
nvcc --version
```

### 3. 相机SDK安装（Basler）

```bash
# 下载pylon SDK (https://www.baslerweb.com/en/downloads/software-downloads/)
# 假设下载的文件是 pylon_6.3.0_setup.tar.gz

tar -xzf pylon_6.3.0_setup.tar.gz
cd pylon_6.3.0_setup
sudo mkdir -p /opt/pylon
sudo tar -C /opt/pylon -xzf pylon_6.3.0_*.tar.gz

# 配置环境
echo 'export PYLON_ROOT=/opt/pylon' >> ~/.bashrc
echo 'export PATH=$PYLON_ROOT/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# 安装pypylon
pip install pypylon
```

### 4. 部署应用

```bash
# 上传部署包到工控机
scp -r potato_inspection_system.tar.gz user@target-ip:/home/user/

# 解压
cd /home/user
tar -xzf potato_inspection_system.tar.gz
cd potato_inspection_system

# 运行安装脚本
chmod +x scripts/*.sh
./scripts/setup.sh
```

### 5. 配置系统

```bash
# 编辑配置文件
vim configs/system_config.yaml
```

**关键配置项：**

```yaml
# 相机配置
camera:
  model: "industrial"  # 使用真实相机
  
# PLC配置
plc:
  enable: true
  protocol: "modbus"
  ip: "192.168.1.100"  # 替换为实际PLC IP
  port: 502

# 模型配置
model:
  defect_model:
    path: "models/defect_detection.onnx"
    device: "cuda"  # 或 "cpu"
  grading_model:
    path: "models/grading_classifier.onnx"
    device: "cuda"  # 或 "cpu"

# 存储配置
storage:
  save_images: true
  save_ng_only: false  # 根据需求调整
```

### 6. 网络配置

**相机网络（假设eth0）：**
```bash
# 配置静态IP
sudo vim /etc/netplan/01-netcfg.yaml
```

添加：
```yaml
network:
  version: 2
  ethernets:
    eth0:  # 相机网口
      dhcp4: no
      addresses: [192.168.0.10/24]
    eth1:  # PLC网口
      dhcp4: no
      addresses: [192.168.1.10/24]
```

应用配置：
```bash
sudo netplan apply
```

**防火墙配置：**
```bash
# 允许相机和PLC通信
sudo ufw allow from 192.168.0.0/24
sudo ufw allow from 192.168.1.0/24
```

### 7. 测试部署

```bash
# 测试相机
cd scripts
python test_camera.py

# 测试PLC
python test_plc.py

# 完整测试
cd ..
./scripts/start.sh
```

## 生产部署

### 创建系统服务

创建systemd服务文件：
```bash
sudo vim /etc/systemd/system/potato-inspection.service
```

内容：
```ini
[Unit]
Description=Potato Inspection System
After=network.target

[Service]
Type=simple
User=potato
WorkingDirectory=/home/potato/potato_inspection_system
ExecStart=/home/potato/potato_inspection_system/scripts/start.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable potato-inspection.service
sudo systemctl start potato-inspection.service

# 查看状态
sudo systemctl status potato-inspection.service

# 查看日志
sudo journalctl -u potato-inspection.service -f
```

### 开机自启动

```bash
# 创建开机启动脚本
sudo vim /etc/rc.local
```

添加：
```bash
#!/bin/bash
# 等待网络就绪
sleep 10

# 启动服务
systemctl start potato-inspection.service

exit 0
```

设置权限：
```bash
sudo chmod +x /etc/rc.local
```

### 自动重启策略

在 `scripts/start.sh` 中添加守护逻辑：

```bash
#!/bin/bash
# 带自动重启的启动脚本

MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "启动系统 (尝试 $((RETRY_COUNT+1))/$MAX_RETRIES)..."
    
    source venv/bin/activate
    cd src
    python main.py
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "系统正常退出"
        exit 0
    else
        echo "系统异常退出，代码: $EXIT_CODE"
        RETRY_COUNT=$((RETRY_COUNT+1))
        sleep 5
    fi
done

echo "达到最大重试次数，退出"
exit 1
```

## 性能优化

### 1. 系统优化

```bash
# 关闭不必要的服务
sudo systemctl disable bluetooth
sudo systemctl disable cups

# 调整系统参数
sudo vim /etc/sysctl.conf
```

添加：
```
# 网络优化
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864

# 实时性优化
kernel.sched_rt_runtime_us = -1
```

应用：
```bash
sudo sysctl -p
```

### 2. 进程优先级

```bash
# 提高进程优先级
sudo renice -n -10 -p $(pgrep -f "python.*main.py")
```

### 3. CPU亲和性

在代码中设置：
```python
import os
os.sched_setaffinity(0, {0, 1, 2, 3})  # 绑定到核心0-3
```

### 4. GPU优化

```python
# 在推理前设置
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
```

## 备份与恢复

### 备份脚本

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="potato_system_backup_$DATE.tar.gz"

# 创建备份
tar -czf $BACKUP_DIR/$BACKUP_FILE \
    configs/ \
    models/ \
    scripts/ \
    src/ \
    requirements.txt

echo "备份完成: $BACKUP_DIR/$BACKUP_FILE"

# 清理旧备份（保留最近7天）
find $BACKUP_DIR -name "potato_system_backup_*.tar.gz" -mtime +7 -delete
```

### 恢复步骤

```bash
# 解压备份
tar -xzf potato_system_backup_YYYYMMDD_HHMMSS.tar.gz

# 重新安装依赖
./scripts/setup.sh

# 重启服务
sudo systemctl restart potato-inspection.service
```

## 监控与告警

### 日志监控

```bash
# 创建日志监控脚本
vim scripts/monitor.sh
```

```bash
#!/bin/bash
# 监控错误日志，发现异常发送告警

ERROR_LOG="logs/system/error_$(date +%Y-%m-%d).log"
LAST_CHECK="/tmp/last_check_time"

if [ ! -f $LAST_CHECK ]; then
    touch $LAST_CHECK
fi

# 检查新增的错误
new_errors=$(find $ERROR_LOG -newer $LAST_CHECK 2>/dev/null | wc -l)

if [ $new_errors -gt 0 ]; then
    echo "检测到 $new_errors 个新错误"
    # TODO: 发送告警（邮件、短信等）
fi

touch $LAST_CHECK
```

### 性能监控

使用Prometheus + Grafana或简单的脚本：

```python
# scripts/performance_monitor.py
import psutil
import time

while True:
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    
    print(f"CPU: {cpu}%, 内存: {mem}%")
    
    if cpu > 90 or mem > 90:
        # 发送告警
        pass
    
    time.sleep(60)
```

## 故障恢复

### 常见故障处理

1. **相机断线**
   - 自动重连机制已内置
   - 检查网线和相机电源

2. **PLC通信中断**
   - 检查网络连通性
   - 重启PLC服务

3. **系统卡死**
   - 查看日志定位原因
   - 重启服务：`sudo systemctl restart potato-inspection.service`

4. **磁盘空间不足**
   - 清理旧日志和图像
   - 运行：`./scripts/cleanup.sh`

### 紧急恢复流程

1. 停止服务
2. 备份当前数据
3. 检查日志找出问题
4. 修复或回滚到上一个版本
5. 重启服务
6. 验证功能

## 安全加固

### 1. 用户权限

```bash
# 创建专用用户
sudo adduser potato
sudo usermod -aG dialout,video potato

# 限制权限
chmod 750 /home/potato/potato_inspection_system
```

### 2. 网络安全

```bash
# 配置防火墙
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow from 192.168.0.0/24  # 相机网段
sudo ufw allow from 192.168.1.0/24  # PLC网段
```

### 3. 访问控制

- 使用SSH密钥认证
- 禁用root远程登录
- 定期更新密码

## 验收清单

- [ ] 硬件连接正常（相机、PLC、光源）
- [ ] 网络配置正确
- [ ] 软件安装完整
- [ ] 配置文件正确
- [ ] 模型文件就位
- [ ] 相机测试通过
- [ ] PLC测试通过
- [ ] 系统测试通过（8小时连续运行）
- [ ] 性能指标达标（FPS≥3, 延迟<300ms）
- [ ] 检测准确率达标（≥95%）
- [ ] 分级准确率达标（≥90%）
- [ ] 日志系统正常
- [ ] 自动重启机制正常
- [ ] 备份机制就位
- [ ] 文档齐全



