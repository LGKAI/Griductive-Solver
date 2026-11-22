"""Công cụ thêm hoặc thay thế ảnh chân dung cầu thủ cho chủ đề hiển thị (macOS sips).

Cách dùng:
    python tools/add_portrait.py football Messi ~/Downloads/messi.jpg --source https://...
    python tools/add_portrait.py football "Van Dijk" vvd.jpg --center 0.5 0.25 --size 0.6

Ảnh được cắt vuông quanh tâm mặt, thu gọn về 320x320 và lưu tại web/portraits/<theme>/<slug>.jpg,
đồng thời ghi bổ sung nguồn bản quyền vào web/portraits/CREDITS.md.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from griductive import themes  # noqa: E402

ROSTERS = {"football": [row[0] for row in themes._FOOTBALLERS]}


def image_size(path: Path) -> tuple[int, int]:
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
                         capture_output=True, text=True, check=True).stdout
    values = [int(line.split(":")[1]) for line in out.splitlines() if "pixel" in line]
    return values[0], values[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("theme", choices=sorted(ROSTERS))
    ap.add_argument("name", help="player name exactly as in themes.py, e.g. Messi or 'Van Dijk'")
    ap.add_argument("image", type=Path)
    ap.add_argument("--center", nargs=2, type=float, default=(0.5, 0.3), metavar=("X", "Y"))
    ap.add_argument("--size", type=float, default=1.0)
    ap.add_argument("--source", default="", help="page or file URL the image came from (for CREDITS.md)")
    ap.add_argument("--credit", default="", help="author / licence note (for CREDITS.md)")
    args = ap.parse_args(argv)

    if args.name not in ROSTERS[args.theme]:
        print(f"Unknown {args.theme} character {args.name!r}. Known: {', '.join(ROSTERS[args.theme])}")
        return 2
    if shutil.which("sips") is None:
        print("This tool needs macOS `sips`. Elsewhere, crop the image to a square yourself and save it as "
              f"web/portraits/{args.theme}/{themes.portrait_slug(args.name)}.jpg")
        return 2
    if not args.image.is_file():
        print(f"No such file: {args.image}")
        return 2

    width, height = image_size(args.image)
    side = max(16, int(min(width, height) * min(max(args.size, 0.05), 1.0)))
    cx, cy = args.center[0] * width, args.center[1] * height
    left = int(min(max(cx - side / 2, 0), width - side))
    top = int(min(max(cy - side / 2, 0), height - side))

    dest = themes.PORTRAIT_DIR / args.theme / f"{themes.portrait_slug(args.name)}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work.png"
        subprocess.run(["sips", "-s", "format", "png", str(args.image), "--out", str(work)],
                       capture_output=True, check=True)
        subprocess.run(["sips", "--cropToHeightWidth", str(side), str(side), "--cropOffset", str(top), str(left),
                        str(work), "--out", str(work)], capture_output=True, check=True)
        subprocess.run(["sips", "-z", "320", "320", "-s", "format", "jpeg", "-s", "formatOptions", "86",
                        str(work), "--out", str(dest)], capture_output=True, check=True)

    credits = themes.PORTRAIT_DIR / "CREDITS.md"
    with credits.open("a", encoding="utf-8") as fh:
        fh.write(f"| {args.name} ({args.theme}, added) | {args.source or 'source not recorded'} | {args.credit} |\n")
    print(f"Saved {dest.relative_to(ROOT)} ({side}x{side} crop at x={left}, y={top}). Restart main.py to use it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
