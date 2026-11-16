# Expertise spheres: Three.js proof of concept

Four expertise spheres are modeled in Blender, exported as Draco-compressed GLBs, and rendered in real time with Three.js. The goal is to compare true 3D with animated GIFs.

**Pages**

- `index.html`: gallery of all four spheres, with the original design render as a corner thumbnail.
- `mockups/sticky.html` (option A): the Expertise list scrolls past a sticky 3D stage. Each sphere spins out and the next one spins in.
- `mockups/orbit.html` (option B): a pinned section with the four spheres on a 3D ring. Scrolling turns the ring, the front sphere lights up and spins fastest, and the back ones fade into fog.
- `mockups/spotlight.html` (option C): each sphere rises out of darkness, then a spotlight snaps on, its glowing parts ignite and the title fills in.

- `realism.html`: before/after of a realism pass on the puffer only: photographed studio lighting (CC0 HDRI from Poly Haven, walls darkened to leave the softboxes), AgX tone mapping, a 4K normal map with crinkled nylon, seam wrinkles and stitching, a roughness map, uneven down fill, and garment details (pull tab, storm flaps, hem binding, chest patch).
- `sprites.html`: the no-WebGL alternative. Path-traced Cycles turntables play back as WebP sprite sheets. Toggle 24, 36 or 72 frames, crossfade or hard cut, and autoplay, drag, scroll or animated WebP.

Switch between pages with the floating pill at the bottom of each page, or press `[` and `]`.

## Sprite sheets

```sh
blender -b --factory-startup -P blender/render_sprites.py -- 72 480   # frames, px
python tools/pack_sprites.py 400                                      # sheets + animated WebP
```

`render_sprites.py` imports each GLB, adds real particle hair to the tennis ball, and renders a 72-frame turntable with a transparent background. `pack_sprites.py` builds 12-column sheets at 72, 36 and 24 frames (`sprites/<id>-<N>.webp`), a 36-frame animated WebP, and `sprites/manifest.json`. `src/sprite.js` plays a sheet with two stacked background layers, crossfading toward the next frame to hide steps at low frame counts.

## Models

| Sphere | GLB | Triangles | Notes |
| --- | --- | --- | --- |
| Puffer | `models/puffer.glb` (~310 KB) | 63k | Stitching, wrinkles and pocket welts baked from a 300k-face sculpt into normal and AO maps. Zipper teeth are real geometry. |
| Tennis | `models/tennis.glb` + `tennis-fur-mask.webp` (~390 KB) | 38k + fur | Painted felt and face texture. The fuzz is ten runtime alpha-cut shells over a 4k-triangle mesh. |
| 8-ball | `models/eightball.glb` (~150 KB) | 33k | Recessed window, glowing die and real text geometry. Uses alpha glass instead of a transmission pass. |
| Robot | `models/robot.glb` (~140 KB) | 46k | Solid visor and gasket. Eyes blink and the ear ring pulses at runtime. |
| Puffer v2 | `models/puffer-v2.glb` (~950 KB) | 87k | Realism pass, built by `blender/puffer_v2.py`. Detail maps are computed with numpy instead of baked. Lit by `env/studio-dark.hdr` on `realism.html`. |

Rebuild the models with Blender 5.2 or later. Cycles bakes on CUDA when it's available:

```sh
blender -b --factory-startup -P blender/build.py -- puffer tennis eightball robot
```

## Performance

- **One renderer per page:** `src/stage.js` uses one WebGL renderer and one fixed canvas, and draws each view into its element's rectangle with scissoring. Views that are off screen are skipped.
- **Cheap materials:** no shadows and no transmission. Lighting is a prefiltered environment plus two directional lights, and the pixel ratio is capped at 1.75.
- **Small models:** meshes are Draco-compressed and textures are WebP.
- **Inspection:** add `?spin=0` to any page to freeze the turntables.

## Run locally

The pages need an HTTP server because ES modules don't load from `file://`:

```sh
npx http-server -p 8765 -c-1
```

There's no build step, so the repo root deploys to GitHub Pages as-is.
