// Building assemblies from the kit (B01–B10, C02–C04). Each returns a GeoBucket in local space, front = +z.
// Proportions follow the manifest design constraints (gate 36×22, main hall 60×40×36, scripture pavilion
// 24×24×52, sword platform Ø40); the rest are this round's estimates. Hidden framing and interiors are not modelled.
import * as THREE from 'three';
import { columns, eaveCourse, hipRoof, lantern, plinth, pyramidRoof, railing, skirtRoof, stair, walls } from './kit';
import { GeoBucket, V } from './util';

const box = (pts: [number, number][], y: number) => pts.map(([x, z]) => V(x, y, z));
const rect = (w: number, d: number, y: number) => box([[-w / 2, d / 2], [-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2]], y);

/** Plinth railing with an opening of width `gap` at the front centre (and optionally the back). */
function plinthRail(b: GeoBucket, w: number, d: number, y: number, gap: number, back = false) {
  const g = gap / 2;
  railing(b, box([[-g, d / 2], [-w / 2, d / 2], [-w / 2, -d / 2], ...(back ? [[-g, -d / 2]] as [number, number][] : [[w / 2, -d / 2]] as [number, number][])], y));
  railing(b, box(back ? [[g, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [g, d / 2]] : [[w / 2, -d / 2], [w / 2, d / 2], [g, d / 2]], y));
}

/** B02 主殿: three-tier plinth, colonnade, lattice walls, three eaves (two skirts + hip roof), three front flights. */
export function mainHall() {
  const b = new GeoBucket();
  const W = 60, D = 40, P = 5;
  plinth(b, W + 18, D + 16, P, 3);
  plinthRail(b, W + 17, D + 15, P, 34, true);
  for (const [x, w] of [[0, 14], [-13, 6], [13, 6]] as const) stair(b, x, 0, (D + 16) / 2 + P * 2.2, w, P, P * 2.2, V(0, 0, -1), 1, x !== 0);
  stair(b, 0, 0, -(D + 16) / 2 - P * 2.2, 8, P, P * 2.2, V(0, 0, 1), 1, true);
  columns(b, W, D, 9, 5, P, 8);
  walls(b, W - 8, D - 8, 7, 4, P + .5, 7.5);
  eaveCourse(b, W, D, P + 8);
  skirtRoof(b, W + 12, D + 12, W - 10, D - 10, 4.5, P + 11);
  // second storey
  walls(b, W - 12, D - 12, 7, 4, P + 15, 3.6, 'lattice');
  eaveCourse(b, W - 10, D - 10, P + 18.4, 2.6, .7);
  skirtRoof(b, W + 2, D + 4, W - 18, D - 18, 3.8, P + 21);
  // top storey and hip roof
  walls(b, W - 20, D - 20, 6, 3, P + 24.5, 2.8, 'beam');
  eaveCourse(b, W - 18, D - 18, P + 27.2, 2.6, .7);
  hipRoof(b, W - 8, D - 6, 8, P + 29.9);
  // plaque on the south face, bronze censers and lanterns in front
  b.box('gold', 9, 3, .4, 0, P + 16.6, (D - 12) / 2 + .7);
  b.box('beam', 7.6, 2.2, .5, 0, P + 16.6, (D - 12) / 2 + .8);
  for (const x of [-24, 24]) lantern(b, x, P, D / 2 + 4);
  for (const x of [-34, 34]) lantern(b, x, 0, D / 2 + 16);
  b.cylinder('gold', 1.6, 2, 2.6, 0, 0, D / 2 + 22, 12);
  return { bucket: b, size: V(W + 18, 42, D + 16) };
}

/** B01 山门: four white-stone piers, three bays with stepped hip roofs, front and back flights. */
export function gate() {
  const b = new GeoBucket();
  const W = 36, D = 10, P = 2.4;
  plinth(b, W + 6, D + 6, P, 2);
  for (const z of [1, -1]) {
    stair(b, 0, 0, z * ((D + 6) / 2 + P * 2.4), 12, P, P * 2.4, V(0, 0, -z), 1, false);
    for (const x of [-12.5, 12.5]) stair(b, x, 0, z * ((D + 6) / 2 + P * 2.4), 7, P, P * 2.4, V(0, 0, -z), 1, false);
  }
  railing(b, box([[-W / 2 - 3, D / 2 + 3], [-W / 2 - 3, -D / 2 - 3]], P));
  railing(b, box([[W / 2 + 3, D / 2 + 3], [W / 2 + 3, -D / 2 - 3]], P));
  const piers = [-16, -6, 6, 16];
  for (const x of piers) {
    b.box('jadeDark', 3.4, 1.4, 3.4, x, P + .7, 0);
    b.box('jade', 2.4, 12.6, 2.4, x, P + 7.7, 0);
    b.box('gold', 2.6, .4, 2.6, x, P + 13.8, 0);
    for (const z of [-1.6, 1.6]) b.box('jadeDark', 2.4, 4, .8, x, P + 2.7, z);       // stone drums bracing the piers
  }
  // bays: centre (higher) and sides
  const bay = (cx: number, w: number, top: number, roofW: number, roofH: number) => {
    b.box('beam', w, 1.6, 1.2, cx, top - 3.2, 0);
    b.box('beam', w, 1.2, 1.2, cx, top - .6, 0);
    eaveCourse(b, w, 3.2, top, 1.8, .55);
    hipRoof(b, roofW, 9, roofH, top + 2.6, { lift: 1.3, flare: .9 });
  };
  bay(0, 12, P + 15.4, 17, 4.2);
  bay(-11, 10, P + 11.6, 13.5, 3.4);
  bay(11, 10, P + 11.6, 13.5, 3.4);
  b.box('gold', 5.2, 2.2, .3, 0, P + 13.3, .75);
  b.box('ridge', 4.4, 1.6, .35, 0, P + 13.3, .8);
  for (const x of [-21, 21]) lantern(b, x, 0, D / 2 + 9);
  return { bucket: b, size: V(W + 6, 24, D + 16) };
}

/** B03 藏经阁: square multi-storey tower (five eaves here for budget; B03 shows seven) with pyramid crown. */
export function scripturePavilion() {
  const b = new GeoBucket();
  const P = 3;
  plinth(b, 32, 32, P, 2);
  plinthRail(b, 31, 31, P, 8);
  stair(b, 0, 0, 16 + P * 2.2, 7, P, P * 2.2, V(0, 0, -1), 1, false);
  let y = P, w = 22;
  for (let k = 0; k < 5; k++) {
    const h = k === 0 ? 7 : 5.2;
    columns(b, w, w, 5, 5, y, h, .42);
    walls(b, w - 3, w - 3, 5, 5, y + .3, h - .6, k % 2 ? 'beam' : 'lattice');
    eaveCourse(b, w, w, y + h, 2.2, .55);
    y += h + 2.6;
    if (k < 4) skirtRoof(b, w + 8, w + 8, w - 4, w - 4, 2.8, y, { lift: 1.3, flare: 1 });
    railing(b, rect(w - 1, w - 1, y + 2.8), 1, true);
    y += 2.8;
    w -= 2.6;
  }
  pyramidRoof(b, 4, (w + 11) / Math.SQRT2, 8, y - 2.8);
  return { bucket: b, size: V(32, y + 10, 32) };
}

/** Generic single/double-eave hall (B04 alchemy, B05 forge, B06/B07 residences). */
export function hall(w: number, d: number, colH: number, bays: [number, number], opts: { eaves?: 1 | 2; plinthH?: number; chimneys?: number[]; stairs?: boolean } = {}) {
  const b = new GeoBucket();
  const P = opts.plinthH ?? 2.4;
  plinth(b, w + 8, d + 8, P, 2);
  plinthRail(b, w + 7, d + 7, P, 8);
  if (opts.stairs !== false) stair(b, 0, 0, (d + 8) / 2 + P * 2.2, 7, P, P * 2.2, V(0, 0, -1), 1, false);
  columns(b, w, d, bays[0], bays[1], P, colH, .45);
  walls(b, w - 5, d - 5, bays[0] - 1, bays[1] - 1, P + .3, colH - .3);
  eaveCourse(b, w, d, P + colH, 2.2, .6);
  let top = P + colH + 3;
  if (opts.eaves === 2) {
    skirtRoof(b, w + 8, d + 8, w - 8, d - 8, 3, top);
    walls(b, w - 8, d - 8, bays[0] - 1, bays[1] - 1, top + 2.6, 3.4, 'beam');
    eaveCourse(b, w - 6, d - 6, top + 6, 2.2, .55);
    top += 9;
    hipRoof(b, w + 2, d + 2, Math.max(4.5, d * .26), top);
  } else hipRoof(b, w + 8, d + 8, Math.max(4.5, d * .3), top);
  for (const x of opts.chimneys ?? []) {
    b.box('jadeDark', 2.4, 10, 2.4, x, top + 3, -d / 2 + 2);
    b.box('dark', 2.8, .8, 2.8, x, top + 8.4, -d / 2 + 2);
  }
  return { bucket: b, size: V(w + 8, top + Math.max(4.5, d * .3) + 2, d + 8) };
}

/** B10 观剑亭: hexagonal double-eave pavilion on a small plinth. */
export function hexPavilion() {
  const b = new GeoBucket();
  plinth(b, 15, 15, 1.6, 2);
  const R = 5.6;
  for (let i = 0; i < 6; i++) {
    const a = i / 6 * Math.PI * 2;
    b.cylinder('wood', .38, .34, 6.8, Math.cos(a) * R, 1.6, Math.sin(a) * R, 8);
    if (i !== 1) {
      const a1 = (i + 1) / 6 * Math.PI * 2;
      railing(b, [V(Math.cos(a) * R, 1.6, Math.sin(a) * R), V(Math.cos(a1) * R, 1.6, Math.sin(a1) * R)], .8);
    }
  }
  b.add('beam', new THREE.CylinderGeometry(R + .5, R + .5, 1, 6, 1, true), new THREE.Matrix4().makeTranslation(0, 8.6, 0));
  pyramidRoof(b, 6, R + 3.2, 2.6, 9.2, { lift: 1.2, flare: .8 });
  b.add('beam', new THREE.CylinderGeometry(R - 1, R - 1, 1.6, 6, 1, true), new THREE.Matrix4().makeTranslation(0, 11.6, 0));
  pyramidRoof(b, 6, R + 1.4, 4.4, 12.4, { lift: 1, flare: .7 });
  return { bucket: b, size: V(15, 20, 15) };
}

/** C03 试剑台: open round platform Ø40 with ring railing, two openings and an inlaid sword emblem. */
export function swordPlatform() {
  const b = new GeoBucket();
  const R = 20;
  b.add('jadeDark', new THREE.CylinderGeometry(R + 1, R + 2.2, 2, 48), new THREE.Matrix4().makeTranslation(0, 1, 0));
  b.add('paving', new THREE.CylinderGeometry(R, R, .3, 48), new THREE.Matrix4().makeTranslation(0, 2.1, 0));
  b.add('gold', new THREE.RingGeometry(R * .55, R * .58, 48).rotateX(-Math.PI / 2), new THREE.Matrix4().makeTranslation(0, 2.3, 0));
  b.add('gold', new THREE.RingGeometry(R * .2, R * .22, 32).rotateX(-Math.PI / 2), new THREE.Matrix4().makeTranslation(0, 2.3, 0));
  for (let i = 0; i < 8; i++) b.box('gold', .5, .06, R * .5, 0, 2.3, 0, i * Math.PI / 4);
  const arc = (a0: number, a1: number) => Array.from({ length: 13 }, (_, i) => { const a = a0 + (a1 - a0) * i / 12; return V(Math.cos(a) * R, 2.2, Math.sin(a) * R); });
  railing(b, arc(.25, Math.PI - .25), 1);
  railing(b, arc(Math.PI + .25, Math.PI * 2 - .25), 1);
  for (const s of [-1, 1]) stair(b, s * (R + 4.6), 0, 0, 7, 2.2, 4.4, V(-s, 0, 0), .5, false);
  // sword stele at the centre
  b.box('jadeDark', 2.4, 1, 2.4, 0, 2.8, 0);
  b.box('gold', .5, 6, .18, 0, 6.2, 0);
  b.box('gold', 1.8, .3, .4, 0, 4.4, 0);
  return { bucket: b, size: V(2 * R + 12, 10, 2 * R + 4) };
}

/** F01-style spirit array used as the secret-realm portal: jade disc, standing stones, glowing rings. */
export function portal() {
  const b = new GeoBucket();
  const R = 8;
  b.add('jadeDark', new THREE.CylinderGeometry(R + 1, R + 1.8, 1.4, 40), new THREE.Matrix4().makeTranslation(0, .7, 0));
  b.add('dark', new THREE.CylinderGeometry(R - .4, R - .4, .2, 40), new THREE.Matrix4().makeTranslation(0, 1.45, 0));
  b.add('glow', new THREE.RingGeometry(R * .78, R * .86, 48).rotateX(-Math.PI / 2), new THREE.Matrix4().makeTranslation(0, 1.6, 0));
  b.add('glow', new THREE.RingGeometry(R * .38, R * .44, 40).rotateX(-Math.PI / 2), new THREE.Matrix4().makeTranslation(0, 1.6, 0));
  for (let i = 0; i < 8; i++) {
    const a = i / 8 * Math.PI * 2;
    b.box('jade', 1.2, 5.5, .8, Math.cos(a) * (R + .2), 1.4 + 2.75, Math.sin(a) * (R + .2), -a + Math.PI / 2);
    b.box('glow', .5, .5, .9, Math.cos(a) * (R + .2), 6.2, Math.sin(a) * (R + .2), -a + Math.PI / 2);
  }
  return { bucket: b, size: V(2 * R + 4, 10, 2 * R + 4) };
}

/** B08 修炼洞府 entrance: carved jade portal framing a dark recess, set into the cave rock face (−z). */
export function caveEntrance() {
  const b = new GeoBucket();
  b.add('dark', new THREE.CylinderGeometry(6, 6, 8, 20, 1, false, 0, Math.PI).rotateX(Math.PI / 2).rotateZ(Math.PI / 2), new THREE.Matrix4().makeTranslation(0, 5, -4));
  b.add('dark', new THREE.BoxGeometry(12, 5, 8), new THREE.Matrix4().makeTranslation(0, 2.5, -4));
  for (const x of [-7, 7]) { b.box('jade', 1.8, 11, 1.8, x, 5.5, 0); b.box('gold', 2, .4, 2, x, 11, 0); }
  b.box('jade', 17, 1.6, 2.2, 0, 11.8, 0);
  b.box('beam', 7, 2, .4, 0, 13.6, .6);
  b.box('gold', 7.6, 2.6, .3, 0, 13.6, .4);
  hipRoof(b, 19, 5, 2.4, 13.4, { lift: 1, flare: .6 });
  plinth(b, 20, 8, .8, 1, 0, 3);
  for (const x of [-11, 11]) lantern(b, x, .8, 5);
  return { bucket: b, size: V(20, 18, 10) };
}

/** Market pavilion (坊市亭): square open pavilion with stall tables. */
export function marketPavilion() {
  const b = new GeoBucket();
  plinth(b, 16, 16, 1.2, 1);
  for (const x of [-6, 6]) for (const z of [-6, 6]) b.cylinder('wood', .36, .32, 6, x, 1.2, z, 8);
  eaveCourse(b, 12, 12, 7.2, 2, .5);
  pyramidRoof(b, 4, 10.5, 4.6, 9.4, { lift: 1.1, flare: .8 });
  for (const [x, z] of [[-3.4, 0], [3.4, 0]] as const) {
    b.box('wood', 3.2, 1, 7, x, 1.7, z);
    b.box('gold', 2.6, .3, 1.2, x, 2.35, z - 2);
    b.box('jade', 2.6, .4, 1.2, x, 2.4, z + 1.6);
  }
  return { bucket: b, size: V(16, 15, 16) };
}

/** Notice stele (告示石) on the plaza: carved jade slab under a small roof. */
export function stele() {
  const b = new GeoBucket();
  b.box('jadeDark', 6, 1.2, 3, 0, .6, 0);
  b.box('jade', 4.6, 6, 1, 0, 4.2, 0);
  b.box('beam', 3.6, 4.4, .2, 0, 4.4, .55);
  b.box('gold', 3.8, .5, .3, 0, 6.9, .55);
  hipRoof(b, 6.4, 2.8, 1.2, 7.4, { lift: .5, flare: .3 });
  return { bucket: b, size: V(7, 10, 4) };
}

export { lantern, railing, stair, plinth };
