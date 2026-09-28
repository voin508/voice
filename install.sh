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
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg git

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

if [[ ! -d "$ROOT/vendor/GigaAM/gigaam" ]]; then
  echo "==> нет vendor/GigaAM/gigaam — положите GigaAM в vendor/GigaAM или запустите install из полного репозитория" >&2
  exit 1
fi
echo "==> vendor/GigaAM OK"

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
pip install -e "$ROOT/vendor/GigaAM"
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
