import * as THREE from 'three';
import { createRecessedSphereGeometry, alignY } from '../lib/recessedSphere.js';

/**
 * Grey robot pod: glossy black visor with ring eyes, glowing side "ear" ring.
 * Eyes blink and the ear ring pulses via group.userData.update(t).
 */
export function createRobotPod({ shellColor = 0x7d746e } = {}) {
  const group = new THREE.Group();
  const robot = new THREE.Group();
  group.add(robot);

  // --- Shell with side recess (+X) -------------------------------------------
  const { geometry, rho, floorY } = createRecessedSphereGeometry({
    capAngle: 0.62,
    depth: 0.06,
    rimFillet: 0.035,
    floorFillet: 0.02,
  });
  const earDir = new THREE.Vector3(1, 0.02, 0.05).normalize();
  const q = alignY(earDir);
  geometry.applyQuaternion(q);

  const shell = new THREE.MeshPhysicalMaterial({
    color: shellColor,
    roughness: 0.48,
    metalness: 0.15,
    clearcoat: 0.35,
    clearcoatRoughness: 0.35,
  });
  robot.add(new THREE.Mesh(geometry, shell));

  // --- Ear: raised disc + glowing ring ----------------------------------------
  const ear = new THREE.Group();
  ear.quaternion.copy(q);
  robot.add(ear);

  const disc = new THREE.Mesh(new THREE.CylinderGeometry(rho * 0.78, rho * 0.8, 0.05, 96), shell);
  disc.position.y = floorY + 0.025;
  ear.add(disc);

  const ringMat = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    emissive: 0xd6f1ff,
    emissiveIntensity: 2,
    roughness: 0.3,
  });
  const ring = new THREE.Mesh(new THREE.TorusGeometry(rho * 0.86, 0.016, 16, 160).rotateX(Math.PI / 2), ringMat);
  ring.position.y = floorY + 0.02;
  ear.add(ring);

  const earGlow = new THREE.PointLight(0xbfe6ff, 0.25, 0, 2);
  earGlow.position.y = floorY + 0.1;
  ear.add(earGlow);

  // --- Visor: rounded-rect patch of a slightly larger sphere -------------------
  const mask = document.createElement('canvas');
  mask.width = mask.height = 512;
  const mctx = mask.getContext('2d');
  mctx.fillStyle = '#000';
  mctx.fillRect(0, 0, 512, 512);
  mctx.fillStyle = '#fff';
  mctx.beginPath();
  mctx.roundRect(6, 6, 500, 500, [150, 150, 190, 190]);
  mctx.fill();
  const maskTex = new THREE.CanvasTexture(mask);

  const visorW = 1.6; // radians of longitude
  const visorH = 1.1; // radians of latitude
  const visorLift = 0.05; // centre slightly above the equator
  const patch = (r, grow) =>
    new THREE.SphereGeometry(
      r,
      128,
      96,
      Math.PI / 2 - (visorW + grow) / 2,
      visorW + grow,
      Math.PI / 2 - (visorH + grow) / 2 - visorLift,
      visorH + grow,
    );

  const gasket = new THREE.Mesh(
    patch(1.01, 0.045),
    new THREE.MeshStandardMaterial({ color: 0x1e1c1b, roughness: 0.55, alphaMap: maskTex, alphaTest: 0.5, alphaToCoverage: true }),
  );
  const visor = new THREE.Mesh(
    patch(1.022, 0),
    new THREE.MeshPhysicalMaterial({
      color: 0x030303,
      roughness: 0.07,
      metalness: 0,
      clearcoat: 1,
      clearcoatRoughness: 0.02,
      alphaMap: maskTex,
      alphaTest: 0.5,
      alphaToCoverage: true,
      side: THREE.DoubleSide,
    }),
  );
  robot.add(gasket, visor);

  // --- Eyes --------------------------------------------------------------------
  const eyeMat = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    emissive: 0xe4f4ff,
    emissiveIntensity: 3,
  });
  const eyes = [];
  for (const lon of [-0.22, 0.22]) {
    const lat = visorLift - 0.08;
    const dir = new THREE.Vector3(Math.sin(lon) * Math.cos(lat), Math.sin(lat), Math.cos(lon) * Math.cos(lat));
    const pivot = new THREE.Group();
    pivot.position.copy(dir.clone().multiplyScalar(1.026));
    pivot.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), dir);
    const eye = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.011, 12, 64), eyeMat);
    pivot.add(eye);
    robot.add(pivot);
    eyes.push(eye);
  }

  robot.rotation.y = -0.3;

  group.userData.update = (t) => {
    // Blink: quick squash every ~4s.
    const cycle = t % 4;
    const blink = cycle < 0.18 ? Math.abs(Math.cos((cycle / 0.18) * Math.PI)) : 1;
    for (const eye of eyes) eye.scale.y = Math.max(blink, 0.08);
    ringMat.emissiveIntensity = 1.6 + Math.sin(t * 2.2) * 0.7;
    earGlow.intensity = 0.18 + Math.sin(t * 2.2) * 0.08;
    // Curious look-around.
    robot.rotation.y = -0.3 + Math.sin(t * 0.5) * 0.25;
    robot.rotation.x = Math.sin(t * 0.7) * 0.06;
  };

  return group;
}
