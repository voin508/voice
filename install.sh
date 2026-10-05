#!/usr/bin/env bash
# ./install.sh          — cuda, если есть nvidia-smi, иначе cpu
# ./install.sh cpu
# ./install.sh cuda

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

DEVICE="${1:-auto}"
if [[ "$DEVICE" == "auto" ]]; then
  if command -v nvidia-smi >/dev/null 2>&1; then
    DEVICE="cuda"
  else
    DEVICE="cpu"
  fi
fi

if [[ "$DEVICE" != "cuda" && "$DEVICE" != "cpu" ]]; then
  echo "Использование: ./install.sh [auto|cuda|cpu]" >&2
  exit 1
fi

echo "==> $DEVICE"
echo "==> apt: python3 ffmpeg git"
_apt() {
  if [[ "${DOCKER:-}" == 1 ]] || [[ "$(id -u)" -eq 0 ]]; then
    apt-get "$@"
  else
    sudo apt-get "$@"
  fi
}
_apt update
_apt install -y python3 python3-venv python3-pip ffmpeg git

if ! command -v python3 >/dev/null; then
  echo "python3 не найден" >&2
  exit 1
fi

PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "==> Python $PY_VER"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "Нужен Python >= 3.10" >&2
  exit 1
}

GIGAAM_VENDOR="$ROOT/vendor/GigaAM"
GIGAAM_REPO="${GIGAAM_REPO:-https://github.com/salute-developers/GigaAM.git}"
GIGAAM_REF="$(tr -d ' \r\n' < "$ROOT/vendor/GIGAAM_COMMIT")"

ensure_gigaam_source() {
  if [[ -d "$GIGAAM_VENDOR/gigaam" ]]; then
    return 0
  fi
  echo "==> GigaAM: git submodule или clone $GIGAAM_REF"
  if [[ -d "$ROOT/.git" ]] && [[ -f "$ROOT/.gitmodules" ]]; then
    git -C "$ROOT" submodule update --init --depth 1 vendor/GigaAM
    if [[ -n "$GIGAAM_REF" ]]; then
      git -C "$GIGAAM_VENDOR" checkout --detach "$GIGAAM_REF" 2>/dev/null || true
    fi
  fi
  if [[ ! -d "$GIGAAM_VENDOR/gigaam" ]]; then
    rm -rf "$GIGAAM_VENDOR"
    git clone --filter=blob:none --no-checkout "$GIGAAM_REPO" "$GIGAAM_VENDOR"
    git -C "$GIGAAM_VENDOR" checkout "$GIGAAM_REF"
  fi
  if [[ ! -d "$GIGAAM_VENDOR/gigaam" ]]; then
    echo "==> не удалось получить GigaAM в $GIGAAM_VENDOR" >&2
    exit 1
  fi
}

ensure_gigaam_source
echo "==> GigaAM @ ${GIGAAM_REF:-submodule}"

echo "==> venv: $ROOT/.venv"
python3 -m venv "$ROOT/.venv"
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip install --upgrade pip

echo "==> PyTorch ($DEVICE)"
if [[ "$DEVICE" == "cuda" ]]; then
  pip install "torch>=2.6" "torchaudio>=2.6" --index-url https://download.pytorch.org/whl/cu124
else
  pip install "torch>=2.6" "torchaudio>=2.6" --index-url https://download.pytorch.org/whl/cpu
fi

echo "==> gigaam"
pip install -e "$GIGAAM_VENDOR"
if grep -qE '^[^#[:space:]]' "$ROOT/requirements.txt"; then
  pip install -r "$ROOT/requirements.txt"
fi

echo "==> проверка"
python - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "-")
import gigaam
print("gigaam ok")
PY

echo
echo "Установлено в $ROOT/.venv"
echo "Дальше: ./run.sh --preload && ./run.sh --rx rx.wav --tx tx.wav"
