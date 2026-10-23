#!/bin/bash
# Source from Bash only; launch scripts select Bash explicitly.
if [ -z "${BASH_VERSION:-}" ]; then
  echo "Run the project shell scripts directly; env.sh requires Bash." >&2
  return 1
fi
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
export PROJECT_ROOT
export UV_CACHE_DIR="$PROJECT_ROOT/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$PROJECT_ROOT/.runtime/python"
export UV_PYTHON_BIN_DIR="$PROJECT_ROOT/.runtime/bin"
export UV_TOOL_DIR="$PROJECT_ROOT/.runtime/tools"
export UV_TOOL_BIN_DIR="$PROJECT_ROOT/.runtime/bin"
export UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.venv"
export UV_NO_MODIFY_PATH=1 UV_PYTHON_PREFERENCE=only-managed UV_NO_CONFIG=1
export HF_HOME="$PROJECT_ROOT/.cache/huggingface"
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_XET_CACHE="$HF_HOME/xet"
export HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
export XDG_CACHE_HOME="$PROJECT_ROOT/.cache/xdg"
export XDG_CONFIG_HOME="$PROJECT_ROOT/.runtime/config"
export XDG_DATA_HOME="$PROJECT_ROOT/.runtime/data"
export XDG_STATE_HOME="$PROJECT_ROOT/.runtime/state"
export MPLCONFIGDIR="$PROJECT_ROOT/.cache/matplotlib"
export TORCH_HOME="$PROJECT_ROOT/.cache/torch"
export TMPDIR="$PROJECT_ROOT/.cache/tmp"
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
export PATH="$PROJECT_ROOT/.runtime/bin:$PATH"
mkdir -p "$TMPDIR" "$UV_CACHE_DIR" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME"
cd "$PROJECT_ROOT"
