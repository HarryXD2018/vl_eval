# LiveViewer

基于 Jupyter + Voila 的视频横向拼接与预览工具。输入一个或多个本地视频路径，可在每路视频上叠加文字 annotation 或烧录字幕，使用 ffmpeg 拼接成一段视频，并同时展示各路原视频预览。

![DEMO](assets/frame.png)

## 功能

- 多视频横向拼接（`hstack`）+ 音频混流（`amix`）；只输入 1 个视频时跳过拼接，直接处理该视频
- 每路视频可叠加多条 annotation 文本，支持 6 种位置：`top / bottom / top-left / top-right / bottom-left / bottom-right`
- Annotation 行动态增删，最多 6 行；每行文本按行对应各路视频（第 N 行对应第 N 个视频）
- 支持文本转义：`\frame_idx`（当前帧编号）、`\name`（视频文件名）、`\timestamp`（秒表，当前播放时间）
- 支持行首颜色前缀 `\red` `\blue` `\yellow`，为该行文字（或字幕）设置颜色，默认白色
- 支持 `\srt /path/to/sub.srt` 转义，为该视频按时间轴烧录字幕文件（`.srt` / `.ass` / `.ssa` / `.vtt`）
- 可选 Caption：在拼接结果下方 pad 一条白色区域，居中显示黑色文字（作用于整段拼接结果，留空则不添加）；文字过长时按视频宽度自动换行（英文按空格折行，无空格的长串/中文按字符折行），白色区域高度随行数自适应
- 拼接结果视频与各路视频预览在同一页面展示，可一键「重置」清空所有输入
- 仅支持 `.mp4` 视频

## 环境依赖

- Python 3.10（conda 环境 `viewer`）
- 系统已安装 `ffmpeg`，且需带 `libass`（烧录字幕用）与 `libfreetype`（drawtext 用）
- Python 包：`voila`、`ipywidgets`、`ipykernel`、`pillow`（Caption 自动换行时用于测量文字宽度；缺失时退化为按字号估算）

### 安装

```bash
conda activate viewer
pip install voila ipywidgets ipykernel pillow

# 在 viewer 环境下注册 Jupyter 内核（首次使用必须）
python -m ipykernel install --user --name viewer --display-name "Python (viewer)"
```

## 运行

```bash
conda activate viewer
voila /ytech_milm_intern/chenhejia/projects/LiveViewer/video_player.ipynb \
    --port=8890 --Voila.ip='0.0.0.0' --no-browser
```

![KML 启动入口](assets/KML_launch.png)

在 KML 界面中使用与 Jupyter 一致的方式打开前端。注意和设置的端口一致。

## 使用步骤

1. 在「视频路径」文本框中每行粘贴一个视频的绝对路径（1 个即可，无需拼接也能加 annotation）。
2. （可选）在「Caption」文本框填写文字，会在拼接结果下方的白色区域居中显示（黑色文字），留空则不添加；文字过长时会按视频宽度自动换行。
3. （可选）点击 `+ 新增 annotation` 添加一行 annotation：
   - 左侧 dropdown 选择文字/字幕位置。
   - 右侧文本框按行写入：第 1 行对应第 1 个视频，第 2 行对应第 2 个视频……留空则该视频此条 annotation 不显示。
   - 行首可加 `\red` / `\blue` / `\yellow` 设置该行颜色；不加则为默认白色。
   - 行内写 `\srt /path/to/sub.srt` 可为该视频烧录字幕文件，而非普通文字。
4. 点击「拼接」按钮，等待 ffmpeg 处理；点击「重置」可清空所有输入。
5. 页面下方依次显示：状态信息、处理结果视频、各视频预览（含 annotation 清单）。

### Annotation 转义命令

文本中可插入以下占位符，渲染到对应视频时展开：

| 命令 | 含义 | 说明 |
| --- | --- | --- |
| `\frame_idx` | 当前帧编号 | 动态值，随视频播放变化 |
| `\name` | 当前视频的文件名 | 例如 `demo.mp4`，按所属视频分别替换 |
| `\timestamp` | 秒表（当前播放时间） | 动态值，格式 `HH:MM:SS.mmm`，随视频播放变化 |

行首颜色前缀（可选，放在行的最前面）：

| 前缀 | 颜色 |
| --- | --- |
| `\red` | 红色 |
| `\blue` | 蓝色 |
| `\yellow` | 黄色 |

字幕转义（该行剩余部分整体视为文件路径）：

| 命令 | 含义 | 说明 |
| --- | --- | --- |
| `\srt <path>` | 烧录字幕文件 | 支持 `.srt` / `.ass` / `.ssa` / `.vtt`，按字幕自带时间轴显示；可与颜色前缀组合，如 `\red \srt /path/to/sub.srt` |

示例：
```
frame: \frame_idx  (\name)  \timestamp
\blue \srt /data/subs/demo.srt
```

## 已知事项

- 视频通过 base64 内嵌到 `<video>` 标签播放，适合中小文件；超大视频会占用较多内存/带宽。
- 输入视频可有可无音频流：≥2 路有音频则混流（`amix` + 音量补偿），仅 1 路有音频则直接映射，全部无则输出无音轨。
- 拼接输出写入 `/tmp`，由系统自行清理。
- 字幕烧录依赖 ffmpeg 的 `subtitles` 滤镜（libass），若运行环境 ffmpeg 未编译该功能，`\srt` 会在 ffmpeg 阶段报错。
