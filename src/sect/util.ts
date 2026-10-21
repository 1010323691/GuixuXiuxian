// Shared helpers for the sect scene: math, seeded randomness, geometry merging and canvas textures.
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

export const TAU = Math.PI * 2;
export const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const smooth = (t: number) => { t = clamp(t); return t * t * (3 - 2 * t); };
export const easeInOut = (t: number) => { t = clamp(t); return t < .5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2; };

/** Deterministic layouts keep screenshots comparable between runs. */
export function rng(seed: number) {
  let s = seed >>> 0;
  const next = () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  return { next, range: (a: number, b: number) => a + next() * (b - a) };
}
export type Rng = ReturnType<typeof rng>;

/** Smooth 2D value noise (deterministic, CPU side) for terrain outlines and strata. */
function hash2(x: number, y: number) { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); }
export function noise2(x: number, y: number) {
  const ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy;
  const ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
  const a = hash2(ix, iy), b = hash2(ix + 1, iy), c = hash2(ix, iy + 1), d = hash2(ix + 1, iy + 1);
  return lerp(lerp(a, b, ux), lerp(c, d, ux), uy);
}
export function fbm2(x: number, y: number, octaves = 4) {
  let v = 0, a = .5;
  for (let i = 0; i < octaves; i++) { v += a * noise2(x, y); x = x * 2.03 + 7.1; y = y * 2.03 + 3.7; a *= .5; }
  return v;
}

/**
 * Collects geometries per material key so a whole building becomes one mesh per material.
 * Every part is transformed into the bucket's local space before merging.
 */
export class GeoBucket {
  private parts = new Map<string, THREE.BufferGeometry[]>();
  add(key: string, geo: THREE.BufferGeometry, matrix?: THREE.Matrix4) {
    const g = geo.index ? geo.toNonIndexed() : geo;
    if (g !== geo) geo.dispose();
    if (matrix) g.applyMatrix4(matrix);
    // mergeGeometries needs identical attribute sets: keep position/normal/uv only
    for (const name of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(name)) g.deleteAttribute(name);
    if (!g.attributes.uv) g.setAttribute('uv', new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
    if (!g.attributes.normal) g.computeVertexNormals();
    (this.parts.get(key) ?? this.parts.set(key, []).get(key)!).push(g);
  }
  box(key: string, w: number, h: number, d: number, x: number, y: number, z: number, ry = 0) {
    const m = new THREE.Matrix4().compose(V(x, y, z), new THREE.Quaternion().setFromAxisAngle(V(0, 1, 0), ry), V(1, 1, 1));
    this.add(key, new THREE.BoxGeometry(w, h, d), m);
  }
  cylinder(key: string, r0: number, r1: number, h: number, x: number, y: number, z: number, seg = 10) {
    this.add(key, new THREE.CylinderGeometry(r1, r0, h, seg, 1), new THREE.Matrix4().makeTranslation(x, y + h / 2, z));
  }
  /** Merges everything into meshes; `materials` maps bucket keys to materials. */
  build(materials: Record<string, THREE.Material>, group = new THREE.Group()) {
    for (const [key, list] of this.parts) {
      const merged = mergeGeometries(list, false);
      list.forEach((g) => g.dispose());
      if (!merged) continue;
      const mesh = new THREE.Mesh(merged, materials[key]);
      mesh.name = key;
      mesh.castShadow = key !== 'glow';
      mesh.receiveShadow = true;
      group.add(mesh);
    }
    this.parts.clear();
    return group;
  }
}

export function canvasTexture(size: number, paint: (g: CanvasRenderingContext2D, s: number) => void, repeat = true) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  paint(canvas.getContext('2d')!, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  if (repeat) tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 4;
  return tex;
}
