# Expertise spheres: Three.js proof of concept

Real-time, procedural 3D spheres. They let us compare true 3D with animated GIFs.

| Model | Module |
| --- | --- |
| Puffer ball | `src/spheres/puffer.js` → `createPufferBall()` |
| Tennis smiley | `src/spheres/tennis.js` → `createTennisBall()` |
| Data Ritual 8-ball | `src/spheres/eightBall.js` → `createEightBall({ message })` |
| Robot pod | `src/spheres/robot.js` → `createRobotPod()` |

Each factory returns a `THREE.Group`, with no model files and no textures to load. Every texture is drawn on a canvas at runtime. If the group sets `group.userData.update(t)`, call it every frame to run the idle animation.

## Run locally

The demo needs an HTTP server because ES modules don't load from `file://`:

```sh
npx http-server -p 8765 -c-1
# open http://localhost:8765
```

`index.html` loads three@0.170.0 from jsDelivr through an import map. No build step is needed, so the repo root deploys to GitHub Pages as-is.

## Use in a site

```js
import { mountViewer } from './src/viewer.js';
import { createRobotPod } from './src/spheres/robot.js';

const viewer = mountViewer(document.querySelector('#hero-orb'), createRobotPod);
// viewer.dispose() on unmount
```

In React Three Fiber, use `<primitive object={useMemo(createRobotPod, [])} />` and call `userData.update` inside `useFrame`.
