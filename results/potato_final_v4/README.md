# 土豆检测结果 - v4（最终版）

**生成时间**: 2025-11-05 13:59:11  
**模型**: YOLOv8s-OBB-v22（包含potato标签）  
**测试集**: 12张图片

---

## 检测结果总览

- ✅ **检测土豆**: 44个
- ✅ **OK土豆**: 30个（68.2%）
- ✅ **NG土豆**: 14个（31.8%）
- ✅ **总缺陷**: 123个

---

## 分级分布

| 分级 | 数量 | 通道 | 信号位 |
|------|------|------|--------|
| OK_S2 | 1 | Lane 2 | 01000000 |
| OK_S3 | 3 | Lane 3 | 00100000 |
| OK_S4 | 2 | Lane 4 | 00010000 |
| OK_S5 | 1 | Lane 5 | 00001000 |
| OK_S6 | 4 | Lane 6 | 00000100 |
| OK_S7 | 19 | Lane 7 | 00000010 |
| NG | 14 | Lane 8 | 00000001 |

---

## 土豆ID列表（全部44个）

### 按图片分组

#### 图1: 0142ce97 (8个土豆)
1. `2025110513591101` - OK_S7 - 缺陷: black_spots×2, red_spots×1
2. `2025110513591102` - OK_S7 - 缺陷: red_spots×2
3. `2025110513591103` - OK_S7 - 缺陷: black_spots×2, scabs×1
4. `2025110513591104` - **NG** - 缺陷: red_spots×4, black_spots×2, scabs×1
5. `2025110513591105` - OK_S7 - 缺陷: black_spots×1, scabs×1
6. `2025110513591106` - **NG** - 缺陷: scabs×3, red_spots×1
7. `2025110513591107` - OK_S3 - 缺陷: scabs×1
8. `2025110513591108` - OK_S3 - 无缺陷

#### 图2: 1cd36156 (1个土豆)
9. `2025110513591109` - OK_S7 - 缺陷: black_spots×3, scabs×1

#### 图3: 1ddcb126 (1个土豆)
10. `2025110513591110` - OK_S7 - 缺陷: scabs×1, pits×1

#### 图4: 20a6beec (8个土豆)
11. `2025110513591201` - **NG** - 缺陷: red_spots×1, pits×1, scabs×1
12. `2025110513591202` - OK_S7 - 缺陷: scabs×3, red_spots×1
13. `2025110513591203` - OK_S6 - 缺陷: scabs×3, red_spots×1
14. `2025110513591204` - OK_S7 - 缺陷: scabs×1
15. `2025110513591205` - **NG** - 缺陷: scabs×2
16. `2025110513591206` - OK_S2 - 无缺陷
17. `2025110513591207` - OK_S4 - 无缺陷
18. `2025110513591208` - OK_S4 - 无缺陷

#### 图5: 309e98ef (9个土豆)
19. `2025110513591209` - OK_S7 - 缺陷: scabs×2
20. `2025110513591210` - **NG** - 缺陷: scabs×7, black_spots×1
21. `2025110513591211` - OK_S7 - 缺陷: scabs×2, red_spots×1
22. `2025110513591212` - OK_S7 - 缺陷: scabs×2, black_spots×1
23. `2025110513591213` - OK_S7 - 缺陷: scabs×2, red_spots×2
24. `2025110513591214` - **NG** - 缺陷: red_spots×1, pits×1, black_spots×1
25. `2025110513591215` - **NG** - 缺陷: black_spots×1, pits×2, red_spots×1, scabs×1
26. `2025110513591216` - **NG** - 缺陷: red_spots×1, scabs×2, pits×1
27. `2025110513591217` - OK_S3 - 无缺陷

#### 图6: 32baca87 (2个土豆)
28. `2025110513591218` - **NG** - 缺陷: black_spots×1, scabs×2
29. `2025110513591219` - OK_S6 - 缺陷: scabs×1, red_spots×1

#### 图7: 3b7c3445 (1个土豆)
30. `2025110513591220` - OK_S5 - 缺陷: scabs×2, red_spots×1

#### 图8: a519ccb1 (1个土豆)
31. `2025110513591301` - OK_S7 - 缺陷: scabs×1, red_spots×1

#### 图9: b1e224e1 (1个土豆)
32. `2025110513591302` - OK_S7 - 缺陷: scabs×1, black_spots×1

#### 图10: c80481f7 (8个土豆)
33. `2025110513591303` - OK_S7 - 缺陷: scabs×2, black_spots×1
34. `2025110513591304` - OK_S7 - 缺陷: scabs×2
35. `2025110513591305` - OK_S7 - 缺陷: scabs×1
36. `2025110513591306` - **NG** - 缺陷: pits×1, red_spots×1
37. `2025110513591307` - **NG** - 缺陷: scabs×3, pits×1
38. `2025110513591308` - **NG** - 缺陷: scabs×3, pits×3
39. `2025110513591309` - OK_S7 - 缺陷: scabs×3, red_spots×1
40. `2025110513591310` - **NG** - 缺陷: scabs×3, pits×1

#### 图11: e6963a94 (2个土豆)
41. `2025110513591401` - OK_S6 - 缺陷: red_spots×1, scabs×1
42. `2025110513591402` - OK_S6 - 缺陷: red_spots×1, deformities×1

#### 图12: f17352fd (2个土豆)
43. `2025110513591403` - OK_S7 - 缺陷: red_spots×2
44. `2025110513591404` - **NG** - 缺陷: scabs×3, pits×2

---

## NG土豆详细分析

### 全部14个NG土豆

| ID | 缺陷详情 | NG原因 |
|----|----------|--------|
| 2025110513591104 | red_spots×4, black_spots×2, scabs×1 | red_spots超标 |
| 2025110513591106 | scabs×3, red_spots×1 | scabs超标 |
| 2025110513591201 | red_spots×1, pits×1, scabs×1 | 含禁用缺陷pits |
| 2025110513591205 | scabs×2 | scabs超标 |
| 2025110513591210 | scabs×7, black_spots×1 | scabs严重超标 |
| 2025110513591214 | red_spots×1, pits×1, black_spots×1 | 含禁用缺陷pits |
| 2025110513591215 | black_spots×1, pits×2, red_spots×1, scabs×1 | 含禁用缺陷pits |
| 2025110513591216 | red_spots×1, scabs×2, pits×1 | 含禁用缺陷pits |
| 2025110513591218 | black_spots×1, scabs×2 | scabs超标 |
| 2025110513591306 | pits×1, red_spots×1 | 含禁用缺陷pits |
| 2025110513591307 | scabs×3, pits×1 | scabs超标+含pits |
| 2025110513591308 | scabs×3, pits×3 | scabs超标+含pits（严重） |
| 2025110513591310 | scabs×3, pits×1 | scabs超标+含pits |
| 2025110513591404 | scabs×3, pits×2 | scabs超标+含pits |

---

## 文件说明

### potatoes.jsonl（44行）
每行一个土豆的完整信息：
- potato_id: 唯一ID
- bbox: 位置坐标
- area: 面积
- grade: 分级
- signal: 8位信号+通道
- defects: 所有缺陷详情列表（含OBB坐标）

### potatoes.csv（45行含表头）
CSV格式，便于Excel分析和传感器读取。

### visualizations/（12张图片）
每张图片标注：
- potato旋转边界框（粗线，绿=OK，红=NG）
- 土豆ID和分级信息
- 缺陷旋转边界框（细线，只显示类别名）

---

## 使用此结果

### 给传感器团队
直接读取 `potatoes.csv`：
```python
import csv
with open('potato_final_v4/potatoes.csv') as f:
    for row in csv.DictReader(f):
        print(f"{row['potato_id']} → Lane {row['lane']} ({row['grade']})")
```

### 查看可视化
打开 `visualizations/` 目录，查看每张图片的标注效果。

---

**检测完成！系统已准备就绪。**

