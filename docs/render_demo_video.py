"""Render the 30-second BayNumber demo from synthetic UI captures.

Optional tooling is pinned in ``docs/requirements-video.txt``. Run from the repository root with
``python docs/render_demo_video.py`` after capturing the demo screens.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
CAPTURES = ROOT / "video-captures"
OUTPUT = ROOT / "baynumber-demo-30s.mp4"
INTERMEDIATE = CAPTURES / "render-mp4v.mp4"
WIDTH, HEIGHT, FPS = 1280, 720, 24
BG = "#121212"
PANEL = "#1c1c1b"
YELLOW = "#F5C518"
CONCRETE = "#E8E4D9"
MUTED = "#b4b0a6"
RED = "#ff776c"
GREEN = "#a6d4a3"


@dataclass(frozen=True)
class Scene:
    start: int
    end: int
    number: str
    eyebrow: str
    headline: tuple[str, ...]
    body: tuple[str, ...]
    image: str | None
    crop: tuple[int, int, int, int] | None
    accent: str = YELLOW


SCENES = (
    Scene(0, 3, "00", "BAYNUMBER / A 30-SECOND WALKTHROUGH", ("Parking,", "accounted for."),
          ("A society bay ledger built for a busy guard shift.", "Synthetic demo records only."), None, None),
    Scene(3, 7, "01", "THE PUBLIC BOARD", ("Status at", "a glance."),
          ("Large bay labels and clear states.", "Resident details stay behind sign-in."),
          "01-public.png", (50, 790, 840, 1260)),
    Scene(7, 12, "02", "GUARD / LOOKUP", ("Find the", "right bay."),
          ("Search a synthetic plate.", "DEMO1234 belongs to A-04."),
          "03-lookup.png", (50, 560, 840, 1030)),
    Scene(12, 16, "03", "GUARD / ARRIVAL", ("Record IN.", "See occupied."),
          ("One movement changes the live board.", "The event is timestamped in the ledger."),
          "04-arrival.png", (50, 790, 840, 1260), GREEN),
    Scene(16, 21, "04", "GUARD / CONFLICT", ("Second IN?", "Blocked."),
          ("The occupied bay shows a clear conflict.", "No duplicate IN event is recorded."),
          "05-conflict.png", (50, 790, 840, 1260), RED),
    Scene(21, 24, "05", "GUARD / DEPARTURE", ("Record OUT.", "Bay assigned."),
          ("The bay returns to its assigned state.", "Movement history remains intact."),
          "06-departure.png", (50, 790, 840, 1260), YELLOW),
    Scene(24, 27, "06", "SECRETARY / ADMIN", ("Manage.", "Export."),
          ("Create bays and assignments.", "Export movement and assignment audit CSVs."),
          "07-admin.png", (0, 1205, 1116, 1870)),
    Scene(27, 30, "07", "BUILT AND OPEN-SOURCED", ("BayNumber", "is on GitHub."),
          ("Python 3.12 · FastAPI · SQLite", "MIT licensed · Synthetic demo only"), None, None),
)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    filename = "segoeuib.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / filename), size)


def fit_capture(name: str, crop: tuple[int, int, int, int], frame_index: int, frames: int) -> Image.Image:
    source = Image.open(CAPTURES / name).convert("RGB")
    left, top, right, bottom = crop
    # A restrained camera move keeps the recorded interface readable.
    progress = frame_index / max(frames - 1, 1)
    inset = round(progress * 12)
    image = source.crop((left + inset, top + inset // 2, right - inset, bottom - inset // 2))
    return image.resize((760, 452), Image.Resampling.LANCZOS)


def draw_scene(scene: Scene, index: int) -> Image.Image:
    canvas = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, WIDTH, 8), fill=YELLOW)
    draw.rectangle((42, 36, 92, 86), outline=YELLOW, width=3)
    draw.text((52, 45), "B·N", font=font(19, True), fill=YELLOW)
    draw.text((110, 43), "BAYNUMBER", font=font(24, True), fill=CONCRETE)
    draw.text((111, 72), "PARKING LEDGER / SOCIETY EDITION", font=font(11, True), fill=MUTED)
    draw.text((1053, 49), f"{scene.number} / 07", font=font(16, True), fill=YELLOW)
    draw.line((42, 108, 1238, 108), fill="#3c3b37", width=1)

    if scene.image and scene.crop:
        draw.rounded_rectangle((40, 137, 814, 606), radius=12, fill="#070707", outline="#555045", width=2)
        shot = fit_capture(scene.image, scene.crop, index, (scene.end - scene.start) * FPS)
        canvas.paste(shot, (47, 145))
        draw = ImageDraw.Draw(canvas)
        draw.text((52, 619), "LIVE APP / SYNTHETIC DATA", font=font(12, True), fill=MUTED)
        text_x = 856
        top = 156
        headline_size = 45
    else:
        text_x = 76
        top = 184
        headline_size = 78
        draw.rectangle((883, 188, 1193, 498), outline="#5b4b18", width=2)
        draw.rectangle((909, 216, 1167, 472), outline=YELLOW, width=5)
        draw.text((937, 255), "A-04", font=font(75, True), fill=CONCRETE)
        draw.rectangle((941, 381, 1134, 427), outline=scene.accent, width=2)
        draw.text((966, 389), "OCCUPIED" if scene.start == 0 else "OPEN SOURCE",
                  font=font(19, True), fill=scene.accent)

    draw.text((text_x, top), scene.eyebrow, font=font(15, True), fill=scene.accent)
    y = top + 52
    for line in scene.headline:
        draw.text((text_x, y), line, font=font(headline_size, True), fill=CONCRETE if y == top + 52 else scene.accent)
        y += headline_size + 5
    y += 31
    body_size = 20 if scene.image else 23
    for line in scene.body:
        draw.text((text_x, y), line, font=font(body_size), fill=MUTED)
        y += body_size + 16
    if scene.start == 27:
        draw.text((76, 568), "github.com/san342147/baynumber", font=font(26, True), fill=YELLOW)

    draw.line((42, 668, 1238, 668), fill="#3c3b37", width=1)
    draw.text((44, 683), "BAYNUMBER  /  BUILD LOG 01", font=font(11, True), fill=MUTED)
    draw.text((1025, 683), "30 SEC DEMO", font=font(11, True), fill=MUTED)
    return canvas


def main() -> None:
    writer = cv2.VideoWriter(str(INTERMEDIATE), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError("Could not open MP4 writer")
    try:
        for scene in SCENES:
            count = (scene.end - scene.start) * FPS
            for index in range(count):
                frame = draw_scene(scene, index)
                # Brief fade gives each real UI state a clean entrance and exit.
                opacity = min(1.0, (index + 1) / 7, (count - index) / 7)
                if opacity < 1:
                    frame = Image.blend(Image.new("RGB", (WIDTH, HEIGHT), BG), frame, opacity)
                writer.write(cv2.cvtColor(np.asarray(frame), cv2.COLOR_RGB2BGR))
    finally:
        writer.release()
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(INTERMEDIATE), "-an",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(OUTPUT)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    INTERMEDIATE.unlink()
    print(f"Wrote {OUTPUT} ({sum((s.end - s.start) * FPS for s in SCENES)} frames at {FPS} fps)")


if __name__ == "__main__":
    main()
