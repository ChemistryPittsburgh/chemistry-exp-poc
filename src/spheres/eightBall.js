import * as THREE from 'three';
import { DecalGeometry } from 'three/addons/geometries/DecalGeometry.js';
import { createRecessedSphereGeometry, alignY } from '../lib/recessedSphere.js';

/**
 * Magic 8-ball with a real recessed glass window and a floating answer die.
 * `message` lines are drawn on the die; change them freely.
 */
export function createEightBall({ message = ['Data', 'Ritual', 'Complete'] } = {}) {
  const group = new THREE.Group();
  const windowDir = new THREE.Vector3(0.42, 0.42, 0.8).normalize();
  const eightDir = new THREE.Vector3(-0.8, -0.38, 0.46).normalize();

  // --- Body with window recess -----------------------------------------------
  const { geometry, rho, y0, floorY } = createRecessedSphereGeometry({
    capAngle: 0.5,
    depth: 0.16,
    rimFillet: 0.03,
  });
  const q = alignY(windowDir);
  geometry.applyQuaternion(q);

  const lacquer = new THREE.MeshPhysicalMaterial({
    color: 0x060606,
    roughness: 0.2,
    metalness: 0,
    clearcoat: 1,
    clearcoatRoughness: 0.04,
  });
  const body = new THREE.Mesh(geometry, lacquer);
  group.add(body);

  // --- "8" decal --------------------------------------------------------------
  const label = document.createElement('canvas');
  label.width = label.height = 512;
  const lctx = label.getContext('2d');
  lctx.fillStyle = '#efede6';
  lctx.beginPath();
  lctx.arc(256, 256, 248, 0, Math.PI * 2);
  lctx.fill();
  lctx.fillStyle = '#0a0a0a';
  lctx.font = 'bold 340px Helvetica, Arial, sans-serif';
  lctx.textAlign = 'center';
  lctx.textBaseline = 'middle';
  lctx.fillText('8', 256, 274);
  const labelTex = new THREE.CanvasTexture(label);
  labelTex.colorSpace = THREE.SRGBColorSpace;
  labelTex.anisotropy = 8;

  const projector = new THREE.Object3D();
  projector.position.copy(eightDir);
  projector.lookAt(eightDir.clone().multiplyScalar(2));
  projector.rotateZ(-0.5);
  body.updateMatrixWorld(true);
  const decal = new THREE.Mesh(
    new DecalGeometry(body, projector.position, projector.rotation, new THREE.Vector3(0.78, 0.78, 0.6)),
    new THREE.MeshPhysicalMaterial({
      map: labelTex,
      transparent: true,
      depthWrite: false,
      polygonOffset: true,
      polygonOffsetFactor: -4,
      roughness: 0.2,
      clearcoat: 1,
      clearcoatRoughness: 0.05,
    }),
  );
  group.add(decal);

  // --- Window internals (built along +Y, then aligned) -------------------------
  const win = new THREE.Group();
  win.quaternion.copy(q);
  group.add(win);

  const liquid = new THREE.Mesh(
    new THREE.CircleGeometry(rho * 0.97, 64).rotateX(-Math.PI / 2),
    new THREE.MeshStandardMaterial({ color: 0x010208, emissive: 0x06103f, emissiveIntensity: 0.6, roughness: 0.5, envMapIntensity: 0.1 }),
  );
  liquid.position.y = floorY + 0.003;
  win.add(liquid);

  // Answer die: an extruded down-pointing triangle with text on its face.
  const side = 0.5;
  const h = (side * Math.sqrt(3)) / 2;
  const tri = new THREE.Shape();
  tri.moveTo(-side / 2, h / 3);
  tri.lineTo(side / 2, h / 3);
  tri.lineTo(0, (-2 * h) / 3);
  tri.closePath();
  const dieGeo = new THREE.ExtrudeGeometry(tri, {
    depth: 0.03,
    bevelEnabled: true,
    bevelThickness: 0.012,
    bevelSize: 0.02,
    bevelSegments: 3,
  }).rotateX(-Math.PI / 2);
  const die = new THREE.Group();
  die.add(
    new THREE.Mesh(
      dieGeo,
      new THREE.MeshPhysicalMaterial({
        color: 0x0a1a8a,
        emissive: 0x1e3cff,
        emissiveIntensity: 0.55,
        roughness: 0.6,
        envMapIntensity: 0.15,
      }),
    ),
  );

  const text = document.createElement('canvas');
  text.width = text.height = 512;
  const tctx = text.getContext('2d');
  tctx.textAlign = 'center';
  tctx.textBaseline = 'middle';
  tctx.font = '700 84px Helvetica, Arial, sans-serif';
  tctx.shadowColor = 'rgba(120,170,255,0.9)';
  tctx.shadowBlur = 18;
  tctx.fillStyle = '#dce8ff';
  const lineH = 86;
  message.forEach((line, i) => {
    tctx.fillText(line, 256, 256 + (i - (message.length - 1) / 2) * lineH);
  });
  const textTex = new THREE.CanvasTexture(text);
  textTex.colorSpace = THREE.SRGBColorSpace;
  const textMat = new THREE.MeshBasicMaterial({ map: textTex, alphaTest: 0.25, toneMapped: false });
  const textPlane = new THREE.Mesh(new THREE.PlaneGeometry(0.36, 0.36).rotateX(-Math.PI / 2), textMat);
  textPlane.position.set(0, 0.047, -0.03);
  die.add(textPlane);
  die.position.y = floorY + 0.025;
  win.add(die);

  const glow = new THREE.PointLight(0x2f55ff, 0.6, 0, 2);
  glow.position.y = floorY + 0.12;
  win.add(glow);

  // Bezel ring + glass lens flush with the sphere.
  const bezel = new THREE.Mesh(
    new THREE.TorusGeometry(rho, 0.014, 16, 160).rotateX(Math.PI / 2),
    new THREE.MeshStandardMaterial({ color: 0x1a1a1c, metalness: 0.85, roughness: 0.22 }),
  );
  bezel.position.y = y0 - 0.006;
  win.add(bezel);

  const lens = new THREE.Mesh(
    new THREE.SphereGeometry(1.001, 96, 24, 0, Math.PI * 2, 0, Math.asin(rho)),
    new THREE.MeshPhysicalMaterial({
      color: 0xffffff,
      roughness: 0.02,
      metalness: 0,
      transmission: 1,
      thickness: 0.06,
      ior: 1.45,
      envMapIntensity: 0.5,
    }),
  );
  win.add(lens);

  group.userData.update = (t) => {
    die.rotation.y = Math.sin(t * 0.6) * 0.12;
    die.position.y = floorY + 0.025 + Math.sin(t * 1.3) * 0.008;
    textMat.color.setScalar(0.8 + 0.2 * Math.sin(t * 2));
    group.rotation.y = Math.sin(t * 0.3) * 0.3;
    group.rotation.x = Math.sin(t * 0.45) * 0.08;
  };

  return group;
}
