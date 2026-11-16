import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { RGBELoader } from 'three/addons/loaders/RGBELoader.js';

/**
 * One WebGL renderer + one fixed, full-viewport canvas drawing any number of views.
 * Each view is tied to a DOM element and rendered into that element's rectangle with
 * scissoring, so a page with four spheres costs one GL context and skips offscreen views.
 */
export class Stage {
  constructor({ maxPixelRatio = 1.75, exposure = 1 } = {}) {
    this.canvas = document.createElement('canvas');
    Object.assign(this.canvas.style, {
      position: 'fixed',
      inset: '0',
      width: '100%',
      height: '100%',
      pointerEvents: 'none',
      zIndex: '1',
    });
    document.body.appendChild(this.canvas);

    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, maxPixelRatio));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = exposure;
    this.renderer.setScissorTest(true);

    this.pmrem = new THREE.PMREMGenerator(this.renderer);
    this.environment = this.pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

    this.views = [];
    this.clock = new THREE.Clock();
    this.onFrame = null;
    this.visibility = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        const view = this.views.find((v) => v.el === entry.target);
        if (view) view.onScreen = entry.isIntersecting;
      }
    });
    this.renderer.setAnimationLoop(() => this.frame());
  }

  /**
   * Adds a view rendering `object` inside `el`.
   * Options: spin (rad/s), cameraZ, orbit (drag to rotate), lights (bool),
   * toneMapping (THREE constant, per view), envIntensity.
   *
   * Dragging rotates the object, not the camera: lights and environment stay fixed
   * relative to the viewer, so highlights hold still like a product turned in a studio.
   */
  addView(el, object, {
    spin = 0.9, cameraZ = 5.4, fov = 30, orbit = true, lights = true,
    toneMapping = THREE.ACESFilmicToneMapping, envIntensity = 0.7,
  } = {}) {
    const scene = new THREE.Scene();
    scene.environment = this.environment;
    scene.environmentIntensity = envIntensity;
    const viewLights = {};
    if (lights) {
      viewLights.key = new THREE.DirectionalLight(0xffffff, 2.4);
      viewLights.key.position.set(-3, 4, 4);
      viewLights.rim = new THREE.DirectionalLight(0xdfe6ff, 1.8);
      viewLights.rim.position.set(3.5, 2, -3);
      scene.add(viewLights.key, viewLights.rim);
    }
    const camera = new THREE.PerspectiveCamera(fov, 1, 0.1, 100);
    camera.position.set(0, 0, cameraZ);
    const tilt = new THREE.Group(); // drag up/down tips the object toward or away from the viewer
    const turntable = new THREE.Group(); // auto-spin and drag left/right turn around the vertical axis
    if (object) turntable.add(object);
    tilt.add(turntable);
    scene.add(tilt);

    const spinParam = new URLSearchParams(location.search).get('spin');
    if (spinParam !== null) spin *= Number(spinParam);
    const view = { el, scene, camera, tilt, turntable, spin, toneMapping, lights: viewLights, onScreen: true, holdUntil: 0, update: null };
    if (orbit) view.drag = this.attachDrag(view);
    this.views.push(view);
    this.visibility.observe(el);
    return view;
  }

  /** Pointer drag that rotates the object with a little inertia; tilt eases back to level. */
  attachDrag(view) {
    const drag = { active: false, x: 0, y: 0, vx: 0, vy: 0 };
    const el = view.el;
    const speed = 0.009; // radians per pixel
    el.addEventListener('pointerdown', (e) => {
      Object.assign(drag, { active: true, x: e.clientX, y: e.clientY, vx: 0, vy: 0 });
      view.holdUntil = Infinity;
    });
    window.addEventListener('pointermove', (e) => {
      if (!drag.active) return;
      drag.vx = (e.clientX - drag.x) * speed;
      drag.vy = (e.clientY - drag.y) * speed;
      drag.x = e.clientX;
      drag.y = e.clientY;
      view.turntable.rotation.y += drag.vx;
      view.tilt.rotation.x = THREE.MathUtils.clamp(view.tilt.rotation.x + drag.vy, -1.2, 1.2);
    });
    const end = () => {
      if (!drag.active) return;
      drag.active = false;
      view.holdUntil = this.clock.elapsedTime + 1.2;
    };
    window.addEventListener('pointerup', end);
    window.addEventListener('pointercancel', end);
    drag.step = (dt) => {
      if (drag.active) return;
      const decay = Math.exp(-dt * 6);
      drag.vx *= decay;
      drag.vy *= decay;
      view.turntable.rotation.y += drag.vx;
      view.tilt.rotation.x = THREE.MathUtils.clamp(view.tilt.rotation.x + drag.vy, -1.2, 1.2);
      if (this.clock.elapsedTime > view.holdUntil) view.tilt.rotation.x *= Math.exp(-dt * 2);
    };
    return drag;
  }

  /** Loads an equirect .hdr as a prefiltered environment for view.scene.environment. */
  async loadEnvironment(url) {
    const hdr = await new RGBELoader().loadAsync(url);
    hdr.mapping = THREE.EquirectangularReflectionMapping;
    const env = this.pmrem.fromEquirectangular(hdr).texture;
    hdr.dispose();
    return env;
  }

  setObject(view, object) {
    view.turntable.clear();
    if (object) view.turntable.add(object);
  }

  frame() {
    const dt = Math.min(this.clock.getDelta(), 0.1);
    const t = this.clock.elapsedTime;
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    const size = this.renderer.getSize(new THREE.Vector2());
    if (size.x !== w || size.y !== h) this.renderer.setSize(w, h, false);

    this.onFrame?.(t, dt);
    this.renderer.setScissor(0, 0, w, h);
    this.renderer.clear();

    for (const view of this.views) {
      if (!view.onScreen) continue;
      const r = view.el.getBoundingClientRect();
      if (r.bottom < 0 || r.top > h || r.right < 0 || r.left > w || r.width < 2) continue;
      if (t > view.holdUntil) view.turntable.rotation.y += view.spin * dt;
      view.update?.(t, dt);
      for (const child of view.turntable.children) child.userData.update?.(t, dt);
      view.drag?.step(dt);
      view.camera.aspect = r.width / r.height;
      view.camera.updateProjectionMatrix();
      const y = h - r.bottom;
      this.renderer.setViewport(r.left, y, r.width, r.height);
      this.renderer.setScissor(r.left, y, r.width, r.height);
      this.renderer.toneMapping = view.toneMapping;
      this.renderer.render(view.scene, view.camera);
    }
  }
}
