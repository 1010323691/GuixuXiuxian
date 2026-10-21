// The world around the duel: bright daytime sky, layered cloud sea, Zhangjiajie-style stone pillars
// crowned with pines and pagodas, waterfalls, floating isles, distant ranges and drifting birds.
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { C, V, TAU, canvasTexture, rng, toon, inked, setInkFog } from './util';

export const PALETTE = {
  zenith: C(0x3d7cc9), horizon: C(0xdcebf3), haze: C(0xc9dbe6), sun: C(0xfff1d6),
  cloudLit: C(0xffffff), cloudShade: C(0x9fb4c8), rock: C(0xb8a68c), rockDark: C(0x6f604e), moss: C(0x5f8a4a), pine: C(0x2f5a3c),
};
export const SUN_DIR = V(.45, .42, -.78).normalize();
const FOG_DENSITY = .0027;

const NOISE = `
  float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float n2(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f*f*(3.-2.*f);
    return mix(mix(h21(i), h21(i+vec2(1,0)), u.x), mix(h21(i+vec2(0,1)), h21(i+vec2(1,1)), u.x), u.y); }
  float fbm(vec2 p){ float v = 0., a = .5; for (int i = 0; i < 6; i++){ v += a*n2(p); p = p*2.02 + 3.1; a *= .5; } return v; }`;

function skyDome() {
  return new THREE.Mesh(new THREE.SphereGeometry(900, 48, 24), new THREE.ShaderMaterial({
    uniforms: { zenith: { value: PALETTE.zenith }, horizon: { value: PALETTE.horizon }, sun: { value: PALETTE.sun }, dir: { value: SUN_DIR }, time: { value: 0 } },
    vertexShader: 'varying vec3 d; void main(){ d = position; vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.); gl_Position = p.xyww; }',
    fragmentShader: `uniform vec3 zenith, horizon, sun, dir; uniform float time; varying vec3 d; ${NOISE}
      void main(){
        vec3 v = normalize(d); float h = v.y;
        vec3 c = mix(horizon, zenith, pow(smoothstep(-.02, .75, h), .7));
        c = mix(c, horizon * .96, smoothstep(.02, -.25, h));
        // high cirrus streaks
        vec2 q = v.xz / max(h, .08) * .9 + vec2(time * .004, 0.);
        float cir = smoothstep(.55, .85, fbm(q * vec2(1., 3.2))) * smoothstep(.05, .35, h);
        c = mix(c, vec3(1.), cir * .45);
        float s = max(dot(v, dir), 0.);
        c += sun * (pow(s, 1800.) * 18. + pow(s, 60.) * .35 + pow(s, 6.) * .12);
        gl_FragColor = vec4(c, 1.);
      }`,
    side: THREE.BackSide, depthWrite: false, depthTest: false,
  }));
}

function cloudSea(y: number, scale: number, alpha: number, speed: number) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 }, lit: { value: PALETTE.cloudLit }, shade: { value: PALETTE.cloudShade }, haze: { value: PALETTE.horizon }, sunDir: { value: SUN_DIR }, alpha: { value: alpha } },
    transparent: true, depthWrite: false,
    vertexShader: 'varying vec3 w; void main(){ vec4 p = modelMatrix * vec4(position, 1.); w = p.xyz; gl_Position = projectionMatrix * viewMatrix * p; }',
    fragmentShader: `uniform float time, alpha; uniform vec3 lit, shade, haze, sunDir; varying vec3 w; ${NOISE}
      void main(){
        vec2 q = w.xz * ${scale.toFixed(4)} + vec2(time * ${speed.toFixed(4)}, time * ${(speed * .35).toFixed(4)});
        float k = fbm(q + .9 * fbm(q * 1.7 + 4.));
        float k2 = fbm(q + vec2(.06, .06) + .9 * fbm(q * 1.7 + 4.06));
        float light = clamp(.55 + (k - k2) * 9. * sunDir.x + k * .5, 0., 1.);
        vec3 c = mix(shade, lit, smoothstep(.25, .85, light));
        float dist = length(w.xz - cameraPosition.xz);
        c = mix(c, haze, smoothstep(60., 620., dist));
        float a = smoothstep(.32, .62, k) * alpha * (1. - smoothstep(700., 880., dist));
        gl_FragColor = vec4(c, a);
      }`,
  });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(1800, 1800), mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.y = y;
  return mesh;
}

/** Soft cumulus billboard texture: lit top, cool shaded underside. */
function puffTexture() {
  return canvasTexture(256, 256, (g, w, h) => {
    const r = rng(7);
    for (let i = 0; i < 26; i++) {
      const x = w * r.range(.2, .8), y = h * r.range(.38, .7), rad = w * r.range(.1, .22);
      const grd = g.createRadialGradient(x, y - rad * .35, rad * .1, x, y, rad);
      grd.addColorStop(0, 'rgba(255,255,255,.95)'); grd.addColorStop(.55, 'rgba(236,242,248,.75)'); grd.addColorStop(1, 'rgba(176,196,214,0)');
      g.fillStyle = grd; g.beginPath(); g.arc(x, y, rad, 0, TAU); g.fill();
    }
    const fade = g.createLinearGradient(0, h * .55, 0, h);
    fade.addColorStop(0, 'rgba(0,0,0,0)'); fade.addColorStop(1, 'rgba(0,0,0,1)');
    g.globalCompositeOperation = 'destination-out'; g.fillStyle = fade; g.fillRect(0, 0, w, h);
  });
}

function billboardClouds(count: number, seed: number, place: (r: ReturnType<typeof rng>) => [THREE.Vector3, number]) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { map: { value: puffTexture() }, haze: { value: PALETTE.horizon }, shade: { value: C(0xb7c8d8) } },
    transparent: true, depthWrite: false,
    vertexShader: `varying vec2 vUv; varying float vDist;
      void main(){ vec4 c = modelViewMatrix * instanceMatrix * vec4(0., 0., 0., 1.); float s = length(instanceMatrix[0].xyz);
        c.xy += position.xy * s; vUv = uv; vDist = -c.z; gl_Position = projectionMatrix * c; }`,
    fragmentShader: `uniform sampler2D map; uniform vec3 haze, shade; varying vec2 vUv; varying float vDist;
      void main(){ vec4 t = texture2D(map, vUv); vec3 c = mix(shade, vec3(1.), smoothstep(.1, .75, vUv.y) * .6 + t.r * .4);
        c = mix(c, haze, smoothstep(80., 700., vDist)); gl_FragColor = vec4(c, t.a * .92); }`,
  });
  const mesh = new THREE.InstancedMesh(new THREE.PlaneGeometry(1, .6), mat, count);
  const r = rng(seed), m = new THREE.Matrix4(), q = new THREE.Quaternion();
  for (let i = 0; i < count; i++) { const [p, s] = place(r); m.compose(p, q, V(s, s, s)); mesh.setMatrixAt(i, m); }
  mesh.frustumCulled = false;
  return mesh;
}

// ------------------------------------------------------------------ stone pillars
/** A sandstone column: vertical ridges, horizontal strata, mossy ledges and a flat green crown. */
function pillarGeometry(seed: number, height: number, radius: number) {
  const r = rng(seed);
  const radial = 22, rows = 46;
  const geo = new THREE.CylinderGeometry(radius, radius * 1.15, height, radial, rows, false);
  geo.translate(0, height / 2, 0);
  const pos = geo.attributes.position, colors = new Float32Array(pos.count * 3);
  const ridge = Array.from({ length: radial + 1 }, () => r.range(.62, 1.22));
  ridge[radial] = ridge[0];
  const strata = Array.from({ length: rows + 1 }, () => r.range(.94, 1.06));
  const lean = V(r.range(-.06, .06), 0, r.range(-.06, .06));
  const col = new THREE.Color();
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i);
    const u = (Math.atan2(z, x) / TAU + 1) % 1, v = y / height;
    const seg = u * radial, k = Math.floor(seg), f = seg - k;
    const ridgeK = ridge[k] * (1 - f) + ridge[(k + 1) % (radial + 1)] * f;
    const crack = Math.abs(Math.sin(u * TAU * 7 + seed)) < .12 ? .9 : 1;
    const top = v > .97 ? .86 : 1;
    const s = ridgeK * strata[Math.round(v * rows)] * crack * top * (1 - v * .12);
    const isCap = Math.abs(y - height) < 1e-3 && Math.hypot(x, z) < radius * .99;
    pos.setXYZ(i, x * s + lean.x * y, isCap ? y + r.range(0, .004) : y, z * s + lean.z * y);
    // colour: warm sandstone, dark cracks, moss on the crown and on ledges
    const shade = .82 + (ridgeK - .95) * .9 + r.range(-.04, .04);
    col.copy(PALETTE.rock).lerp(PALETTE.rockDark, crack < 1 ? .65 : clamp01(.5 - shade * .4));
    col.multiplyScalar(shade);
    const band = Math.sin(v * 140 + seed) * .06;
    col.multiplyScalar(1 + band);
    const moss = v > .985 ? 1 : strata[Math.round(v * rows)] > 1.04 && r.next() < .35 ? .55 : 0;
    col.lerp(PALETTE.moss, moss);
    col.lerp(PALETTE.haze, (1 - v) * .2);
    colors.set([col.r, col.g, col.b], i * 3);
  }
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.computeVertexNormals();
  return geo;
}
const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

function paint(geo: THREE.BufferGeometry, hex: number, jitter = 0, seed = 1) {
  const g = geo.index ? geo.toNonIndexed() : geo;
  const n = g.attributes.position.count, colors = new Float32Array(n * 3), c = C(hex), r = rng(seed);
  for (let i = 0; i < n; i++) { const k = 1 + r.range(-jitter, jitter); colors.set([c.r * k, c.g * k, c.b * k], i * 3); }
  g.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  g.deleteAttribute('uv');
  return g;
}

function pineGeometry() {
  const parts: THREE.BufferGeometry[] = [paint(new THREE.CylinderGeometry(.08, .14, 1.4, 6).translate(0, .7, 0), 0x5a3e2a)];
  [[1.1, .95, 1.0], [.9, .85, 1.6], [.68, .75, 2.15], [.45, .6, 2.6]].forEach(([w, h, y], i) => {
    const cone = new THREE.ConeGeometry(w, h, 7, 1).translate(0, y, 0);
    cone.scale(1, .8, 1);
    parts.push(paint(cone, i % 2 ? 0x2f5a3c : 0x3b6a46, .08, i + 3));
  });
  return mergeGeometries(parts)!;
}

/** Five-tier pagoda: red walls, dark upswept roofs, gold finial. */
function pagodaGeometry() {
  const parts: THREE.BufferGeometry[] = [paint(new THREE.BoxGeometry(2.4, .35, 2.4).translate(0, .17, 0), 0xbcb2a0)];
  let y = .35;
  for (let i = 0; i < 5; i++) {
    const w = 1.7 - i * .24, h = .9 - i * .06;
    parts.push(paint(new THREE.BoxGeometry(w, h, w).translate(0, y + h / 2, 0), 0xa8362c, .05, i));
    parts.push(paint(new THREE.BoxGeometry(w * .3, h * .55, w + .02).translate(0, y + h * .4, 0), 0x3a2018));
    y += h;
    const roof = new THREE.CylinderGeometry(w * .28, w * .98, .42, 4, 1).rotateY(Math.PI / 4);
    const p = roof.attributes.position;
    for (let k = 0; k < p.count; k++) if (p.getY(k) < 0) p.setY(k, p.getY(k) + .16); // eaves curl upward at the corners
    roof.translate(0, y + .14, 0);
    parts.push(paint(roof, 0x2c3a38, .06, i + 9));
    y += .32;
  }
  parts.push(paint(new THREE.ConeGeometry(.1, 1.1, 6).translate(0, y + .55, 0), 0xd9b24a));
  parts.push(paint(new THREE.SphereGeometry(.14, 8, 6).translate(0, y + .3, 0), 0xd9b24a));
  return mergeGeometries(parts.map((g) => (g.index ? g.toNonIndexed() : g)))!;
}

function pavilionGeometry() {
  const parts: THREE.BufferGeometry[] = [paint(new THREE.CylinderGeometry(1.5, 1.6, .3, 6).translate(0, .15, 0), 0xbcb2a0)];
  for (let i = 0; i < 6; i++) { const a = i / 6 * TAU; parts.push(paint(new THREE.CylinderGeometry(.07, .07, 1.5, 6).translate(Math.cos(a) * 1.2, 1.05, Math.sin(a) * 1.2), 0xa8362c)); }
  const roof = new THREE.ConeGeometry(2.1, 1.1, 6, 1);
  const p = roof.attributes.position;
  for (let k = 0; k < p.count; k++) if (p.getY(k) < 0) p.setY(k, p.getY(k) + .25);
  parts.push(paint(roof.translate(0, 2.3, 0), 0x2c3a38, .05, 4));
  parts.push(paint(new THREE.SphereGeometry(.13, 8, 6).translate(0, 2.95, 0), 0xd9b24a));
  return mergeGeometries(parts.map((g) => (g.index ? g.toNonIndexed() : g)))!;
}

function waterfall(height: number, width: number) {
  const mat = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 } }, transparent: true, depthWrite: false, side: THREE.DoubleSide,
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }',
    fragmentShader: `uniform float time; varying vec2 vUv; ${NOISE}
      void main(){ float s = fbm(vec2(vUv.x * 9., vUv.y * 2.2 + time * 1.6));
        float streak = smoothstep(.35, .8, s);
        float edge = smoothstep(0., .25, vUv.x) * smoothstep(1., .75, vUv.x);
        float a = (.35 + streak * .6) * edge * smoothstep(0., .3, vUv.y) * smoothstep(1., .96, vUv.y);
        gl_FragColor = vec4(mix(vec3(.72, .84, .9), vec3(1.), streak), a * .85); }`,
  });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, height, 1, 8), mat);
  return mesh;
}

/** Inverted rocky cone with a grassy crown. */
function isleGeometry(seed: number) {
  const r = rng(seed);
  const rock = new THREE.ConeGeometry(6, 9, 14, 6).rotateX(Math.PI).translate(0, -4.5, 0);
  const p = rock.attributes.position;
  for (let i = 0; i < p.count; i++) { const k = r.range(.8, 1.2); p.setX(i, p.getX(i) * k); p.setZ(i, p.getZ(i) * k); }
  const top = new THREE.CylinderGeometry(6.2, 6, .8, 14).translate(0, .1, 0);
  return mergeGeometries([paint(rock, 0x8f7f68, .1, seed), paint(top, 0x6a9a50, .08, seed + 1)].map((g) => { g.computeVertexNormals(); return g; }))!;
}

function birds(count: number, seed: number) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array([0, 0, .25, -.9, 0, -.1, 0, 0, -.25, 0, 0, .25, .9, 0, -.1, 0, 0, -.25]), 3));
  const phase = new Float32Array(count), r = rng(seed);
  for (let i = 0; i < count; i++) phase[i] = r.range(0, TAU);
  geo.setAttribute('phase', new THREE.InstancedBufferAttribute(phase, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 } }, side: THREE.DoubleSide,
    vertexShader: `uniform float time; attribute float phase;
      void main(){ vec3 p = position; p.y += abs(p.x) * sin(time * 9. + phase) * .7; gl_Position = projectionMatrix * modelViewMatrix * instanceMatrix * vec4(p, 1.); }`,
    fragmentShader: 'void main(){ gl_FragColor = vec4(.16, .18, .2, 1.); }',
  });
  const mesh = new THREE.InstancedMesh(geo, mat, count);
  mesh.frustumCulled = false;
  return { mesh, phase };
}

export interface Environment { group: THREE.Group; update(t: number, dt: number): void; obstacles: { x: number; z: number; r: number; top: number }[]; setDetail(low: boolean): void }

/** Pillars inside the arena, flanking the far side beyond the foe (stage 4: something real to fly around).
 *  Kept off the shoulder-camera corridor (+z) and outside the wide shot's early orbit. */
export const ARENA_PILLARS = [{ x: -15, z: -15, r: 3.4, top: 9 }, { x: 17, z: -19, r: 3.9, top: 5 }, { x: -6, z: -34, r: 4.2, top: 14 }];

export function buildEnvironment(scene: THREE.Scene, quality: number): Environment {
  const group = new THREE.Group();
  scene.add(group);
  scene.fog = new THREE.FogExp2(PALETTE.haze, FOG_DENSITY);
  scene.background = PALETTE.horizon;
  setInkFog(PALETTE.haze, FOG_DENSITY);

  const sky = skyDome(); sky.renderOrder = -10; group.add(sky);
  const seaLow = cloudSea(-46, .006, 1, .012), seaHigh = cloudSea(-30, .011, .55, .02);
  group.add(seaLow, seaHigh);

  const hemi = new THREE.HemisphereLight(0xe8f2ff, 0x8a8574, 1.25);
  const sun = new THREE.DirectionalLight(PALETTE.sun, 2.1);
  sun.position.copy(SUN_DIR).multiplyScalar(50);
  group.add(hemi, sun);

  const r = rng(20261021);
  const pillarMat = toon(0xffffff, { vertexColors: true, rim: 0xfff0d0, rimPower: 4 });
  const variants = [0, 1, 2, 3].map((k) => pillarGeometry(100 + k, 1, 1));
  const obstacles: Environment['obstacles'] = [];
  const pillarSlots: { pos: THREE.Vector3; radius: number; height: number }[] = [];
  const count = quality >= 2 ? 46 : quality === 1 ? 34 : 22;
  for (let i = 0; i < count; i++) {
    // keep a clear stage around the duel (origin) and the shoulder camera behind the hero (+z)
    let x = 0, z = 0;
    for (let tries = 0; tries < 30; tries++) {
      const ang = r.range(0, TAU), dist = i < 10 ? r.range(48, 90) : r.range(80, 330);
      x = Math.cos(ang) * dist; z = Math.sin(ang) * dist - 3;
      const inShot = Math.hypot(x, z + 3) < 44 || (z > 0 && Math.abs(x) < 36);
      if (!inShot && !pillarSlots.some((s) => Math.hypot(s.pos.x - x, s.pos.z - z) < s.radius + 9)) break;
    }
    const radius = r.range(3, 7.5) * (i < 10 ? .9 : 1.2), top = r.range(-18, 26) + (i < 10 ? 0 : r.range(0, 20));
    const height = top + 90;
    pillarSlots.push({ pos: V(x, -90, z), radius, height });
    obstacles.push({ x, z, r: radius * 1.2, top });
  }
  for (const p of ARENA_PILLARS) { pillarSlots.push({ pos: V(p.x, -90, p.z), radius: p.r / 1.2, height: p.top + 90 }); obstacles.push({ ...p }); }
  const meshes = variants.map((geo) => new THREE.InstancedMesh(geo, pillarMat, pillarSlots.length));
  const counts = [0, 0, 0, 0], m = new THREE.Matrix4(), q = new THREE.Quaternion();
  pillarSlots.forEach((s, i) => {
    const k = i % 4;
    q.setFromAxisAngle(V(0, 1, 0), r.range(0, TAU));
    m.compose(s.pos, q, V(s.radius, s.height, s.radius));
    meshes[k].setMatrixAt(counts[k]++, m);
  });
  meshes.forEach((mesh, k) => { mesh.count = counts[k]; mesh.computeBoundingSphere(); group.add(mesh); });

  // crowns: pines on every summit, pagodas and pavilions on a few, waterfalls down some faces
  const pineMat = toon(0xffffff, { vertexColors: true, rim: 0xe8ffd8 });
  const pines = new THREE.InstancedMesh(pineGeometry(), pineMat, count * 5 + 40);
  const pagodas = new THREE.InstancedMesh(pagodaGeometry(), toon(0xffffff, { vertexColors: true }), 8);
  const pavilions = new THREE.InstancedMesh(pavilionGeometry(), toon(0xffffff, { vertexColors: true }), 8);
  let nPine = 0, nPagoda = 0, nPavilion = 0;
  const falls: THREE.Mesh[] = [];
  const placeTree = (x: number, y: number, z: number, s: number) => {
    if (nPine >= pines.count) return;
    m.compose(V(x, y, z), q.setFromAxisAngle(V(0, 1, 0), r.range(0, TAU)), V(s, s * r.range(.85, 1.25), s));
    pines.setMatrixAt(nPine++, m);
  };
  pillarSlots.forEach((s, i) => {
    const top = s.pos.y + s.height;
    const trees = Math.round(s.radius * .7) + 1;
    for (let k = 0; k < trees; k++) { const a = r.range(0, TAU), d = r.range(.2, .8) * s.radius; placeTree(s.pos.x + Math.cos(a) * d, top + .1, s.pos.z + Math.sin(a) * d, r.range(.9, 1.7)); }
    const rot = q.setFromAxisAngle(V(0, 1, 0), r.range(0, TAU));
    if (i % 5 === 1 && nPagoda < 8) { m.compose(V(s.pos.x, top + .3, s.pos.z), rot, V(1.3, 1.3, 1.3)); pagodas.setMatrixAt(nPagoda++, m); }
    else if (i % 5 === 3 && nPavilion < 8) { m.compose(V(s.pos.x, top + .3, s.pos.z), rot, V(1.1, 1.1, 1.1)); pavilions.setMatrixAt(nPavilion++, m); }
    if (i % 4 === 2 && falls.length < 6) {
      const fall = waterfall(Math.min(60, s.height * .6), s.radius * .45);
      const face = Math.atan2(-s.pos.x, 30 - s.pos.z); // turn toward the stage
      fall.position.set(s.pos.x + Math.sin(face) * s.radius * .98, top - Math.min(60, s.height * .6) / 2, s.pos.z + Math.cos(face) * s.radius * .98);
      fall.rotation.y = face;
      falls.push(fall); group.add(fall);
    }
  });
  pines.count = nPine; pagodas.count = nPagoda; pavilions.count = nPavilion;
  [pines, pagodas, pavilions].forEach((mesh) => { mesh.computeBoundingSphere(); group.add(mesh); });

  // floating isles drifting at fighter altitude, each with a pavilion and pines
  const isleMat = toon(0xffffff, { vertexColors: true });
  const isles = [0, 1, 2, 3, 4].map((k) => {
    const isle = new THREE.Group();
    isle.add(inked(new THREE.Mesh(isleGeometry(300 + k), isleMat), .05));
    const pav = new THREE.Mesh(k % 2 ? pavilionGeometry() : pineGeometry(), isleMat);
    pav.scale.setScalar(k % 2 ? .9 : 1.4); pav.position.y = .5; isle.add(pav);
    const ang = [-.9, -2.3, 1.9, 3.0, -1.5][k], dist = [52, 58, 80, 95, 74][k];
    isle.position.set(Math.cos(ang) * dist, [6, -4, 14, 2, 20][k], Math.sin(ang) * dist - 10);
    isle.scale.setScalar([.8, 1.1, 1.4, 1.8, 1.2][k]);
    isle.userData.base = isle.position.y;
    group.add(isle);
    return isle;
  });

  // distant ranges: layered silhouettes that melt into the haze
  {
    const geo = new THREE.ConeGeometry(1, 1, 7, 4);
    const p = geo.attributes.position;
    for (let i = 0; i < p.count; i++) if (Math.abs(p.getY(i)) < .49) { p.setX(i, p.getX(i) * r.range(.7, 1.3)); p.setZ(i, p.getZ(i) * r.range(.7, 1.3)); }
    geo.computeVertexNormals();
    const mat = new THREE.MeshLambertMaterial({ color: 0x7f97a8, flatShading: true });
    const ranges = new THREE.InstancedMesh(geo, mat, 40);
    for (let i = 0; i < 40; i++) {
      const ang = r.range(0, TAU), dist = r.range(420, 640), h = r.range(70, 170);
      m.compose(V(Math.cos(ang) * dist, -60 + h * .45, Math.sin(ang) * dist), q.identity(), V(h * r.range(.35, .6), h, h * r.range(.35, .6)));
      ranges.setMatrixAt(i, m);
    }
    group.add(ranges);
  }

  const puffs = billboardClouds(quality >= 1 ? 70 : 36, 9, (rr) => {
    const ang = rr.range(0, TAU), dist = rr.range(45, 420);
    return [V(Math.cos(ang) * dist, rr.range(-38, -16), Math.sin(ang) * dist - 20), rr.range(40, 110)];
  });
  group.add(puffs);

  const flock = birds(14, 33);
  group.add(flock.mesh);
  const birdM = new THREE.Matrix4(), birdQ = new THREE.Quaternion();

  const animated = [sky.material, seaLow.material, seaHigh.material, flock.mesh.material, ...falls.map((f) => f.material)] as THREE.ShaderMaterial[];
  return {
    group, obstacles,
    /** Low detail drops the far billboard clouds, the bird flock and the waterfalls (quality ladder). */
    setDetail(low) { puffs.visible = !low; flock.mesh.visible = !low; falls.forEach((f) => { f.visible = !low; }); },
    update(t) {
      for (const mat of animated) mat.uniforms.time.value = t;
      isles.forEach((isle, k) => { isle.position.y = isle.userData.base + Math.sin(t * .35 + k) * 1.2; isle.rotation.y = t * .01 * (k % 2 ? 1 : -1); });
      for (let i = 0; i < 14; i++) {
        const a = t * .05 + flock.phase[i] * .3, rad = 70 + (i % 5) * 6;
        const pos = V(Math.cos(a) * rad + 30, 22 + Math.sin(t * .4 + i) * 2 + (i % 3) * 2, Math.sin(a) * rad - 90);
        birdQ.setFromAxisAngle(V(0, 1, 0), -a);
        birdM.compose(pos, birdQ, V(1.4, 1.4, 1.4));
        flock.mesh.setMatrixAt(i, birdM);
      }
      flock.mesh.instanceMatrix.needsUpdate = true;
    },
  };
}
