# whisper-transcribe

Transcribe audio and video in Arabic (Moroccan darija) and French, locally on an Apple Silicon Mac, with Whisper large-v3 from Hugging Face ([`mlx-community/whisper-large-v3-mlx`](https://huggingface.co/mlx-community/whisper-large-v3-mlx)) run through `mlx-whisper`.

## Setup

```bash
brew install ffmpeg uv
uv sync
```

The model (about 3 GB) is downloaded to `~/.cache/huggingface` on the first run.

## Usage

```bash
uv run transcribe interview.mp3                 # language detected automatically
uv run transcribe call.m4a -l ar                # force Arabic (darija)
uv run transcribe meeting.mp4 -l fr             # force French; video files work too
uv run transcribe recordings/ -o out/           # every audio/video file in a folder
uv run transcribe a.mp3 -f srt                  # only the subtitles
uv run transcribe a.mp3 --words                 # per-word timestamps in the JSON
uv run transcribe a.mp3 -l ar -p "أونوجور، المحكمة الابتدائية"   # help with names and terms
```

Each input `name.ext` gives three files, next to the input or in `--out`:

| File | Content |
|---|---|
| `name.txt` | transcript, one segment per line |
| `name.srt` | subtitles with timestamps |
| `name.json` | detected language, full text, segments with start/end (and words with `--words`) |

Files whose outputs already exist are skipped; add `--overwrite` to redo them.

## Options

| Option | Default | Meaning |
|---|---|---|
| `-l, --language` | `auto` | `auto`, `ar` or `fr` |
| `-o, --out` | next to the input | output folder |
| `-f, --formats` | `txt,srt,json` | outputs to write |
| `-m, --model` | `mlx-community/whisper-large-v3-mlx` | any MLX Whisper repo on Hugging Face, or a local path |
| `-p, --prompt` | none | short text in the spoken language to guide spelling |
| `--words` | off | per-word timestamps |
| `--overwrite` | off | redo existing outputs |

## Notes

- `auto` picks one language per file from its first 30 seconds. For a darija recording that opens in French (or the reverse), pass `-l ar` or `-l fr`.
- Darija is written in Arabic script. French words spoken inside darija are sometimes written in Arabic letters; proofread names, numbers and legal terms.
- To try another model, for example the faster turbo version: `-m mlx-community/whisper-large-v3-turbo`. Only models converted to MLX format work.
