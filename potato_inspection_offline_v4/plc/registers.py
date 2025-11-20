# -*- coding: utf-8 -*-
"""
文件: plc/registers.py
说明: 新寄存器地址常量 + 工具函数（1..60 环与通道映射）
"""

# ---- 顶层控制 ----

REG_HEARTBEAT  = 500     # 上位机每0.5s写一次: 0

REG_RUN_STATUS = 501     # 0-停止/暂停, 1-启动, 2-重启(清零)

REG_MOV_SPEED  = 502     # REAL u1 mm/s

REG_ROT_SPEED  = 504     # REAL u2 mm/s

# ---- 通道1 ----

C1_READY_1     = 506     # 0待机/1就绪开始采相 (读)

C1_READY_2     = 507     # 上位机发布：本波"可读取的最大ID"(写)

C1_ATTRS_BASE  = 508     # 508..567 共60格 INT

C1_NOW         = 568     # PLC已分配目标序号(1..60)、0为无就绪 (读)

C1_RENEW       = 569     # 保留 (读)

# ---- 通道2 ----

C2_READY_1     = 570

C2_READY_2     = 571

C2_ATTRS_BASE  = 572

C2_NOW         = 632

C2_RENEW       = 633

# ---- 通道3 ----

C3_READY_1     = 634

C3_READY_2     = 635

C3_ATTRS_BASE  = 636

C3_NOW         = 696

C3_RENEW       = 697

# ---- 通道4 ----

C4_READY_1     = 698

C4_READY_2     = 699

C4_ATTRS_BASE  = 700

C4_NOW         = 760

C4_RENEW       = 761

# ---------- 通用工具 ----------

def wrap60(x: int) -> int:
    """把任意整数映射到 1..60（1为起点的环）"""
    return ((int(x) - 1) % 60) + 1

def attrs_base(ch: int) -> int:
    """返回通道的属性寄存器基地址"""
    return {1:C1_ATTRS_BASE, 2:C2_ATTRS_BASE, 3:C3_ATTRS_BASE, 4:C4_ATTRS_BASE}[int(ch)]

def ready1_reg(ch: int) -> int:
    """返回通道的READY_1寄存器地址"""
    return {1:C1_READY_1, 2:C2_READY_1, 3:C3_READY_1, 4:C4_READY_1}[int(ch)]

def ready2_reg(ch: int) -> int:
    """返回通道的READY_2寄存器地址"""
    return {1:C1_READY_2, 2:C2_READY_2, 3:C3_READY_2, 4:C4_READY_2}[int(ch)]

def now_reg(ch: int) -> int:
    """返回通道的NOW寄存器地址（当前处理的序号）"""
    return {1:C1_NOW, 2:C2_NOW, 3:C3_NOW, 4:C4_NOW}[int(ch)]

def renew_reg(ch: int) -> int:
    """返回通道的RENEW寄存器地址"""
    return {1:C1_RENEW, 2:C2_RENEW, 3:C3_RENEW, 4:C4_RENEW}[int(ch)]
