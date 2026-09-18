"""Create WebP copies of large referenced images and update source references.

Run after adding product images. Originals remain untouched for future editing.
Requires Pillow: ``python -m pip install Pillow``.
"""
from pathlib import Path
import re

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
SOURCE_DIRS = ("assets", "config", "content", "data", "themes")
SOURCE_SUFFIXES = {".css", ".html", ".md", ".toml", ".yaml", ".yml"}
IMAGE_PATTERN = re.compile(rb"images/[A-Za-z0-9_./-]+\.(?:png|jpe?g)", re.IGNORECASE)
MIN_BYTES = 400_000


def source_files():
    for directory in SOURCE_DIRS:
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
                yield path


def save_webp(source: Path, destination: Path, max_side: int):
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "transparency" in image.info else "RGB")
        if max(image.size) > max_side:
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(
            destination,
            "WEBP",
            quality=88,
            method=6,
            icc_profile=image.info.get("icc_profile"),
        )


def main():
    files = list(source_files())
    replacements = {}
    for path in files:
        for match in IMAGE_PATTERN.findall(path.read_bytes()):
            relative = match.decode("ascii")
            source = STATIC / relative
            if source.exists() and source.stat().st_size >= MIN_BYTES:
                optimized = source.with_suffix(".webp")
                max_side = 900 if relative.startswith("images/cards/") else 1920
                save_webp(source, optimized, max_side)
                replacements[match] = optimized.relative_to(STATIC).as_posix().encode("ascii")

    for path in files:
        content = path.read_bytes()
        updated = content
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != content:
            path.write_bytes(updated)

    before = sum((STATIC / old.decode("ascii")).stat().st_size for old in replacements)
    after = sum((STATIC / new.decode("ascii")).stat().st_size for new in replacements.values())
    reduction = 100 * (before - after) / before if before else 0
    print(
        f"Optimized {len(replacements)} images: "
        f"{before / 1_048_576:.1f} MB -> {after / 1_048_576:.1f} MB "
        f"({reduction:.1f}% smaller)."
    )


if __name__ == "__main__":
    main()
