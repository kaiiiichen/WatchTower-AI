#!/usr/bin/env python3
"""Download a YouTube thumbnail and overlay a centered play button."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw

VIDEO_ID = "IKbsyVAsRDw"
THUMBNAIL_QUALITIES = ("maxresdefault", "sddefault", "hqdefault")
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "assets" / "youtube_preview.jpg"


def download_thumbnail(video_id: str) -> Image.Image:
    """Try thumbnail qualities in order until one returns a valid image."""
    for quality in THUMBNAIL_QUALITIES:
        url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        image = Image.open(io.BytesIO(response.content)).convert("RGBA")
        # YouTube returns a small placeholder when the quality is unavailable.
        if image.size[0] > 120 and image.size[1] > 90:
            print(f"Downloaded thumbnail: {quality} ({image.size[0]}x{image.size[1]})")
            return image

        print(f"Skipping {quality}: placeholder or too small ({image.size[0]}x{image.size[1]})")

    raise RuntimeError(f"Could not download a valid thumbnail for video {video_id}")


def draw_play_button(image: Image.Image) -> Image.Image:
    """Overlay a centered play button on the thumbnail."""
    width, height = image.size
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    diameter = int(min(width, height) * 0.18)
    radius = diameter // 2
    center_x = width // 2
    center_y = height // 2
    bbox = (
        center_x - radius,
        center_y - radius,
        center_x + radius,
        center_y + radius,
    )

    draw.ellipse(bbox, fill=(0, 0, 0, 140), outline=(255, 255, 255, 255), width=4)

    triangle_height = int(diameter * 0.42)
    triangle_width = int(triangle_height * 0.86)
    left = center_x - triangle_width // 2 + int(diameter * 0.06)
    top = center_y - triangle_height // 2
    triangle = [
        (left, top),
        (left, top + triangle_height),
        (left + triangle_width, center_y),
    ]
    draw.polygon(triangle, fill=(255, 255, 255, 255))

    return Image.alpha_composite(image, overlay).convert("RGB")


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    thumbnail = download_thumbnail(VIDEO_ID)
    preview = draw_play_button(thumbnail)
    preview.save(OUTPUT_PATH, format="JPEG", quality=92, optimize=True)

    print(f"Saved preview to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
