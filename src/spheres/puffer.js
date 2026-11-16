import * as THREE from 'three';
import { mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';

/**
 * Blue puffer-jacket ball: quilted horizontal baffles, front zipper, stand collar.
 * Returns a THREE.Group; call group.userData.update(t) each frame for idle motion.
 */
export function createPufferBall({ color = 0x1f2cc4 } = {}) {
  const group = new THREE.Group();

  const THETA_TOP = 0.2 * Math.PI; // where the collar meets the body
  const THETA_BOTTOM = 0.97 * Math.PI;
  const BANDS = 8;
  const BAND_H = (THETA_BOTTOM - THETA_TOP) / BANDS;
  const PANELS = 4; // vertical seams: front (zipper), sides, back
  const FRONT = Math.PI / 2; // SphereGeometry phi that faces +Z

  // Radius of the quilted surface at a given polar (theta) / azimuth (phi) angle.
  function radiusAt(theta, phi) {
    const t = (theta - THETA_TOP) / BAND_H;
    const local = t - Math.floor(t);
    const band = t < 0 ? 0 : Math.pow(Math.sin(Math.PI * local), 0.55);

    const s = ((((phi - FRONT) / (Math.PI * 2)) * PANELS) % 1 + 1) % 1;
    const panel = Math.pow(Math.sin(Math.PI * s), 0.3);

    const puff = band * (0.45 + 0.55 * panel);
    // Fabric gathers into small wrinkles where it's stitched down.
    const pinch = Math.pow(1 - band, 2);
    const wrinkle = 0.006 * pinch * Math.sin(phi * 64 + theta * 9);
    return 0.94 + 0.06 * puff + wrinkle;
  }

  // --- Body -----------------------------------------------------------------
  let body = new THREE.SphereGeometry(1, 320, 220);
  const pos = body.attributes.position;
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).normalize();
    const theta = Math.acos(THREE.MathUtils.clamp(v.y, -1, 1));
    const phi = Math.atan2(v.z, -v.x);
    v.multiplyScalar(radiusAt(theta, phi));
    pos.setXYZ(i, v.x, v.y, v.z);
  }
  body.deleteAttribute('normal');
  body.deleteAttribute('uv');
  body = mergeVertices(body);
  body.computeVertexNormals();

  const nylon = new THREE.MeshPhysicalMaterial({
    color,
    roughness: 0.3,
    metalness: 0,
    clearcoat: 1,
    clearcoatRoughness: 0.18,
    sheen: 0.35,
    sheenRoughness: 0.4,
    sheenColor: new THREE.Color(0x8a9bff),
  });
  group.add(new THREE.Mesh(body, nylon));

  // --- Collar ---------------------------------------------------------------
  const collarProfile = new THREE.SplineCurve([
    new THREE.Vector2(0.38, 0.74),
    new THREE.Vector2(0.37, 0.9),
    new THREE.Vector2(0.39, 0.98),
    new THREE.Vector2(0.44, 1.0),
    new THREE.Vector2(0.49, 0.95),
    new THREE.Vector2(0.54, 0.8),
    new THREE.Vector2(0.55, 0.72),
  ]).getPoints(80);
  const collar = new THREE.Mesh(new THREE.LatheGeometry(collarProfile, 160), nylon);
  group.add(collar);

  const neckHole = new THREE.Mesh(
    new THREE.CircleGeometry(0.4, 64).rotateX(-Math.PI / 2),
    new THREE.MeshStandardMaterial({ color: 0x05061a, roughness: 1 }),
  );
  neckHole.position.y = 0.86;
  group.add(neckHole);

  // --- Zipper ---------------------------------------------------------------
  const zipPts = [];
  // Up the collar's outer face (lathe phi=0 faces +Z).
  const outer = collarProfile.filter((p) => p.y > 0.76 && p.x > 0.44);
  outer.sort((a, b) => b.y - a.y);
  for (const p of outer) zipPts.push(new THREE.Vector3(0, p.y, p.x + 0.012));
  // Down the front seam of the body.
  for (let i = 0; i <= 200; i++) {
    const theta = THETA_TOP + 0.04 + (THETA_BOTTOM - 0.06 - THETA_TOP) * (i / 200);
    const r = radiusAt(theta, FRONT) + 0.012;
    zipPts.push(new THREE.Vector3(0, r * Math.cos(theta), r * Math.sin(theta)));
  }
  const zipCurve = new THREE.CatmullRomCurve3(zipPts);

  const teeth = document.createElement('canvas');
  teeth.width = 64;
  teeth.height = 8;
  const tctx = teeth.getContext('2d');
  tctx.fillStyle = '#000';
  tctx.fillRect(0, 0, 64, 8);
  tctx.fillStyle = '#fff';
  tctx.fillRect(8, 0, 28, 8);
  const teethTex = new THREE.CanvasTexture(teeth);
  teethTex.wrapS = THREE.RepeatWrapping;
  teethTex.repeat.set(220, 1);

  const zipMat = new THREE.MeshStandardMaterial({
    color: 0x0c0c0e,
    roughness: 0.35,
    metalness: 0.6,
    bumpMap: teethTex,
    bumpScale: 2,
  });
  group.add(new THREE.Mesh(new THREE.TubeGeometry(zipCurve, 400, 0.016, 10, false), zipMat));

  // Slider + pull tab near the top of the collar.
  const pullMat = new THREE.MeshStandardMaterial({ color: 0x111114, roughness: 0.25, metalness: 0.85 });
  const slider = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.07, 0.035), pullMat);
  slider.position.set(0, 0.93, 0.505);
  slider.rotation.x = -0.25;
  const tab = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.12, 0.012), pullMat);
  tab.position.set(0, 0.86, 0.54);
  tab.rotation.x = -0.15;
  group.add(slider, tab);

  group.userData.update = (t) => {
    const breathe = 1 + Math.sin(t * 1.4) * 0.008;
    group.scale.setScalar(breathe);
    group.rotation.y = Math.sin(t * 0.35) * 0.35;
    group.position.y = Math.sin(t * 0.9) * 0.03;
  };

  return group;
}
