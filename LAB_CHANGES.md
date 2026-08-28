# LAB_CHANGES.md

本 fork 相对标准 CWatM 的全部偏离。论文的模型描述章节直接引用本文件。

- **上游**：[iiasa/CWatM](https://github.com/iiasa/CWatM)，跟踪 `develop` 分支
- **当前基线**：上游 `32cae7d`（2026-08-28，"Watercycle LakeRes correction"）
- **工作分支**：`lab/main`
- **率定体系**：[SongshGeoLab/cwatm-cali](https://github.com/SongshGeoLab/cwatm-cali)（private）

## 唯一需要记住的不变量

```bash
git diff upstream/develop -- cwatm/
```

**这条命令的输出就是本 fork 的全部偏离**——四个文件、约 40 行，一屏读完。
不需要读历史，不需要信任本文件的叙述，直接看 diff。

由 `python3 tools/check_lab_patches.py` 机器校验，每次合并上游后**必跑**，退出码 0 才可以
`--ff-only` 落地 `lab/main`。

---

## P1 — 灌溉作物的土壤水分消耗系数 p 改用作物组数

**状态**：实验室科学改动，**永不提交上游**。

**文件**：`cwatm/hydrological_modules/soil.py`（`irrPaddy` / `irrNonPaddy` 分支）、
`cwatm/hydrological_modules/water_demand/irrigation.py`（`initial()` 载入；`dynamic()` 非水田灌溉触发）

**改动**：两项都改，与上游自有的非灌溉分支逐字一致。

```python
# 上游（灌溉地类，两项都固定为作物组 1）
p = 1 / (0.76 + 1.5 * etpotMax) - 0.4
p = p + (etpotMax - 0.6) / 4                    # 4 = 1 * (1 + 3)

# 本 fork
p = 1 / (0.76 + 1.5 * etpotMax) - 0.10 * (5 - self.var.cropGroupNumber)
p = np.where(self.var.cropGroupNumber <= 2.5,
             p + (etpotMax - 0.6) / (self.var.cropGroupNumber * (self.var.cropGroupNumber + 3)), p)
```

**依据**：Van Diepen et al. (1988), WOFOST 6.0, p.87。上游对灌溉地类的隐含假设是"灌溉作物
对干旱适应性低，等同作物组 1"；本 fork 改用输入图 `cropgroupnumber` 的实际取值，理由是研究区
灌溉作物类型多样，统一按水稻处理不合适。**上游对非灌溉地类本来就用通用式**
（`soil.py` 的 `else` 分支），本改动等于把同一处理推广到灌溉地类。

**设置文件**：无需改动。`cropgroupnumber` 是 CWatM 标准键，位于 `[VEGETATION]` 段。

**为何两个文件必须同一个 commit**：`soil.py` 用的 `cropGroupNumber` 由上游 `soil.py:215` 载入，
自足；`irrigation.py` 里那句载入是防模块初始化顺序的冗余保护（develop 的 `irrigation.py`
本身不载入它）。拆开会留下可能 `AttributeError` 的中间状态。

**上游把我们的两行原样注释在旁边**（`develop:irrigation.py:205,210-211`），所以在 `irrigation.py`
里重打 P1 实际上就是换注释——这也让每次合并后的核对非常容易。

### 数值后果

`p` 只影响**灌溉触发时机**（阈值 = `α·(1−p)·totAvlWater`），不影响单次灌溉量
（`α·totAvlWater − readAvlWater`）。p 越大 → 阈值越低 → 触发越晚。
`n_cg = 1` 时本 fork 与上游完全相同，差异随作物组增大：

| ETmax | n_cg | 上游 | 本 fork | 触发阈值变化 |
|---:|---:|---:|---:|---:|
| 0.2 | 1 | 0.443 | 0.443 | 0% |
| 0.2 | 3 | 0.443 | 0.743 | −54% |
| 0.2 | 5 | 0.443 | 0.943 | −90% |
| 1.0 | 3 | 0.142 | 0.242 | −12% |
| 1.0 | 5 | 0.142 | 0.442 | −35% |

**注意 `≤ 2.5` 门限**：作物组 3–5 的格点完全不施加第二项修正，此时
`p = 1/(0.76+1.5·E) − 0.10·(5−n_cg)`。若研究区作物组集中在 3–5，论文中需说明。

**待办（需 Windows 数据）**：尚未核对研究区 `$(PathMaps)/soil/cropgrp.nc` 的实际取值分布。
若基本都是 1，本改动相对上游无实质差别；若 2–5 占比可观，则是模型行为的实质偏离，
必须在论文中论证。

### 未采纳的方案

方案 B（撤销 P1、灌溉地类回到上游 `− 0.4` + `/4`）保留在分支 `lab/p-option-b`，
标签 `p-option-b-not-taken`。它同样自洽，代价是放弃"灌溉作物按真实作物组"这一主张。

---

## P2 — `swAbstractionFrac` 为空间分布图时的比较保护

**状态**：通用 bug 修复，**上游至今未修**（`develop:729`，2026-08-28 核实）。**PR 候选**（暂缓提交）。

**文件**：`cwatm/hydrological_modules/water_demand/water_demand.py`

`loadmap('swAbstractionFrac')` 在设置为数值时返回标量、指向 netCDF/GeoTIFF 图时返回数组。
裸的 `if swAbstractionFraction < 0:` 在后一种情况抛
`ValueError: truth value of an array with more than one element is ambiguous`。

```python
if np.min(np.asarray(swAbstractionFraction)) < 0:
```

用 `np.asarray` 而不是迁移前那版的 `isinstance(x, float)`——后者对 `np.float32` 标量返回 `False`。

补丁点位于 `if checkOption('includeWaterDemand'):` 之内，只有当 `swAbstractionFrac` 指向图时
才会触发原 bug，**标量配置测不出来**，回归测试必须专门构造。

来源：`CtJiao/CWatM-version1.06@e29dea7`（Chentai Jiao）。

---

## P4 — inflow 读取报错追加 utf-8 BOM 提示

**状态**：仅提示文本，无行为变化。可选 PR。

**文件**：`cwatm/hydrological_modules/inflow.py`。Error 218 原本不给任何线索，
而 BOM 前缀是最常见原因。

来源：`CtJiao/CWatM-version1.06@e29dea7`。

---

## 已撤销的补丁

### P3 — 写 netCDF 时跳过 lon/lat 的 `_FillValue`（2026-08-28 撤销）

上游已在源头修复：`data_handling.py:869` 构建 `metadataNCDF` 时就用字典推导式过滤掉
`_FillValue`（提交 `bf388fc` / `56bdc92`，2026-08-05）。本 fork 原先在写入端跳过，现已删除。

`check_lab_patches.py` 里保留了一条**反向**检查：确认上游那个源头修复没有被回退。
若它消失，netCDF 写入会在带该属性的输入上崩溃，需要重新打回旧的写入端保护。

### CP1 — `satAreaFrac` / `arnoBeta`（2026-08-28 随重基线并入上游）

上游 `c3282dd`（2025-03-27）已修，且已是 `develop` 的祖先，`develop:irrigation.py:178`
就是正确形式。本地补丁不再需要。**但这段历史对论文仍然重要，见下节。**

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

**来源**：上游 `537b09d`（2023-08-09）在加 `np.maximum` 防运行时警告时把 `1 -` 挪进了括号内；
上游 `c3282dd`（2025-03-27）修复。本 fork 基线 2024-01-30 恰好落在两者之间，
因而继承了 bug 又错过了修复。

**影响**：`potInf = store · (1 - satAreaFrac)^((β+1)/β)`。取 `irrNonPaddy_arnoBeta ≈ 0.2`、
`relSat = 0.5`：正确形式 `potInf/store = 0.435`，错误形式 `0.0000047`，
即 `potInf ≈ 0.002 mm/day`。而 `irrigation.py` 用它作硬上限：

```python
pot_irrConsumption[3] = np.minimum(pot_irrConsumption[3], potInf)
```

**因此 2024-01 至 2026-08 期间，非水田灌溉需求被钳制在 ~0，与 `alphaDepletion`、
`fraction_IncreaseIrrigation_Nonpaddy` 的取值无关。** 这正是"调参数不敏感"的成因。
水田分支（`No=2`）不经过 `potInf`，不受影响。

误差随 `arnoBeta` 变化：β = 0.2 时比值 1e-5，β = 0.6 时 0.17，**β = 1.0 时两式恰好相等**。

**与率定的交互（2026-08-28 补充）**：`cwatm-cali` 的三个 ParamRanges 文件都把 `arnoBeta_add`
放在 **[0.01, 1.0]** 区间里率定，而这恰恰是 bug 严重程度从 1e-5 变到 1 的整个跨度。
过去的最优参数组很可能是被 bug 塑形的，而不是被水文过程塑形的。

**验收测试**：`alphaDepletion` 必须重新表现出敏感性。注意
**`fraction_IncreaseIrrigation_Nonpaddy` 根本不在率定搜索空间里**（任何模板都没设它，
代码侧由 `if ... in binding` 保护），只能靠单独的敏感性试验观察，率定看不到。

**待办**：本次修复前的所有率定结果均基于被钳制的灌溉，需重新率定；
结果登记到 `cwatm-cali` 的 README 表格。

### 重基线（2026-08-28）— 从 `c2a1255` 一跳到 `32cae7d`

放弃了原先规划的 CP2→CP5 四级检查点阶梯。理由：本 fork 相对上游只有 5 个文件、约 40 行偏离，
且每个补丁点在 `develop` tip 上都还原样存在，而上游对这 5 个文件的改写量巨大
（`data_handling.py` +1416/−455、`water_demand.py` +901/−897、`soil.py` +454/−357），
逐级合并等于把同一份冲突解决四遍。归因需求事后用 `git bisect` 即可满足。

重基线前的状态由标签 `pre-rebaseline-2026-08` 永久保留。

合并时的实测：`merge upstream/develop` 报了 3 处文本冲突（`inflow.py`、`irrigation.py`、
`data_handling.py`），而 `soil.py` 与 `water_demand.py` **"自动合并成功"**——
正是补丁被静默保留/吞掉的危险情形。**一次干净的 merge 完全不能说明补丁还在。**
因此 5 个文件一律 `git checkout upstream/develop --`，补丁在下一个 commit 里单独重打。

---

## 继承的上游科学变更（论文必须记录）

从 `c2a1255..32cae7d` 的 175 个提交里筛出的行为变更：

- **蒸散发**：新增 `PET_modus` 选项与修正 Thornthwaite 方法（`b764a2f`）、Priestley 修正
  （`c21fa82`）、Tdew 改回 Magnus 方程（`a047109`）。日尺度作物系数与 Kc 曲线修正
  （`ce35bed`、`f34a6da`、`324fb4c`）。
- **土壤**：`thetares = 0` 时土壤含水量可能变负导致 NaN 的保护（`cea63eb`）；
  土壤深度计算复核（`88be87d`）。
- **水库**：**调水从 waterdemand 移到 lakes_reservoirs**、调水规则集重写（`dd2d1d7`）——
  对含水库的黄河配置影响直接。负库容修正（`aef4571`）。新增湿地例程（`88be87d`）。
- **冻土**：FrostIndex 计算改变（`86066b1`、`32b2a9c`），新增 `FrostDay`。
- **水量平衡**：多处闭合修正（`1c7fdbc`、`4fa8ad1`）——雪的蒸发改从雪盖而非融雪扣，
  冰川面积参与土壤过程。
- **灌溉**：`irrNonPaddy_efficiency` 可按年读 netCDF（`1a9a363`，有 `if` 保护，向后兼容）。
- **雪 / 冰川**：新增可选的 pySnowClim 模块，冰川贡献改按 m³ 载入（`c671b85`）。默认关闭。
- **输出**：netCDF 升到 CF-1.13 并写入 `crs` 投影变量（`bcb8d59`）。

---

## ⚠️ 上游 QC 能力回退（最严重的一处）

上游 `5e11e9d`（2025-09-01）删掉 `waterbalance.py`（459 行）的同时，把各水文模块里的
`if checkOption('calcWaterBalance')` 断言块**全部剥掉**了。

| 键 | 状态 |
|---|---|
| `sumWaterBalance` | **彻底失效**，唯一的读取方 `waterbalance.py` 已删除 |
| `budyko` | **彻底失效**，同上 |
| `calcWaterBalance` | 键还在、还能读，但各模块里的断言块已被剥掉，**近似 no-op** |

**逐时步质量平衡断言没有替代物。** 上游 commit message 说"will be done with water circles later"，
指的是 `OUT_TSS_AreaSum_Daily = WaterCycle` 这条**输出**通道（写出
`WaterCycle_areasum_daily.csv`，`output.py:877,1211`），那是事后对账，不是运行时断言。

**后果**：论文里关于模型质量守恒的可信度论证不能再引用 `calcWaterBalance`。
应改用 WaterCycle 输出做事后核算，并在重新率定前，用标签 `pre-rebaseline-2026-08` 的旧代码
跑一次 `calcWaterBalance = True` 留档，作为对照基线。

---

## ⚠️ settings.ini 迁移清单

### 必须添加

```ini
[OPTIONS]
reportOldTss = True
```

**原因**：上游 `328313c`（2024-04-29）把时间序列输出的默认格式从 PCRaster `.tss` 改成了带真实
日期的 `.csv`（`output.py:213-220`）。**缺省就是新格式**：

```python
newcsvformat = True
suffix = ".csv"
if 'reportOldTss' in option:
    newcsvformat = not(checkOption('reportOldTss'))
if not(newcsvformat):
    suffix = ".tss"
```

**为什么这会静默打断率定**：`cwatm-cali` 硬编码了旧格式，且**同一段解析在三个脚本里各复制了
一份**——`calibration_partial.py:73-80,232,285,586`、`calibration_single.py:73,77,191,235,241,557`、
`calibration_single_ns.py`（同行号）。

不加 `reportOldTss = True` 的后果不是报错，是**误导**：
1. 文件名变成 `discharge_daily.csv`，`calibration_partial.py:232` 的"已跑过"哨兵永不命中 →
   每个个体重复跑，checkpoint 失效；
2. `:282` 抛 `"No simulated streamflow found. Probably the model failed to start?"`——
   模型其实成功了；
3. 若只改文件名不改解析器，`sep=r"\s+"` + `skiprows=4` + `header=None` 会错误解析带日期的
   逗号分隔文件（新表头是 4 行**逗号**分隔，第一列 `DD/MM/YYYY`）。

develop 仍保留旧 TSS writer（`output.py:938-982`，同样 4 行表头），上游自己的率定工具包
正是靠 `settings_CWatM_template.ini:20` 加这一行绕开的。**加这行是最小且逐字节兼容的修法。**

### 必须删除（已成死条目）

```ini
writeNetcdfStack = True     # 删 —— 注意：这个键在 c2a1255 时就已经没有任何代码读取，
                            #      只活在 .ini 文件里，不是 328313c 移除的
reportMap = True            # 删（328313c 变成默认行为并从 OPTION 移除）
reportTss = True            # 删（同上）
sumWaterBalance = ...       # 删（随 waterbalance.py 一起消失）
budyko = ...                # 删（同上）
save_git = ...              # 删
```

### 失效但无害（可留可删）

- **`metaNetcdfFile`** —— develop 的 `run_cwatm.py:122,190` 改成硬编码
  `read_metanetcdf('metaNetcdf.xml')`，`configuration.py:337` 把路径钉死在 **cwatm 包目录**。
  设置里那行被完全忽略。**若实验室有自定义的变量元数据，必须并进仓库里的
  `cwatm/metaNetcdf.xml`，否则静默丢失。**
- `Elevation`、`Elevation_avg`、`TempSnowHigh`、`TempSnowLow`、`CatchmentNo`、
  `irrPaddy_cropDeplFactor`、`irrNonPaddy_cropDeplFactor` —— 已无读取方。

`parse_configuration`（`configuration.py:260-289`）对未知键**静默忽略**，没有 schema 校验，
所以留着不会报错。

### 后处理脚本需要复核

- **netCDF 时间单位全面统一**为 `days since <1650|1861|1901>-01-01`
  （`data_handling.py:2257`）。月度文件的时间戳快到当月 1 号、年度快到 1 月 1 日
  （`:2345-2346`）。旧代码的 `Months since` / `Years since` 已被上游注释掉——
  上游自己修了这个 pandas 不认的格式。
- **`netcdfasindex = True`**（新选项，默认关闭）会只存有效格点的索引向量而非 lat/lon 栅格，
  输出 netCDF 就不能当普通栅格读了。
- **`dzRel0001…` 改名**为列表 `self.var.dzRel[i]`（从 `soil.py:159` 移到 `snow_frost.py:219`）。
  任何 `OUT_MAP_*` 里按名字引用 `dzRel0001` 的行会失效。

### 已核实的非问题

- `MaskMap` **没有**被移除。
- `alphaDepletion`、`fraction_IncreaseIrrigation_Nonpaddy`、`cropgroupnumber` 语义不变，
  前两者仍由 `if ... in binding` 保护。
- develop 新增的 `[OPTIONS]` 键（`reportOldTss`、`netcdfasindex`、`maps_cut_individually`、
  `reportsnowstations`、`stopaftersnow`、`usepySnowClim`、`wetlands_variable_area`、
  `using_reservoir_command_areas`、`reservoir_add_info_in_Excel`）**全部有 `in option` 或
  `checkOption(..., True)` 保护**，旧 settings 不会硬报 Error 116。
- pySnowClim 那一大批新键全在 `if self.var.usepySnowClim:` 之内，默认关闭。

---

## 运行环境

- **gdal 已被 rasterio 取代**（上游 `6ae8b68`，2026-05-18）。`data_handling.py:19-22` 里
  三行 osgeo import 全部注释掉。`git grep` 在 `cwatm/` 下找不到任何 osgeo 导入。
  GeoTIFF 读写仍然支持（`rasterio.open`），率定用的"参数即 GeoTIFF 路径"工作流不受影响——
  但 `cwatm-cali` 自己的 `createGeoTIFF()` 仍直接用 `osgeo` 低层 API，那边的环境**仍需 gdal**。
- **上游的 `requirements.txt` 是陈旧的**（从 2024-01 至今一字未改，仍写 gdal 和 Python 3.8）。
  本仓库的 `requirements.txt` 已重写为实际清单。
- **`setup.py` 被上游删除且无替代**（无 `pyproject.toml`）。CWatM 不是 pip 可安装包，
  直接 `python run_cwatm.py <settings>` 运行。
- **Mac (Apple Silicon) 跑不了**：上游自带的路由 C 库 `t5_mac.so` 是 x86_64，
  `import cwatm.run_cwatm` 直接 `OSError: incompatible architecture`。
  源码 `t5.cpp` 在仓库里，`g++ -shared -fPIC -O3 -o t5_mac.so t5.cpp` 能编出可用的 arm64 版，
  但那会成为第 5 处偏离（一个与上游不同的二进制），已决定不做。**Mac 只用于代码工作，
  所有运行在 Windows 上。**
- **`cwatm/version.py`** 由 GitHub Actions 生成，其 git hash / 分支 / 提交者会写进输出 netCDF
  与 CSV 表头的 metadata（`output.py:852`）。本 fork 已把 `lab/main` 加进
  `.github/workflows/version.yml` 的触发分支，否则溯源信息会永远停在上游的 hash。

---

## 同步纪律

1. **PR 默认打向父仓库。** 从本 fork 开 PR，base 默认是 `iiasa/CWatM`；若从 `lab/main` 开，
   等于公开向上游提交 P1。PR 分支一律从 `upstream/develop` 切，`gh pr create` 永远显式带
   `--repo` 和 `--base`。GitHub 没有服务端开关。
2. **每次 merge 上游后、`--ff-only` 之前，必须跑补丁存活校验**：

   ```bash
   python3 tools/check_lab_patches.py
   ```

   退出码 0 才可以合入。**merge 可以干净解决却依然吞掉补丁**——2026-08 重基线时，
   `soil.py` 和 `water_demand.py` 就是"自动合并成功"的。

   脚本有两层检查。最强的一层是**偏离面**：`git diff upstream/develop -- cwatm/`
   必须恰好触及那四个文件。这能抓到按模式匹配抓不到的东西。第二层是逐补丁的模式匹配，
   刻意不用 grep：`soil.py` 里同一个作物组表达式出现两次（灌溉分支是我们的，
   非灌溉分支是上游自有的），脚本按分支定位、且对空白不敏感。

   四种回退方式已做过负向测试，全部能被抓到。
3. **不要引入 `.gitattributes`。** 前身仓库的 LFS 声明正是 5 个 tutorial `.map` 文件退化成
   130 字节指针的原因，而 git-lfs 从未安装。
4. 同步一律在 `lab/sync-YYYY-MM` 分支做，验证后 `--ff-only` 落地 `lab/main`。
