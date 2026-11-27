"""MCP server (stdio) exposing the Whisper transcription as a tool."""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer

from .cli import DEFAULT_MODEL, to_json, to_srt

mcp = MCPServer("whisper-transcribe")

# Apps launched outside a terminal often lack Homebrew in PATH; ffmpeg lives there.
if shutil.which("ffmpeg") is None:
    os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")


@mcp.tool()
def transcribe(
    path: str,
    language: Literal["auto", "ar", "fr"] = "auto",
    prompt: str | None = None,
    timestamps: bool = False,
    save_formats: list[Literal["txt", "srt", "json"]] | None = None,
    out_dir: str | None = None,
) -> dict:
    """Transcribe an audio or video file in Arabic (Moroccan darija) or French
    with Whisper large-v3, locally.

    Args:
        path: absolute path of the audio or video file.
        language: "ar", "fr", or "auto" to detect it from the first 30 seconds.
        prompt: short text in the spoken language to guide spelling of names and terms.
        timestamps: also return the segments with start and end times in seconds.
        save_formats: files to write (txt, srt, json); nothing is written when omitted.
        out_dir: folder for the saved files (default: next to the input file).

    Returns the detected language, the audio duration in seconds, the full text,
    and the paths of any saved files.
    """
    source = Path(path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"No such file: {source}")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required: brew install ffmpeg")

    import mlx_whisper

    # stdout carries the MCP protocol: keep any library output away from it.
    with contextlib.redirect_stdout(sys.stderr):
        result = mlx_whisper.transcribe(
            str(source),
            path_or_hf_repo=os.environ.get("WHISPER_MODEL", DEFAULT_MODEL),
            language=None if language == "auto" else language,
            initial_prompt=prompt,
            condition_on_previous_text=False,
            verbose=None,
        )

    segments = result["segments"]
    lines = [s["text"].strip() for s in segments if s["text"].strip()]
    output: dict = {
        "language": result.get("language"),
        "duration": round(segments[-1]["end"], 1) if segments else 0,
        "text": "\n".join(lines),
    }
    if timestamps:
        output["segments"] = [
            {"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()}
            for s in segments
            if s["text"].strip()
        ]

    if save_formats:
        folder = Path(out_dir).expanduser() if out_dir else source.parent
        folder.mkdir(parents=True, exist_ok=True)
        contents = {
            "txt": lambda: "\n".join(lines) + "\n",
            "srt": lambda: to_srt(segments),
            "json": lambda: to_json(result, source, os.environ.get("WHISPER_MODEL", DEFAULT_MODEL), False),
        }
        output["files"] = []
        for fmt in dict.fromkeys(save_formats):
            target = folder / f"{source.stem}.{fmt}"
            target.write_text(contents[fmt](), encoding="utf-8")
            output["files"].append(str(target))
    return output


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
