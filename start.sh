#!/usr/bin/env bash
# 启动 LiveViewer（voila 服务）
#
#   bash start.sh                              # 使用 conda 环境 liveviewer
#   LV_ENV=volia_viewer bash start.sh          # 指定 conda 环境
#   LV_PORT=8891 bash start.sh                 # 指定端口
#   LV_PYTHON_BIN=/usr/bin/python3 bash start.sh  # 不用 conda

set -euo pipefail
cd "$(dirname "$0")"

ENV_NAME="${LV_ENV:-liveviewer}"
# 优先使用显式传入的 LV_PORT，其次使用平台注入的 WEBSERVER_PORT，最后回落到 8890
PORT="${LV_PORT:-${WEBSERVER_PORT:-8890}}"

die() { printf '\033[1;31m[LiveViewer]\033[0m %s\n' "$*" >&2; exit 1; }
info(){ printf '\033[1;34m[LiveViewer]\033[0m %s\n' "$*"; }

# 定位 voila
if [ -n "${LV_PYTHON_BIN:-}" ]; then
    VOILA="$(dirname "$LV_PYTHON_BIN")/voila"
elif command -v conda >/dev/null 2>&1; then
    CONDA_BASE="$(conda info --base)"
    VOILA="$CONDA_BASE/envs/$ENV_NAME/bin/voila"
    [ -x "$VOILA" ] || die "找不到 $VOILA，请先执行 bash setup.sh"
else
    VOILA="$(command -v voila || true)"
    [ -n "$VOILA" ] || die "找不到 voila，请先执行 bash setup.sh"
fi

info "voila : $VOILA"
info "端口  : $PORT"
info "地址  :"
info "  评测界面     http://<host>:$PORT/voila/render/user_study.ipynb"
info "  目录列表     http://<host>:$PORT"

exec "$VOILA" "$(pwd)" \
    --port="$PORT" \
    --Voila.ip='0.0.0.0' \
    --no-browser
