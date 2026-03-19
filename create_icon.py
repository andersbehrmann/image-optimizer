#!/usr/bin/env python3
"""
Skapa en `.icns` från `appicon.png`.

Detta gör att PyInstaller kan använda `icon.icns` i `Image Optimizer.spec`,
och att ikonen matchar den nya grafiska profilen i repo:t.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PIL import Image


def _crop_to_square(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    input_png = repo_root / "appicon.png"
    iconset_dir = repo_root / "icon.iconset"
    output_icns = repo_root / "icon.icns"

    if not input_png.exists():
        raise SystemExit(f"Saknar {input_png}")

    img = Image.open(input_png).convert("RGBA")
    img = _crop_to_square(img)
    base = img.resize((1024, 1024), Image.LANCZOS)

    if iconset_dir.exists():
        shutil.rmtree(iconset_dir)
    iconset_dir.mkdir(parents=True, exist_ok=True)

    sizes = [16, 32, 128, 256, 512, 1024]
    for s in sizes:
        resized = base.resize((s, s), Image.LANCZOS)
        resized.save(iconset_dir / f"icon_{s}x{s}.png")
        # Retina-versioner för 16/32/128/256/512 (inte 1024).
        if s < 1024:
            resized2x = base.resize((s * 2, s * 2), Image.LANCZOS)
            resized2x.save(iconset_dir / f"icon_{s}x{s}@2x.png")

    if output_icns.exists():
        output_icns.unlink()

    # iconutil finns på macOS.
    subprocess.check_call(["iconutil", "-c", "icns", str(iconset_dir)])
    print(f"Ikon byggd: {output_icns}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
