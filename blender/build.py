"""Build one or more sphere GLBs headless.

    blender -b --factory-startup -P blender/build.py -- puffer tennis eightball robot
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

names = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
names = names or ["puffer", "tennis", "eightball", "robot"]
for name in names:
    print(f"=== building {name}")
    importlib.import_module(name).build()
