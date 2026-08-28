# LAB_CHANGES.md

本 fork 相对标准 CWatM 的全部偏离。论文的模型描述章节直接引用本文件。

- **上游**：[iiasa/CWatM](https://github.com/iiasa/CWatM)，跟踪 `develop` 分支
- **分叉基线**：上游 `c2a12553`（2024-01-30，"Merge pull request #109 from iiasa/main"）
- **工作分支**：`lab/main`
- **率定体系**：[SongshGeoLab/cwatm-cali](https://github.com/SongshGeoLab/cwatm-cali)（private）

分叉基线的确定方式：本 fork 的前身 `CtJiao/CWatM-version1.06` 是 2024-05 的一次代码拷贝，与上游无共同祖先。通过逐文件比对 blob 哈希确定基线——`cwatm/` 下 60 个文件中 58 个与 `c2a12553` 逐字节相同，其余 2 个即下方的 P1。

---

## P1 — 灌溉作物的土壤水分消耗系数 p 改用作物组数

**状态**：实验室科学改动，**永不提交上游**。标签 `lab-science-v1`。

**文件**：
- `cwatm/hydrological_modules/water_demand/irrigation.py`（`initial()` 载入；`dynamic()` 非水田灌溉触发）
- `cwatm/hydrological_modules/soil.py`（`irrPaddy` / `irrNonPaddy` 地类）

**改动**：

```python
# 标准 CWatM
p = 1 / (0.76 + 1.5 * etpotMax) - 0.4
# 本 fork
p = 1 / (0.76 + 1.5 * etpotMax) - 0.10 * (5 - self.var.cropGroupNumber)
```

**依据**：Van Diepen et al. (1988), WOFOST 6.0, p.87。标准 CWatM 对灌溉地类固定取 `- 0.4`（隐含假设灌溉作物对干旱适应性低，作物组数 = 1）；本 fork 改用输入图 `cropgroupnumber` 的实际取值，使 p 随作物类型变化。上游对**非灌溉**地类本来就用作物组形式（`soil.py:416`），本改动等于把同一处理推广到灌溉地类。

**设置文件**：无需改动。`cropgroupnumber` 是 CWatM 标准键，位于 `[VEGETATION]` 段。

**为何两个文件必须同一个 commit**：`soil.py` 用的 `cropGroupNumber` 由上游 `soil.py:166` 载入，自足；`irrigation.py:109` 的载入是防模块初始化顺序的冗余保护。拆开会留下可能 `AttributeError` 的中间状态。

> ### ⚠️ 已知不自洽 —— 重新率定前必须定夺
>
> p 的**第二项修正仍写死为作物组 = 1 的特例**：
>
> ```python
> p = p + (etpotMax - 0.6) / 4      # 未改
> ```
>
> Van Diepen 通用式分母是 `n_cg · (n_cg + 3)`，`4` 正是 `n_cg = 1` 时的 `1 × (1+3)`。上游把通用形式作为注释保留在 `irrigation.py`：
>
> ```python
> # p = np.where(cropGroupNumber <= 2.5,
> #              p + (etpotMax - 0.6) / (cropGroupNumber * (cropGroupNumber + 3)), p)
> ```
>
> 现状是第一项按真实作物组算、第二项按水稻算。取 `etpotMax = 1.0, n_cg = 4`：正确修正 `0.4/28 = 0.014`，当前给出 `0.4/4 = 0.100`，p 偏高 0.086 → `wCrit` 偏低 → 灌溉触发被推迟。
>
> **两个选项**：(a) 第二项一并改成通用式；(b) 退回 `- 0.4` 保持内部一致。**尚未决定。**

---

## P2 — `swAbstractionFrac` 为空间分布图时的比较保护

**状态**：通用 bug 修复，**上游至今未修**（`origin/develop:729`，2026-08-28 核实）。**PR 候选。**

**文件**：`cwatm/hydrological_modules/water_demand/water_demand.py`

`loadmap('swAbstractionFrac')` 在设置为数值时返回标量、指向 netCDF 图时返回数组。裸的 `if swAbstractionFraction < 0:` 在后一种情况抛 `ValueError: truth value of an array with more than one element is ambiguous`。改为先取最小值再比较。

**提 PR 前需改写**：当前实现用 `isinstance(swAbstractionFraction, float)`，对 `np.float32` 标量返回 `False`。应写成 `np.min(np.asarray(swAbstractionFraction)) < 0`。

来源：`CtJiao/CWatM-version1.06@e29dea7`（Chentai Jiao）。

---

## P3 — 写 netCDF 时跳过 lon/lat 的 `_FillValue`

**状态**：**上游已在源头修复，CP4/CP5 时删除本补丁。不要提 PR。**

**文件**：`cwatm/management_modules/data_handling.py`

netCDF4 不允许在变量创建后设置 `_FillValue`，源文件带该属性时 `writenetcdf()` 崩溃。本补丁在写入端跳过。上游改在源头：`develop:869` 构建 `metadataNCDF` 时就用字典推导式过滤掉 `_FillValue`（提交 `bf388fc` / `56bdc92`，2026-08-05）。

来源：`CtJiao/CWatM-version1.06@e29dea7`。

---

## P4 — inflow 读取报错追加 utf-8 BOM 提示

**状态**：仅提示文本，无行为变化。可选 PR。

**文件**：`cwatm/hydrological_modules/inflow.py`。Error 218 原本不给任何线索，而 BOM 前缀是最常见原因。

来源：`CtJiao/CWatM-version1.06@e29dea7`。

---

## 行为变更记录

### CP1（2026-08-28）— `satAreaFrac` / `arnoBeta` 修复

**这是本模型与标准 CWatM 分岔历史中最重要的一次数值变更，论文必须记录。**

```python
# 错误形式（本 fork 2024-01-30 至 2026-08-28）
satAreaFrac = np.maximum(1 - (1 - relSat), 0) ** arnoBeta   # 恒等于 relSat ** beta
# 正确形式
satAreaFrac = 1 - np.maximum((1 - relSat), 0) ** arnoBeta
```

**来源**：上游 `537b09d`（2023-08-09）在加 `np.maximum` 防运行时警告时把 `1 -` 挪进了括号内；上游 `c3282dd`（2025-03-27）修复。本 fork 基线 2024-01-30 恰好落在两者之间，因而继承了 bug 又错过了修复。本次只取 `satAreaFrac` 那一行（`c3282dd` 另有 31 个文件的无关改动，其中对 `p` 公式的注释挪动会与 P1 冲突）。

**影响**：`potInf = store · (1 - satAreaFrac)^((β+1)/β)`。取 `irrNonPaddy_arnoBeta ≈ 0.2`、`relSat = 0.5`：

| | `potInf / store` |
|---|---|
| 正确形式 | 0.435 |
| 错误形式 | 0.0000047 |

即 `potInf ≈ 0.002 mm/day`。而 `irrigation.py` 用它作硬上限：

```python
pot_irrConsumption[3] = np.minimum(pot_irrConsumption[3], potInf)
```

**因此 2024-01 至 2026-08 期间，非水田灌溉需求被钳制在 ~0，与 `alphaDepletion`、`fraction_IncreaseIrrigation_Nonpaddy` 的取值无关。** 这正是"调参数不敏感"的成因。水田分支（`No=2`）不经过 `potInf`，不受影响。

误差随 `arnoBeta` 变化：β = 0.2 时比值 1e-5，β = 0.6 时 0.17，**β = 1.0 时两式恰好相等**。

**验收测试**：`alphaDepletion` 与 `fraction_IncreaseIrrigation_Nonpaddy` 必须重新表现出敏感性。若仍平坦，说明修复未生效或另有钳制。

**待办**：本次修复前的所有率定结果均基于被钳制的灌溉，需重新率定；结果登记到 `cwatm-cali` 的 README 表格。

---

## 上游追赶检查点

| 检查点 | 上游目标 | 状态 |
|---|---|---|
| CP0 | `c2a12553`（2024-01-30）+ P1–P4 | ✅ 已完成，与迁移前逐字节等价 |
| **CP1** | `satAreaFrac` 修复 | ✅ 已完成，**待重新率定** |
| CP2 | `cea63eb`（2025-07-08）| 未开始。`waterbalance.py` 存在的最后一点，可用现有水量平衡 QC 验证 |
| CP3 | `88be87d`（2025-08-29）| 未开始 |
| CP4 | `86066b1`（2025-09-11）| 未开始。删 `waterbalance.py`、重写 `water_demand.py`、全模块 pep8；P1 需手工重打，此时删除 P3 |
| CP5 | `develop` tip | 未开始。含 gdal → rasterio，属环境迁移 |

---

## 同步纪律

1. **PR 默认打向父仓库。** 从本 fork 开 PR，base 默认是 `iiasa/CWatM`；若从 `lab/main` 开，等于公开向上游提交 P1。PR 分支一律从 `upstream/develop` 切，`gh pr create` 永远显式带 `--repo` 和 `--base`。GitHub 没有服务端开关。
2. **每次 merge 上游后必须验证 P1 存活**：

   ```bash
   grep -n "0.10 \* (5 - self.var.cropGroupNumber)" \
     cwatm/hydrological_modules/soil.py \
     cwatm/hydrological_modules/water_demand/irrigation.py
   ```

   必须两个文件都命中。merge 可以干净解决却依然吞掉补丁。
3. **不要引入 `.gitattributes`。** 前身仓库的 LFS 声明正是 5 个 tutorial `.map` 文件退化成 130 字节指针的原因，而 git-lfs 从未安装。
4. 同步一律在 `lab/sync-YYYY-MM` 分支做，验证后 `--ff-only` 落地 `lab/main`。
