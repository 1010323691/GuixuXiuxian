// Reusable architecture kit (B group sheets): plinths, stairs, railings, columns, lattice walls, painted beams,
// bracket sets, curved hip / pyramid / skirt roofs with up-turned corners, ridges and gilded ornaments.
// Everything is emitted into a GeoBucket in the building's local space (x east, y up, z south = front).
// Roof curvature, bracket spacing, bay counts and hidden framing are estimates, not measured data.
import * as THREE from 'three';
import { GeoBucket, V } from './util';

type XYZ = [number, number, number];

/** Parametric surface (u,v ∈ [0,1]) → indexed geometry with smooth normals and metre-based uvs. */
export function surface(nu: number, nv: number, at: (u: number, v: number) => XYZ, uvScale: [number, number] = [1, 1]) {
  const pos: number[] = [], uv: number[] = [], idx: number[] = [];
  for (let j = 0; j <= nv; j++) for (let i = 0; i <= nu; i++) {
    const p = at(i / nu, j / nv);
    pos.push(...p);
    uv.push(i / nu * uvScale[0], j / nv * uvScale[1]);
  }
  for (let j = 0; j < nv; j++) for (let i = 0; i < nu; i++) {
    const a = j * (nu + 1) + i, b = a + 1, c = a + nu + 1, d = c + 1;
    idx.push(a, c, b, b, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

const profile = (v: number) => v ** 1.7;                     // concave roof slope: flat eave, steep top
const T = (x: number, y: number, z: number) => new THREE.Matrix4().makeTranslation(x, y, z);

export interface RoofOpts { overhang?: number; lift?: number; flare?: number; mat?: string }

/**
 * A curved roof face between an eave polyline and a top polyline, lifted at both ends (corners).
 * Emits tiles on top, a wooden soffit below and an eave fascia between them.
 */
function roofFace(b: GeoBucket, e0: THREE.Vector3, e1: THREE.Vector3, t0: THREE.Vector3, t1: THREE.Vector3, h: number, lift: number, flare: number, cornerDirs: [THREE.Vector3, THREE.Vector3]) {
  const len = e0.distanceTo(e1), slope = Math.hypot(h, e0.clone().lerp(e1, .5).distanceTo(t0.clone().lerp(t1, .5)));
  const at = (u: number, v: number, drop: number): XYZ => {
    const e = e0.clone().lerp(e1, u), t = t0.clone().lerp(t1, u);
    const p = e.lerp(t, v);
    const cw = Math.max(Math.abs(2 * u - 1) ** 5, 0) * (1 - v) ** 2;
    const dir = u < .5 ? cornerDirs[0] : cornerDirs[1];
    p.addScaledVector(dir, cw * flare);
    return [p.x, h * profile(v) + cw * lift - drop, p.z];
  };
  const nu = 14, nv = 7;
  b.add('tile', surface(nu, nv, (u, v) => at(u, v, 0), [len / 4, slope / 3]));
  const soffit = surface(nu, nv, (u, v) => at(u, v, .55));
  (soffit.index!.array as Uint16Array | Uint32Array).reverse();      // flip winding so the underside faces down
  soffit.computeVertexNormals();
  b.add('wood', soffit);
  // fascia (连檐): a thin vertical band along the eave
  b.add('ridge', surface(nu, 1, (u, v) => { const p = at(u, 0, 0); return [p[0], p[1] - v * .55, p[2]]; }));
}

/** 庑殿 hip roof over a W×D eave rectangle centred at the origin, eave at y=0, ridge at y=h. */
export function hipRoof(b: GeoBucket, w: number, d: number, h: number, y: number, o: RoofOpts = {}) {
  const lift = o.lift ?? Math.min(2.4, w * .05), flare = o.flare ?? Math.min(1.6, w * .03);
  const a = w / 2, c = d / 2, r = Math.max(0, a - c * .85);
  const g = new GeoBucket();
  const dir = (sx: number, sz: number) => V(sx, 0, sz).normalize();
  const E = (sx: number, sz: number) => V(sx * a, 0, sz * c);
  // front, back, left, right
  roofFace(g, E(-1, 1), E(1, 1), V(-r, 0, 0), V(r, 0, 0), h, lift, flare, [dir(-1, 1), dir(1, 1)]);
  roofFace(g, E(1, -1), E(-1, -1), V(r, 0, 0), V(-r, 0, 0), h, lift, flare, [dir(1, -1), dir(-1, -1)]);
  roofFace(g, E(-1, -1), E(-1, 1), V(-r, 0, 0), V(-r, 0, 0), h, lift, flare, [dir(-1, -1), dir(-1, 1)]);
  roofFace(g, E(1, 1), E(1, -1), V(r, 0, 0), V(r, 0, 0), h, lift, flare, [dir(1, 1), dir(1, -1)]);
  // main ridge, hip ridges and gilded ends
  g.box('ridge', 2 * r + 1.2, 1.1, 1.1, 0, h + .35, 0);
  for (const s of [-1, 1]) {
    g.box('gold', .9, 2.2, .9, s * (r + .3), h + 1.3, 0);
    for (const sz of [-1, 1]) {
      const top = V(s * r, h, 0), eave = V(s * (a + flare * .7), lift, sz * (c + flare * .7));
      hipLine(g, top, eave, h, lift);
      g.box('gold', .6, .9, .6, eave.x, eave.y + .55, eave.z);
    }
  }
  pour(g, b, T(0, y, 0));
}

/** Hip ridge following the concave profile from the ridge end down to the up-turned corner. */
function hipLine(b: GeoBucket, top: THREE.Vector3, eave: THREE.Vector3, h: number, lift: number) {
  const n = 5;
  let prev = top.clone().setY(h + .25);
  for (let i = 1; i <= n; i++) {
    const v = 1 - i / n;
    const p = eave.clone().lerp(top, v);
    p.y = h * profile(v) + lift * (1 - v) ** 2 + .25;
    const mid = prev.clone().lerp(p, .5), len = prev.distanceTo(p);
    const m = new THREE.Matrix4().lookAt(prev, p, V(0, 1, 0)).setPosition(mid);
    b.add('ridge', new THREE.BoxGeometry(.75, .75, len + .2), m);
    prev = p;
  }
}

/** 攒尖 pyramid roof over a regular n-gon (radius to corners), apex finial in gold. */
export function pyramidRoof(b: GeoBucket, sides: number, radius: number, h: number, y: number, o: RoofOpts = {}) {
  const lift = o.lift ?? radius * .14, flare = o.flare ?? radius * .08, rot = sides === 4 ? Math.PI / 4 : 0;
  const g = new GeoBucket();
  const corner = (i: number) => V(Math.cos(rot + i / sides * Math.PI * 2) * radius, 0, Math.sin(rot + i / sides * Math.PI * 2) * radius);
  const apex = V(0, 0, 0);
  for (let i = 0; i < sides; i++) {
    const c0 = corner(i), c1 = corner(i + 1);
    roofFace(g, c0, c1, apex, apex, h, lift, flare, [c0.clone().normalize(), c1.clone().normalize()]);
    const tip = c0.clone().multiplyScalar(1 + flare * .7 / radius);
    hipLine(g, V(0, h, 0), tip.setY(lift), h, lift);
    g.box('gold', .45, .7, .45, tip.x, lift + .5, tip.z);
  }
  g.cylinder('gold', .7, .15, 3.2, 0, h - .2, 0, 8);
  g.add('gold', new THREE.SphereGeometry(.7, 10, 8), T(0, h + 3.1, 0));
  pour(g, b, T(0, y, 0));
}

/** 腰檐 skirt roof: a sloped eave ring from an outer W×D eave up to an inner w×d wall line. */
export function skirtRoof(b: GeoBucket, W: number, D: number, w: number, d: number, h: number, y: number, o: RoofOpts = {}) {
  const lift = o.lift ?? Math.min(2, W * .04), flare = o.flare ?? Math.min(1.4, W * .025);
  const g = new GeoBucket();
  const A = W / 2, C = D / 2, a = w / 2, c = d / 2;
  const dir = (sx: number, sz: number) => V(sx, 0, sz).normalize();
  roofFace(g, V(-A, 0, C), V(A, 0, C), V(-a, 0, c), V(a, 0, c), h, lift, flare, [dir(-1, 1), dir(1, 1)]);
  roofFace(g, V(A, 0, -C), V(-A, 0, -C), V(a, 0, -c), V(-a, 0, -c), h, lift, flare, [dir(1, -1), dir(-1, -1)]);
  roofFace(g, V(-A, 0, -C), V(-A, 0, C), V(-a, 0, -c), V(-a, 0, c), h, lift, flare, [dir(-1, -1), dir(-1, 1)]);
  roofFace(g, V(A, 0, C), V(A, 0, -C), V(a, 0, c), V(a, 0, -c), h, lift, flare, [dir(1, 1), dir(1, -1)]);
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    const eave = V(sx * (A + flare * .7), lift, sz * (C + flare * .7));
    hipLine(g, V(sx * a, h, sz * c), eave, h, lift);
    g.box('gold', .55, .8, .55, eave.x, eave.y + .5, eave.z);
  }
  pour(g, b, T(0, y, 0));
}

// GeoBucket has no public access to its parts; buildings are merged per material, so a nested bucket is
// flattened by building it into temporary meshes and re-adding their geometry with a transform.
function pour(from: GeoBucket, into: GeoBucket, m: THREE.Matrix4) {
  const tmp = from.build({});
  for (const child of tmp.children) {
    const mesh = child as THREE.Mesh;
    into.add(mesh.name, mesh.geometry, m);
  }
}

/** 须弥座 stepped plinth: tiers shrinking upwards, top paved, footprint w×d, top at y=h. */
export function plinth(b: GeoBucket, w: number, d: number, h: number, tiers = 2, x = 0, z = 0, y0 = 0) {
  const th = h / tiers;
  for (let i = 0; i < tiers; i++) {
    const inset = i * 1.2;
    b.box(i === tiers - 1 ? 'jade' : 'jadeDark', w - inset * 2 + .6, th * .78, d - inset * 2 + .6, x, y0 + i * th + th * .39, z);
    b.box('jade', w - inset * 2, th * .22 + .02, d - inset * 2, x, y0 + i * th + th * .89, z);
  }
  b.add('paving', new THREE.PlaneGeometry(w - (tiers - 1) * 2.4 - .2, d - (tiers - 1) * 2.4 - .2).rotateX(-Math.PI / 2), T(x, y0 + h + .02, z));
}

/** 白玉栏杆 along a polyline: posts every ~2.2m, a top rail and a solid lower panel. */
export function railing(b: GeoBucket, pts: THREE.Vector3[], height = 1.1, closed = false) {
  const list = closed ? [...pts, pts[0]] : pts;
  for (let i = 0; i < list.length - 1; i++) {
    const a = list[i], c = list[i + 1], len = a.distanceTo(c);
    if (len < .5) continue;
    const n = Math.max(1, Math.round(len / 2.2));
    const yaw = Math.atan2(c.x - a.x, c.z - a.z);
    const pitch = Math.atan2(c.y - a.y, Math.hypot(c.x - a.x, c.z - a.z));
    const mid = a.clone().lerp(c, .5);
    const rail = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(-pitch, yaw, 0, 'YXZ'));
    b.add('jade', new THREE.BoxGeometry(.22, .16, len), rail.clone().setPosition(mid.x, mid.y + height - .08, mid.z));
    b.add('jade', new THREE.BoxGeometry(.14, height * .45, len), rail.clone().setPosition(mid.x, mid.y + height * .3, mid.z));
    for (let k = 0; k <= n; k++) {
      if (k === n && i < list.length - 2) continue;
      const p = a.clone().lerp(c, k / n);
      b.box('jade', .32, height + .3, .32, p.x, p.y + (height + .3) / 2, p.z);
    }
  }
}

/**
 * Straight stair from (x, y0, z0) rising `rise` over `run` along `dir` (unit vector in xz), with solid
 * stone body down to `y0 - base`, sloped cheek walls (垂带) and railings on both sides.
 */
export function stair(b: GeoBucket, x: number, y0: number, z0: number, width: number, rise: number, run: number, dir: THREE.Vector3, base = 6, rails = true, stepH = .32) {
  const steps = Math.max(2, Math.round(rise / stepH));
  const sh = rise / steps, sd = run / steps;
  const side = V(-dir.z, 0, dir.x);
  const pos: number[] = [], uv: number[] = [];
  const P = (s: number, along: number, h: number) => { const o = V(x, y0 + h, z0).addScaledVector(dir, along).addScaledVector(side, s * width / 2); return [o.x, o.y, o.z]; };
  const quad = (a: number[], b2: number[], c: number[], d: number[], uvs = [0, 0, 1, 0, 1, 1, 0, 1]) => {
    pos.push(...a, ...b2, ...c, ...a, ...c, ...d);
    uv.push(uvs[0], uvs[1], uvs[2], uvs[3], uvs[4], uvs[5], uvs[0], uvs[1], uvs[4], uvs[5], uvs[6], uvs[7]);
  };
  for (let i = 0; i < steps; i++) {
    const a0 = i * sd, a1 = (i + 1) * sd, h0 = i * sh, h1 = (i + 1) * sh;
    const u = width / 2;
    quad(P(-1, a0, h0), P(1, a0, h0), P(1, a0, h1), P(-1, a0, h1), [0, 0, u, 0, u, .2, 0, .2]);   // riser
    quad(P(-1, a0, h1), P(1, a0, h1), P(1, a1, h1), P(-1, a1, h1), [0, 0, u, 0, u, .3, 0, .3]);   // tread
    for (const s of [-1, 1]) {                                                                 // side walls to the base line
      const lo = -base;
      const q = [P(s, a0, lo), P(s, a1, lo), P(s, a1, h1), P(s, a0, h1)];
      if (s < 0) quad(q[0], q[1], q[2], q[3]); else quad(q[1], q[0], q[3], q[2]);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.computeVertexNormals();
  b.add('jade', g);
  // cheek walls and rails
  const slope = Math.atan2(rise, run), len = Math.hypot(rise, run);
  for (const s of [-1, 1]) {
    const start = V(x, y0, z0).addScaledVector(side, s * (width / 2 + .5));
    const end = start.clone().addScaledVector(dir, run).setY(y0 + rise);
    const mid = start.clone().lerp(end, .5);
    const m = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(-slope, Math.atan2(dir.x, dir.z), 0, 'YXZ')).setPosition(mid.x, mid.y + .1, mid.z);
    b.add('jadeDark', new THREE.BoxGeometry(1, 1.2, len), m);
    if (rails) railing(b, [start.clone().setY(start.y + .7), end.clone().setY(end.y + .7)], 1);
  }
}

/** Ring of wooden columns on a w×d rectangle with `bx`×`bz` bays, carved jade bases and gilded collars. */
export function columns(b: GeoBucket, w: number, d: number, bx: number, bz: number, y: number, h: number, r = .55) {
  const pts: [number, number][] = [];
  for (let i = 0; i <= bx; i++) { pts.push([-w / 2 + i * w / bx, d / 2], [-w / 2 + i * w / bx, -d / 2]); }
  for (let j = 1; j < bz; j++) { pts.push([-w / 2, -d / 2 + j * d / bz], [w / 2, -d / 2 + j * d / bz]); }
  for (const [x, z] of pts) {
    b.box('jade', r * 2.6, .5, r * 2.6, x, y + .25, z);
    b.cylinder('wood', r, r * .92, h, x, y + .5, z, 10);
    b.cylinder('gold', r * 1.1, r * 1.1, .35, x, y + h - .2, z, 10);
  }
}

/** Lattice-door walls (格扇) set back inside the colonnade; uv repeats once per bay. */
export function walls(b: GeoBucket, w: number, d: number, bx: number, bz: number, y: number, h: number, mat = 'lattice') {
  const face = (len: number, bays: number, m: THREE.Matrix4) => {
    const g = new THREE.PlaneGeometry(len, h);
    const uvs = g.attributes.uv as THREE.BufferAttribute;
    for (let i = 0; i < uvs.count; i++) uvs.setX(i, uvs.getX(i) * bays);
    b.add(mat, g, m);
  };
  const R = (ry: number, x: number, z: number) => new THREE.Matrix4().makeRotationY(ry).setPosition(x, y + h / 2, z);
  face(w, bx, R(0, 0, d / 2));
  face(w, bx, R(Math.PI, 0, -d / 2));
  face(d, bz, R(Math.PI / 2, w / 2, 0));
  face(d, bz, R(-Math.PI / 2, -w / 2, 0));
  b.box('wood', w + .4, .5, d + .4, 0, y + h + .25, 0);
  b.box('jadeDark', w + .2, .35, d + .2, 0, y + .17, 0);
}

/** Painted architrave band (额枋) and a bracket-set course (斗拱) carrying the eave. */
export function eaveCourse(b: GeoBucket, w: number, d: number, y: number, spacing = 2.4, size = .8) {
  for (const [len, x, z, ry] of [[w, 0, d / 2, 0], [w, 0, -d / 2, 0], [d, w / 2, 0, Math.PI / 2], [d, -w / 2, 0, Math.PI / 2]] as const) {
    b.box('beam', ry ? 1 : len + 1, 1.3, ry ? len + 1 : 1, x, y + .65, z);
    const n = Math.max(2, Math.round(len / spacing));
    for (let i = 0; i <= n; i++) {
      const t = -len / 2 + i * len / n;
      const px = ry ? x : t, pz = ry ? t : z;
      const ox = ry ? Math.sign(x) : 0, oz = ry ? 0 : Math.sign(z);
      b.box('wood', size, size * .7, size, px + ox * .35, y + 1.6, pz + oz * .35);
      b.box('wood', ry ? size * 2.2 : size * .6, size * .5, ry ? size * .6 : size * 2.2, px + ox * .7, y + 2.1, pz + oz * .7);
      b.box('gold', size * .5, size * .3, size * .5, px + ox * .35, y + 1.2, pz + oz * .35);
    }
  }
  b.box('wood', w + 1.6, .7, d + 1.6, 0, y + 2.6, 0);
}

/** Stone lantern (石灯) — C08 path module. */
export function lantern(b: GeoBucket, x: number, y: number, z: number) {
  b.box('jade', .9, .3, .9, x, y + .15, z);
  b.cylinder('jade', .2, .2, 1.3, x, y + .3, z, 6);
  b.box('glow', .55, .55, .55, x, y + 1.85, z);
  b.box('jadeDark', 1, .2, 1, x, y + 2.2, z);
  b.add('jadeDark', new THREE.ConeGeometry(.7, .5, 4).rotateY(Math.PI / 4), T(x, y + 2.55, z));
}
