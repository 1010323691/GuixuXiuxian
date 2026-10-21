// Procedural spell effects. Every effect is a short-lived object driven by update(dt) → alive?
// Particles use three.quarks; trails, glyph circles, talismans, shields and slashes are custom geometry/shaders.
import * as THREE from 'three';
import {
  BatchedRenderer, ParticleSystem, ParticleEmitter, RenderMode, SphereEmitter, ConeEmitter, IntervalValue, ConstantValue, ColorRange,
  ColorOverLife, SizeOverLife, Gradient, PiecewiseBezier, Bezier, ApplyForce, Vector4, Vector3 as QVector3, SpeedOverLife,
} from 'three.quarks';
import { makeSword } from './actors';
import { artSword, type ArtSet } from './art';
import { C, V, TAU, GLYPHS, canvasTexture, clamp, easeIn, easeInOut, easeOut, glowMat, lerp, rng, smooth, softDot } from './util';

export interface Effect { update(dt: number): boolean; dispose?(): void }

// ------------------------------------------------------------------ textures
const tex = {
  dot: null as THREE.Texture | null,
  spark: null as THREE.Texture | null,
  smoke: null as THREE.Texture | null,
  circle: null as THREE.Texture | null,
  circleInner: null as THREE.Texture | null,
  talisman: null as THREE.Texture | null,
  bagua: null as THREE.Texture | null,
};
function textures() {
  tex.dot ??= softDot();
  tex.spark ??= canvasTexture(64, 64, (g) => {
    const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    r.addColorStop(0, '#fff'); r.addColorStop(.15, 'rgba(255,255,255,.9)'); r.addColorStop(.4, 'rgba(255,255,255,.25)'); r.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = r; g.fillRect(0, 0, 64, 64);
  });
  tex.smoke ??= canvasTexture(128, 128, (g) => {
    const r = rng(5);
    for (let i = 0; i < 14; i++) {
      const x = r.range(36, 92), y = r.range(36, 92), rad = r.range(18, 36);
      const grd = g.createRadialGradient(x, y, 0, x, y, rad);
      grd.addColorStop(0, 'rgba(255,255,255,.35)'); grd.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = grd; g.fillRect(0, 0, 128, 128);
    }
  });
  tex.circle ??= canvasTexture(1024, 1024, (g, w) => { // the outer array: rings, glyph band, star polygon
    const c = w / 2;
    g.translate(c, c);
    g.strokeStyle = '#fff'; g.fillStyle = '#fff'; g.shadowColor = '#fff'; g.shadowBlur = 10;
    const ring = (r: number, lw: number) => { g.lineWidth = lw; g.beginPath(); g.arc(0, 0, r, 0, TAU); g.stroke(); };
    ring(500, 6); ring(482, 2); ring(400, 3); ring(386, 1.5); ring(250, 4);
    g.font = 'bold 54px "KaiTi","STKaiti","SimSun",serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
    const n = 24;
    for (let i = 0; i < n; i++) { g.save(); g.rotate(i / n * TAU); g.fillText(GLYPHS[i % GLYPHS.length], 0, -441); g.restore(); }
    g.lineWidth = 3;
    for (const step of [2, 3]) { // two interlaced heptagrams
      g.beginPath();
      for (let i = 0; i <= 7; i++) { const a = (i * step) / 7 * TAU - Math.PI / 2; const x = Math.cos(a) * 386, y = Math.sin(a) * 386; if (i) g.lineTo(x, y); else g.moveTo(x, y); }
      g.stroke();
    }
    for (let i = 0; i < 72; i++) { g.save(); g.rotate(i / 72 * TAU); g.fillRect(-1.5, -500, 3, i % 6 ? 10 : 22); g.restore(); }
  });
  tex.circleInner ??= canvasTexture(512, 512, (g, w) => { // the inner core: trigrams around a taiji-like eye
    const c = w / 2;
    g.translate(c, c);
    g.strokeStyle = '#fff'; g.fillStyle = '#fff'; g.shadowColor = '#fff'; g.shadowBlur = 8;
    g.lineWidth = 4; g.beginPath(); g.arc(0, 0, 240, 0, TAU); g.stroke();
    g.lineWidth = 2; g.beginPath(); g.arc(0, 0, 120, 0, TAU); g.stroke();
    for (let i = 0; i < 8; i++) {
      g.save(); g.rotate(i / 8 * TAU);
      for (let k = 0; k < 3; k++) { const broken = (i >> k) & 1; const y = -200 + k * 22; if (broken) { g.fillRect(-46, y, 36, 10); g.fillRect(10, y, 36, 10); } else g.fillRect(-46, y, 92, 10); }
      g.restore();
    }
    g.beginPath(); g.arc(0, 0, 40, 0, TAU); g.fill();
  });
  tex.talisman ??= canvasTexture(128, 320, (g, w, h) => { // yellow paper, cinnabar strokes
    g.fillStyle = '#f2cf5a'; g.fillRect(0, 0, w, h);
    g.strokeStyle = '#b8332a'; g.lineWidth = 6; g.strokeRect(8, 8, w - 16, h - 16);
    g.fillStyle = '#b8332a'; g.font = 'bold 50px "KaiTi","STKaiti","SimSun",serif'; g.textAlign = 'center';
    g.fillText('敕', w / 2, 80); g.fillText('令', w / 2, 140);
    g.lineWidth = 5; g.beginPath(); g.moveTo(w / 2, 160);
    for (let i = 0; i < 6; i++) g.lineTo(w / 2 + (i % 2 ? 26 : -26), 175 + i * 22);
    g.stroke();
    g.font = 'bold 34px serif'; g.fillText('雷', w / 2, 300);
  });
  tex.bagua ??= canvasTexture(512, 512, (g, w) => { // bronze mirror: eight trigrams around a polished face
    const c = w / 2;
    g.translate(c, c);
    const bronze = g.createRadialGradient(0, -40, 20, 0, 0, 250);
    bronze.addColorStop(0, '#fff4c8'); bronze.addColorStop(.5, '#e2b450'); bronze.addColorStop(1, '#8a5a1a');
    g.fillStyle = bronze; g.beginPath();
    for (let i = 0; i < 8; i++) { const a = i / 8 * TAU + TAU / 16; g[i ? 'lineTo' : 'moveTo'](Math.cos(a) * 250, Math.sin(a) * 250); }
    g.closePath(); g.fill();
    g.fillStyle = '#5a3410';
    for (let i = 0; i < 8; i++) {
      g.save(); g.rotate(i / 8 * TAU);
      for (let k = 0; k < 3; k++) { const broken = (i * 5 >> k) & 1; const y = -215 + k * 20; if (broken) { g.fillRect(-42, y, 34, 10); g.fillRect(8, y, 34, 10); } else g.fillRect(-42, y, 84, 10); }
      g.restore();
    }
    const face = g.createRadialGradient(-30, -40, 10, 0, 0, 130);
    face.addColorStop(0, '#ffffff'); face.addColorStop(.4, '#dff4ff'); face.addColorStop(1, '#7fa6b8');
    g.fillStyle = face; g.beginPath(); g.arc(0, 0, 128, 0, TAU); g.fill();
    g.strokeStyle = '#5a3410'; g.lineWidth = 8; g.stroke();
  });
  return tex as { [K in keyof typeof tex]: THREE.Texture };
}
export function disposeTextures() { for (const k of Object.keys(tex) as (keyof typeof tex)[]) { tex[k]?.dispose(); tex[k] = null; } }

// ------------------------------------------------------------------ trails
/** Camera-facing ribbon that remembers its head's recent positions. */
export class Trail {
  readonly mesh: THREE.Mesh;
  private pts: THREE.Vector3[] = [];
  private geo = new THREE.BufferGeometry();
  private mat: THREE.ShaderMaterial;
  constructor(private n: number, private width: number, color: THREE.ColorRepresentation, intensity = 2.2) {
    this.geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 2 * 3), 3));
    const along = new Float32Array(n * 2), across = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) { along[i * 2] = along[i * 2 + 1] = i / (n - 1); across[i * 2] = -1; across[i * 2 + 1] = 1; }
    this.geo.setAttribute('along', new THREE.BufferAttribute(along, 1));
    this.geo.setAttribute('across', new THREE.BufferAttribute(across, 1));
    const index: number[] = [];
    for (let i = 0; i < n - 1; i++) { const k = i * 2; index.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
    this.geo.setIndex(index);
    this.mat = new THREE.ShaderMaterial({
      uniforms: { color: { value: C(color).multiplyScalar(intensity) }, fade: { value: 1 } },
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      vertexShader: 'attribute float along, across; varying float vA, vX; void main(){ vA = along; vX = across; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }',
      fragmentShader: `uniform vec3 color; uniform float fade; varying float vA, vX;
        void main(){ float head = clamp(1. - vA, 0., 1.); float core = clamp(1. - abs(vX), 0., 1.); float a = pow(head, 1.6) * smoothstep(0., .9, core) * fade;
          gl_FragColor = vec4(mix(color, vec3(2.4), pow(core, 6.) * head), a); }`,
    });
    this.mesh = new THREE.Mesh(this.geo, this.mat);
    this.mesh.frustumCulled = false;
  }
  set fade(v: number) { this.mat.uniforms.fade.value = v; }
  reset(p: THREE.Vector3) { this.pts = Array.from({ length: this.n }, () => p.clone()); }
  push(p: THREE.Vector3, camera: THREE.Camera) {
    if (!this.pts.length) this.reset(p);
    const last = this.pts.pop()!; last.copy(p); this.pts.unshift(last);
    const pos = this.geo.attributes.position as THREE.BufferAttribute, dir = V(), toCam = V(), side = V();
    for (let i = 0; i < this.n; i++) {
      const a = this.pts[Math.max(0, i - 1)], b = this.pts[Math.min(this.n - 1, i + 1)];
      dir.subVectors(a, b); toCam.subVectors(camera.position, this.pts[i]);
      side.crossVectors(dir, toCam).normalize().multiplyScalar(this.width * (1 - i / this.n * .7));
      if (!Number.isFinite(side.x)) side.set(0, 0, 0);
      const q = this.pts[i];
      pos.setXYZ(i * 2, q.x - side.x, q.y - side.y, q.z - side.z);
      pos.setXYZ(i * 2 + 1, q.x + side.x, q.y + side.y, q.z + side.z);
    }
    pos.needsUpdate = true;
  }
  dispose() { this.geo.dispose(); this.mat.dispose(); }
}

// ------------------------------------------------------------------ the effects host
export interface FxHooks { shake(amount: number): void; hitstop(seconds: number): void; flash(amount: number, color?: THREE.ColorRepresentation): void; aberrate(amount: number): void }

export class FxSystem {
  readonly group = new THREE.Group();
  readonly quarks = new BatchedRenderer();
  private live: Effect[] = [];
  private pools = new Map<string, { systems: ParticleSystem[]; next: number }>();
  private looping: ParticleSystem[] = [];
  private art: ArtSet | null = null;
  /** Use the painted sword, talisman, glyph circle and jade pendant instead of the procedural ones. */
  setArt(art: ArtSet) { this.art = art; }
  private sword(color: THREE.ColorRepresentation, scale: number) { return this.art ? artSword(this.art, color, 2.4 * scale) : makeSword(color, scale); }
  private shared = { ringGeo: new THREE.RingGeometry(.9, 1, 64), planeGeo: new THREE.PlaneGeometry(1, 1), sphereGeo: new THREE.SphereGeometry(1, 32, 20) };

  constructor(scene: THREE.Scene, private camera: THREE.Camera, private hooks: FxHooks, private reduced: boolean) {
    textures();
    scene.add(this.group, this.quarks);
    this.makePool('spark', 6, (color) => this.sparkSystem(color));
    this.makePool('smoke', 4, () => this.smokeSystem());
    this.makePool('ember', 4, (color) => this.emberBurst(color));
  }

  get count() { return this.live.length; }
  add(effect: Effect) { this.live.push(effect); return effect; }

  update(dt: number) {
    for (let i = this.live.length - 1; i >= 0; i--) if (!this.live[i].update(dt)) { this.live[i].dispose?.(); this.live.splice(i, 1); }
    this.quarks.update(dt);
  }

  clear() {
    for (const e of this.live) e.dispose?.();
    this.live = [];
    for (const { systems } of this.pools.values()) for (const s of systems) s.stop();
  }

  dispose() {
    this.clear();
    for (const { systems } of this.pools.values()) for (const s of systems) { this.quarks.deleteSystem(s); s.dispose(); }
    for (const s of this.looping) { this.quarks.deleteSystem(s); s.dispose(); }
    Object.values(this.shared).forEach((g) => g.dispose());
    disposeTextures();
  }

  // ---------------------------------------------------------------- quarks particle pools
  private makePool(name: string, size: number, make: (color: THREE.Color) => ParticleSystem) {
    const systems = Array.from({ length: size }, () => { const s = make(C(0xffffff)); s.stop(); this.quarks.addSystem(s); this.group.add(s.emitter); return s; });
    this.pools.set(name, { systems, next: 0 });
  }
  private fire(name: string, at: THREE.Vector3, color: THREE.ColorRepresentation, scale = 1) {
    const pool = this.pools.get(name)!;
    const sys = pool.systems[pool.next];
    pool.next = (pool.next + 1) % pool.systems.length;
    const c = C(color);
    sys.startColor = new ColorRange(new Vector4(c.r * 3, c.g * 3, c.b * 3, 1), new Vector4(2.6, 2.6, 2.6, 1));
    if (name === 'smoke') sys.startColor = new ColorRange(new Vector4(c.r, c.g, c.b, .55), new Vector4(c.r * .7, c.g * .7, c.b * .7, .35));
    sys.emitter.position.copy(at);
    sys.emitter.scale.setScalar(scale);
    sys.restart();
  }
  sparks(at: THREE.Vector3, color: THREE.ColorRepresentation, scale = 1) { this.fire('spark', at, color, scale); }
  smoke(at: THREE.Vector3, color: THREE.ColorRepresentation = 0x2a2226, scale = 1) { this.fire('smoke', at, color, scale); }
  embers(at: THREE.Vector3, color: THREE.ColorRepresentation, scale = 1) { this.fire('ember', at, color, scale); }

  private sparkSystem(color: THREE.Color) {
    return new ParticleSystem({
      duration: 1, looping: false, worldSpace: true, autoDestroy: false,
      startLife: new IntervalValue(.25, .7), startSpeed: new IntervalValue(8, 26), startSize: new IntervalValue(.08, .22), startLength: new IntervalValue(.4, 1.4),
      startColor: new ColorRange(new Vector4(color.r, color.g, color.b, 1), new Vector4(1, 1, 1, 1)),
      emissionOverTime: new ConstantValue(0), emissionBursts: [{ time: 0, count: new ConstantValue(this.reduced ? 18 : 46), cycle: 1, interval: .01, probability: 1 }],
      shape: new SphereEmitter({ radius: .3 }),
      material: new THREE.MeshBasicMaterial({ map: textures().spark, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false }),
      renderMode: RenderMode.StretchedBillBoard, rendererEmitterSettings: { speedFactor: .04, lengthFactor: 1 } as never,
      behaviors: [new SpeedOverLife(new PiecewiseBezier([[new Bezier(1, .5, .2, 0), 0]])), new ApplyForce(new QVector3(0, -1, 0), new ConstantValue(10)), new SizeOverLife(new PiecewiseBezier([[new Bezier(1, .8, .4, 0), 0]]))],
    });
  }
  private smokeSystem() {
    return new ParticleSystem({
      duration: 1, looping: false, worldSpace: true,
      startLife: new IntervalValue(1.2, 2.2), startSpeed: new IntervalValue(1, 4), startSize: new IntervalValue(2, 4.5), startRotation: new IntervalValue(0, TAU),
      startColor: new ColorRange(new Vector4(.3, .25, .25, .5), new Vector4(.2, .18, .2, .3)),
      emissionOverTime: new ConstantValue(0), emissionBursts: [{ time: 0, count: new ConstantValue(this.reduced ? 6 : 14), cycle: 1, interval: .01, probability: 1 }],
      shape: new SphereEmitter({ radius: 1 }),
      material: new THREE.MeshBasicMaterial({ map: textures().smoke, transparent: true, depthWrite: false }),
      renderMode: RenderMode.BillBoard,
      behaviors: [new SizeOverLife(new PiecewiseBezier([[new Bezier(.6, 1, 1.3, 1.6), 0]])), new ColorOverLife(new Gradient([[new QVector3(1, 1, 1), 0], [new QVector3(1, 1, 1), 1]], [[0, 0], [1, .15], [0, 1]]))],
    });
  }
  private emberBurst(color: THREE.Color) {
    return new ParticleSystem({
      duration: 1, looping: false, worldSpace: true,
      startLife: new IntervalValue(.8, 1.8), startSpeed: new IntervalValue(2, 9), startSize: new IntervalValue(.12, .35),
      startColor: new ColorRange(new Vector4(color.r, color.g, color.b, 1), new Vector4(1, 1, 1, 1)),
      emissionOverTime: new ConstantValue(0), emissionBursts: [{ time: 0, count: new ConstantValue(this.reduced ? 14 : 36), cycle: 1, interval: .01, probability: 1 }],
      shape: new SphereEmitter({ radius: 1.2 }),
      material: new THREE.MeshBasicMaterial({ map: textures().dot, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false }),
      renderMode: RenderMode.BillBoard,
      behaviors: [new ApplyForce(new QVector3(0, 1, 0), new ConstantValue(3)), new SizeOverLife(new PiecewiseBezier([[new Bezier(1, .9, .5, 0), 0]]))],
    });
  }

  /** A continuous emitter that follows an object (demon aura, mount wake). */
  attachAura(target: THREE.Object3D, opts: { color: THREE.ColorRepresentation; rate: number; radius: number; rise: number; size: [number, number]; smoke?: boolean; offset?: THREE.Vector3 }) {
    const c = C(opts.color);
    const sys = new ParticleSystem({
      duration: 5, looping: true, worldSpace: true,
      startLife: new IntervalValue(.8, 1.8), startSpeed: new IntervalValue(.2, 1.2), startSize: new IntervalValue(opts.size[0], opts.size[1]), startRotation: new IntervalValue(0, TAU),
      startColor: opts.smoke ? new ColorRange(new Vector4(c.r, c.g, c.b, .5), new Vector4(c.r * .6, c.g * .6, c.b * .6, .3)) : new ColorRange(new Vector4(c.r * 2.5, c.g * 2.5, c.b * 2.5, 1), new Vector4(c.r * 1.2, c.g * 1.2, c.b * 1.2, 1)),
      emissionOverTime: new ConstantValue(this.reduced ? opts.rate * .4 : opts.rate),
      shape: new SphereEmitter({ radius: opts.radius }),
      material: new THREE.MeshBasicMaterial({ map: opts.smoke ? textures().smoke : textures().dot, blending: opts.smoke ? THREE.NormalBlending : THREE.AdditiveBlending, transparent: true, depthWrite: false }),
      renderMode: RenderMode.BillBoard,
      behaviors: [
        new ApplyForce(new QVector3(0, 1, 0), new ConstantValue(opts.rise)),
        new SizeOverLife(new PiecewiseBezier([[new Bezier(opts.smoke ? .5 : 1, opts.smoke ? 1 : .8, opts.smoke ? 1.3 : .4, opts.smoke ? 1.5 : 0), 0]])),
        new ColorOverLife(new Gradient([[new QVector3(1, 1, 1), 0], [new QVector3(1, 1, 1), 1]], [[0, 0], [1, .2], [0, 1]])),
      ],
    });
    if (opts.offset) sys.emitter.position.copy(opts.offset);
    target.add(sys.emitter);
    this.quarks.addSystem(sys);
    this.looping.push(sys);
    return sys;
  }

  /** Cone stream that shoots from a point toward a direction (beam spray, charge inflow). */
  stream(at: THREE.Vector3, dir: THREE.Vector3, color: THREE.ColorRepresentation, seconds: number) {
    const c = C(color);
    const sys = new ParticleSystem({
      duration: seconds, looping: false, worldSpace: true,
      startLife: new IntervalValue(.3, .6), startSpeed: new IntervalValue(14, 30), startSize: new IntervalValue(.1, .3), startLength: new IntervalValue(.6, 1.6),
      startColor: new ColorRange(new Vector4(c.r * 3, c.g * 3, c.b * 3, 1), new Vector4(2, 2, 2, 1)),
      emissionOverTime: new ConstantValue(this.reduced ? 30 : 90),
      shape: new ConeEmitter({ radius: .5, angle: .25 }),
      material: new THREE.MeshBasicMaterial({ map: textures().spark, blending: THREE.AdditiveBlending, transparent: true, depthWrite: false }),
      renderMode: RenderMode.StretchedBillBoard, rendererEmitterSettings: { speedFactor: .05, lengthFactor: 1 } as never,
      behaviors: [new SizeOverLife(new PiecewiseBezier([[new Bezier(1, .8, .4, 0), 0]]))],
    });
    const emitter = sys.emitter as ParticleEmitter;
    emitter.position.copy(at);
    emitter.quaternion.setFromUnitVectors(V(0, 0, 1), dir.clone().normalize());
    this.group.add(emitter);
    this.quarks.addSystem(sys);
    let t = 0;
    return this.add({
      update: (dt) => { t += dt; return t < seconds + .8; },
      dispose: () => { this.quarks.deleteSystem(sys); this.group.remove(emitter); sys.dispose(); },
    });
  }

  // ---------------------------------------------------------------- building blocks
  /** Expanding additive shell with fresnel rim (shockwave, burst). */
  shockwave(at: THREE.Vector3, color: THREE.ColorRepresentation, radius: number, seconds = .6, flat = false) {
    const mat = new THREE.ShaderMaterial({
      uniforms: { color: { value: C(color).multiplyScalar(2.2) }, life: { value: 0 } },
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      vertexShader: 'varying vec3 vN, vV; void main(){ vec4 mv = modelViewMatrix * vec4(position, 1.); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }',
      fragmentShader: `uniform vec3 color; uniform float life; varying vec3 vN, vV;
        void main(){ float f = pow(clamp(1. - abs(dot(vN, vV)), 0., 1.), 2.5); gl_FragColor = vec4(color, f * (1. - life) * 1.2); }`,
    });
    const mesh = new THREE.Mesh(flat ? this.shared.ringGeo : this.shared.sphereGeo, flat ? glowRingMat(color) : mat);
    mesh.position.copy(at);
    if (flat) mesh.lookAt(this.camera.position);
    this.group.add(mesh);
    let t = 0;
    return this.add({
      update: (dt) => {
        t += dt; const u = t / seconds;
        mesh.scale.setScalar(.2 + easeOut(u) * radius);
        if (flat) (mesh.material as THREE.MeshBasicMaterial).opacity = 1 - u; else mat.uniforms.life.value = u;
        return u < 1;
      },
      dispose: () => { this.group.remove(mesh); (mesh.material as THREE.Material).dispose(); mat.dispose(); },
    });
  }

  glowBurst(at: THREE.Vector3, color: THREE.ColorRepresentation, size: number, seconds = .45) {
    const sprite = new THREE.Sprite(glowMat(C(color).multiplyScalar(3), textures().dot));
    sprite.position.copy(at);
    this.group.add(sprite);
    let t = 0;
    return this.add({
      update: (dt) => { t += dt; const u = t / seconds; sprite.scale.setScalar(size * (.4 + easeOut(u) * .8)); sprite.material.opacity = 1 - u; return u < 1; },
      dispose: () => { this.group.remove(sprite); sprite.material.dispose(); },
    });
  }

  /** Full impact package: glow, shockwave, sparks, camera feedback. */
  impact(at: THREE.Vector3, color: THREE.ColorRepresentation, power = 1) {
    this.glowBurst(at, color, 3 + power * 4);
    this.shockwave(at, color, 2 + power * 3, .5);
    this.shockwave(at, color, 3 + power * 4, .7, true);
    this.sparks(at, color, .6 + power * .5);
    if (power > .8) this.smoke(at, 0x8f8a8a, .6 + power * .4);
    this.hooks.shake(.15 + power * .35);
    this.hooks.hitstop(power > .9 ? .09 : .045);
    this.hooks.aberrate(.004 + power * .006);
    if (power > 1.2) this.hooks.flash(.35, color);
  }

  // ---------------------------------------------------------------- signature spells
  /** 剑阵: swords fan out behind the caster, then dive at the target along curved paths. */
  swordSwarm(from: () => THREE.Vector3, back: () => THREE.Vector3, target: () => THREE.Vector3, color: THREE.ColorRepresentation, count: number, onHit: (i: number) => void) {
    const r = rng(77);
    const swords = Array.from({ length: count }, (_, i) => {
      const mesh = this.sword(color, .9);
      const trail = new Trail(22, .16, color);
      this.group.add(mesh, trail.mesh);
      const fan = (i / (count - 1) - .5) * 2;
      return { mesh, trail, fan, delay: .55 + i * .07 + r.range(0, .05), lift: r.range(1.2, 3.2), swing: r.range(.6, 1.4), hit: false, curve: null as THREE.CubicBezierCurve3 | null };
    });
    let t = 0;
    const p = V(), ahead = V();
    return this.add({
      update: (dt) => {
        t += dt;
        const origin = from(), behind = back(), aim = target();
        let alive = false;
        for (const s of swords) {
          const fanPos = V(behind.x, behind.y + 1.2 + Math.abs(s.fan) * -.4 + s.lift * .25, behind.z).add(V(-(aim.z - origin.z), 0, aim.x - origin.x).normalize().multiplyScalar(s.fan * 3.2));
          if (t < s.delay) { // materialise into the fan, hilts toward the caster
            const u = easeOut(t / .5);
            p.lerpVectors(origin, fanPos, u);
            s.mesh.position.copy(p); s.mesh.scale.setScalar(Math.max(.02, .9 * u));
            s.mesh.lookAt(aim); s.mesh.rotateY(-Math.PI / 2);
            s.trail.push(p, this.camera);
            alive = true;
            continue;
          }
          if (!s.curve) {
            const side = V(-(aim.z - fanPos.z), 0, aim.x - fanPos.x).normalize().multiplyScalar(s.fan * 9 * s.swing);
            s.curve = new THREE.CubicBezierCurve3(fanPos.clone(), fanPos.clone().add(V(0, s.lift * 2, 0)).add(side), aim.clone().add(side.multiplyScalar(.6)).add(V(0, s.lift * 3, 0)), aim.clone());
          }
          s.curve.v3.copy(aim);
          const u = clamp((t - s.delay) / .75);
          if (u >= 1) {
            if (!s.hit) { s.hit = true; s.mesh.visible = false; onHit(swords.indexOf(s)); }
            s.trail.fade = Math.max(0, 1 - (t - s.delay - .75) * 3);
            s.trail.push(aim, this.camera);
            if (t - s.delay < 1.2) alive = true;
            continue;
          }
          const k = easeIn(u) * .7 + u * .3;
          s.curve.getPoint(k, p); s.curve.getPoint(Math.min(1, k + .02), ahead);
          s.mesh.position.copy(p); s.mesh.lookAt(ahead); s.mesh.rotateY(-Math.PI / 2);
          s.trail.push(p, this.camera);
          alive = true;
        }
        return alive;
      },
      dispose: () => swords.forEach((s) => { this.group.remove(s.mesh, s.trail.mesh); s.trail.dispose(); disposeTree(s.mesh); }),
    });
  }

  /** 符箓: paper talismans spin out in a fan, ignite and detonate in gold. */
  talismans(from: () => THREE.Vector3, target: () => THREE.Vector3, count: number, onHit: (i: number) => void) {
    const r = rng(13);
    const mat = new THREE.MeshBasicMaterial({ map: this.art?.talisman ?? textures().talisman, side: THREE.DoubleSide, transparent: true, color: C(0xffffff).multiplyScalar(this.art ? 1.4 : 1) });
    const items = Array.from({ length: count }, (_, i) => {
      const mesh = new THREE.Mesh(this.shared.planeGeo, mat);
      if (this.art) mesh.scale.set(.62, .62 / this.art.aspect.talisman, 1); else mesh.scale.set(.5, 1.25, 1);
      const halo = new THREE.Sprite(glowMat(C(0xffc850).multiplyScalar(2), textures().dot, .8));
      halo.scale.setScalar(1.6);
      mesh.add(halo);
      const trail = new Trail(16, .1, 0xffc040, 1.8);
      this.group.add(mesh, trail.mesh);
      return { mesh, trail, delay: i * .09, spread: (i / (count - 1) - .5) * 2, arc: r.range(1, 3), spin: r.range(9, 16), hit: false };
    });
    let t = 0;
    const p = V();
    return this.add({
      update: (dt) => {
        t += dt;
        const a = from(), b = target();
        let alive = false;
        for (const it of items) {
          const u = clamp((t - it.delay) / .9);
          if (u <= 0) { it.mesh.visible = false; alive = true; continue; }
          it.mesh.visible = !it.hit;
          if (u >= 1) {
            if (!it.hit) { it.hit = true; onHit(items.indexOf(it)); }
            it.trail.fade = Math.max(0, 1 - (t - it.delay - .9) * 4);
            if (t - it.delay < 1.3) alive = true;
            continue;
          }
          const side = V(-(b.z - a.z), 0, b.x - a.x).normalize().multiplyScalar(it.spread * 4 * Math.sin(u * Math.PI));
          p.lerpVectors(a, b, easeInOut(u)).add(side).add(V(0, Math.sin(u * Math.PI) * it.arc, 0));
          it.mesh.position.copy(p);
          it.mesh.rotation.set(t * it.spin * .3, t * it.spin, t * it.spin * .5);
          it.trail.push(p, this.camera);
          alive = true;
        }
        return alive;
      },
      dispose: () => { items.forEach((it) => { this.group.remove(it.mesh, it.trail.mesh); it.trail.dispose(); (it.mesh.children[0] as THREE.Sprite).material.dispose(); }); mat.dispose(); },
    });
  }

  /** 法阵: layered glyph circle that unfurls before the caster, spins up, then fires a beam. */
  runeCircle(center: () => THREE.Vector3, facing: () => THREE.Vector3, color: THREE.ColorRepresentation, size: number, seconds: number) {
    const col = C(color);
    const layers = [
      ...(this.art ? [{ map: this.art.circle, scale: 1.05, spin: .3, alpha: 1, tint: C(0xffffff).multiplyScalar(1.5) }] : [{ map: textures().circle, scale: 1, spin: .35, alpha: 1 }]),
      { map: textures().circleInner, scale: .5, spin: -.8, alpha: this.art ? .4 : 1 },
      { map: textures().circle, scale: 1.35, spin: -.15, alpha: .35 },
    ].map((l) => {
      const mat = new THREE.MeshBasicMaterial({ map: l.map, color: 'tint' in l ? (l.tint as THREE.Color) : col.clone().multiplyScalar(2.4), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
      const mesh = new THREE.Mesh(this.shared.planeGeo, mat);
      return { ...l, mesh, mat };
    });
    const holder = new THREE.Group();
    layers.forEach((l, i) => { l.mesh.position.z = i * -.05; holder.add(l.mesh); });
    const core = new THREE.Sprite(glowMat(col.clone().multiplyScalar(3), textures().dot, 0));
    holder.add(core);
    this.group.add(holder);
    let t = 0;
    const handle = {
      charge: 0,
      update: (dt: number) => {
        t += dt;
        const open = backOutish(clamp(t / .6)), close = 1 - smooth((t - seconds + .4) / .4);
        holder.position.copy(center());
        holder.lookAt(facing());
        const pulseK = 1 + Math.sin(t * 14) * .03 * handle.charge;
        layers.forEach((l) => {
          l.mesh.scale.setScalar(Math.max(.01, size * l.scale * open * pulseK));
          l.mesh.rotation.z += dt * l.spin * (1 + handle.charge * 4);
          l.mat.opacity = l.alpha * close * (.75 + .25 * handle.charge);
        });
        core.scale.setScalar(size * (.3 + handle.charge * .9));
        core.material.opacity = handle.charge * close;
        return t < seconds;
      },
      dispose: () => { this.group.remove(holder); layers.forEach((l) => l.mat.dispose()); core.material.dispose(); },
    };
    this.add(handle);
    return handle;
  }

  /** Energy beam with scrolling turbulence from a to b. */
  beam(from: THREE.Vector3, to: () => THREE.Vector3, color: THREE.ColorRepresentation, width: number, seconds: number) {
    const geo = new THREE.CylinderGeometry(1, 1, 1, 24, 12, true).rotateX(Math.PI / 2).translate(0, 0, .5);
    const mat = new THREE.ShaderMaterial({
      uniforms: { color: { value: C(color).multiplyScalar(2.5) }, time: { value: 0 }, life: { value: 0 } },
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      vertexShader: 'varying vec2 vUv; varying vec3 vN, vV; void main(){ vUv = uv; vec4 mv = modelViewMatrix * vec4(position, 1.); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }',
      fragmentShader: `uniform vec3 color; uniform float time, life; varying vec2 vUv; varying vec3 vN, vV;
        float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
        float n(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f*f*(3.-2.*f); return mix(mix(h(i),h(i+vec2(1,0)),u.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),u.x), u.y); }
        void main(){ float core = pow(clamp(abs(dot(vN, vV)), 0., 1.), 1.5); float s = n(vec2(vUv.x * 8., vUv.y * 10. - time * 22.));
          float a = (core * 1.2 + s * .5) * smoothstep(0., .04, vUv.y) * (1. - life);
          gl_FragColor = vec4(mix(color, vec3(3.), core * core), a); }`,
    });
    const mesh = new THREE.Mesh(geo, mat);
    this.group.add(mesh);
    let t = 0;
    return this.add({
      update: (dt) => {
        t += dt; const u = t / seconds;
        const b = to();
        mesh.position.copy(from); mesh.lookAt(b);
        const grow = easeOut(clamp(t / .12));
        mesh.scale.set(width * (1 - u * .6) * (1 + Math.sin(t * 60) * .08), width * (1 - u * .6), Math.max(.01, from.distanceTo(b) * grow));
        mat.uniforms.time.value = t; mat.uniforms.life.value = smooth((u - .6) / .4);
        return u < 1;
      },
      dispose: () => { this.group.remove(mesh); geo.dispose(); mat.dispose(); },
    });
  }

  /** 八卦镜: a bronze mirror spins into place and throws up a hexagonal ward that ripples on impact. */
  baguaWard(anchor: () => THREE.Vector3, facing: () => THREE.Vector3, seconds: number) {
    const mirrorMat = new THREE.MeshBasicMaterial({ map: this.art?.jade ?? textures().bagua, transparent: true, side: THREE.DoubleSide, color: C(0xffffff).multiplyScalar(this.art ? 1.5 : 1) });
    const mirror = new THREE.Mesh(this.shared.planeGeo, mirrorMat);
    const wardMat = new THREE.ShaderMaterial({
      uniforms: { color: { value: C(0xffd77a).multiplyScalar(1.6) }, time: { value: 0 }, hit: { value: V(0, 0, 1) }, ripple: { value: 9 }, alpha: { value: 0 } },
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      vertexShader: 'varying vec3 vP, vN, vV; void main(){ vP = normalize(position); vec4 mv = modelViewMatrix * vec4(position, 1.); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }',
      fragmentShader: `uniform vec3 color, hit; uniform float time, ripple, alpha; varying vec3 vP, vN, vV;
        float hexEdge(vec2 p){ p *= 9.; vec2 r = vec2(1., 1.732); vec2 h = r * .5; vec2 a = mod(p, r) - h; vec2 b = mod(p - h, r) - h;
          vec2 g = dot(a, a) < dot(b, b) ? a : b; vec2 q = abs(g); return smoothstep(.42, .5, max(q.x * .866 + q.y * .5, q.y)); }
        void main(){ vec2 uv = vec2(atan(vP.z, vP.x), asin(vP.y)); float rim = pow(clamp(1. - abs(dot(vN, vV)), 0., 1.), 2.);
          float d = acos(clamp(dot(vP, normalize(hit)), -1., 1.)); float wave = smoothstep(.25, 0., abs(d - ripple)) * (1. - clamp(ripple / 2.5, 0., 1.));
          float a = (hexEdge(uv) * .35 + rim * .55 + wave * 1.6) * alpha;
          gl_FragColor = vec4(color * (1. + wave * 2.), a); }`,
    });
    const ward = new THREE.Mesh(this.shared.sphereGeo, wardMat);
    const group = new THREE.Group();
    group.add(mirror, ward);
    this.group.add(group);
    let t = 0;
    const handle = {
      strike: (worldPoint: THREE.Vector3) => { wardMat.uniforms.hit.value.copy(worldPoint).sub(group.position).normalize(); wardMat.uniforms.ripple.value = 0; },
      update: (dt: number) => {
        t += dt;
        const a = anchor(), f = facing();
        const dir = V().subVectors(f, a).normalize();
        group.position.copy(a);
        const open = easeOut(clamp(t / .35)), close = 1 - smooth((t - seconds + .35) / .35);
        mirror.position.copy(dir).multiplyScalar(1.4);
        mirror.lookAt(a.clone().add(dir.clone().multiplyScalar(10)).sub(group.position).add(mirror.position));
        mirror.rotateZ(t * 2);
        const ms = Math.max(.01, (this.art ? 1.9 : 1.5) * open * close);
        mirror.scale.set(this.art ? ms * this.art.aspect.jade : ms, ms, 1);
        ward.scale.setScalar(Math.max(.01, 2.2 * open));
        wardMat.uniforms.alpha.value = open * close;
        wardMat.uniforms.time.value = t;
        wardMat.uniforms.ripple.value += dt * 4;
        mirrorMat.opacity = close;
        return t < seconds;
      },
      dispose: () => { this.group.remove(group); mirrorMat.dispose(); wardMat.dispose(); },
    };
    this.add(handle);
    return handle;
  }

  /** 魔爪: three crimson arcs raked across the path of the claw. */
  clawSlash(at: THREE.Vector3, facing: THREE.Vector3, color: THREE.ColorRepresentation, size: number) {
    const mats: THREE.ShaderMaterial[] = [];
    const group = new THREE.Group();
    for (let k = 0; k < 3; k++) {
      const geo = new THREE.RingGeometry(size * (.85 + k * .08), size * (1 + k * .08), 48, 1, Math.PI * .1, Math.PI * .8);
      const mat = new THREE.ShaderMaterial({
        uniforms: { color: { value: C(color).multiplyScalar(2.6) }, sweep: { value: 0 }, fade: { value: 1 } },
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
        vertexShader: 'varying vec2 vUv; varying vec3 vP; void main(){ vUv = uv; vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }',
        fragmentShader: `uniform vec3 color; uniform float sweep, fade; varying vec3 vP;
          void main(){ float a = atan(vP.y, vP.x) / 3.14159; float lead = smoothstep(sweep - .5, sweep, a) * step(a, sweep);
            gl_FragColor = vec4(mix(color, vec3(3., 2.4, 2.), lead * .5), lead * fade); }`,
      });
      mats.push(mat);
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(0, (k - 1) * size * .18, (k - 1) * .4);
      group.add(mesh);
    }
    group.position.copy(at);
    group.lookAt(facing);
    group.rotateZ(-.6);
    this.group.add(group);
    let t = 0;
    return this.add({
      update: (dt) => {
        t += dt;
        mats.forEach((m, k) => { m.uniforms.sweep.value = lerp(0, 1.4, easeOut(clamp((t - k * .04) / .22))); m.uniforms.fade.value = 1 - smooth((t - .25) / .35); });
        return t < .65;
      },
      dispose: () => { this.group.remove(group); group.children.forEach((c) => (c as THREE.Mesh).geometry.dispose()); mats.forEach((m) => m.dispose()); },
    });
  }

  /** Energy gathering into a point (charge-up). */
  gather(center: () => THREE.Vector3, color: THREE.ColorRepresentation, seconds: number, radius = 4) {
    const r = rng(41);
    const motes = Array.from({ length: this.reduced ? 10 : 26 }, () => {
      const s = new THREE.Sprite(glowMat(C(color).multiplyScalar(2.5), textures().dot, 0));
      const dir = V(r.range(-1, 1), r.range(-1, 1), r.range(-1, 1)).normalize();
      this.group.add(s);
      return { s, dir, delay: r.range(0, seconds * .7), speed: r.range(.5, .9) };
    });
    let t = 0;
    return this.add({
      update: (dt) => {
        t += dt;
        const c = center();
        for (const m of motes) {
          const u = clamp((t - m.delay) / (seconds * .35 * m.speed + .2));
          const d = radius * (1 - easeIn(u));
          m.s.position.copy(c).addScaledVector(m.dir, d);
          m.s.scale.setScalar(.25 + (1 - u) * .2);
          m.s.material.opacity = u > 0 && u < 1 ? Math.sin(u * Math.PI) : 0;
          if (u >= 1) m.delay = t + r.range(0, .2);
        }
        return t < seconds;
      },
      dispose: () => motes.forEach((m) => { this.group.remove(m.s); m.s.material.dispose(); }),
    });
  }

  /** A sword grown to colossal size above the caster, then driven down onto the target. */
  heavenSword(above: () => THREE.Vector3, target: () => THREE.Vector3, color: THREE.ColorRepresentation, rise: number, fall: number, onHit: () => void) {
    const sword = this.sword(color, 1);
    const halo = new THREE.Sprite(glowMat(C(color).multiplyScalar(2.2), textures().dot, .9));
    halo.scale.set(18, 4, 1); halo.position.x = .3;
    sword.add(halo);
    const trail = new Trail(26, 1.1, color, 2.6);
    this.group.add(sword, trail.mesh);
    let t = 0, hit = false;
    const start = V(), p = V();
    return this.add({
      update: (dt) => {
        t += dt;
        const top = above(), aim = target();
        if (t < rise) {
          const u = easeOut(t / rise);
          sword.scale.setScalar(lerp(.6, 9, u));
          sword.position.copy(top).add(V(0, lerp(0, 6, u), 0));
          sword.rotation.set(0, 0, -Math.PI / 2 + Math.sin(t * 3) * .03); // point straight down
          start.copy(sword.position);
          trail.reset(sword.position);
          return true;
        }
        const u = clamp((t - rise) / fall);
        if (u < 1) {
          p.lerpVectors(start, aim, easeIn(u));
          sword.position.copy(p);
          sword.lookAt(aim); sword.rotateY(-Math.PI / 2);
          trail.push(p.clone().add(V(0, 4, 0)), this.camera);
          return true;
        }
        if (!hit) { hit = true; sword.visible = false; onHit(); }
        trail.fade = Math.max(0, 1 - (t - rise - fall) * 2);
        return t < rise + fall + .6;
      },
      dispose: () => { this.group.remove(sword, trail.mesh); trail.dispose(); disposeTree(sword); },
    });
  }
}

function glowRingMat(color: THREE.ColorRepresentation) {
  return new THREE.MeshBasicMaterial({ color: C(color).multiplyScalar(2), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
}
function backOutish(t: number) { return 1 + 2.2 * (t - 1) ** 3 + 1.2 * (t - 1) ** 2; }

export function disposeTree(obj: THREE.Object3D) {
  obj.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (mesh.geometry) mesh.geometry.dispose();
    if (o.name === 'ink') return; // shared, cached outline material
    const mats = mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : [];
    for (const m of mats) m.dispose();
  });
}
