#!/usr/bin/env python3
"""Extract and verify the MODE1 data track of a single-image PC Engine CD.

The source image is read only. Outputs stay under .local by default. An image
override can inspect a recovered prefix, but every requested sector must exist
and pass its CD EDC. This does not certify the archive or its audio tracks.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"


def frames(time):
    minute, second, frame = map(int, time.split(":"))
    if second >= 60 or frame >= 75:
        raise ValueError(f"Invalid CUE time: {time}")
    return (minute * 60 + second) * 75 + frame


def edc_table():
    table = []
    for value in range(256):
        for _ in range(8):
            value = (value >> 1) ^ (0xD8018001 if value & 1 else 0)
        table.append(value)
    return table


def probe(cue, image, output):
    text = cue.read_text(encoding="utf-8-sig")
    files = re.findall(r'^\s*FILE\s+"([^"]+)"\s+BINARY\s*$', text, re.M | re.I)
    if len(files) != 1:
        raise ValueError("Expected one BINARY image in the CUE")
    if image is None:
        image = cue.parent / files[0]
        if not image.exists():
            matches = [p for p in cue.parent.iterdir() if p.name.lower() == files[0].lower()]
            if len(matches) == 1:
                image = matches[0]
    tracks = []
    for line in text.splitlines():
        match = re.match(r"\s*TRACK\s+(\d+)\s+(\S+)", line, re.I)
        if match:
            tracks.append(dict(number=int(match[1]), mode=match[2].upper(), indexes={}))
        match = re.match(r"\s*INDEX\s+(\d+)\s+(\d+:\d+:\d+)", line, re.I)
        if match and tracks:
            tracks[-1]["indexes"][int(match[1])] = frames(match[2])
    candidates = [(i, t) for i, t in enumerate(tracks) if t["mode"] == "MODE1/2352"]
    if len(candidates) != 1:
        raise ValueError("Expected exactly one MODE1/2352 data track")
    index, track = candidates[0]
    start = track["indexes"][1]
    if index + 1 == len(tracks):
        raise ValueError("A following track is required to establish the data-track end")
    following = tracks[index + 1]["indexes"]
    end = following.get(0, following[1])
    if end <= start or image.stat().st_size < end * 2352:
        raise ValueError("Image does not contain the complete data track")
    table = edc_table()
    data = bytearray()
    with image.open("rb") as source:
        source.seek(start * 2352)
        for sector in range(start, end):
            raw = source.read(2352)
            if raw[:12] != SYNC or raw[15] != 1:
                raise ValueError(f"Sector {sector}: invalid MODE1 header")
            checksum = 0
            for byte in raw[:2064]:
                checksum = (checksum >> 8) ^ table[(checksum ^ byte) & 255]
            if checksum != int.from_bytes(raw[2064:2068], "little"):
                raise ValueError(f"Sector {sector}: EDC mismatch")
            data.extend(raw[16:2064])
    output.mkdir(parents=True, exist_ok=True)
    binary = output / f"track{track['number']:02d}.bin"
    binary.write_bytes(data)
    report = dict(cue=str(cue.resolve()), image=str(image.resolve()),
                  track=track["number"], start_sector=start, end_sector=end,
                  sectors=end-start, data_bytes=len(data), edc_valid=True,
                  sha256=hashlib.sha256(data).hexdigest(),
                  archive_and_audio_verified=False)
    (output / "probe.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cue", type=Path)
    parser.add_argument("--image", type=Path, help="Override the image named by the CUE")
    parser.add_argument("--output", type=Path, default=ROOT / ".local/pce-reference")
    args = parser.parse_args()
    probe(args.cue, args.image, args.output)
