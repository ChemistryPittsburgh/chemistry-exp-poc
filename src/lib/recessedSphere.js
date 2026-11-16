import * as THREE from 'three';

/**
 * Sphere with a flat-bottomed circular recess cut into its +Y pole.
 * Built as a lathe so the recess is real geometry (no clipping planes),
 * which means it survives any rotation/animation applied to the mesh.
 *
 * Rotate the returned geometry (or its mesh) to point the recess anywhere.
 */
export function createRecessedSphereGeometry({
  radius = 1,
  capAngle = 0.45, // polar angle of the opening, in radians
  depth = 0.1, // how far the floor sits below the opening plane
  rimFillet = 0.025,
  floorFillet = 0.02,
  segments = 160,
  rings = 120,
} = {}) {
  const R = radius;
  const y0 = R * Math.cos(capAngle);
  const rho = R * Math.sin(capAngle);
  const floorY = y0 - depth;
  const pts = [];

  // Outer sphere: bottom pole up to just shy of the opening.
  const arcEnd = capAngle + rimFillet / R;
  for (let i = 0; i <= rings; i++) {
    const a = Math.PI - (Math.PI - arcEnd) * (i / rings);
    pts.push(new THREE.Vector2(Math.max(R * Math.sin(a), 1e-5), R * Math.cos(a)));
  }

  // Rounded lip into the vertical wall.
  const rim = new THREE.QuadraticBezierCurve(
    pts[pts.length - 1].clone(),
    new THREE.Vector2(rho, y0),
    new THREE.Vector2(rho, y0 - rimFillet),
  );
  pts.push(...rim.getPoints(10).slice(1));

  // Wall, rounded into the floor, then the floor to the axis.
  const floor = new THREE.QuadraticBezierCurve(
    new THREE.Vector2(rho, floorY + floorFillet),
    new THREE.Vector2(rho, floorY),
    new THREE.Vector2(rho - floorFillet, floorY),
  );
  pts.push(...floor.getPoints(8));
  pts.push(new THREE.Vector2(rho * 0.5, floorY));
  pts.push(new THREE.Vector2(1e-5, floorY));

  const geometry = new THREE.LatheGeometry(pts, segments);
  return { geometry, rho, y0, floorY };
}

/** Quaternion that turns local +Y to point along `dir`. */
export function alignY(dir) {
  return new THREE.Quaternion().setFromUnitVectors(
    new THREE.Vector3(0, 1, 0),
    dir.clone().normalize(),
  );
}
