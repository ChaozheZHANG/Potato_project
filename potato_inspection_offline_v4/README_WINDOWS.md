# Windows系统使用指南

**适用**: Windows 10/11 + PowerShell

---

## 🚀 快速开始

### 步骤1: 解压
右键点击 `potato_inspection_offline_v4_complete.tar.gz` → 解压到当前文件夹

或使用命令：
```powershell
# 如果有tar命令
tar -xzf potato_inspection_offline_v4_complete.tar.gz

# 或使用7-Zip等工具解压
```

### 步骤2: 进入目录
```powershell
cd potato_inspection_offline_v4
```

### 步骤3: 允许脚本执行（任选其一）
```powershell
# 仅对当前PowerShell窗口生效，更安全（推荐）
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

# 或者永久允许当前账号运行本地脚本
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 步骤4: 部署
```powershell
.\deploy.ps1
```

### 步骤5: 检测
```powershell
.\detect.ps1 test_images
```

> 提示: 脚本输出内容已改为英文，避免在老版本 PowerShell 中出现乱码或解析错误。

---

## 💻 详细使用方法

### 方法1: PowerShell脚本（推荐）

#### 部署系统
```powershell
.\deploy.ps1
```

#### 检测图片
```powershell
# 检测目录
.\detect.ps1 test_images

# 检测单张图片
.\detect.ps1 "C:\path\to\potato.jpg"

# 调整置信度
.\detect.ps1 test_images 0.3
```

### 方法2: Python直接调用

#### 激活虚拟环境
```powershell
.\venv\Scripts\Activate.ps1
```

#### 运行检测
```powershell
python scripts\grade_with_potato_label.py `
    --model models\yolov8s-obb-potato-v22_best.pt `
    --source test_images `
    --out results\my_output `
    --conf 0.25
```

### 方法3: Python代码
```powershell
python example_detect.py test_images\0142ce97-Pic_2025_10_21_154621_149.jpeg
```

---

## 🔧 常见问题

### 问题1: 无法运行.ps1脚本
**错误**: "无法加载文件，因为在此系统上禁止运行脚本"

**解决**:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### 问题2: Python未找到
**错误**: "python不是内部或外部命令"

**解决**:
1. 安装Python 3.8+: https://www.python.org/downloads/
2. 安装时勾选 "Add Python to PATH"
3. 重启PowerShell

### 问题3: pip安装失败
**解决**:
```powershell
# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题4: 路径包含空格
**解决**: 使用引号
```powershell
.\detect.ps1 "C:\My Documents\potato images"
```

---

## 📊 查看结果

### 在PowerShell中查看CSV
```powershell
# 查看前10行
Get-Content results\*\potatoes.csv | Select-Object -First 10

# 统计土豆数
(Get-Content results\*\potatoes.csv | Measure-Object -Line).Lines - 1
```

### 在Excel中打开
```powershell
# 直接用Excel打开CSV
Start-Process excel results\*\potatoes.csv
```

### 查看可视化图片
```powershell
# 打开文件夹
explorer results\*\visualizations\
```

---

## 🎯 完整示例（Windows）

```powershell
# 1. 解压并进入目录
cd F:\potato_project
tar -xzf potato_inspection_offline_v4_complete.tar.gz
cd potato_inspection_offline_v4

# 2. 允许脚本执行
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 3. 部署
.\deploy.ps1

# 4. 检测测试图片
.\detect.ps1 test_images

# 5. 查看结果
Get-Content results\*\potatoes.csv | Select-Object -First 5

# 6. 打开可视化图片
explorer results\*\visualizations\

# 7. 检测自己的图片
.\detect.ps1 "D:\my_potato_images"
```

---

## 📝 输出格式（Windows路径）

检测完成后，结果保存在：
```
results\20251107_140530\
├── potatoes.csv           # CSV文件
├── potatoes.jsonl         # JSON格式
└── visualizations\        # 可视化图片
    ├── img1_labeled.jpg
    └── img2_labeled.jpg
```

---

## 🔄 如果需要重新部署

```powershell
# 删除虚拟环境
Remove-Item -Recurse -Force venv

# 重新部署
.\deploy.ps1
```

---

## 🔄 实时监控模式（生产环境）

### 监控相机目录并自动检测

系统可以实时监控相机存储目录，自动处理新拍摄的图片：

```powershell
# 基本用法（不连接PLC）
.\monitor_realtime.ps1 -CameraDir "F:\data\camera"

# 启用PLC输出
.\monitor_realtime.ps1 -CameraDir "F:\data\camera" -PLCEnable -PLCHost "192.168.1.100" -PLCPort 502

# 自定义参数
.\monitor_realtime.ps1 `
    -CameraDir "F:\data\camera" `
    -PLCEnable `
    -PLCHost "192.168.1.100" `
    -PLCPort 502 `
    -PLCAddress 0 `
    -Conf 0.3 `
    -ScanInterval 0.5
```

### 参数说明

- `-CameraDir`: 相机图片存储根目录（默认: `F:\data\camera`）
- `-PLCEnable`: 启用PLC输出
- `-PLCHost`: PLC IP地址（默认: `192.168.1.100`）
- `-PLCPort`: PLC端口（默认: `502`）
- `-PLCAddress`: PLC起始地址（默认: `0`）
- `-Conf`: 检测置信度阈值（默认: `0.25`）
- `-ScanInterval`: 扫描间隔秒数（默认: `0.5`）

### 图片路径格式

系统自动识别以下格式的图片：
```
F:/data/camera/YYYYMMDD/ch{CC}_{HHMMSS}-{NNN}.jpg
```

示例：
- `F:/data/camera/20251112/ch01_121608-001.jpg`
- `F:/data/camera/20251112/ch02_121610-001.jpg`

### 输出结果

实时监控结果保存在：
```
results\realtime_monitor\
├── results_YYYYMMDD.jsonl  # JSON格式结果
└── results_YYYYMMDD.csv    # CSV格式结果
```

### 停止监控

按 `Ctrl+C` 停止监控，系统会显示最终统计信息。

---

## 📞 技术支持

- 查看 `README.md` 了解完整功能
- 查看 `USAGE_EXAMPLES.md` 查看代码示例
- 查看 `docs\SENSOR_TEAM_QUICK_GUIDE.md` 了解输出格式

---

**Windows系统已完全支持！** 🎉
