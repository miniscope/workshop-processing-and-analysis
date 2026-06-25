"""Prepare a raw Miniscope DAQ session for the workshop / Zenodo.

Takes a recording straight off the Miniscope DAQ -- a session folder with
``Behavior/`` and ``Miniscope/`` subdirs, each holding serially numbered AVI
segments (``0.avi``, ``1.avi``, ...), ``timeStamps.csv`` and ``metaData.json`` --
and produces a clean, trimmed, space-efficient copy ready to analyze or upload:

* **Timestamps** trimmed to the first ``--minutes`` of the recording. The cutoff
  is the first frame whose ``Time Stamp (ms)`` reaches ``minutes*60000`` (the
  frame that *hits* the mark is kept), and each device is cut on its own clock.
* **Behavior** video consolidated (all segments -> one file), trimmed to the same
  frame count, and re-encoded grayscale H.264 (``--crf``). ezTrack reads it fine
  and it is ~10x smaller than the source MJPEG.
* **Miniscope** video trimmed losslessly (stream copy) to its frame count and
  left as serial raw AVIs -- the calcium-imaging data is never re-compressed, so
  CNMF-E / Minian see the original pixels. Files past the cutoff are dropped; the
  boundary file is cut to the exact frame.

Output mirrors the DAQ layout so downstream tools (and Zenodo upload) can
treat it like any session::

    <out>/Behavior/behavior.mp4, timeStamps.csv, metaData.json
    <out>/Miniscope/0.avi ... N.avi, timeStamps.csv, metaData.json

Per-device frame count of video == rows in that device's ``timeStamps.csv``, so
frame N aligns 1:1 with row N.

Requires ``ffmpeg``/``ffprobe`` on PATH (see INSTALL.md).

Examples
--------
    python scripts/prepare_session.py /data/CA1_OpenField
    python scripts/prepare_session.py /data/live_rec --minutes 20 --crf 23
    python scripts/prepare_session.py /data/rec --out /data/rec_20min
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    sys.exit(f"ERROR: {msg}")


def numbered_avis(d: Path) -> list[Path]:
    """Serial DAQ segments (``0.avi``, ``1.avi``, ...) in numeric order."""
    files = [p for p in d.glob("*.avi") if re.fullmatch(r"\d+", p.stem)]
    return sorted(files, key=lambda p: int(p.stem))


def _ffprobe_count(path: Path, entry: str, extra: list[str]) -> str:
    return subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0", *extra,
         "-show_entries", entry, "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def nb_frames(path: Path) -> int:
    """Frame count of a video. Falls back to counting packets when the container
    header has no ``nb_frames`` (common for the raw AVIs the DAQ writes)."""
    out = _ffprobe_count(path, "stream=nb_frames", [])
    if not out.isdigit():  # AVI/rawvideo often report N/A — count packets instead
        out = _ffprobe_count(path, "stream=nb_read_packets", ["-count_packets"])
    if not out.isdigit():
        die(f"could not read frame count of {path} (got {out!r})")
    return int(out)


def cutoff_frames(ts_csv: Path, target_ms: float) -> tuple[int, float]:
    """Frames to keep so the recording reaches ``target_ms``.

    Returns (keep_count, last_kept_ms). keep_count is the count of rows up to and
    including the first frame whose timestamp >= target_ms; if the recording
    never reaches target_ms, every row is kept.
    """
    with open(ts_csv, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        try:
            ts_col = next(i for i, h in enumerate(header) if "Time Stamp" in h)
        except StopIteration:
            die(f"{ts_csv}: no 'Time Stamp (ms)' column in header {header}")
        keep, last_ms = 0, 0.0
        for row in reader:
            if not row:
                continue
            keep += 1
            try:
                last_ms = float(row[ts_col])
            except (IndexError, ValueError):
                die(f"{ts_csv}: row {keep} has no readable timestamp in column "
                    f"{ts_col} (got {row[ts_col:ts_col+1] or row!r})")
            if last_ms >= target_ms:
                break
    return keep, last_ms


def trim_timestamps(src: Path, dest: Path, keep: int) -> None:
    with open(src, newline="") as fin, open(dest, "w", newline="") as fout:
        reader, writer = csv.reader(fin), csv.writer(fout)
        writer.writerow(next(reader))  # header
        for i, row in enumerate(reader):
            if i >= keep:
                break
            writer.writerow(row)


def trim_miniscope(src_dir: Path, out_dir: Path, keep: int) -> int:
    """Copy serial AVIs up to ``keep`` frames; stream-copy-trim the boundary file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for seg in numbered_avis(src_dir):
        if written >= keep:
            break
        n = nb_frames(seg)
        dest = out_dir / seg.name
        if written + n <= keep:
            shutil.copy2(seg, dest)
            written += n
        else:  # boundary segment: keep only the frames up to the cutoff
            take = keep - written
            subprocess.run(
                [FFMPEG, "-y", "-loglevel", "error", "-i", str(seg),
                 "-frames:v", str(take), "-c", "copy", str(dest)],
                check=True,
            )
            written += take
    return written


def _concat_quote(p: Path) -> str:
    """A path for ffmpeg's concat list. Its demuxer treats ' as a quote
    delimiter, so a literal apostrophe (e.g. C:/Users/O'Brien/...) becomes '\\''."""
    return p.as_posix().replace("'", "'\\''")


def encode_behavior(src_dir: Path, dest: Path, keep: int, crf: int, gop: int) -> None:
    """Concat serial AVIs, trim to ``keep`` frames, encode grayscale H.264."""
    segs = numbered_avis(src_dir)
    if not segs:
        die(f"no serial .avi segments found in {src_dir}")
    listfile = dest.parent / "_concat.txt"
    listfile.write_text("".join(f"file '{_concat_quote(p)}'\n" for p in segs))
    try:
        subprocess.run(
            [FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(listfile), "-frames:v", str(keep),
             "-vf", "format=gray", "-c:v", "libx264", "-crf", str(crf),
             "-g", str(gop), "-pix_fmt", "gray", str(dest)],
            check=True,
        )
    finally:
        listfile.unlink(missing_ok=True)


def prepare_device(name: str, src: Path, out: Path, target_ms: float) -> tuple[int, float]:
    ts = src / "timeStamps.csv"
    if not ts.is_file():
        die(f"{name}: missing {ts}")
    keep, last_ms = cutoff_frames(ts, target_ms)
    out.mkdir(parents=True, exist_ok=True)
    trim_timestamps(ts, out / "timeStamps.csv", keep)
    meta = src / "metaData.json"
    if meta.is_file():
        shutil.copy2(meta, out / "metaData.json")
    return keep, last_ms


def main(argv=None) -> int:
    if not FFMPEG or not FFPROBE:
        die("ffmpeg/ffprobe not found on PATH (see INSTALL.md).")
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", type=Path, help="raw DAQ session dir (has Behavior/ + Miniscope/)")
    ap.add_argument("--minutes", type=float, default=20.0, help="keep the first N minutes (default 20)")
    ap.add_argument("--crf", type=int, default=23, help="behavior H.264 quality, lower=better (default 23)")
    ap.add_argument("--gop", type=int, default=25, help="behavior keyframe interval (default 25, aids seeking)")
    ap.add_argument("--out", type=Path, help="output dir (default: <session>_<minutes>min next to input)")
    args = ap.parse_args(argv)

    session = args.session.resolve()
    beh_src, ms_src = session / "Behavior", session / "Miniscope"
    if not beh_src.is_dir() or not ms_src.is_dir():
        die(f"{session} must contain Behavior/ and Miniscope/ subdirs")

    out = (args.out or session.parent / f"{session.name}_{args.minutes:g}min").resolve()
    if out.exists() and any(out.iterdir()):
        die(f"output dir {out} exists and is not empty (pass a fresh --out)")
    target_ms = args.minutes * 60_000
    print(f"Preparing {session}\n  -> {out}  (first {args.minutes:g} min, behavior CRF {args.crf})")

    # Miniscope: trim timestamps + losslessly trim raw video.
    ms_keep, ms_ms = prepare_device("Miniscope", ms_src, out / "Miniscope", target_ms)
    written = trim_miniscope(ms_src, out / "Miniscope", ms_keep)
    if written != ms_keep:
        die(f"Miniscope: kept {written} video frames but timestamps want {ms_keep} "
            f"(recording shorter than {args.minutes:g} min?)")
    print(f"  Miniscope: {ms_keep} frames ({ms_ms/1000:.1f}s), raw AVIs trimmed losslessly")

    # Behavior: trim timestamps + consolidate/trim/compress video.
    beh_keep, beh_ms = prepare_device("Behavior", beh_src, out / "Behavior", target_ms)
    encode_behavior(beh_src, out / "Behavior" / "behavior.mp4", beh_keep, args.crf, args.gop)
    eff_fps = beh_keep / (beh_ms / 1000) if beh_ms else float("nan")
    print(f"  Behavior:  {beh_keep} frames ({beh_ms/1000:.1f}s, ~{eff_fps:.1f} fps), "
          f"consolidated -> behavior.mp4 (H.264 CRF {args.crf})")

    print(f"\nDone. Prepared session at {out}\n"
          f"  Next: upload this dir to Zenodo, or point tutorials at it directly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
