#!/usr/bin/env python3
"""Generate Tauri icon assets without extra dependencies."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src-tauri" / "icons"
BLUE = (59, 130, 246)
WHITE = (255, 255, 255)


def png(width: int, height: int, pixels: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b""
    stride = width * 4
    for y in range(height):
        raw += b"\x00" + pixels[y * stride : (y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def draw(size: int) -> bytes:
    pixels = bytearray(size * size * 4)
    radius = size * 0.22
    cx = cy = size / 2
    for y in range(size):
        for x in range(size):
            dx, dy = x + 0.5 - cx, y + 0.5 - cy
            # rounded square
            ax, ay = abs(dx) - (size / 2 - radius), abs(dy) - (size / 2 - radius)
            inside = max(ax, 0) ** 2 + max(ay, 0) ** 2 <= radius ** 2 or (ax <= 0 and ay <= 0)
            i = (y * size + x) * 4
            if inside:
                # simple "cv" bar mark
                bar = abs(dx) < size * 0.08 and abs(dy) < size * 0.28
                cross = abs(dy) < size * 0.08 and dx > -size * 0.18 and dx < size * 0.22
                if bar or cross:
                    pixels[i : i + 4] = bytes((*WHITE, 255))
                else:
                    pixels[i : i + 4] = bytes((*BLUE, 255))
            else:
                pixels[i : i + 4] = b"\x00\x00\x00\x00"
    return png(size, size, bytes(pixels))


def ico(png_bytes: bytes, size: int) -> bytes:
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0, 0, 0, 1, 32, len(png_bytes), 22)
    return header + entry + png_bytes


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    data32 = draw(32)
    data128 = draw(128)
    data256 = draw(256)
    (ROOT / "32x32.png").write_bytes(data32)
    (ROOT / "128x128.png").write_bytes(data128)
    (ROOT / "128x128@2x.png").write_bytes(data256)
    (ROOT / "icon.png").write_bytes(data256)
    (ROOT / "icon.ico").write_bytes(ico(data256, 256))
    iconset = ROOT / "icon.iconset"
    iconset.mkdir(exist_ok=True)
    mapping = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    for name, size in mapping.items():
        (iconset / name).write_bytes(draw(size))
    print(f"wrote icons to {ROOT}")


if __name__ == "__main__":
    main()
