#!/usr/bin/env python3
"""
rx — звонящий, tx — принимающий.
  out-*   исходящий: rx=оператор, tx=клиент
  exten-* входящий:  rx=клиент,  tx=оператор
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from asr import ensure_ffmpeg, find_gigaam_sources, load_gigaam, transcribe_channel_turns  # noqa: E402

for src in find_gigaam_sources():
    if (src / "gigaam").is_dir():
        sys.path.insert(0, str(src))
        break

ROLE_MAP_INBOUND = {"rx": "client", "tx": "agent"}
ROLE_MAP_OUTBOUND = {"rx": "agent", "tx": "client"}
LABELS = {"agent": "Оператор", "client": "Клиент"}


def file_stem(path: Path) -> str:
    name = path.name
    lower = name.lower()
    for ext in (".wav", ".mp3", ".flac", ".ogg", ".m4a"):
        if lower.endswith(ext):
            return name[: -len(ext)]
    return name


def infer_output_stem(*paths: Path) -> str:
    stem = file_stem(paths[0])
    for suffix in ("-rx", "-tx", "_rx", "_tx"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def infer_direction(*paths: Path) -> str | None:
    name = infer_output_stem(*paths).lower()
    if name.startswith("out-") or name.startswith("out_"):
        return "outbound"
    if name.startswith("exten-") or name.startswith("exten_"):
        return "inbound"
    return None


def resolve_role_map(*paths: Path) -> tuple[dict[str, str], str]:
    direction = infer_direction(*paths)
    if direction == "outbound":
        return dict(ROLE_MAP_OUTBOUND), "исходящий: сотрудник → клиент (rx=оператор, tx=клиент)"
    if direction == "inbound":
        return dict(ROLE_MAP_INBOUND), "входящий: клиент → нам (rx=клиент, tx=оператор)"
    return dict(ROLE_MAP_INBOUND), "направление неизвестно, как входящий (rx=клиент, tx=оператор)"


def find_channel_file(stem: str, channel: str, search_dirs: list[Path]) -> Path | None:
    names = (
        f"{stem}-{channel}.wav",
        f"{stem}_{channel}.wav",
        f"{stem}-{channel}.WAV",
        f"{stem}_{channel}.WAV",
    )
    for directory in search_dirs:
        for name in names:
            path = directory / name
            if path.is_file():
                return path.resolve()
    return None


def default_search_dirs(target: Path, extra: list[Path]) -> list[Path]:
    dirs: list[Path] = []
    if target.parent.as_posix() not in (".", ""):
        parent = target.parent
        dirs.append(parent.resolve() if parent.exists() else Path.cwd())
    dirs.append(Path.cwd())
    env_dir = os.environ.get("CALLS_DIR")
    if env_dir:
        dirs.append(Path(env_dir).expanduser())
    dirs.extend(extra)

    seen: set[Path] = set()
    unique: list[Path] = []
    for directory in dirs:
        try:
            resolved = directory.expanduser().resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def resolve_rx_tx(target: Path, extra: list[Path]) -> tuple[Path, Path]:
    search_dirs = default_search_dirs(target, extra)
    stem = infer_output_stem(target.expanduser())
    rx = find_channel_file(stem, "rx", search_dirs)
    tx = find_channel_file(stem, "tx", search_dirs)
    if rx is None or tx is None:
        tried = ", ".join(str(d) for d in search_dirs)
        missing = []
        if rx is None:
            missing.append(f"{stem}-rx.wav")
        if tx is None:
            missing.append(f"{stem}-tx.wav")
        raise FileNotFoundError(f"Не найдены: {', '.join(missing)}. Искал в: {tried}")
    return rx, tx


def format_ts(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"{total // 60:02d}:{total % 60:02d}"


def merge_dialogue(rx_turns: list[dict], tx_turns: list[dict], role_map: dict[str, str]) -> list[dict]:
    turns: list[dict] = []
    for source, channel_turns in (("rx", rx_turns), ("tx", tx_turns)):
        role = role_map[source]
        for item in channel_turns:
            turns.append(
                {
                    "role": role,
                    "source": source,
                    "start": item["start"],
                    "end": item["end"],
                    "text": item["text"],
                }
            )
    turns.sort(key=lambda item: (item["start"], item["end"], item["source"]))
    for index, turn in enumerate(turns):
        turn["id"] = index
    return turns


def format_dialogue_text(turns: list[dict]) -> str:
    lines = []
    for turn in turns:
        label = LABELS.get(turn["role"], turn["role"])
        lines.append(f"[{format_ts(turn['start'])}] {label}: {turn['text']}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Диалог rx/tx через GigaAM")
    parser.add_argument("call", nargs="?", type=Path, help="Стем звонка (подставит -rx.wav и -tx.wav)")
    parser.add_argument("--rx", type=Path, help="WAV канала rx")
    parser.add_argument("--tx", type=Path, help="WAV канала tx")
    parser.add_argument("--model", default="v3_e2e_rnnt", help="Модель GigaAM")
    parser.add_argument("--device", default=None, help="cuda или cpu")
    parser.add_argument("--output-dir", "-o", type=Path, default=ROOT / "transcripts")
    parser.add_argument("--search-dir", action="append", default=[], type=Path, help="Где искать rx/tx по стему")
    parser.add_argument("--quiet", action="store_true", help="Печатать только путь к txt")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    has_pair = args.rx is not None or args.tx is not None
    if has_pair and (args.rx is None or args.tx is None):
        print("Укажите оба файла: --rx и --tx", file=sys.stderr)
        return 1
    if not has_pair and args.call is None:
        print("Укажите стем звонка или пару --rx/--tx", file=sys.stderr)
        return 1

    try:
        if has_pair:
            rx_path = args.rx.expanduser().resolve()
            tx_path = args.tx.expanduser().resolve()
            for label, path in (("rx", rx_path), ("tx", tx_path)):
                if not path.is_file():
                    print(f"Файл {label} не найден: {path}", file=sys.stderr)
                    return 1
        else:
            rx_path, tx_path = resolve_rx_tx(args.call, args.search_dir)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    role_map, role_description = resolve_role_map(rx_path, tx_path)
    try:
        ensure_ffmpeg()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1
    verbose = not args.quiet

    if verbose:
        print("Режим: rx/tx dialogue", flush=True)
        print(f"Модель: {args.model}", flush=True)
        print(f"Направление: {role_description}", flush=True)
        print(f"rx (звонящий) → {LABELS[role_map['rx']]}: {rx_path.name}", flush=True)
        print(f"tx (принимающий) → {LABELS[role_map['tx']]}: {tx_path.name}", flush=True)

    t0 = time.perf_counter()
    if verbose:
        print(f"Загрузка {args.model} ...", flush=True)
    model = load_gigaam(args.model, args.device)
    load_sec = time.perf_counter() - t0
    device = str(model._device)
    if verbose:
        print(f"Устройство: {device}", flush=True)

    t_tx0 = time.perf_counter()
    if verbose:
        print(f"\n--- rx → {LABELS[role_map['rx']]} ---", flush=True)
    rx_turns = transcribe_channel_turns(model, str(rx_path), verbose=verbose)
    if verbose:
        print(f"\n--- tx → {LABELS[role_map['tx']]} ---", flush=True)
    tx_turns = transcribe_channel_turns(model, str(tx_path), verbose=verbose)
    transcribe_sec = time.perf_counter() - t_tx0
    total_sec = time.perf_counter() - t0

    turns = merge_dialogue(rx_turns, tx_turns, role_map)
    dialogue_text = format_dialogue_text(turns)
    stem = infer_output_stem(rx_path, tx_path)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    txt_path = args.output_dir / f"{stem}.gigaam.dialogue.txt"
    txt_path.write_text(dialogue_text + "\n", encoding="utf-8")

    timing_line = (
        f"Время: загрузка {load_sec:.1f}с | транскрипция {transcribe_sec:.1f}с | всего {total_sec:.1f}с"
    )

    if args.quiet:
        print(txt_path)
        print(timing_line, file=sys.stderr, flush=True)
        return 0

    print("\n=== ДИАЛОГ ===")
    print(dialogue_text)
    print(f"\nСохранено: {txt_path}")
    print(f"Реплик: {len(turns)} (rx={len(rx_turns)}, tx={len(tx_turns)})")
    print(timing_line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
