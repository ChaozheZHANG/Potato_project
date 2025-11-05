#!/bin/bash
# 土豆质检分级系统安装脚本
# 用于初始化环境和安装依赖

set -e

echo "================================"
echo "土豆质检分级系统 - 环境配置"
echo "================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查Python版本
echo -e "${YELLOW}检查Python版本...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python版本: $python_version"

if ! python3 -c 'import sys; assert sys.version_info >= (3, 8)' 2>/dev/null; then
    echo -e "${RED}错误: 需要Python 3.8或更高版本${NC}"
    exit 1
fi

# 创建虚拟环境
echo -e "${YELLOW}创建Python虚拟环境...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}虚拟环境创建成功${NC}"
else
    echo -e "${YELLOW}虚拟环境已存在${NC}"
fi

# 激活虚拟环境
echo -e "${YELLOW}激活虚拟环境...${NC}"
source venv/bin/activate

# 升级pip
echo -e "${YELLOW}升级pip...${NC}"
pip install --upgrade pip setuptools wheel

# 安装依赖
echo -e "${YELLOW}安装Python依赖包...${NC}"
pip install -r requirements.txt

# 创建必要的目录
echo -e "${YELLOW}创建系统目录...${NC}"
mkdir -p logs/{system,acquisition,inference,tracking,plc}
mkdir -p captures/{raw,processed}
mkdir -p models
mkdir -p data/{train,val,test,annotations}
echo -e "${GREEN}目录创建完成${NC}"

# 检查配置文件
echo -e "${YELLOW}检查配置文件...${NC}"
if [ ! -f "configs/system_config.yaml" ]; then
    echo -e "${RED}错误: 配置文件不存在: configs/system_config.yaml${NC}"
    exit 1
else
    echo -e "${GREEN}配置文件检查通过${NC}"
fi

# 系统信息
echo ""
echo "================================"
echo "系统信息"
echo "================================"
echo "操作系统: $(uname -s)"
echo "内核版本: $(uname -r)"
echo "Python版本: $python_version"
echo "工作目录: $(pwd)"

# 检查GPU（可选）
echo ""
echo "================================"
echo "GPU检查"
echo "================================"
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}检测到NVIDIA GPU:${NC}"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
else
    echo -e "${YELLOW}未检测到NVIDIA GPU，将使用CPU进行推理${NC}"
fi

echo ""
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}环境配置完成！${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo "下一步："
echo "  1. 检查并修改配置文件: configs/system_config.yaml"
echo "  2. 准备模型文件（放置在 models/ 目录）"
echo "  3. 运行系统: ./scripts/start.sh"
echo ""

