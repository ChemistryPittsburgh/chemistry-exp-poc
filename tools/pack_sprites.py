"""Pack Blender turntable frames into WebP sprite sheets + animated WebPs.

    python tools/pack_sprites.py [frame_px] [ids...]

Reads blender/_renders/<id>/0000.png... (72 frames) and writes:
  sprites/<id>-<N>.webp       sheet of N frames (N = 72, 36, 24), 12 columns
  sprites/<id>-anim.webp      animated WebP, 36 frames, loops (no JS needed)
  sprites/manifest.json       frame size, columns, byte sizes
"""

import json
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "blender", "_renders")
OUT = os.path.join(ROOT, "sprites")
IDS = sys.argv[2:] or ["puffer", "tennis", "eightball", "robot"]
COUNTS = [72, 36, 24]
COLS = 12
PX = int(sys.argv[1]) if len(sys.argv) > 1 else 400
QUALITY = 80

os.makedirs(OUT, exist_ok=True)
manifest = {"frame": PX, "cols": COLS, "counts": COUNTS, "spheres": {}}

for sid in IDS:
    names = sorted(f for f in os.listdir(os.path.join(SRC, sid)) if f.endswith(".png"))
    total = len(names)
    frames = [Image.open(os.path.join(SRC, sid, n)).convert("RGBA").resize((PX, PX), Image.LANCZOS) for n in names]
    entry = {"sheets": {}}
    for n in COUNTS:
        step = total // n
        pick = frames[::step][:n]
        rows = -(-n // COLS)
        sheet = Image.new("RGBA", (COLS * PX, rows * PX), (0, 0, 0, 0))
        for i, im in enumerate(pick):
            sheet.paste(im, ((i % COLS) * PX, (i // COLS) * PX))
        path = os.path.join(OUT, f"{sid}-{n}.webp")
        sheet.save(path, "WEBP", quality=QUALITY, method=6, alpha_quality=90)
        entry["sheets"][str(n)] = {"file": f"{sid}-{n}.webp", "rows": rows, "bytes": os.path.getsize(path)}
        print(f"{sid}-{n}: {sheet.size[0]}x{sheet.size[1]} {os.path.getsize(path) // 1024} KB")

    anim = frames[:: total // 36][:36]
    path = os.path.join(OUT, f"{sid}-anim.webp")
    anim[0].save(path, "WEBP", save_all=True, append_images=anim[1:], duration=1000 // 6, loop=0,
                 quality=QUALITY, method=6, alpha_quality=90)
    entry["anim"] = {"file": f"{sid}-anim.webp", "frames": 36, "bytes": os.path.getsize(path)}
    print(f"{sid}-anim: {os.path.getsize(path) // 1024} KB")
    manifest["spheres"][sid] = entry

with open(os.path.join(OUT, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)
print("wrote manifest")
