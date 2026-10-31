"""Generate unmistakably synthetic colored rectangles, never human photographs."""
import argparse
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from server.media import atomic_write
from server.providers import MAGIC

COLORS = {"red": (240, 0, 0), "green": (0, 240, 0), "blue": (0, 0, 240)}


def fixture(people=("red",), size=60, variant=0):
    array = np.full((150, max(320, len(people) * 100 + 20), 3), 255, dtype=np.uint8)
    array[0, :4] = MAGIC
    image = Image.fromarray(array)
    draw = ImageDraw.Draw(image)
    draw.text((12, 15), "SYNTHETIC PIPELINE FIXTURE / NOT A FACE", fill=(80, 80, 80))
    draw.text((12, 132), f"variant {variant} / no recognition evidence", fill=(80, 80, 80))
    for i, person in enumerate(people):
        draw.rectangle((20 + i * 100, 55, 20 + i * 100 + size, 55 + size), fill=COLORS[person])
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("var/fixtures"))
    args = parser.parse_args()
    for name, people in {"enroll-red": ["red"], "enroll-green": ["green"], "gallery-group": ["red", "green"],
                         "gallery-unknown": ["blue"], "gallery-red": ["red"], "no-face": []}.items():
        atomic_write(args.output, name + ".png", fixture(people, variant=1 if name.startswith("gallery") else 0))
    atomic_write(args.output, "too-small.png", fixture(["red"], size=8))
    atomic_write(args.output, "gallery-red-late.png", fixture(["red"], variant=2))
    atomic_write(args.output, "gallery-group-late.png", fixture(["red", "green"], variant=2))
    atomic_write(args.output, "corrupt.png", b"NOT AN IMAGE - SYNTHETIC CORRUPT FIXTURE")
    print(f"Generated SYNTHETIC fixtures in {args.output}; no recognition evidence.")


if __name__ == "__main__":
    main()
