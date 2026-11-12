# LiveViewer

基于 Jupyter + Voila 的视频主观评测工具：把同一个片段下多个方法的生成结果并排盲测播放，评价者按两个维度打 1–5 分，提交后落盘 CSV，可汇总成方法级 MOS 与逐对比较报告。

| 文件 | 作用 |
| --- | --- |
| [`user_study.ipynb`](user_study.ipynb) | 评测界面：读取 `attr.json` 按片段分组，组内随机打乱后盲测打分，提交落盘 |
| [`user_study_stats.py`](user_study_stats.py) | 统计脚本：汇总 `logs/` 下所有评分 CSV，输出排名、置信区间与逐对比较 |
| [`v1112_compare/attr.json`](v1112_compare/attr.json) | 评测清单：片段 → 各方法视频路径 |
| `v1112_compare/videos/` | 评测视频，按方法分目录 |

---

## 快速开始（一键部署）

```bash
bash setup.sh     # 1. 装环境（首次执行一次，幂等）
bash start.sh     # 2. 启动服务
```

然后在浏览器打开 `http://<host>:<端口>/voila/render/user_study.ipynb` 即可开始评测。

### 1. 安装环境

```bash
bash setup.sh
```

默认在 conda 中创建名为 `liveviewer` 的环境，安装 `voila / ipywidgets / ipykernel` 并注册 Jupyter 内核；最后自检 `attr.json` 引用的视频是否齐全，缺文件会给出提示。

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `LV_ENV` | 指定或复用已有的 conda 环境名 | `liveviewer` |
| `LV_PYTHON_BIN` | 不用 conda，直接装到指定 python 解释器 | 不设 |
| `LV_PYTHON` | 新建 conda 环境时的 Python 版本 | `3.10` |

```bash
LV_ENV=volia_viewer bash setup.sh        # 复用已有环境
```

不使用脚本时手动安装：

```bash
conda create -y -n liveviewer python=3.10
conda activate liveviewer
pip install -r requirements.txt
python -m ipykernel install --user --name liveviewer --display-name "Python (liveviewer)"
```

### 2. 启动服务

```bash
bash start.sh
```

监听 `0.0.0.0`，端口优先级为 `LV_PORT` → `$WEBSERVER_PORT`（平台注入）→ `8890`。

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `LV_ENV` | conda 环境名 | `liveviewer` |
| `LV_PORT` | 监听端口，显式指定时优先级最高 | 不设（读 `$WEBSERVER_PORT`） |
| `WEBSERVER_PORT` | 平台注入的端口，未设 `LV_PORT` 时使用 | 不设，回落到 `8890` |

```bash
LV_ENV=volia_viewer bash start.sh                 # 端口自动取 $WEBSERVER_PORT
LV_ENV=volia_viewer LV_PORT=8891 bash start.sh    # 强制指定端口
```

### 3. 打开页面

| 页面 | 地址 |
| --- | --- |
| 评测界面 | `http://<host>:8890/voila/render/user_study.ipynb` |
| 目录列表 | `http://<host>:8890` |

![KML 启动入口](assets/KML_launch.png)

在 KML 界面中使用与 Jupyter 一致的方式打开前端。注意和设置的端口一致。

---

## 评测流程

### 评分维度

| 维度 | 含义 |
| --- | --- |
| 自然程度 | 反应的面部 / 口型 / 肢体是否自然，有无崩坏、模糊、伪影 |
| 时机恰当 | 反应的时机是否合理，与对方的说话 / 动作是否同步 |

两维都是 `1 很差 / 2 较差 / 3 一般 / 4 较好 / 5 很好`。

### 页面行为

- **盲测**：组内视频位置每轮随机打乱，只显示「视频 A / B / C / D / E」，不暴露方法名、文件名与片段编号；方法归属只写进 CSV。
- **整组同屏**：一个片段的全部方法并排播放，一组评完才触发「自动下一组」，事后回看改分不会被弹走。
- **翻页与重打乱**：上一组 / 下一组 / 跳到未完成 / 重新开始（重新打乱）。
- **对齐时机**：全部播放 / 全部暂停 / 循环播放，便于判断反应时机。
- **提交**：全部组评完后才能提交，落盘后展示各方法均值（此时盲测结束）。

### 使用步骤

1. 打开页面，填写评价者姓名或编号——只写进 CSV，不影响盲测。
2. 按需勾选「本组评完自动下一组」。
3. 逐组观看同片段的各路结果，对每一格打两个维度的分。
4. 全部评完后点击「提交并保存 CSV」。
5. 多人评测结束后，用 `user_study_stats.py` 汇总。

---

## 数据准备

`v1112_compare/attr.json` 是一个数组，每个元素代表一个片段，除 `id` 外的**每个键都是一个方法**，值为该片段对应方法的视频路径：

```json
[
  {
    "id": 88,
    "ours": "./v1112_compare/videos/ours/88.mp4",
    "avtr-1": "./v1112_compare/videos/avtr_nobc/88.mp4",
    "avatar forcing": "./v1112_compare/videos/avatarforcing_nobc/88.mp4",
    "ovi": "./v1112_compare/videos/ovi/88.mp4",
    "GT": "./v1112_compare/videos/gt/88.mp4"
  }
]
```

- 路径支持相对（相对项目根目录）与绝对路径，只支持 `.mp4`。
- 方法名即提交后与统计报告里的展示名；方法个数不固定，页面按 `GROUP_COLUMNS`（默认 5）换行排布。
- 文件缺失的条目**不会静默跳过**，会在状态栏列出缺失项，避免「共 N 段」与实际不符。
- 换自己的数据：改 `attr.json`，或整体替换 `v1112_compare/videos/`。若要改 `attr.json` 的位置，需同步修改 notebook 里的 `PROJECT_ROOT` / `ATTR_JSON`。

---

## 结果与统计

### 落盘文件

每次提交在 `v1112_compare/logs/` 下写两个文件（`logs/` 与 `stats/` 已 gitignore）：

| 文件 | 内容 |
| --- | --- |
| `YYYYMMDD_HHMMSS.csv` | 一行一个视频 |
| `YYYYMMDD_HHMMSS_summary.csv` | 方法级均值 |

评分 CSV 列：

```
group_index  slot  order_index  clip_id  method  naturalness  timing  avg
subject  session_id  seed  rated_at  path
```

`slot` / `order_index` 记录的是随机后的展示位置，`method` 才是真实归属。

### 统计脚本

```bash
python user_study_stats.py
```

只依赖标准库（`volia_viewer` 环境即可运行）。结果打印到终端，同时落盘到 `v1112_compare/stats/<时间戳>_*.csv`：

| 文件 | 内容 |
| --- | --- |
| `*_overall.csv` | 方法级 MOS：均值 / 标准差 / 95% 置信区间，按两维平均排名 |
| `*_by_clip.csv` | 片段 × 方法 的均分 |
| `*_by_session.csv` | 每个会话（评价者）的方法均分，以及与其他人均值的相关系数（筛查异常评价者） |
| `*_vs_ours.csv` | 参考方法与其它方法逐对比较：胜 / 平 / 负、平均分差、符号检验 p 值 |

常用参数：

```bash
python user_study_stats.py --exclude 20261112_125813    # 剔除某个会话
python user_study_stats.py --ref GT                     # 换参考方法（默认 ours）
python user_study_stats.py --log-dir path/to/logs --no-save
```

notebook 最后一个代码格也有一份快速汇总（名次 / n / 双维度均值），适合评测当场看个大概。

---

## 目录结构

```
LiveViewer/
├── setup.sh                  # 一键安装环境 + 数据自检
├── start.sh                  # 一键启动 voila
├── requirements.txt          # Python 依赖
├── user_study.ipynb          # 评测界面
├── user_study_stats.py       # 统计汇总
├── assets/                   # README 图片
└── v1112_compare/
    ├── attr.json             # 片段 → 各方法视频路径
    ├── videos/{ours,avtr_nobc,avatarforcing_nobc,ovi,gt}/
    ├── logs/                 # 评分 CSV（gitignore）
    └── stats/                # 统计输出（gitignore）
```

---

## 常见问题

**页面打不开**
确认 `start.sh` 打印的端口与实际监听端口一致；端口被占用时用 `LV_PORT=8891 bash start.sh` 换端口。

**报 `No module named 'ipywidgets'`**
内核与运行环境不一致。重新执行 `bash setup.sh` 注册内核，并确认 Voila 用的是同一个 conda 环境。

**部分视频没出现**
说明 `attr.json` 里对应路径不存在。页面状态栏会列出缺失项，`bash setup.sh` 也会在安装末尾提示。

**评分丢了**
评分只存在于当前页面状态，未点「提交并保存 CSV」就刷新会丢失。

**一次渲染的视频太多 / 太大**
页面只渲染当前组，体量由单组视频大小决定；可在 notebook 顶部调小 `VIDEO_MAX_WIDTH`，或减少 `attr.json` 里每个方法的视频分辨率。

**换了机器或路径**
`setup.sh` / `start.sh` 都基于脚本所在目录定位项目，无需改路径；`user_study.ipynb` 通过从 cwd 向上查找 `v1112_compare/attr.json` 定位项目根目录，找不到时才回落到硬编码路径，换目录部署需同步修改。
