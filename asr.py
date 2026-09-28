#!/usr/bin/env python3
"""Нарезка канала по паузам и распознавание через GigaAM."""

from __future__ import annotations

import os
from pathlib import Path
from shutil import which

import torch

HARD_LIMIT_SEC = 24.0
MIN_SPEECH_SEC = 0.20
MIN_SILENCE_SEC = 0.40
PAD_SEC = 0.20
CHUNK_LOOKBACK_SEC = 0.50


def ensure_ffmpeg() -> None:
    if which("ffmpeg"):
        return

    worker_bin = Path(__file__).resolve().parent / "bin"
    if worker_bin.is_dir():
        os.environ["PATH"] = str(worker_bin) + os.pathsep + os.environ.get("PATH", "")
        if which("ffmpeg"):
            return

    raise RuntimeError(
        "ffmpeg не найден. Варианты: sudo apt install -y ffmpeg "
        "или положите бинарник в gigaam-worker/bin/ffmpeg"
    )


def detect_speech_intervals(
    audio: torch.Tensor,
    sr: int,
    frame_ms: float = 30.0,
) -> list[tuple[float, float]]:
    frame = max(1, int(sr * frame_ms / 1000))
    n_frames = audio.numel() // frame
    if n_frames == 0:
        duration = audio.numel() / sr
        return [(0.0, duration)] if duration >= MIN_SPEECH_SEC else []

    frames = audio[: n_frames * frame].view(n_frames, frame)
    rms = torch.sqrt(frames.pow(2).mean(dim=1) + 1e-12)
    p15 = float(torch.quantile(rms, 0.15))
    p90 = float(torch.quantile(rms, 0.90))
    thresh = p15 + 0.22 * max(p90 - p15, 1e-6)
    thresh = max(thresh, 1e-4)

    speech = (rms > thresh).tolist()
    hang = 3
    last_on = -hang
    for i, is_speech in enumerate(speech):
        if is_speech:
            last_on = i
        elif i - last_on <= hang:
            speech[i] = True

    intervals: list[tuple[float, float]] = []
    start_i: int | None = None
    for i, is_speech in enumerate(speech):
        if is_speech and start_i is None:
            start_i = i
        elif not is_speech and start_i is not None:
            start_sec = start_i * frame / sr
            end_sec = i * frame / sr
            if end_sec - start_sec >= MIN_SPEECH_SEC:
                intervals.append((start_sec, end_sec))
            start_i = None
    if start_i is not None:
        start_sec = start_i * frame / sr
        end_sec = min(n_frames * frame / sr, audio.numel() / sr)
        if end_sec - start_sec >= MIN_SPEECH_SEC:
            intervals.append((start_sec, end_sec))

    if not intervals:
        return []

    padded: list[tuple[float, float]] = []
    duration = audio.numel() / sr
    for start, end in intervals:
        padded.append((max(0.0, start - PAD_SEC), min(duration, end + PAD_SEC)))

    merged: list[tuple[float, float]] = [padded[0]]
    for start, end in padded[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= MIN_SILENCE_SEC:
            merged[-1] = (prev_start, end)
        else:
            merged.append((start, end))
    return merged


def split_long_interval(start: float, end: float, hard_limit: float = HARD_LIMIT_SEC) -> list[tuple[float, float]]:
    duration = end - start
    if duration <= hard_limit:
        return [(start, end)]
    n_parts = int(duration / hard_limit) + 1
    part = duration / n_parts
    out: list[tuple[float, float]] = []
    pos = start
    for _ in range(n_parts - 1):
        nxt = pos + part
        out.append((pos, nxt))
        pos = nxt
    out.append((pos, end))
    return out


def transcribe_waveform(model, piece: torch.Tensor) -> str:
    wav = piece.to(model._device).to(model._dtype).unsqueeze(0)
    length = torch.full([1], wav.shape[-1], device=model._device)
    encoded, encoded_len = model.forward(wav, length)
    text, _ = model._decode(encoded, encoded_len, length, False)[0]
    return text.strip()


def transcribe_channel_turns(model, wav_file: str, *, verbose: bool = True) -> list[dict]:
    from gigaam.preprocess import SAMPLE_RATE, load_audio

    audio = load_audio(wav_file)
    intervals = detect_speech_intervals(audio, SAMPLE_RATE)
    pieces: list[tuple[float, float]] = []
    for start, end in intervals:
        pieces.extend(split_long_interval(start, end))

    if verbose:
        print(f"VAD: {len(intervals)} участков речи → {len(pieces)} реплик", flush=True)

    turns: list[dict] = []
    prev_end = 0.0
    for start, end in pieces:
        cut_start = max(prev_end, start - CHUNK_LOOKBACK_SEC)
        piece = audio[int(cut_start * SAMPLE_RATE) : int(end * SAMPLE_RATE)]
        prev_end = end
        if piece.numel() < int(0.25 * SAMPLE_RATE):
            continue
        text = transcribe_waveform(model, piece)
        if not text:
            continue
        turn = {"start": round(start, 3), "end": round(end, 3), "text": text}
        turns.append(turn)
        if verbose:
            print(f"[{start:6.1f}–{end:5.1f}s] {text}", flush=True)
    return turns


def load_gigaam(model_name: str, device: str | None = None):
    import gigaam

    kwargs: dict = {}
    if device is not None:
        kwargs["device"] = device
        if device == "cpu":
            kwargs["fp16_encoder"] = False
    cache = os.environ.get("GIGAAM_CACHE")
    if cache:
        kwargs["download_root"] = cache
    return gigaam.load_model(model_name, **kwargs)


def find_gigaam_sources() -> list[Path]:
    here = Path(__file__).resolve().parent
    return [
        here / "vendor" / "GigaAM",
        here.parent / "GigaAM-main",
    ]
