#!/usr/bin/env bash
# Три аргумента: rx.wav tx.wav result.txt
# Кэш модели — named volume voice-transcription-cache (создаётся сам).
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Использование: $0 RX.wav TX.wav OUT.txt" >&2
  echo "Пример: $0 /data/call-rx.wav /data/call-tx.wav /data/out/dialog.txt" >&2
  exit 1
fi

IMAGE="${GIGAAM_IMAGE:-voice-transcription}"
CACHE_VOL="${GIGAAM_CACHE_VOLUME:-voice-transcription-cache}"

abs() {
  python3 -c "import pathlib, sys; print(pathlib.Path(sys.argv[1]).resolve())" "$1"
}

RX="$(abs "$1")"
TX="$(abs "$2")"
OUT="$(abs "$3")"
OUT_DIR="$(dirname "$OUT")"

if [[ ! -f "$RX" ]]; then echo "Нет файла: $RX" >&2; exit 1; fi
if [[ ! -f "$TX" ]]; then echo "Нет файла: $TX" >&2; exit 1; fi
mkdir -p "$OUT_DIR"

docker volume inspect "$CACHE_VOL" >/dev/null 2>&1 || docker volume create "$CACHE_VOL" >/dev/null

docker run --rm \
  -v "${CACHE_VOL}:/app/.cache" \
  -v "${RX}:${RX}:ro" \
  -v "${TX}:${TX}:ro" \
  -v "${OUT_DIR}:${OUT_DIR}" \
  "$IMAGE" \
  --rx "$RX" --tx "$TX" --output-file "$OUT" --quiet
