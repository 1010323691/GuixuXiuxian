// Shared helpers for the arena: math, seeded randomness, the toon/ink material family and canvas textures.
import * as THREE from 'three';

export const TAU = Math.PI * 2;
export const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
export const C = (hex: THREE.ColorRepresentation) => new THREE.Color(hex);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
export const smooth = (t: number) => { t = clamp(t); return t * t * (3 - 2 * t); };
export const easeOut = (t: number) => 1 - (1 - clamp(t)) ** 3;
export const easeIn = (t: number) => clamp(t) ** 3;
export const easeInOut = (t: number) => { t = clamp(t); return t < .5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2; };
export const backOut = (t: number) => { t = clamp(t); const k = 1.70158; return 1 + (k + 1) * (t - 1) ** 3 + k * (t - 1) ** 2; };
/** 0 → 1 → 0 over [0,1] with a quick attack and soft release. */
export const pulse = (t: number, attack = .25) => (t <= 0 || t >= 1 ? 0 : t < attack ? easeOut(t / attack) : 1 - smooth((t - attack) / (1 - attack)));

/** Deterministic layouts make screenshots and regression comparisons stable. */
export function rng(seed: number) {
  let s = seed >>> 0;
  const next = () => { s = (s + 0x6d2b79f5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  return { next, range: (a: number, b: number) => a + next() * (b - a), pick: <T>(list: T[]) => list[Math.floor(next() * list.length)] };
}

// ------------------------------------------------------------------ toon + ink
export const INK = C(0x1a1d22);

let ramp: THREE.DataTexture | null = null;
/** Five soft bands: painterly shading rather than hard cel steps. */
export function toonRamp() {
  if (ramp) return ramp;
  ramp = new THREE.DataTexture(new Uint8Array([86, 128, 176, 222, 255]), 5, 1, THREE.RedFormat);
  ramp.minFilter = ramp.magFilter = THREE.NearestFilter;
  ramp.needsUpdate = true;
  return ramp;
}

/** Releases module-level shared resources (call after the last arena is disposed). */
export function disposeShared() { ramp?.dispose(); ramp = null; }

export interface ToonOptions extends THREE.MeshToonMaterialParameters { rim?: THREE.ColorRepresentation; rimPower?: number }

/** Toon material with a view-dependent rim light, so silhouettes read against the bright sky. */
export function toon(color: THREE.ColorRepresentation, { rim = 0xfff2dc, rimPower = 3, ...extra }: ToonOptions = {}) {
  const mat = new THREE.MeshToonMaterial({ color, gradientMap: toonRamp(), ...extra });
  const rimColor = C(rim).multiplyScalar(.55);
  mat.userData.rim = rimColor;
  mat.onBeforeCompile = (shader) => {
    shader.uniforms.rimColor = { value: rimColor };
    shader.uniforms.rimPower = { value: rimPower };
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform vec3 rimColor;\nuniform float rimPower;')
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n  totalEmissiveRadiance += rimColor * pow(1.0 - saturate(dot(normal, normalize(vViewPosition))), rimPower);');
  };
  mat.customProgramCacheKey = () => 'toon-rim';
  return mat;
}

const outlineCache = new Map<number, THREE.ShaderMaterial>();
/** Inverted-hull ink line; thickness grows slightly with distance so far silhouettes stay legible. */
export function outlineMat(thick: number) {
  const key = Math.round(thick * 1000);
  let mat = outlineCache.get(key);
  if (!mat) {
    mat = new THREE.ShaderMaterial({
      uniforms: { t: { value: thick }, ink: { value: INK }, fogColor: { value: C(0xdfeef5) }, fogDensity: { value: 0 } },
      side: THREE.BackSide,
      vertexShader: `uniform float t; varying float vDepth;
        void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.); float k = t * (1. + clamp(-mv.z * .02, 0., 1.5));
          mv = modelViewMatrix * vec4(position + normal * k, 1.); vDepth = -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform vec3 ink, fogColor; uniform float fogDensity; varying float vDepth;
        void main(){ float f = 1. - exp(-fogDensity * fogDensity * vDepth * vDepth); gl_FragColor = vec4(mix(ink, fogColor, f), 1.); }`,
    });
    outlineCache.set(key, mat);
  }
  return mat;
}
export function setInkFog(color: THREE.Color, density: number) {
  for (const mat of outlineCache.values()) { mat.uniforms.fogColor.value = color; mat.uniforms.fogDensity.value = density; }
}
export function disposeOutlines() { for (const mat of outlineCache.values()) mat.dispose(); outlineCache.clear(); }

export function inked<T extends THREE.Mesh>(mesh: T, thick = .02): T {
  const line = new THREE.Mesh(mesh.geometry, outlineMat(thick));
  line.name = 'ink';
  mesh.add(line);
  return mesh;
}

export function smoothLathe(points: [number, number][], segments = 40, phiStart = 0, phiLength = TAU) {
  const curve = new THREE.SplineCurve(points.map(([x, y]) => new THREE.Vector2(x, y)));
  return new THREE.LatheGeometry(curve.getPoints(32), segments, phiStart, phiLength);
}

/** Tapered tube rebuilt along a curve (tails, horns, hair locks). */
export function taperTube(segments: number, radial: number, material: THREE.Material) {
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array((segments + 1) * radial * 3);
  const index: number[] = [];
  for (let i = 0; i < segments; i++) for (let j = 0; j < radial; j++) {
    const a = i * radial + j, b = i * radial + (j + 1) % radial, c = (i + 1) * radial + j, d = (i + 1) * radial + (j + 1) % radial;
    index.push(a, c, b, b, c, d);
  }
  geo.setIndex(index);
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const mesh = new THREE.Mesh(geo, material);
  mesh.frustumCulled = false;
  const up = V(0, 1, 0), n = V(), b = V(), tan = V(), p = V();
  const build = (curve: THREE.Curve<THREE.Vector3>, radius: (u: number) => number) => {
    for (let i = 0; i <= segments; i++) {
      const u = i / segments;
      curve.getPointAt(u, p); curve.getTangentAt(u, tan);
      n.crossVectors(tan, up); if (n.lengthSq() < 1e-4) n.set(1, 0, 0); n.normalize(); b.crossVectors(n, tan).normalize();
      const r = radius(u);
      for (let j = 0; j < radial; j++) {
        const a = j / radial * TAU, k = (i * radial + j) * 3;
        pos[k] = p.x + (Math.cos(a) * n.x + Math.sin(a) * b.x) * r;
        pos[k + 1] = p.y + (Math.cos(a) * n.y + Math.sin(a) * b.y) * r;
        pos[k + 2] = p.z + (Math.cos(a) * n.z + Math.sin(a) * b.z) * r;
      }
    }
    geo.attributes.position.needsUpdate = true;
    geo.computeVertexNormals();
    geo.computeBoundingSphere();
  };
  return { mesh, build };
}

// ------------------------------------------------------------------ canvas textures
export function canvasTexture(w: number, h: number, draw: (g: CanvasRenderingContext2D, w: number, h: number) => void) {
  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  draw(canvas.getContext('2d')!, w, h);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

export const softDot = () => canvasTexture(64, 64, (g) => {
  const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, 'rgba(255,255,255,1)'); r.addColorStop(.25, 'rgba(255,255,255,.7)'); r.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = r; g.fillRect(0, 0, 64, 64);
});

/** Additive glow material for halos and cores; colour above 1 feeds bloom. */
export function glowMat(color: THREE.ColorRepresentation, map: THREE.Texture, opacity = 1) {
  return new THREE.SpriteMaterial({ map, color: C(color), transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false });
}

export const GLYPHS = '天地玄黄宇宙洪荒日月盈昃辰宿列张寒来暑往秋收冬藏乾坤震巽坎离艮兑敕令雷火风云剑';
