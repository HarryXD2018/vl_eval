#!/usr/bin/env bash
# LiveViewer 一键环境准备（可重复执行，已满足的条件会跳过）
#
#   bash setup.sh                                  # 新建/复用 conda 环境 liveviewer
#   LV_ENV=volia_viewer bash setup.sh              # 复用已有的 conda 环境
#   LV_PYTHON_BIN=/usr/bin/python3 bash setup.sh   # 不用 conda，直接装在指定解释器上
set -euo pipefail
cd "$(dirname "$0")"

ENV_NAME="${LV_ENV:-liveviewer}"
PY_VER="${LV_PYTHON:-3.10}"

info() { printf '\033[1;34m[LiveViewer]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[LiveViewer]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[LiveViewer]\033[0m %s\n' "$*" >&2; exit 1; }

# 1. 定位解释器：优先 conda 环境，其次 LV_PYTHON_BIN / python3
if [ -n "${LV_PYTHON_BIN:-}" ]; then
    PY="$LV_PYTHON_BIN"
    info "使用指定解释器：$PY"
elif command -v conda >/dev/null 2>&1; then
    CONDA_BASE="$(conda info --base)"
    if [ -d "$CONDA_BASE/envs/$ENV_NAME" ]; then
        info "复用已有 conda 环境：$ENV_NAME"
    else
        info "创建 conda 环境：$ENV_NAME (python $PY_VER)"
        conda create -y -n "$ENV_NAME" "python=$PY_VER"
    fi
    PY="$CONDA_BASE/envs/$ENV_NAME/bin/python"
else
    PY="$(command -v python3 || true)"
    [ -n "$PY" ] || die "没有 conda，也找不到 python3；请先安装 Python 3.10+"
    warn "未找到 conda，直接安装到：$PY"
fi
[ -x "$PY" ] || die "解释器不可用：$PY"

# 2. Python 包（voila + ipywidgets 是运行必需）
info "安装 Python 依赖：$("$PY" -V 2>&1)"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt

# 3. 注册 Jupyter 内核（notebook 里 import ipywidgets 要用）
info "注册 Jupyter 内核：$ENV_NAME"
"$PY" -m ipykernel install --user --name "$ENV_NAME" \
    --display-name "Python ($ENV_NAME)" >/dev/null

# 4. 数据自检：attr.json 里引用的视频是否齐全
if "$PY" - <<'PY'
import json, os, sys
attr = "v1112_compare/attr.json"
if not os.path.isfile(attr):
    print(f"  ! 缺少 {attr}")
    sys.exit(1)
missing = []
for rec in json.load(open(attr, encoding="utf-8")):
    for k, v in rec.items():
        if k != "id" and not os.path.isfile(os.path.abspath(v)):
            missing.append(v)
if missing:
    print(f"  ! {len(missing)} 个视频文件缺失，例如 {missing[0]}")
    sys.exit(1)
PY
then
    info "attr.json 引用的视频齐全"
else
    warn "评测数据不完整：页面会列出缺失项并跳过，请补齐 v1112_compare/videos/ 下的文件"
fi

info "环境就绪。启动：bash start.sh    （或 LV_ENV=$ENV_NAME bash start.sh）"
