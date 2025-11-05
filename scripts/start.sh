#!/bin/bash
# 土豆质检分级系统启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "================================"
echo "土豆质检分级系统 - 启动"
echo "================================"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${RED}错误: 虚拟环境不存在，请先运行 ./scripts/setup.sh${NC}"
    exit 1
fi

# 激活虚拟环境
echo -e "${YELLOW}激活虚拟环境...${NC}"
source venv/bin/activate

# 检查配置文件
if [ ! -f "configs/system_config.yaml" ]; then
    echo -e "${RED}错误: 配置文件不存在${NC}"
    exit 1
fi

# 启动系统
echo -e "${GREEN}启动土豆质检分级系统...${NC}"
echo ""

cd src
python main.py "$@"

