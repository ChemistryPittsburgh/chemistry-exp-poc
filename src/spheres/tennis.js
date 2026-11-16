import * as THREE from 'three';

/**
 * Fuzzy tennis ball with a hand-drawn graffiti face.
 * Felt is shell-rendered (stacked alpha-tested shells), so it reads as real fuzz
 * from any angle rather than a painted-on texture.
 */
export function createTennisBall({
  feltColor = '#c6dc2c',
  inkColor = '#2b2b27',
  furLength = 0.045,
  shells = 22,
} = {}) {
  const group = new THREE.Group();
  const W = 2048;
  const H = 1024;
  const PX_PER_RAD = W / (Math.PI * 2);

  // --- Seam curve (exactly on the unit sphere) -------------------------------
  const k = 0.27;
  const c = 2 * Math.sqrt(k * (1 - k));
  const seam = [];
  for (let i = 0; i < 720; i++) {
    const t = (i / 720) * Math.PI * 2;
    const x = (1 - k) * Math.cos(t) + k * Math.cos(3 * t);
    const y = (1 - k) * Math.sin(t) - k * Math.sin(3 * t);
    const z = c * Math.sin(2 * t);
    // Re-orient so the seam swings across the lower face like the reference.
    seam.push(new THREE.Vector3(x, z, y).applyAxisAngle(new THREE.Vector3(1, 0, 0), 0.35));
  }

  // Maps a unit-sphere direction to equirect canvas pixels (SphereGeometry UVs).
  const toCanvas = (p) => {
    const theta = Math.acos(THREE.MathUtils.clamp(p.y, -1, 1));
    let u = Math.atan2(p.z, -p.x) / (Math.PI * 2);
    u = ((u % 1) + 1) % 1;
    return { x: u * W, y: (theta / Math.PI) * H, s: Math.max(Math.sin(theta), 0.05) };
  };

  // --- Felt colour + face ----------------------------------------------------
  const base = document.createElement('canvas');
  base.width = W;
  base.height = H;
  const ctx = base.getContext('2d');
  ctx.fillStyle = feltColor;
  ctx.fillRect(0, 0, W, H);
  for (let i = 0; i < 26000; i++) {
    const l = Math.random();
    ctx.fillStyle = l > 0.5 ? 'rgba(235,250,120,0.18)' : 'rgba(90,110,10,0.16)';
    ctx.fillRect(Math.random() * W, Math.random() * H, 2 + Math.random() * 5, 2 + Math.random() * 5);
  }

  // Face sits at u = 0.25 (the +Z side of the sphere), slightly above the equator.
  const cx = W * 0.25;
  const cy = H * 0.5;
  ctx.fillStyle = inkColor;
  ctx.strokeStyle = inkColor;

  const roughBlob = (x, y, rx, ry, jitter = 0.28) => {
    ctx.beginPath();
    for (let i = 0; i <= 48; i++) {
      const a = (i / 48) * Math.PI * 2;
      const n = 1 + (Math.random() - 0.5) * jitter + 0.18 * Math.sin(a * 5 + x);
      const px = x + Math.cos(a) * rx * n;
      const py = y + Math.sin(a) * ry * n;
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    }
    ctx.closePath();
    ctx.fill();
  };
  // Eyes: drippy vertical streaks built from stacked rough blobs.
  for (const ex of [cx - 105, cx + 70]) {
    for (let j = 0; j < 6; j++) {
      roughBlob(ex + (Math.random() - 0.5) * 20, cy - 200 + j * 32, 26 + Math.random() * 14, 22);
    }
    roughBlob(ex + 18, cy - 175, 22, 16);
    roughBlob(ex - 10, cy - 70, 12, 26);
  }
  // Mouth: a wide wavy grin with curled ends.
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.lineWidth = 38;
  ctx.beginPath();
  ctx.moveTo(cx - 330, cy - 90);
  ctx.bezierCurveTo(cx - 380, cy + 10, cx - 300, cy + 60, cx - 210, cy + 40);
  ctx.bezierCurveTo(cx - 120, cy + 20, cx - 150, cy + 140, cx - 40, cy + 120);
  ctx.bezierCurveTo(cx + 80, cy + 100, cx + 160, cy + 120, cx + 240, cy + 40);
  ctx.bezierCurveTo(cx + 290, cy - 10, cx + 300, cy - 80, cx + 260, cy - 130);
  ctx.stroke();
  // Tongue-ish drip under the grin.
  roughBlob(cx - 70, cy + 175, 30, 55, 0.2);

  const baseTex = new THREE.CanvasTexture(base);
  baseTex.colorSpace = THREE.SRGBColorSpace;
  baseTex.anisotropy = 8;

  // Fur colour = base minus a groove along the seam (no felt grows on the rubber).
  const fur = document.createElement('canvas');
  fur.width = W;
  fur.height = H;
  const fctx = fur.getContext('2d');
  fctx.drawImage(base, 0, 0);
  fctx.globalCompositeOperation = 'destination-out';
  const grooveRad = 0.036 * PX_PER_RAD;
  for (const p of seam) {
    const q = toCanvas(p);
    for (const dx of [-W, 0, W]) {
      fctx.beginPath();
      fctx.ellipse(q.x + dx, q.y, grooveRad / q.s, grooveRad, 0, 0, Math.PI * 2);
      fctx.fill();
    }
  }
  const furTex = new THREE.CanvasTexture(fur);
  furTex.colorSpace = THREE.SRGBColorSpace;
  furTex.anisotropy = 8;

  // Strand noise for the shells.
  const N = 256;
  const noise = document.createElement('canvas');
  noise.width = N;
  noise.height = N;
  const nctx = noise.getContext('2d');
  const img = nctx.createImageData(N, N);
  for (let i = 0; i < N * N; i++) {
    const val = Math.pow(Math.random(), 0.8) * 255;
    img.data[i * 4] = img.data[i * 4 + 1] = img.data[i * 4 + 2] = val;
    img.data[i * 4 + 3] = 255;
  }
  nctx.putImageData(img, 0, 0);
  const noiseTex = new THREE.CanvasTexture(noise);
  noiseTex.wrapS = noiseTex.wrapT = THREE.RepeatWrapping;
  noiseTex.repeat.set(28, 14);

  // --- Meshes ----------------------------------------------------------------
  const sphere = new THREE.SphereGeometry(1, 160, 100);
  const core = new THREE.Mesh(
    sphere,
    new THREE.MeshStandardMaterial({ map: baseTex, roughness: 1, color: new THREE.Color(0.55, 0.55, 0.55) }),
  );
  group.add(core);

  for (let i = 1; i <= shells; i++) {
    const f = i / shells;
    const mat = new THREE.MeshStandardMaterial({
      map: furTex,
      alphaMap: noiseTex,
      alphaTest: 0.15 + 0.75 * f,
      roughness: 1,
      color: new THREE.Color().setScalar(0.6 + 0.55 * f),
    });
    const shell = new THREE.Mesh(sphere, mat);
    shell.scale.setScalar(1 + furLength * f);
    group.add(shell);
  }

  const seamCurve = new THREE.CatmullRomCurve3(seam.map((p) => p.clone().multiplyScalar(1.012)), true);
  group.add(
    new THREE.Mesh(
      new THREE.TubeGeometry(seamCurve, 720, 0.019, 12, true),
      new THREE.MeshStandardMaterial({ color: 0xd8d5b6, roughness: 0.7 }),
    ),
  );

  group.rotation.set(0.1, 0, -0.18);
  group.userData.update = (t) => {
    group.rotation.y = Math.sin(t * 0.5) * 0.5;
    group.rotation.x = 0.1 + Math.sin(t * 0.8) * 0.06;
    group.position.y = Math.abs(Math.sin(t * 1.6)) * 0.05;
  };

  return group;
}
