#!/usr/bin/env python3
"""Скачать веса GigaAM в кэш (GIGAAM_CACHE или ~/.cache/gigaam)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from asr import find_gigaam_sources, load_gigaam  # noqa: E402

for src in find_gigaam_sources():
    if (src / "gigaam").is_dir():
        sys.path.insert(0, str(src))
        break


def main() -> int:
    parser = argparse.ArgumentParser(description="Скачать веса GigaAM")
    parser.add_argument("--model", default="v3_e2e_rnnt")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    print(f"Качаю {args.model} ...", flush=True)
    model = load_gigaam(args.model, args.device)
    print(f"Готово. Устройство: {model._device}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
