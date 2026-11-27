"""Transcribe Arabic (darija) and French audio with Whisper large-v3 (MLX)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

DEFAULT_MODEL = "mlx-community/whisper-large-v3-mlx"
MEDIA_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".amr", ".aiff",
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".3gp",
}
FORMATS = ("txt", "srt", "json")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcribe",
        description="Transcribe audio or video files in Arabic (darija) and French.",
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="audio/video files or folders")
    parser.add_argument(
        "-l", "--language", default="auto", choices=("auto", "ar", "fr"),
        help="spoken language; 'auto' detects it from the first 30 seconds (default: auto)",
    )
    parser.add_argument(
        "-o", "--out", type=Path, default=None,
        help="output folder (default: next to each input file)",
    )
    parser.add_argument(
        "-f", "--formats", default="txt,srt,json",
        help="comma-separated outputs among txt, srt, json (default: all three)",
    )
    parser.add_argument(
        "-m", "--model", default=DEFAULT_MODEL,
        help=f"Hugging Face repo or local path of an MLX Whisper model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "-p", "--prompt", default=None,
        help="short text in the spoken language to guide spelling and vocabulary (names, terms)",
    )
    parser.add_argument(
        "--words", action="store_true",
        help="add per-word timestamps to the JSON (slower)",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="transcribe again even when the outputs already exist",
    )
    args = parser.parse_args(argv)

    args.formats = [f.strip().lower() for f in args.formats.split(",") if f.strip()]
    unknown = [f for f in args.formats if f not in FORMATS]
    if unknown or not args.formats:
        parser.error(f"--formats accepts {', '.join(FORMATS)} (got: {', '.join(unknown) or 'nothing'})")
    return args


def collect_files(inputs: list[Path]) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        if item.is_dir():
            files += sorted(
                p for p in item.rglob("*")
                if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
            )
        elif item.is_file():
            files.append(item)
        else:
            sys.exit(f"Not found: {item}")
    return files


def srt_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def to_srt(segments: list[dict]) -> str:
    blocks = []
    for segment in segments:
        text = segment["text"].strip()
        if not text:
            continue
        blocks.append(
            f"{len(blocks) + 1}\n{srt_time(segment['start'])} --> {srt_time(segment['end'])}\n{text}\n"
        )
    return "\n".join(blocks)


def to_json(result: dict, source: Path, model: str, with_words: bool) -> str:
    segments = []
    for segment in result["segments"]:
        entry = {
            "id": segment["id"],
            "start": round(segment["start"], 3),
            "end": round(segment["end"], 3),
            "text": segment["text"].strip(),
        }
        if with_words:
            entry["words"] = [
                {
                    "word": word["word"].strip(),
                    "start": round(float(word["start"]), 3),
                    "end": round(float(word["end"]), 3),
                }
                for word in segment.get("words", [])
            ]
        segments.append(entry)
    payload = {
        "file": source.name,
        "model": model,
        "language": result.get("language"),
        "text": result["text"].strip(),
        "segments": segments,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def transcribe_file(source: Path, args: argparse.Namespace) -> None:
    import mlx_whisper

    out_dir = args.out or source.parent
    targets = {fmt: out_dir / f"{source.stem}.{fmt}" for fmt in args.formats}
    if not args.overwrite and all(path.exists() for path in targets.values()):
        print(f"skip  {source.name} (outputs exist, use --overwrite)")
        return

    started = time.time()
    result = mlx_whisper.transcribe(
        str(source),
        path_or_hf_repo=args.model,
        language=None if args.language == "auto" else args.language,
        initial_prompt=args.prompt,
        word_timestamps=args.words,
        # Each 30 s window is decoded on its own: one bad window cannot make
        # the following ones repeat the same sentence.
        condition_on_previous_text=False,
        verbose=None,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    if "txt" in targets:
        lines = [s["text"].strip() for s in result["segments"] if s["text"].strip()]
        targets["txt"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    if "srt" in targets:
        targets["srt"].write_text(to_srt(result["segments"]), encoding="utf-8")
    if "json" in targets:
        targets["json"].write_text(
            to_json(result, source, args.model, args.words), encoding="utf-8"
        )

    duration = result["segments"][-1]["end"] if result["segments"] else 0
    print(
        f"done  {source.name}  language={result.get('language')}  "
        f"audio={duration:.0f}s  time={time.time() - started:.0f}s  -> {out_dir}"
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg is required: brew install ffmpeg")

    files = collect_files(args.inputs)
    if not files:
        sys.exit("No audio or video file found.")

    failed = 0
    for source in files:
        try:
            transcribe_file(source, args)
        except Exception as error:  # keep going on a folder with one bad file
            failed += 1
            print(f"FAIL  {source.name}: {error}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
