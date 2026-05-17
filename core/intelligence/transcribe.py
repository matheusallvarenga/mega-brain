#!/usr/bin/env python3
"""
transcribe.py — Local Whisper transcription via mlx-whisper (Apple M-series)

Usage:
    python3.9 transcribe.py <file_or_youtube_url> [options]

Examples:
    python3.9 transcribe.py video.mp4
    python3.9 transcribe.py https://youtube.com/watch?v=xxx
    python3.9 transcribe.py audio.m4a --model large-v3-turbo --lang pt
    python3.9 transcribe.py video.mp4 --output transcript.txt

Requires: mlx-whisper, yt-dlp, ffmpeg (all on Python 3.9 env)
"""

import sys
import os
import argparse
import subprocess
import tempfile
import time
import json
from pathlib import Path
from typing import Optional

PYTHON39 = "/Library/Developer/CommandLineTools/usr/bin/python3.9"

MODELS = {
    "tiny":          "mlx-community/whisper-tiny",
    "small":         "mlx-community/whisper-small",
    "medium":        "mlx-community/whisper-medium",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "large-v3":      "mlx-community/whisper-large-v3",
}
DEFAULT_MODEL = "large-v3-turbo"

SUPPORTED_AUDIO = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".flac",
                   ".webm", ".mkv", ".mov", ".avi", ".aac", ".opus"}


def is_youtube_url(path: str) -> bool:
    return "youtube.com" in path or "youtu.be" in path


def download_youtube(url: str, out_dir: Path) -> Path:
    print(f"  Baixando áudio do YouTube...")
    out_template = str(out_dir / "%(id)s.%(ext)s")
    result = subprocess.run([
        "yt-dlp", url,
        "--extract-audio",
        "--audio-format", "m4a",
        "--audio-quality", "0",
        "--output", out_template,
        "--no-playlist",
        "--quiet", "--no-warnings",
        "--print", "after_move:filepath",
    ], capture_output=True, text=True, check=True)
    audio_path = Path(result.stdout.strip())
    print(f"  Baixado: {audio_path.name}")
    return audio_path


def convert_to_wav(input_path: Path, out_dir: Path) -> Path:
    wav_path = out_dir / (input_path.stem + ".wav")
    subprocess.run([
        "ffmpeg", "-i", str(input_path),
        "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le",
        str(wav_path), "-y", "-loglevel", "quiet"
    ], check=True)
    return wav_path


def transcribe_local(audio_path: Path, model: str, language: Optional[str]) -> dict:
    import mlx_whisper  # noqa — only available in Python 3.9

    model_repo = MODELS.get(model, MODELS[DEFAULT_MODEL])
    kwargs = {"path_or_hf_repo": model_repo, "verbose": False}
    if language:
        kwargs["language"] = language

    print(f"  Modelo: {model} ({model_repo})")
    print(f"  Idioma: {language or 'auto-detect'}")
    t0 = time.time()
    result = mlx_whisper.transcribe(str(audio_path), **kwargs)
    elapsed = time.time() - t0
    result["_meta"] = {
        "model": model,
        "duration_seconds": elapsed,
        "source_file": str(audio_path),
    }
    return result


def format_output(result: dict, fmt: str) -> str:
    if fmt == "txt":
        return result.get("text", "").strip()
    elif fmt == "srt":
        lines = []
        for i, seg in enumerate(result.get("segments", []), 1):
            start = seg["start"]
            end = seg["end"]
            def ts(s):
                h, m = int(s // 3600), int((s % 3600) // 60)
                sec, ms = int(s % 60), int((s % 1) * 1000)
                return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"
            lines += [str(i), f"{ts(start)} --> {ts(end)}", seg["text"].strip(), ""]
        return "\n".join(lines)
    elif fmt == "json":
        return json.dumps(result, ensure_ascii=False, indent=2)
    return result.get("text", "").strip()


def main():
    parser = argparse.ArgumentParser(description="Transcrição local com mlx-whisper (Apple M-series)")
    parser.add_argument("source", help="Arquivo de áudio/vídeo ou URL do YouTube")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL,
                        choices=list(MODELS.keys()),
                        help=f"Modelo Whisper (padrão: {DEFAULT_MODEL})")
    parser.add_argument("--lang", "-l", default=None,
                        help="Idioma forçado (ex: pt, en). Padrão: auto-detect")
    parser.add_argument("--output", "-o", default=None,
                        help="Arquivo de saída (padrão: <source>.txt)")
    parser.add_argument("--format", "-f", default="txt",
                        choices=["txt", "srt", "json"],
                        help="Formato de saída (padrão: txt)")
    args = parser.parse_args()

    source = args.source

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Step 1: Obter arquivo de áudio
        if is_youtube_url(source):
            audio_file = download_youtube(source, tmp_path)
        else:
            audio_file = Path(source)
            if not audio_file.exists():
                print(f"ERRO: arquivo não encontrado: {audio_file}")
                sys.exit(1)
            if audio_file.suffix.lower() not in SUPPORTED_AUDIO:
                print(f"ERRO: formato não suportado: {audio_file.suffix}")
                sys.exit(1)

        # Step 2: Converter para WAV 16kHz mono (otimizado para Whisper)
        print(f"  Convertendo para WAV 16kHz...")
        wav_file = convert_to_wav(audio_file, tmp_path)

        # Step 3: Transcrever
        print(f"  Transcrevendo com mlx-whisper...")
        result = transcribe_local(wav_file, args.model, args.lang)

        elapsed = result["_meta"]["duration_seconds"]
        print(f"  Concluído em {elapsed:.1f}s")

    # Step 4: Gravar output
    text = format_output(result, args.format)

    if args.output:
        out_path = Path(args.output)
    else:
        base = Path(source).stem if not is_youtube_url(source) else "transcricao"
        out_path = Path(base + "." + args.format)

    out_path.write_text(text, encoding="utf-8")
    chars = len(text)
    print(f"\n  Salvo: {out_path} ({chars:,} caracteres)")
    return str(out_path)


if __name__ == "__main__":
    # Ensure running under Python 3.9 (where mlx_whisper is installed)
    if sys.version_info[:2] != (3, 9):
        os.execv(PYTHON39, [PYTHON39] + sys.argv)
    main()
