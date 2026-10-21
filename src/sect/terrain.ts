// Mountains (D01–D04): every peak is a "mesa" — an irregular outline extruded down into the cloud sea with
// noisy, outward-stepping cliff rings (strata, ledges, overhang-free), a mossy rim and a grass top cap.
// Real closed geometry, so the peaks hold up when orbiting to the sides and back. Also provides the coarse
// height query used for camera collision and label occlusion.
import * as THREE from 'three';
import type { Mesa, Pt } from './layout';
import { clamp, fbm2, lerp, noise2 } from './util';

const BOTTOM = -70;                                         // well under the cloud sea (y≈0)

/** Closed Catmull-Rom resample of the control outline. */
function resample(outline: Pt[], n: number): Pt[] {
  const curve = new THREE.CatmullRomCurve3(outline.map(([x, z]) => new THREE.Vector3(x, 0, z)), true, 'centripetal');
  return curve.getSpacedPoints(n).slice(0, n).map((p) => [p.x, p.z] as Pt);
}

function centroid(pts: Pt[]): Pt {
  let x = 0, z = 0;
  for (const p of pts) { x += p[0]; z += p[1]; }
  return [x / pts.length, z / pts.length];
}

export function pointInPolygon(x: number, z: number, poly: Pt[]) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, zi] = poly[i], [xj, zj] = poly[j];
    if ((zi > z) !== (zj > z) && x < (xj - xi) * (z - zi) / (zj - zi) + xi) inside = !inside;
  }
  return inside;
}

function distToPolygon(x: number, z: number, poly: Pt[]) {
  let best = Infinity;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [ax, az] = poly[j], [bx, bz] = poly[i];
    const dx = bx - ax, dz = bz - az, t = clamp(((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz || 1));
    best = Math.min(best, Math.hypot(x - (ax + dx * t), z - (az + dz * t)));
  }
  return best;
}

export interface Peak { mesa: Mesa; rim: Pt[]; flare: number }

/**
 * Builds one mesa: returns side (rock, vertex coloured) and top (grass) geometries.
 * Rings go from the rim downwards; each ring pushes outward by a flare that grows with depth plus
 * angular/vertical noise, so cliffs read as stacked strata with ledges rather than a smooth cone.
 */
export function buildMesa(m: Mesa): { side: THREE.BufferGeometry; top: THREE.BufferGeometry; peak: Peak } {
  const height = m.top - BOTTOM;
  const N = Math.max(40, Math.min(110, Math.round(perimeter(m.outline) / 5)));
  const rim = resample(m.outline, N);
  const [cx, cz] = centroid(rim);
  const rings = Math.max(8, Math.min(26, Math.round(height / 9)));
  // big massifs spread wide into the clouds; slim pillars stay steep (Zhangjiajie columns)
  const flare = (m.flare ?? 1) * Math.min(.42, 46 / Math.max(height, 40));
  const pos: number[] = [], col: number[] = [], uv: number[] = [];
  const ringPts: THREE.Vector3[][] = [];
  const s = m.seed * 13.7;
  for (let k = 0; k <= rings; k++) {
    const t = k / rings;                                       // 0 rim → 1 bottom
    const y = k === 0 ? m.top : lerp(m.top - 1.5, BOTTOM, t ** 1.08);
    const ring: THREE.Vector3[] = [];
    for (let i = 0; i < N; i++) {
      const [px, pz] = rim[i];
      const nx = px - cx, nz = pz - cz, len = Math.hypot(nx, nz) || 1;
      const a = i / N;
      // depth flare + strata noise; the rim ring stays on the outline (k=0)
      const strata = fbm2(a * 9 + s, y * .045 + s, 3) - .45;
      const ledge = Math.max(0, noise2(a * 5 + s, k * .7 + s) - .6) * 14;
      const flute = (noise2(a * perimeter(m.outline) / 9 + s, y * .006 + s) - .5) * 7;   // vertical joints / buttresses
      const out = k === 0 ? 0 : 1.2 + (m.top - y) * flare * (.45 + 1.1 * fbm2(a * 4 + s, 1.3 + s, 3)) + strata * 12 + ledge + flute * Math.min(1, t * 4);
      ring.push(new THREE.Vector3(px + nx / len * out, y + (k === 0 ? 0 : (noise2(a * 11 + s, k + s) - .5) * 3), pz + nz / len * out));
    }
    ringPts.push(ring);
  }
  const color = new THREE.Color();
  const shade = (p: THREE.Vector3, k: number, i: number) => {
    const t = k / rings;
    const n = fbm2(p.x * .03 + s, p.y * .08, 3);
    const band = .5 + .5 * Math.sin(p.y * .32 + n * 4);
    // pale grey granite with cool blue shadows (E06), mossy only along the rim and on ledges
    const v = (.86 + n * .28);
    color.setRGB(lerp(.6, .78, band) * v, lerp(.63, .8, band) * v, lerp(.64, .8, band) * v);
    const moss = k <= 1 ? .6 : Math.max(0, noise2(i * .37 + s, p.y * .05) - .7) * 1.4 * (1 - t);
    color.lerp(new THREE.Color(.36, .46, .3), clamp(moss));
    color.lerp(new THREE.Color(.62, .7, .78), t ** 1.6 * .55);       // aerial haze towards the cloud sea (A01 depth)
    return color;
  };
  // outline winding is arbitrary: pick the triangle order whose normal faces away from the centroid
  const a0 = ringPts[0][0], b0 = ringPts[1][0], b1 = ringPts[1][1];
  const n0 = new THREE.Vector3().crossVectors(b0.clone().sub(a0), b1.clone().sub(a0));
  const flip = n0.x * (a0.x - cx) + n0.z * (a0.z - cz) < 0;
  for (let k = 0; k < rings; k++) {
    const A = ringPts[k], B = ringPts[k + 1];
    for (let i = 0; i < N; i++) {
      const j = (i + 1) % N;
      const quad = flip ? [A[i], B[j], B[i], A[i], A[j], B[j]] : [A[i], B[i], B[j], A[i], B[j], A[j]];
      const ks = flip ? [k, k + 1, k + 1, k, k, k + 1] : [k, k + 1, k + 1, k, k + 1, k];
      const is = flip ? [i, j, i, i, j, j] : [i, i, j, i, j, j];
      quad.forEach((p, q) => {
        pos.push(p.x, p.y, p.z);
        const c = shade(p, ks[q], is[q]);
        col.push(c.r, c.g, c.b);
        uv.push((j === 0 && is[q] === 0 ? N : is[q]) * .12, p.y * .05);
      });
    }
  }
  const side = new THREE.BufferGeometry();
  side.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  side.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  side.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  side.computeVertexNormals();
  // top cap (winding flipped so it faces up after rotation)
  const shape = new THREE.Shape(rim.map(([x, z]) => new THREE.Vector2(x, -z)));
  const top = new THREE.ShapeGeometry(shape, 1).rotateX(-Math.PI / 2).translate(0, m.top, 0);
  const tuv = top.attributes.uv as THREE.BufferAttribute;
  for (let i = 0; i < tuv.count; i++) tuv.setXY(i, tuv.getX(i) / 18, tuv.getY(i) / 18);
  return { side, top, peak: { mesa: m, rim, flare } };
}

function perimeter(o: Pt[]) { let p = 0; for (let i = 0; i < o.length; i++) { const a = o[i], b = o[(i + 1) % o.length]; p += Math.hypot(b[0] - a[0], b[1] - a[1]); } return p; }

/**
 * Coarse terrain height for camera collision and label occlusion: inside a rim → its top; outside →
 * the top minus the cliff drop implied by the flare (conservative: slightly higher than the real cliff).
 */
export function heightAt(peaks: Peak[], x: number, z: number) {
  let h = BOTTOM;
  for (const p of peaks) {
    if (pointInPolygon(x, z, p.rim)) { h = Math.max(h, p.mesa.top); continue; }
    const d = distToPolygon(x, z, p.rim);
    const drop = (d - 2) / Math.max(p.flare, .05);
    h = Math.max(h, p.mesa.top - Math.max(0, drop) - (d > 2 ? 4 : 0));
  }
  return h;
}

/** Distant ranges (D10): low-poly ridges on rings far away, tinted by aerial perspective in the fog. */
export function distantRanges(seed = 5) {
  const pos: number[] = [], col: number[] = [];
  const rings = [{ r: 1300, h: 260, n: 120, c: [.62, .7, .76] }, { r: 1900, h: 420, n: 140, c: [.72, .79, .85] }, { r: 2600, h: 560, n: 150, c: [.8, .86, .9] }];
  for (const ring of rings) {
    for (let i = 0; i < ring.n; i++) {
      const a0 = i / ring.n * Math.PI * 2, a1 = (i + 1) / ring.n * Math.PI * 2;
      const h0 = ring.h * (.25 + fbm2(i * .23 + seed + ring.r, 1, 4) * 1.4) , h1 = ring.h * (.25 + fbm2((i + 1) * .23 + seed + ring.r, 1, 4) * 1.4);
      const p = (a: number, r: number, y: number) => [Math.cos(a) * r, y, Math.sin(a) * r];
      const tri = [p(a0, ring.r, -40), p(a1, ring.r, -40), p(a1, ring.r, h1), p(a0, ring.r, -40), p(a1, ring.r, h1), p(a0, ring.r, h0)];
      for (const v of tri) { pos.push(...v); const k = v[1] > 0 ? .92 + v[1] / ring.h * .12 : .85; col.push(ring.c[0] * k, ring.c[1] * k, ring.c[2] * k); }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.computeVertexNormals();
  return g;
}
