import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';

/** Content for each sphere, in the order the Expertise page lists them. */
export const SPHERES = [
  {
    id: 'puffer',
    title: 'Market and consumer research',
    line: 'Real people, real behavior, real insights that drive decisions',
    accent: '#3d4dff',
    pose: [0.05, 0, 0],
  },
  {
    id: 'tennis',
    title: 'Creative and brand innovation',
    line: 'Unignorable stories and ideas that build emotional connection',
    accent: '#c9de2e',
    pose: [0.12, 0.1, -0.12],
  },
  {
    id: 'eightball',
    title: 'Media, performance, and intelligence',
    line: 'How data and insight guide opportunity',
    accent: '#2f55ff',
    pose: [0, 0, 0],
  },
  {
    id: 'robot',
    title: 'Digital experience and engagement',
    line: 'Where vision and innovation create meaningful experiences',
    accent: '#bfe6ff',
    pose: [0.04, -0.55, 0],
  },
];

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

  eightball() {
    return (t, dt, applyGlow) => applyGlow(0.82 + 0.18 * Math.sin(t * 1.8));
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
