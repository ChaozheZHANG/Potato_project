# PLC模块说明

## 文件说明

### `plc/registers.py`
此文件在生产环境已经存在，包含了所有PLC寄存器地址定义。

**重要**：不要覆盖生产环境的 `plc/registers.py` 文件！

如果您的生产环境已经有这个文件，请：
1. 保留原有文件不变
2. 确保文件包含 `attrs_base(ch)` 函数（原文件已有）

### `plc/__init__.py`
这是一个空文件，用于使 `plc` 成为一个Python包。

**如果生产环境的 `plc/__init__.py` 是空的，可以：**
- 保持为空（空文件即可）
- 或者复制我们提供的 `__init__.py`（也是空的，只是有注释）

## 寄存器地址说明

根据生产环境的 `registers.py`：

- **通道1**: `C1_ATTRS_BASE = 508` (508..567 共60格)
- **通道2**: `C2_ATTRS_BASE = 572` (572..631 共60格)
- **通道3**: `C3_ATTRS_BASE = 636` (636..695 共60格)
- **通道4**: `C4_ATTRS_BASE = 700` (700..759 共60格)

`attrs_base(ch)` 函数会根据通道号返回对应的基地址。

## 使用示例

```python
from plc.registers import attrs_base

# 获取通道1的基地址
base = attrs_base(1)  # 返回 508

# 获取通道2的基地址
base = attrs_base(2)  # 返回 572
```

## 检测服务如何使用

检测服务 `scripts/detect_and_write_plc.py` 会：
1. 导入 `from plc.registers import attrs_base`
2. 根据图片文件名提取通道号
3. 调用 `attrs_base(channel)` 获取基地址
4. 将检测结果写入到该基地址

