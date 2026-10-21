// Pines (D05): ancient and common pines as two InstancedMeshes (trunks, tiered canopies), scattered on the
// mesa tops and spine ledges away from courts, stairs, bridges and buildings. Rocks (D04) on the rims.
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { BRIDGES, COURTS, ENTRIES, FLIGHTS, type Pt } from './layout';
import type { SectMaterials } from './materials';
import { pointInPolygon, type Peak } from './terrain';
import { rng } from './util';

function pineGeometries() {
  const trunk = new THREE.CylinderGeometry(.35, .7, 9, 6, 3);
  const tp = trunk.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < tp.count; i++) { const y = tp.getY(i); tp.setX(i, tp.getX(i) + Math.sin(y * .45) * .7); }
  trunk.translate(0, 4.5, 0);
  trunk.computeVertexNormals();
  // Huangshan-style flat tiers leaning to one side
  const tiers: THREE.BufferGeometry[] = [];
  for (const [y, r, dx] of [[5.4, 4.4, 1.4], [7.4, 3.6, .4], [9.2, 2.6, -.6], [10.6, 1.6, .2]] as const) {
    const g = new THREE.IcosahedronGeometry(1, 1);
    g.scale(r, r * .32, r * .9);
    g.translate(dx, y, 0);
    tiers.push(g);
  }
  const canopy = mergeGeometries(tiers)!;
  tiers.forEach((g) => g.dispose());
  return { trunk, canopy };
}

export function buildFlora(peaks: Peak[], mats: SectMaterials, quality: number) {
  const r = rng(101);
  const blocked = (x: number, z: number) => {
    for (const c of COURTS) if (Math.abs(x - c.cx) < c.w / 2 + 3 && Math.abs(z - c.cz) < c.d / 2 + 3) return true;
    for (const e of ENTRIES) if (Math.hypot(x - e.x, z - e.z) < 24) return true;
    if (Math.abs(x) < 16 && FLIGHTS.some((f) => z <= f.z0 + 4 && z >= f.z1 - 4)) return true;
    if (Math.abs(x) < 14 && z < 130 && z > -250) return true;                      // the axis road
    for (const b of BRIDGES) {
      const [ax, az] = b.a, [bx, bz] = b.b, dx = bx - ax, dz = bz - az;
      const t = Math.max(0, Math.min(1, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz)));
      if (Math.hypot(x - ax - dx * t, z - az - dz * t) < 10) return true;
    }
    return false;
  };
  const spots: { x: number; y: number; z: number; s: number; rot: number }[] = [];
  const target = quality > 1 ? 760 : quality > 0 ? 520 : 300;
  for (const p of peaks) {
    const xs = p.rim.map((q) => q[0]), zs = p.rim.map((q) => q[1]);
    const [x0, x1, z0, z1] = [Math.min(...xs), Math.max(...xs), Math.min(...zs), Math.max(...zs)];
    const area = (x1 - x0) * (z1 - z0);
    const n = Math.round(target * area / 260000) + 6;
    for (let i = 0; i < n * 3 && i < 900; i++) {
      // bias towards the rim: pick a rim point and pull it inwards a little
      const onRim = r.next() < .55;
      let x: number, z: number;
      if (onRim) {
        const q: Pt = p.rim[Math.floor(r.next() * p.rim.length)];
        const cx = (x0 + x1) / 2, cz = (z0 + z1) / 2, k = .02 + r.next() * .12;
        x = q[0] + (cx - q[0]) * k; z = q[1] + (cz - q[1]) * k;
      } else { x = x0 + r.next() * (x1 - x0); z = z0 + r.next() * (z1 - z0); }
      if (!pointInPolygon(x, z, p.rim) || blocked(x, z)) continue;
      spots.push({ x, y: p.mesa.top, z, s: .42 + r.next() * .5, rot: r.next() * Math.PI * 2 });
      if (spots.length > target) break;
    }
  }
  const { trunk, canopy } = pineGeometries();
  const trunks = new THREE.InstancedMesh(trunk, mats.bark, spots.length);
  const crowns = new THREE.InstancedMesh(canopy, mats.pine, spots.length);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), color = new THREE.Color();
  spots.forEach((s, i) => {
    q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), s.rot);
    m.compose(new THREE.Vector3(s.x, s.y - .3, s.z), q, new THREE.Vector3(s.s, s.s * (.9 + r.next() * .3), s.s));
    trunks.setMatrixAt(i, m);
    crowns.setMatrixAt(i, m);
    color.setHSL(.33 + r.next() * .07, .26 + r.next() * .14, .24 + r.next() * .1);
    crowns.setColorAt(i, color);
  });
  for (const mesh of [trunks, crowns]) { mesh.castShadow = true; mesh.receiveShadow = true; mesh.name = 'pines'; }

  // rim rocks (D04): flattened noisy boulders
  const rockGeo = new THREE.DodecahedronGeometry(1, 0);
  const rocks = new THREE.InstancedMesh(rockGeo, mats.rock, quality > 0 ? 260 : 120);
  rockGeo.setAttribute('color', new THREE.Float32BufferAttribute(new Array(rockGeo.attributes.position.count * 3).fill(.78), 3));
  let k = 0;
  for (const p of peaks) for (let i = 0; i < p.rim.length && k < rocks.count; i += 3) {
    const [x, z] = p.rim[i];
    if (blocked(x, z) || r.next() < .4) continue;
    const s = .8 + r.next() * 2.2;
    m.compose(new THREE.Vector3(x, p.mesa.top + s * .2, z), q.setFromEuler(new THREE.Euler(r.next(), r.next() * 6, r.next())), new THREE.Vector3(s * 1.4, s * .7, s));
    rocks.setMatrixAt(k++, m);
  }
  rocks.count = k;
  rocks.castShadow = rocks.receiveShadow = true;
  return { meshes: [trunks, crowns, rocks], count: spots.length };
}
