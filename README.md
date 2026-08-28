# CWatM — SongshGeoLab fork

这是 [iiasa/CWatM](https://github.com/iiasa/CWatM) 的实验室 fork，**不是上游仓库**。
模型本身的文档在 [cwatm.iiasa.ac.at](https://cwatm.iiasa.ac.at)；本文件只讲**这个 fork 怎么维护**。

- **上游基线**：`develop` @ `32cae7d`（2026-08-28）
- **主干**：`lab/main`
- **相对上游的全部偏离**：见 [`LAB_CHANGES.md`](LAB_CHANGES.md)
- **率定体系**：[SongshGeoLab/cwatm-cali](https://github.com/SongshGeoLab/cwatm-cali)（private）

---

## 一、唯一需要记住的不变量

```bash
git diff upstream/develop -- cwatm/
```

**这条命令的输出就是本 fork 的全部偏离**——4 个文件、约 40 行，一屏读完。
不需要读历史，不需要相信任何文档的叙述，直接看 diff。

由 `python3 tools/check_lab_patches.py` 机器校验，**每次合并上游后必跑**，
退出码 0 才可以 `--ff-only` 落地 `lab/main`。

## 二、仓库是怎么叠起来的

不是把两边的改动搅在一起，是分层叠上去的：

```
lab/main
├─ 上游 develop 的整棵树              ← 逐字节一致，一个字没动
├─ + 补丁层：4 个文件、约 40 行        ← P1 科学改动 + P2 bug 修复 + P4 报错文案
└─ + 实验室独有目录                    ← basins/ resolution/ docu/ assets/ tools/
                                         上游没有这些路径，永不冲突
```

`git log` 上每一轮同步就是两个提交：一个 merge（上游原样），一个补丁。
正因如此 `git diff upstream/develop -- cwatm/` 才能精确等于补丁层。
**这是刻意设计的**——下次同步时上游改了什么、我们改了什么，永远分得开。

| | 谁的 | 规则 |
|---|---|---|
| `cwatm/` | 上游的 + 4 个文件的补丁层 | 只能通过重打补丁改动，不在这里随手写代码 |
| `Toolkit/` `Tutorials/` `pytest/` `mf6/` | 纯上游 | 一行都不要改，同步时无条件取上游 |
| `basins/` `resolution/` `docu/` `assets/` | 实验室的 | 随便改，上游没有这些路径 |
| `tools/` | 实验室的 | 补丁存活校验脚本 |
| `LAB_CHANGES.md` `README.md` `requirements.txt` `.github/` | 实验室接管 | 同步时**永远保留我们的**，见第五节 |

## 三、分支怎么管

**长期存在的只有三个：**

| 分支 | 是什么 | 规则 |
|---|---|---|
| `lab/main` | **唯一主干** | **只准 `--ff-only` 前进**。不在它上面直接改，不在它上面 merge 上游 |
| `origin/main` | 上游 `main` 的镜像，fork 自带 | **别碰、别合并**。它的唯一用处是让 GitHub 认得出这是 fork |
| `upstream/develop` | 远端追踪引用，不是你的分支 | 只读 |

**临时分支：**

- `lab/sync-YYYY-MM` —— 每次同步开一个，验证通过后 ff 进 `lab/main` 然后删掉
- PR 分支 —— **从 `upstream/develop` 切**，不从 `lab/main` 切（见第六节）

不要留长期的功能分支。这个仓库的作用是"上游 + 一薄层补丁"，任何在 `cwatm/`
里长期存活的旁支都会让那一薄层慢慢变厚。

## 四、同步上游的标准流程

```bash
git fetch upstream
git switch -c lab/sync-YYYY-MM lab/main
git merge upstream/develop

# 冲突文件一律取上游，不逐行解决
git checkout upstream/develop -- <每一个冲突文件>
git commit                                  # 提交 1：上游原样

# 手工重打 LAB_CHANGES.md 里列出的补丁
git commit                                  # 提交 2：实验室偏离

python3 tools/check_lab_patches.py          # 必须退出 0
# ……验证（见 LAB_CHANGES.md）……

git tag -a pre-rebaseline-YYYY-MM lab/main   # 先打标签，此时 lab/main 还是旧状态
git switch lab/main
git merge --ff-only lab/sync-YYYY-MM
git push origin lab/main --tags
git branch -d lab/sync-YYYY-MM
```

### 为什么是"取上游 + 重打"而不是"解决冲突"

2026-08 那次同步的实测：`merge upstream/develop` 在 `inflow.py`、`irrigation.py`、
`data_handling.py` 报冲突，而 `soil.py` 和 `water_demand.py` **"自动合并成功"**——
补丁被静默保留了下来，看起来一切正常。

**一次干净的 merge 完全不能说明补丁还在，也不能说明补丁没被混进上游代码里。**
如果你相信 merge 的结果，补丁层会一轮一轮地和上游代码纠缠，几次之后就再也说不清
哪一行是谁的了。逐行解决大文件冲突同样如此——上游对 `data_handling.py` 一次就改了
1400 行，人是读不完的。

所以：**冲突文件一律 `git checkout upstream/develop --` 全盘取上游，补丁在下一个
提交里手工重打。** 代价是每次要重打约 40 行，收益是补丁层永远干净、永远可审计。

## 五、README / requirements / workflow 的同步策略

这四类文件实验室已经接管，与上游会长期分歧：

- `README.md` —— 本文件
- `requirements.txt` —— 上游那份是陈旧的（至今仍写 gdal 和 Python 3.8，而 develop
  早已换 rasterio），已重写为实际清单
- `.github/workflows/version.yml` —— 加了 `lab/main` 触发分支，否则 `cwatm/version.py`
  会永远停在上游的 git hash，而它会被写进本实验室输出文件的 metadata
- `.github/workflows/codecov.yml` —— 已停用（需要 fork 上没有的 secret，必然红叉）

同步时这几个文件会冲突，**一律保留我们的**：

```bash
git checkout --ours README.md requirements.txt .github/workflows/*.yml
```

然后**人工看一眼上游那边改了什么**（`git diff HEAD...upstream/develop -- <文件>`），
有值得吸收的再手工合。

## 六、给上游提 PR 的规矩

**从本 fork 开 PR，base 默认是 `iiasa/CWatM`。** 若从 `lab/main` 开，等于公开向上游
提交 P1——那是实验室的科学改动，**永不上游**。GitHub 没有服务端开关能拦住这件事。

所以：

```bash
git switch -c fix/xxx upstream/develop        # 从上游切，不从 lab/main 切
# ……只放这一个修复……
gh pr create --repo iiasa/CWatM --base develop   # 两个参数都必须显式写出
```

当前的 PR 候选：P2（`swAbstractionFrac` 为图时的比较保护，上游至今未修）、
P4（inflow 报错的 BOM 提示）。详见 `LAB_CHANGES.md`。

## 七、标签约定

| 标签 | 含义 |
|---|---|
| `pre-rebaseline-YYYY-MM` | 每次重基线**之前**的最后状态 |
| `lab-science-vN` | 科学改动（P1）所在的提交 |
| `p-option-b-not-taken` | 未采纳的方案 B，分支已删，标签保住 commit |

**每次重基线都必须打 `pre-rebaseline-YYYY-MM`。** 率定结果是和某个具体代码状态绑定的，
没有标签就复现不了；而且有些上游能力会在跨版本时消失（例如 `calcWaterBalance` 的
逐时步质量平衡断言在 2026-08 那一跳后变成了 no-op），旧代码是唯一能补做对照的地方。

## 八、运行环境

- **不要在 Mac 上跑。** 上游自带的路由 C 库 `t5_mac.so` 是 x86_64，Apple Silicon 上
  `import cwatm.run_cwatm` 直接 `OSError: incompatible architecture`。
  Mac 只用于代码工作，所有模型运行在 Windows 上。
- 依赖见本仓库的 `requirements.txt`（**不是**上游那份）。
- CWatM 不是 pip 可安装包——上游删了 `setup.py` 且无替代。直接 `python run_cwatm.py <settings>`。
- **不要引入 `.gitattributes`。** 前身仓库的 LFS 声明正是 5 个 tutorial `.map` 文件
  退化成 130 字节指针的原因，而 git-lfs 从未安装过。

## 九、上游文档

模型本身的用法、公式、输入数据说明都在上游，本 fork 不重复：

- 用户手册与模型文档：[cwatm.iiasa.ac.at](https://cwatm.iiasa.ac.at)
- 30 弧分输入数据：[iiasa/CWatM-Earth-30min](https://github.com/iiasa/CWatM-Earth-30min)
- 讨论区：[github.com/iiasa/CWatM/discussions](https://github.com/iiasa/CWatM/discussions)
- 引用：[10.5281/zenodo.3528097](https://doi.org/10.5281/zenodo.3528097)

CWatM 由 IIASA Water Security 研究组维护，采用 GPL-3.0（见 [`LICENSE`](LICENSE)）。
