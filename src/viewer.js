import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

/**
 * Mounts a self-contained Three.js viewer into `container`.
 * `factory` returns an Object3D; if it sets userData.update(t, dt) that runs every frame.
 * Returns { renderer, scene, camera, object, dispose }.
 */
export function mountViewer(container, factory, { exposure = 1, cameraZ = 5.4, interactive = true } = {}) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = exposure;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envRT = pmrem.fromScene(new RoomEnvironment(), 0.04);
  scene.environment = envRT.texture;
  scene.environmentIntensity = 0.65;

  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50);
  camera.position.set(0, 0, cameraZ);

  const key = new THREE.DirectionalLight(0xffffff, 2.4);
  key.position.set(-3, 4, 4);
  const rim = new THREE.DirectionalLight(0xdfe6ff, 1.6);
  rim.position.set(3.5, 2, -3);
  const fill = new THREE.DirectionalLight(0xffffff, 0.4);
  fill.position.set(2, -2, 3);
  scene.add(key, rim, fill);

  const object = factory({ renderer, scene });
  scene.add(object);

  let controls;
  if (interactive) {
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false;
    controls.enableZoom = false;
    controls.enableDamping = true;
    controls.rotateSpeed = 0.6;
  }

  const resize = () => {
    const { clientWidth: w, clientHeight: h } = container;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(container);
  resize();

  const clock = new THREE.Clock();
  renderer.setAnimationLoop(() => {
    const dt = clock.getDelta();
    object.userData.update?.(clock.elapsedTime, dt);
    controls?.update();
    renderer.render(scene, camera);
  });

  return {
    renderer,
    scene,
    camera,
    object,
    dispose() {
      renderer.setAnimationLoop(null);
      ro.disconnect();
      controls?.dispose();
      envRT.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
