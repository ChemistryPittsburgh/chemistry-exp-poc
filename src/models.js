import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';

import { SPHERES } from './content.js';

export { SPHERES };

const MODEL_DIR = new URL('../models/', import.meta.url);
const draco = new DRACOLoader().setDecoderPath(
  'https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/libs/draco/gltf/',
);
const loader = new GLTFLoader().setDRACOLoader(draco);
const cache = new Map();

/**
 * Loads a sphere GLB and returns a fresh rig (THREE.Group).
 * rig.userData.update(t, dt) drives idle animation; rig.userData.setGlow(0..1) dims/lights
 * emissive parts so pages can "switch on" a sphere.
 */
export async function loadSphere(id) {
  if (!cache.has(id)) cache.set(id, loader.loadAsync(new URL(`${id}.glb`, MODEL_DIR).href));
  const gltf = await cache.get(id);
  const root = gltf.scene.clone(true);
  root.traverse((o) => {
    if (o.isMesh) o.material = o.material.clone();
  });
  const rig = new THREE.Group();
  rig.name = id;
  rig.add(root);
  const meta = SPHERES.find((s) => s.id === id);
  if (meta?.pose) root.rotation.set(...meta.pose);

  const glowMats = [];
  root.traverse((o) => {
    if (o.isMesh && o.material.emissiveIntensity !== undefined && o.material.emissive.getHex() !== 0) {
      o.material.userData.baseEmissive = o.material.emissiveIntensity;
      glowMats.push(o.material);
    }
  });
  let glow = 1;
  rig.userData.setGlow = (g) => {
    glow = g;
  };
  const applyGlow = (pulse = 1) => {
    for (const m of glowMats) m.emissiveIntensity = m.userData.baseEmissive * glow * pulse;
  };

  // Pages call rig.userData.activate() when a sphere becomes the focus (no-op by default).
  rig.userData.activate = () => {};
  const extra = (RIGS[id] || (() => () => {}))(root, rig);
  rig.userData.update = (t, dt) => {
    applyGlow(1);
    extra(t, dt, applyGlow);
  };
  return rig;
}

export function preloadAll() {
  return Promise.all(SPHERES.map((s) => loadSphere(s.id)));
}

// ---------------------------------------------------------------------------
// Per-model runtime extras
// ---------------------------------------------------------------------------

const RIGS = {
  tennis(root) {
    // Shell fur: stacked, alpha-cut copies of the low-res FurShell mesh.
    const shellMesh = root.getObjectByName('FurShell');
    if (!shellMesh) return () => {};
    shellMesh.visible = false;
    const mask = new THREE.TextureLoader().load(new URL('tennis-fur-mask.webp', MODEL_DIR).href);
    mask.flipY = false;
    mask.colorSpace = THREE.NoColorSpace;
    const noise = strandNoise(128);
    const SHELLS = 10;
    const LENGTH = 0.042;
    for (let i = 1; i <= SHELLS; i++) {
      const f = i / SHELLS;
      const mat = new THREE.MeshStandardMaterial({
        map: shellMesh.material.map,
        roughness: 1,
        color: new THREE.Color().setScalar(0.62 + 0.5 * f),
      });
      const uniforms = {
        uNoise: { value: noise },
        uMask: { value: mask },
        uCut: { value: 0.12 + 0.78 * f },
      };
      mat.onBeforeCompile = (shader) => {
        Object.assign(shader.uniforms, uniforms);
        shader.fragmentShader = shader.fragmentShader
          .replace('void main() {', 'uniform sampler2D uNoise;\nuniform sampler2D uMask;\nuniform float uCut;\nvoid main() {')
          .replace(
            '#include <alphatest_fragment>',
            'if (texture2D(uNoise, vMapUv * vec2(56.0, 28.0)).r * texture2D(uMask, vMapUv).r < uCut) discard;',
          );
      };
      mat.customProgramCacheKey = () => 'tennis-fur';
      const shell = new THREE.Mesh(shellMesh.geometry, mat);
      shell.position.copy(shellMesh.position);
      shell.quaternion.copy(shellMesh.quaternion);
      shell.scale.copy(shellMesh.scale).multiplyScalar(1 + LENGTH * f);
      shellMesh.parent.add(shell);
    }
    return () => {};
  },

  robot(root) {
    const eyes = ['Eye_L', 'Eye_R'].map((n) => root.getObjectByName(n)).filter(Boolean);
    root.updateMatrixWorld(true);
    // Blink along whichever local axis points world-up.
    const axes = eyes.map((eye) => {
      const e = eye.matrixWorld.elements;
      const ys = [Math.abs(e[1]), Math.abs(e[5]), Math.abs(e[9])];
      return ['x', 'y', 'z'][ys.indexOf(Math.max(...ys))];
    });
    const ring = root.getObjectByName('EarRing');
    return (t, dt, applyGlow) => {
      const cycle = t % 3.6;
      const blink = cycle < 0.16 ? Math.abs(Math.cos((cycle / 0.16) * Math.PI)) : 1;
      eyes.forEach((eye, i) => {
        eye.scale[axes[i]] = Math.max(blink, 0.08);
      });
      if (ring) applyGlow(0.75 + 0.25 * Math.sin(t * 2.4));
    };
  },

  eightball(root, rig) {
    // Real 8-ball behaviour: shake, the die sinks into the murk, then floats up,
    // turning as it rises, and settles against the glass.
    const die = root.getObjectByName('Die');
    if (!die) return (t, dt, applyGlow) => applyGlow(1);
    const rest = die.position.clone();
    const normal = rest.clone().normalize();
    const baseQ = die.quaternion.clone();
    const spinQ = new THREE.Quaternion();
    const tiltQ = new THREE.Quaternion();
    const Y = new THREE.Vector3(0, 1, 0); // window axis in the die's local frame
    const X = new THREE.Vector3(1, 0, 0);
    const DEEP = 0.17;
    const SINK = 0.35;
    const RISE = 2.1;
    let now = 0;
    let shakeAt = -10;
    let revealAt = 0.3 - SINK; // first load: start already sunk, rise shortly after
    const easeOut = (x) => 1 - Math.pow(1 - x, 3);

    rig.userData.reveal = () => (revealAt = now);
    rig.userData.activate = () => {
      shakeAt = now;
      revealAt = now + 0.25;
    };

    return (t, dt, applyGlow) => {
      now = t;
      const k = t - revealAt;
      let depth = 0;
      let spin = Math.sin(t * 0.6) * 0.05;
      let tilt = 0;
      let bright = 1;
      if (k < 0) {
        // waiting for a shake to finish: hold where it is
      } else if (k < SINK) {
        const p = k / SINK;
        depth = DEEP * p * p;
        bright = 1 - p;
      } else if (k < SINK + RISE) {
        const p = (k - SINK) / RISE;
        const e = easeOut(p);
        depth = DEEP * (1 - e);
        spin = (1 - e) * 2.4;
        tilt = Math.sin(k * 5) * 0.22 * (1 - e);
        bright = 0.15 + 0.85 * e;
      } else {
        depth = 0.004 * Math.sin(t * 1.3);
      }
      die.position.copy(rest).addScaledVector(normal, -depth);
      spinQ.setFromAxisAngle(Y, spin);
      tiltQ.setFromAxisAngle(X, tilt);
      die.quaternion.copy(baseQ).multiply(spinQ).multiply(tiltQ);

      const s = t - shakeAt;
      root.position.set(0, 0, 0);
      if (s >= 0 && s < 0.45) {
        const amp = 0.06 * (1 - s / 0.45);
        root.position.set(Math.sin(s * 55) * amp, Math.sin(s * 41) * amp * 0.6, 0);
      }
      applyGlow(bright * (0.85 + 0.15 * Math.sin(t * 1.8)));
    };
  },
};

function strandNoise(size) {
  const data = new Uint8Array(size * size * 4);
  for (let i = 0; i < size * size; i++) {
    const v = Math.pow(Math.random(), 0.8) * 255;
    data[i * 4] = data[i * 4 + 1] = data[i * 4 + 2] = v;
    data[i * 4 + 3] = 255;
  }
  const tex = new THREE.DataTexture(data, size, size);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.magFilter = THREE.NearestFilter;
  tex.needsUpdate = true;
  return tex;
}
