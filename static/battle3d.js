// 三维斗法台「云海御空」：只演出服务端已结算的战报，不推进任何规则、不决定胜负。
// 由 fx3d.js 创建并持有唯一的 WebGL 渲染器；本模块只搭场景、编排镜头与招式特效，并在 dispose 时释放全部 GPU 资源。
import * as THREE from "/vendor/three.module.min.js";
import { EffectComposer } from "/vendor/addons/EffectComposer.js";
import { RenderPass } from "/vendor/addons/RenderPass.js";
import { UnrealBloomPass } from "/vendor/addons/UnrealBloomPass.js";
import { ShaderPass } from "/vendor/addons/ShaderPass.js";
import { OutputPass } from "/vendor/addons/OutputPass.js";

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const rand = (a, b) => a + Math.random() * (b - a);
const easeOut = (t) => 1 - (1 - t) ** 3;
const easeIn = (t) => t * t * t;
const easeInOut = (t) => (t < .5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

// 灵根 → 剑光与灵气配色
const ELEMENTS = {
  fire: { main: 0xff7a2e, core: 0xffe2a8, robe: 0xf4ebe2, trim: 0xb3301e },
  wood: { main: 0x3fe39a, core: 0xdcfff0, robe: 0xedf5ef, trim: 0x1f7a52 },
  earth: { main: 0xf0b040, core: 0xfff3c4, robe: 0xf3eedf, trim: 0x8a5a1c },
  jade: { main: 0x52e0cc, core: 0xe6fffb, robe: 0xeef4f1, trim: 0x23786c },
};
// 境界 → 天时（晨 / 昼 / 暮 / 夜），境界越高越近星河
const SKIES = [
  { top: 0x33689a, horizon: 0xf2c48e, bottom: 0xe0cbb4, sun: 0xfff0c8, dir: [-.55, .14, -1], stars: 0, light: 0xfbeedd, shade: 0x8f9fb6, hemi: 1.15 },
  { top: 0x1f62b8, horizon: 0xbcdcea, bottom: 0xd4e6ee, sun: 0xfff8e8, dir: [.35, .42, -1], stars: 0, light: 0xf4f8fb, shade: 0x8ea6c0, hemi: 1.3 },
  { top: 0x2c2b60, horizon: 0xf2925a, bottom: 0xd88a6a, sun: 0xffb06a, dir: [.6, .07, -1], stars: .3, light: 0xffd2aa, shade: 0x7e6690, hemi: .95 },
  { top: 0x060b1e, horizon: 0x2f3d72, bottom: 0x1d2448, sun: 0xdfe8ff, dir: [-.4, .32, -1], stars: 1, light: 0xa5b8e8, shade: 0x2b3459, hemi: .75 },
];
const QUALITY_SWORDS = { 凡品: 3, 下品: 4, 中品: 5, 上品: 7, 极品: 9 };
const BOSS_KINDS = new Set(["guard", "world_boss", "elite"]);
const POS = { player: V(-5.2, 0, 0), enemy: V(5.2, .35, 0), npc: V(-7.6, -1.1, -2.6) };
const PORTRAIT = { player: V(-1.5, -1.9, 1.6), enemy: V(1.4, 2.1, -2.2) };       // 竖屏：一前一后斜对，双方都够大
// 质量档：bloom 开关、像素比上限、远云数量
const TIERS = [
  { bloom: false, ratio: .85, puffs: 26, sparks: .55 },
  { bloom: true, ratio: 1, puffs: 44, sparks: .8 },
  { bloom: true, ratio: 1.5, puffs: 70, sparks: 1 },
];

// ------------------------------------------------------------------ 程序贴图（canvas 生成，零外部资源）
function canvasTexture(w, h, draw) {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const radial = (g, w, h, stops) => {
  const grad = g.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
  for (const [o, c] of stops) grad.addColorStop(o, c);
  g.fillStyle = grad; g.fillRect(0, 0, w, h);
};
const FONT = '"KaiTi","STKaiti","Kaiti SC","SimSun","Songti SC",serif';

function makeTextures() {
  const dot = canvasTexture(64, 64, (g, w, h) => radial(g, w, h, [[0, "rgba(255,255,255,1)"], [.3, "rgba(255,255,255,.6)"], [1, "rgba(255,255,255,0)"]]));
  const smoke = canvasTexture(128, 128, (g, w, h) => {
    for (let i = 0; i < 14; i++) {
      const x = w / 2 + rand(-22, 22), y = h / 2 + rand(-22, 22), r = rand(22, 44);
      const grad = g.createRadialGradient(x, y, 0, x, y, r);
      grad.addColorStop(0, "rgba(255,255,255,.28)"); grad.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = grad; g.beginPath(); g.arc(x, y, r, 0, 6.283); g.fill();
    }
  });
  const puff = canvasTexture(256, 256, (g, w, h) => {
    for (let i = 0; i < 26; i++) {
      const a = rand(0, 6.283), d = rand(0, 70), x = w / 2 + Math.cos(a) * d, y = h / 2 + Math.sin(a) * d * .55, r = rand(40, 78);
      const grad = g.createRadialGradient(x, y, 0, x, y, r);
      grad.addColorStop(0, "rgba(255,255,255,.34)"); grad.addColorStop(.6, "rgba(255,255,255,.12)"); grad.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = grad; g.beginPath(); g.arc(x, y, r, 0, 6.283); g.fill();
    }
  });
  // 八卦：外环八卦爻 + 太极
  const bagua = canvasTexture(256, 256, (g, w) => {
    const c = w / 2;
    g.strokeStyle = "rgba(255,255,255,.95)"; g.fillStyle = "rgba(255,255,255,.95)";
    g.lineWidth = 5; g.beginPath(); g.arc(c, c, 118, 0, 6.283); g.stroke();
    g.lineWidth = 2; g.beginPath(); g.arc(c, c, 100, 0, 6.283); g.stroke();
    const trigrams = ["111", "011", "101", "001", "110", "010", "100", "000"];
    trigrams.forEach((bits, i) => {
      g.save(); g.translate(c, c); g.rotate(i * Math.PI / 4);
      [...bits].forEach((b, k) => {
        const y = -86 + k * 11;
        if (b === "1") g.fillRect(-20, y, 40, 6); else { g.fillRect(-20, y, 16, 6); g.fillRect(4, y, 16, 6); }
      });
      g.restore();
    });
    g.beginPath(); g.arc(c, c, 40, 0, 6.283); g.lineWidth = 3; g.stroke();
    g.beginPath(); g.arc(c, c, 40, -Math.PI / 2, Math.PI / 2); g.arc(c, c + 20, 20, Math.PI / 2, -Math.PI / 2, true); g.arc(c, c - 20, 20, Math.PI / 2, -Math.PI / 2); g.fill();
    g.beginPath(); g.arc(c, c - 20, 6, 0, 6.283); g.fill();
  });
  // 法阵：同心环 + 外圈符文字
  const circle = canvasTexture(512, 512, (g, w) => {
    const c = w / 2;
    g.strokeStyle = "rgba(255,255,255,.95)"; g.fillStyle = "rgba(255,255,255,.95)";
    for (const [r, lw] of [[244, 6], [226, 2], [160, 3], [150, 1.5], [70, 3]]) { g.lineWidth = lw; g.beginPath(); g.arc(c, c, r, 0, 6.283); g.stroke(); }
    g.lineWidth = 2.5; g.beginPath();
    for (let i = 0; i <= 6; i++) { const a = i * Math.PI * 2 / 3 * 2 - Math.PI / 2, x = c + Math.cos(a) * 160, y = c + Math.sin(a) * 160; i ? g.lineTo(x, y) : g.moveTo(x, y); }
    g.stroke(); g.beginPath();
    for (let i = 0; i <= 6; i++) { const a = i * Math.PI * 2 / 3 * 2 + Math.PI / 2, x = c + Math.cos(a) * 160, y = c + Math.sin(a) * 160; i ? g.lineTo(x, y) : g.moveTo(x, y); }
    g.stroke();
    g.font = `40px ${FONT}`; g.textAlign = "center"; g.textBaseline = "middle";
    const runes = "乾坤震巽坎离艮兑天地风雷水火山泽";
    [...runes].forEach((ch, i) => { g.save(); g.translate(c, c); g.rotate(i / runes.length * 6.283); g.fillText(ch, 0, -193); g.restore(); });
  });
  // 符箓：黄纸朱砂
  const talisman = canvasTexture(96, 256, (g, w, h) => {
    g.fillStyle = "#f1cf5f"; g.fillRect(0, 0, w, h);
    g.strokeStyle = "#b8231a"; g.lineWidth = 4; g.strokeRect(8, 8, w - 16, h - 16);
    g.fillStyle = "#b8231a"; g.font = `bold 44px ${FONT}`; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText("敕", w / 2, 52); g.fillText("令", w / 2, 108);
    g.lineWidth = 3; g.beginPath(); g.moveTo(w / 2, 140); for (let y = 140; y < 236; y += 12) g.lineTo(w / 2 + (y % 24 ? 16 : -16), y); g.stroke();
  });
  const runeChars = "敕镇封灵护罡";
  const runes = [...runeChars].map((ch) => canvasTexture(64, 64, (g, w) => {
    g.fillStyle = "rgba(255,255,255,1)"; g.font = `bold 50px ${FONT}`; g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(ch, w / 2, w / 2 + 2);
  }));
  return { dot, smoke, puff, bagua, circle, talisman, runes };
}

// ------------------------------------------------------------------ 着色器
const PARTICLE_VERT = `
attribute float size; attribute float alpha; attribute vec3 tint;
varying float vA; varying vec3 vC;
uniform float scale;
void main() {
  vA = alpha; vC = tint;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = clamp(size * scale / max(.1, -mv.z), 0.0, 256.0);
  gl_Position = projectionMatrix * mv;
}`;
const PARTICLE_FRAG = `
uniform sampler2D map; uniform float boost;
varying float vA; varying vec3 vC;
void main() { vec4 t = texture2D(map, gl_PointCoord); gl_FragColor = vec4(vC * t.rgb * boost, t.a * vA); }`;

const SKY_VERT = `
varying vec3 vDir;
void main() { vDir = normalize(position); vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position = p.xyww; }`;
const SKY_FRAG = `
uniform vec3 top; uniform vec3 horizon; uniform vec3 bottom; uniform vec3 sunColor; uniform vec3 sunDir;
uniform float stars; uniform float time; uniform float storm; uniform float flash;
varying vec3 vDir;
float h3(vec3 p) { return fract(sin(dot(p, vec3(12.9898, 78.233, 45.164))) * 43758.5453); }
void main() {
  vec3 d = normalize(vDir); float h = d.y;
  vec3 col = mix(horizon, top, smoothstep(0.0, 0.6, h));
  col = mix(col, bottom, smoothstep(0.0, -0.3, h));
  float s = max(dot(d, normalize(sunDir)), 0.0);
  col += sunColor * (pow(s, 1400.0) * 14.0 + pow(s, 14.0) * .4 + pow(s, 3.0) * .08);
  if (stars > 0.0) {
    vec3 cell = floor(d * 260.0); float r = h3(cell);
    col += vec3(.9, .95, 1.0) * step(.9965, r) * stars * smoothstep(0.04, .35, h) * (.55 + .45 * sin(time * 2.5 + r * 60.0)) * 1.6;
  }
  col = mix(col, col * vec3(.32, .28, .40) + vec3(.03, 0.0, .02), storm * smoothstep(-.1, .5, h));
  col += vec3(.75, .8, 1.0) * flash * smoothstep(-.05, .45, h);
  gl_FragColor = vec4(col, 1.0);
}`;

const SEA_VERT = `
varying vec3 vW;
void main() { vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz; gl_Position = projectionMatrix * viewMatrix * w; }`;
const SEA_FRAG = `
uniform float time; uniform vec3 light; uniform vec3 shade; uniform vec3 horizon; uniform vec3 camPos; uniform vec3 sunColor;
varying vec3 vW;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) { vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y); }
float fbm(vec2 p) { float v = 0.0, a = .5; for (int i = 0; i < 5; i++) { v += a * noise(p); p = p * 2.03 + vec2(1.7, 9.2); a *= .5; } return v; }
void main() {
  vec2 q = vW.xz * .045 + vec2(time * .09, time * .01);
  float n = fbm(q + .8 * fbm(q * 1.6 - vec2(time * .02, 0.0)));
  float lit = smoothstep(.35, .8, n);
  vec3 col = mix(shade * .8, light * .9, lit) + sunColor * pow(lit, 4.0) * .12;
  float d = length(vW.xz - camPos.xz);
  col = mix(col, horizon, smoothstep(30.0, 230.0, d));
  float a = clamp(.35 + .6 * smoothstep(.3, .7, n), 0.0, 1.0) * (1.0 - smoothstep(240.0, 300.0, d));
  gl_FragColor = vec4(col, a);
}`;

const PUFF_VERT = `
attribute vec4 puff; attribute float shadeK;
varying vec2 vUv; varying float vK; varying float vFog;
uniform float time; uniform float wind; uniform float span;
void main() {
  vUv = uv; vK = shadeK;
  vec3 c = puff.xyz; c.x = mod(c.x - time * wind + span, 2.0 * span) - span;
  vec4 mv = modelViewMatrix * vec4(c, 1.0);
  mv.xy += position.xy * puff.w;
  vFog = smoothstep(40.0, 200.0, -mv.z);
  float edge = smoothstep(span, span * .75, abs(c.x));
  vK *= edge * smoothstep(3.0, 12.0, -mv.z);
  gl_Position = projectionMatrix * mv;
}`;
const PUFF_FRAG = `
uniform sampler2D map; uniform vec3 light; uniform vec3 shade; uniform vec3 horizon; uniform float opacity;
varying vec2 vUv; varying float vK; varying float vFog;
void main() {
  vec4 t = texture2D(map, vUv);
  vec3 col = mix(shade, light, clamp(vUv.y * 1.3, 0.0, 1.0));
  col = mix(col, horizon, vFog);
  gl_FragColor = vec4(col, t.a * opacity * vK * 1.6);
}`;

const TRAIL_VERT = `
attribute float a; attribute float side;
varying float vA; varying float vS;
void main() { vA = a; vS = side; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const TRAIL_FRAG = `
uniform vec3 color; uniform float boost;
varying float vA; varying float vS;
void main() { float core = 1.0 - abs(vS); vec3 c = mix(color, vec3(1.0), core * core * .7); gl_FragColor = vec4(c * boost, vA * pow(core, 1.3)); }`;

// 护盾：菲涅尔边缘 + 六角纹 + 裂痕
const SHIELD_VERT = `
varying vec3 vN; varying vec3 vV; varying vec3 vP;
void main() { vP = position; vec4 w = modelMatrix * vec4(position, 1.0); vN = normalize(mat3(modelMatrix) * normal); vV = normalize(cameraPosition - w.xyz); gl_Position = projectionMatrix * viewMatrix * w; }`;
const SHIELD_FRAG = `
uniform vec3 color; uniform float time; uniform float crack; uniform float flash; uniform float opacity; uniform vec3 hit;
varying vec3 vN; varying vec3 vV; varying vec3 vP;
float hash(vec3 p) { return fract(sin(dot(p, vec3(17.1, 113.7, 41.3))) * 43758.5453); }
void main() {
  vec3 p = normalize(vP);
  float fr = pow(1.0 - abs(dot(normalize(vN), normalize(vV))), 3.2);
  vec2 q = vec2(atan(p.z, p.x) * 3.0, p.y * 5.2);
  vec2 r = vec2(1.0, 1.732); vec2 h = r * .5;
  vec2 a = mod(q, r) - h; vec2 b = mod(q - h, r) - h;
  vec2 g = dot(a, a) < dot(b, b) ? a : b;
  float hexEdge = smoothstep(.36, .5, max(abs(g.x) * .866 + abs(g.y) * .5, abs(g.y)));
  float d = distance(p, normalize(hit));
  float ripple = flash * smoothstep(.25, 0.0, abs(d - (1.0 - flash) * 1.6));
  vec3 cell = floor(vP * 3.0 + .5);
  float cr = step(1.0 - crack * .4, hash(cell)) * hexEdge * .7;
  float pulse = .75 + .25 * sin(time * 3.0 + p.y * 6.0);
  float alpha = (fr * .7 + hexEdge * .12 * pulse + ripple * 1.2 + cr * 1.2 + flash * .2) * opacity * .7;
  vec3 col = mix(color, vec3(1.0), clamp(ripple + cr * .6, 0.0, 1.0));
  gl_FragColor = vec4(col * 1.25, alpha);
}`;

// 收尾合成：暗角 + 色散 + 去饱和 + 闪色
const FINAL_SHADER = {
  uniforms: { tDiffuse: { value: null }, aberration: { value: 0 }, vignette: { value: .45 }, desat: { value: 0 }, flashColor: { value: new THREE.Vector3(1, 1, 1) }, flash: { value: 0 } },
  vertexShader: "varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
  fragmentShader: `
uniform sampler2D tDiffuse; uniform float aberration; uniform float vignette; uniform float desat; uniform vec3 flashColor; uniform float flash;
varying vec2 vUv;
void main() {
  vec2 c = vUv - .5; float d = length(c);
  vec2 off = c * aberration * d;
  vec3 col = vec3(texture2D(tDiffuse, vUv + off).r, texture2D(tDiffuse, vUv).g, texture2D(tDiffuse, vUv - off).b);
  float l = dot(col, vec3(.299, .587, .114));
  col = mix(col, vec3(l) * vec3(.92, .95, 1.02), desat);
  col *= 1.0 - vignette * smoothstep(.35, .85, d);
  col = mix(col, flashColor, flash * smoothstep(.15, .8, d + flash * .3));
  gl_FragColor = vec4(col, 1.0);
}`,
};

// ------------------------------------------------------------------ 粒子与拖尾池
class Particles {
  constructor(max, texture, blending, boost) {
    this.max = max; this.list = [];
    const g = new THREE.BufferGeometry();
    this.pos = new Float32Array(max * 3); this.tint = new Float32Array(max * 3); this.size = new Float32Array(max); this.alpha = new Float32Array(max);
    g.setAttribute("position", new THREE.BufferAttribute(this.pos, 3));
    g.setAttribute("tint", new THREE.BufferAttribute(this.tint, 3));
    g.setAttribute("size", new THREE.BufferAttribute(this.size, 1));
    g.setAttribute("alpha", new THREE.BufferAttribute(this.alpha, 1));
    this.material = new THREE.ShaderMaterial({ uniforms: { map: { value: texture }, scale: { value: 400 }, boost: { value: boost } }, vertexShader: PARTICLE_VERT, fragmentShader: PARTICLE_FRAG, transparent: true, depthWrite: false, blending });
    this.points = new THREE.Points(g, this.material);
    this.points.frustumCulled = false;
    this.geometry = g;
  }
  // o: { p, v, life, size, size1, color(THREE.Color), alpha, gravity, drag, grow }
  spawn(p, v, life, size, color, opts = {}) {
    if (this.list.length >= this.max) this.list.shift();
    this.list.push({ x: p.x, y: p.y, z: p.z, vx: v.x, vy: v.y, vz: v.z, life, span: life, s0: size, s1: opts.size1 ?? size * .3, c: color, a: opts.alpha ?? 1, g: opts.gravity ?? 0, drag: opts.drag ?? 1.6 });
  }
  update(dt) {
    const L = this.list;
    for (let i = L.length - 1; i >= 0; i--) {
      const q = L[i]; q.life -= dt;
      if (q.life <= 0) { L.splice(i, 1); continue; }
      const k = Math.exp(-q.drag * dt);
      q.vx *= k; q.vy = q.vy * k - q.g * dt; q.vz *= k;
      q.x += q.vx * dt; q.y += q.vy * dt; q.z += q.vz * dt;
    }
    const n = Math.min(L.length, this.max);
    for (let i = 0; i < this.max; i++) {
      if (i < n) {
        const q = L[i], t = q.life / q.span;
        this.pos[i * 3] = q.x; this.pos[i * 3 + 1] = q.y; this.pos[i * 3 + 2] = q.z;
        this.tint[i * 3] = q.c.r; this.tint[i * 3 + 1] = q.c.g; this.tint[i * 3 + 2] = q.c.b;
        this.size[i] = lerp(q.s1, q.s0, t); this.alpha[i] = Math.min(1, t * 2.2) * q.a;
      } else this.alpha[i] = 0;
    }
    for (const name of ["position", "tint", "size", "alpha"]) this.geometry.attributes[name].needsUpdate = true;
  }
  clear() { this.list.length = 0; }
}

class Trail {
  constructor(n = 30) {
    this.n = n; this.pts = []; this.active = false; this.releasing = false; this.width = .2; this.fade = 1;
    const g = new THREE.BufferGeometry();
    this.position = new Float32Array(n * 2 * 3); this.a = new Float32Array(n * 2); const side = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) { side[i * 2] = -1; side[i * 2 + 1] = 1; }
    const index = [];
    for (let i = 0; i < n - 1; i++) { const k = i * 2; index.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
    g.setIndex(index);
    g.setAttribute("position", new THREE.BufferAttribute(this.position, 3));
    g.setAttribute("a", new THREE.BufferAttribute(this.a, 1));
    g.setAttribute("side", new THREE.BufferAttribute(side, 1));
    this.material = new THREE.ShaderMaterial({ uniforms: { color: { value: new THREE.Color() }, boost: { value: 2.2 } }, vertexShader: TRAIL_VERT, fragmentShader: TRAIL_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide });
    this.mesh = new THREE.Mesh(g, this.material);
    this.mesh.frustumCulled = false; this.mesh.visible = false;
    this.geometry = g;
  }
  start(color, width, boost = 2.2, limit = this.n) { this.limit = Math.min(this.n, limit); this.pts = []; this.active = true; this.releasing = false; this.width = width; this.fade = 1; this.material.uniforms.color.value.setHex(color); this.material.uniforms.boost.value = boost; this.mesh.visible = true; }
  push(p) { if (!this.active || this.releasing) return; this.pts.push(p.clone()); if (this.pts.length > this.limit) this.pts.shift(); }
  release() { this.releasing = true; }
  update(dt, cam) {
    if (!this.active) return;
    if (this.releasing) { this.fade -= dt * 3.2; if (this.pts.length > 1) this.pts.shift(); if (this.fade <= 0 || this.pts.length < 2) { this.active = false; this.mesh.visible = false; return; } }
    const P = this.pts, m = P.length, tmp = Trail.tmp, side = Trail.side;
    for (let i = 0; i < this.n; i++) {
      if (i >= m || m < 2) { this.a[i * 2] = this.a[i * 2 + 1] = 0; const last = P[m - 1] || V(); for (let k = 0; k < 2; k++) { this.position[(i * 2 + k) * 3] = last.x; this.position[(i * 2 + k) * 3 + 1] = last.y; this.position[(i * 2 + k) * 3 + 2] = last.z; } continue; }
      const p = P[i], prev = P[Math.max(0, i - 1)], next = P[Math.min(m - 1, i + 1)];
      tmp.subVectors(next, prev); Trail.view.subVectors(cam.position, p);
      side.crossVectors(tmp, Trail.view).normalize();
      const t = i / (m - 1), w = this.width * Math.pow(t, .6);
      side.multiplyScalar(w);
      this.position[i * 6] = p.x - side.x; this.position[i * 6 + 1] = p.y - side.y; this.position[i * 6 + 2] = p.z - side.z;
      this.position[i * 6 + 3] = p.x + side.x; this.position[i * 6 + 4] = p.y + side.y; this.position[i * 6 + 5] = p.z + side.z;
      this.a[i * 2] = this.a[i * 2 + 1] = t * this.fade;
    }
    this.geometry.attributes.position.needsUpdate = true; this.geometry.attributes.a.needsUpdate = true;
  }
}
Trail.tmp = V(); Trail.side = V(); Trail.view = V();

// ------------------------------------------------------------------ 模型（全部由几何体拼装）
function swordGeometry(len = 2) {
  const s = new THREE.Shape();
  s.moveTo(0, -.075); s.lineTo(len * .8, -.065); s.lineTo(len, 0); s.lineTo(len * .8, .065); s.lineTo(0, .075); s.lineTo(0, -.075);
  const blade = new THREE.ExtrudeGeometry(s, { depth: .025, bevelEnabled: true, bevelThickness: .012, bevelSize: .012, bevelSegments: 1 });
  blade.translate(0, 0, -.0125);
  const guard = new THREE.BoxGeometry(.06, .34, .08);
  const hilt = new THREE.CylinderGeometry(.035, .035, .42, 8); hilt.rotateZ(Math.PI / 2); hilt.translate(-.24, 0, 0);
  const pommel = new THREE.SphereGeometry(.06, 8, 6); pommel.translate(-.47, 0, 0);
  const merged = mergeGeometries([blade, guard, hilt, pommel]);
  [blade, guard, hilt, pommel].forEach((g) => g.dispose());
  merged.translate(-len * .35, 0, 0);
  return merged;
}
// 轻量合并：只合并 position/normal（各部件已非索引化）
function mergeGeometries(list) {
  const parts = list.map((g) => (g.index ? g.toNonIndexed() : g));
  let count = 0; for (const g of parts) count += g.attributes.position.count;
  const pos = new Float32Array(count * 3), nor = new Float32Array(count * 3);
  let o = 0;
  for (const g of parts) {
    if (!g.attributes.normal) g.computeVertexNormals();
    pos.set(g.attributes.position.array, o * 3); nor.set(g.attributes.normal.array, o * 3); o += g.attributes.position.count;
  }
  parts.forEach((g, i) => { if (g !== list[i]) g.dispose(); });
  const out = new THREE.BufferGeometry();
  out.setAttribute("position", new THREE.BufferAttribute(pos, 3)); out.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
  return out;
}

function std(color, opts = {}) { return new THREE.MeshStandardMaterial({ color, roughness: .62, metalness: .05, ...opts }); }
function glow(color, opacity = 1) { return new THREE.MeshBasicMaterial({ color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }); }

function makeCultivator(pal, dark) {
  const g = new THREE.Group();
  const robe = std(pal.robe, { roughness: .78 });
  const trim = std(pal.trim, { roughness: .5, emissive: new THREE.Color(pal.trim), emissiveIntensity: dark ? .6 : .15 });
  const skin = std(dark ? 0xc9b2a6 : 0xf3dccb, { roughness: .55 });
  const hair = std(0x14161c, { roughness: .4 });
  const profile = [[0, -1.3], [.6, -1.28], [.5, -.75], [.36, -.1], [.28, .35], [.33, .58], [.14, .78], [0, .8]].map(([x, y]) => new THREE.Vector2(x, y));
  const body = new THREE.Mesh(new THREE.LatheGeometry(profile, 18), robe); g.add(body);
  const outer = new THREE.Mesh(new THREE.LatheGeometry([[0, -1.32], [.66, -1.3], [.52, -.6], [.36, .1], [.3, .5], [0, .6]].map(([x, y]) => new THREE.Vector2(x, y)), 18, -Math.PI * .55, Math.PI * 1.1), trim);
  outer.rotation.y = Math.PI; g.add(outer);
  const belt = new THREE.Mesh(new THREE.TorusGeometry(.3, .045, 6, 18), trim); belt.rotation.x = Math.PI / 2; belt.position.y = .2; g.add(belt);
  const head = new THREE.Mesh(new THREE.SphereGeometry(.2, 16, 12), skin); head.position.y = 1.0; g.add(head);
  const hairCap = new THREE.Mesh(new THREE.SphereGeometry(.215, 16, 10, 0, Math.PI * 2, 0, Math.PI * .58), hair); hairCap.position.set(-.02, 1.02, 0); hairCap.rotation.z = .25; g.add(hairCap);
  const bun = new THREE.Mesh(new THREE.SphereGeometry(.1, 10, 8), hair); bun.position.set(-.04, 1.24, 0); g.add(bun);
  const pin = new THREE.Mesh(new THREE.CylinderGeometry(.012, .012, .42, 5), std(0xe8c46a, { metalness: .8, roughness: .3, emissive: new THREE.Color(0x8a6a1c), emissiveIntensity: .4 }));
  pin.rotation.z = Math.PI / 2 - .3; pin.position.set(-.04, 1.25, 0); g.add(pin);
  // 剑指前伸、另一手负于身后
  const armF = new THREE.Mesh(new THREE.CapsuleGeometry(.07, .5, 4, 8), robe); armF.position.set(.3, .45, .12); armF.rotation.z = -1.25; g.add(armF);
  const hand = new THREE.Mesh(new THREE.SphereGeometry(.06, 8, 6), skin); hand.position.set(.6, .55, .12); g.add(hand);
  const armB = new THREE.Mesh(new THREE.CapsuleGeometry(.07, .44, 4, 8), robe); armB.position.set(-.18, .3, -.2); armB.rotation.z = .5; g.add(armB);
  // 披帛：两条飘带，逐帧按正弦扰动顶点
  const ribbons = [0, 1].map((k) => {
    const geo = new THREE.PlaneGeometry(2.6, .13, 24, 1);
    geo.translate(-1.3, 0, 0);
    const mat = std(pal.trim, { side: THREE.DoubleSide, transparent: true, opacity: .9, emissive: new THREE.Color(dark ? 0x8a1020 : pal.trim), emissiveIntensity: dark ? .9 : .35 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(-.05, .62 - k * .5, k ? -.25 : .25);
    mesh.userData.base = Float32Array.from(geo.attributes.position.array); mesh.userData.k = k;
    g.add(mesh);
    return mesh;
  });
  g.userData = { ribbons, height: 2.3, center: V(0, .1, 0), head: V(0, 1.05, 0) };
  return g;
}

function makeSword(geo, color, glowAmt = 1) {
  const mat = std(0xdfe8ee, { metalness: .9, roughness: .22, emissive: new THREE.Color(color), emissiveIntensity: 1.4 * glowAmt });
  return new THREE.Mesh(geo, mat);
}

// 蛟身：自头部向下盘成 S 形，t 为摆动相位
function serpentAt(i, t) { return [Math.sin(i * .42 - t * 1.6) * .75 * (i / 18 + .3) - i * .06, .3 - i * .19, Math.cos(i * .3 - t) * .3 * (i / 18)]; }

function makeEnemy(form, kit) {
  const g = new THREE.Group();
  const flat = { flatShading: true };
  const palettes = {
    beast: [0x4a4b55, 0xff4422], ape: [0x5a4636, 0xffaa22], fox: [0xe8ddd2, 0xd65cff], serpent: [0x1f5a58, 0x7cff6a],
    golem: [0x76736a, 0xff9a3a], shade: [0x1a1424, 0xff2a4a], spirit: [0x2a2040, 0x7ad8ff], human: [0x2a1d2e, 0xff3040],
  };
  const [bodyHex, eyeHex] = palettes[form] || palettes.spirit;
  const body = std(bodyHex, { ...flat, roughness: .8 });
  const dark = std(new THREE.Color(bodyHex).multiplyScalar(.55).getHex(), { ...flat, roughness: .85 });
  const eye = new THREE.MeshBasicMaterial({ color: new THREE.Color(eyeHex).multiplyScalar(4) });
  const eyes = (x, y, z, r = .06) => { for (const s of [-1, 1]) { const e = new THREE.Mesh(kit.eyeGeo, eye); e.scale.setScalar(r / .06); e.position.set(x, y, z * s); g.add(e); } };
  const add = (geo, mat, x, y, z, sx = 1, sy = 1, sz = 1, rz = 0, ry = 0) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.scale.set(sx, sy, sz); m.rotation.set(0, ry, rz); g.add(m); return m; };
  const sphere = new THREE.IcosahedronGeometry(1, 1), cone = new THREE.ConeGeometry(1, 1, 6), cyl = new THREE.CylinderGeometry(1, .7, 1, 6);
  const parts = { tails: [], segs: [], head: null, core: null };
  if (form === "beast" || form === "ape") {
    const ape = form === "ape";
    add(sphere, body, 0, ape ? .2 : 0, 0, ape ? .75 : 1.15, ape ? .95 : .55, .55);
    parts.head = add(sphere, body, ape ? .35 : 1.05, ape ? 1.05 : .38, 0, .38, .36, .36);
    if (!ape) { add(cone, dark, 1.42, .3, 0, .16, .4, .16, -Math.PI / 2); add(cone, body, .98, .78, .16, .1, .28, .1); add(cone, body, .98, .78, -.16, .1, .28, .1); }
    else add(sphere, std(0xc9a27e, flat), .62, 1.0, 0, .12, .16, .22);
    eyes(ape ? .66 : 1.32, ape ? 1.12 : .48, .14);
    const legs = ape ? [[.3, -.5, .45], [.3, -.5, -.45], [-.3, -.9, .3], [-.3, -.9, -.3]] : [[.7, -.65, .3], [.7, -.65, -.3], [-.7, -.65, .3], [-.7, -.65, -.3]];
    for (const [x, y, z] of legs) add(cyl, dark, x, y, z, .12, ape ? .9 : .7, .12, ape && x > 0 ? .5 : 0);
    if (!ape) { const tail = add(cone, body, -1.35, .25, 0, .14, .9, .14, 1.9); parts.tails.push(tail); }
  } else if (form === "fox") {
    add(sphere, body, 0, 0, 0, .95, .5, .45);
    parts.head = add(sphere, body, .95, .42, 0, .32, .3, .3);
    add(cone, body, 1.3, .36, 0, .12, .36, .12, -Math.PI / 2);
    add(cone, dark, .88, .8, .14, .1, .32, .1); add(cone, dark, .88, .8, -.14, .1, .32, .1);
    eyes(1.2, .5, .12, .05);
    for (let i = 0; i < 5; i++) { const t = add(cone, std(0xf6efe8, { ...flat, emissive: new THREE.Color(eyeHex), emissiveIntensity: .25 }), -1.1, .35, (i - 2) * .16, .2, 1.3, .2, 1.2 + (i - 2) * .12, (i - 2) * .3); parts.tails.push(t); }
    for (const [x, z] of [[.6, .25], [.6, -.25], [-.6, .25], [-.6, -.25]]) add(cyl, dark, x, -.55, z, .09, .6, .09);
  } else if (form === "serpent") {
    for (let i = 0; i < 18; i++) { const r = .42 * (1 - i / 22), [x, y, z] = serpentAt(i, 0); parts.segs.push(add(sphere, i % 2 ? dark : body, x, y, z, r, r, r)); }
    parts.head = add(sphere, body, .45, .55, 0, .55, .34, .4);
    add(cone, std(0xe8d48a, flat), .2, 1.0, .18, .07, .5, .07, -.6); add(cone, std(0xe8d48a, flat), .2, 1.0, -.18, .07, .5, .07, -.6);
    eyes(.72, .69, .2, .07);
  } else if (form === "golem") {
    const rock = new THREE.DodecahedronGeometry(1, 0);
    add(rock, body, 0, .1, 0, .85, .95, .7); parts.head = add(rock, dark, .1, 1.15, 0, .38, .34, .36);
    for (const s of [-1, 1]) { add(rock, dark, .1, .75, s * .85, .38, .38, .38); add(rock, body, .25, .1, s * 1.0, .3, .45, .3); add(rock, dark, .45, -.45, s * 1.0, .32, .3, .32); }
    add(rock, dark, -.1, -.95, .35, .3, .4, .3); add(rock, dark, -.1, -.95, -.35, .3, .4, .3);
    parts.core = add(sphere, new THREE.MeshBasicMaterial({ color: new THREE.Color(eyeHex).multiplyScalar(3) }), .62, .25, 0, .16, .16, .16);
    eyes(.42, 1.18, .13, .05);
  } else if (form === "human") {
    const figure = makeCultivator({ robe: 0x2a1d2e, trim: 0x8a1626 }, true);
    g.add(figure); g.userData.figure = figure;
    const s = makeSword(kit.swordGeo, 0xff2a3a, .8); s.position.set(.1, -1.42, 0); s.rotation.x = -Math.PI / 2; g.add(s);
    eyes(.17, 1.03, .07, .025);
  } else {
    // shade / spirit：兜帽或火核 + 环绕鬼火
    const cloak = new THREE.Mesh(new THREE.LatheGeometry([[0, -1.4], [.75, -1.35], [.5, -.4], [.42, .5], [.32, .95], [0, 1.2]].map(([x, y]) => new THREE.Vector2(x, y)), 14), std(bodyHex, { ...flat, roughness: .95, transparent: true, opacity: .95 }));
    g.add(cloak);
    parts.core = add(sphere, new THREE.MeshBasicMaterial({ color: new THREE.Color(eyeHex).multiplyScalar(form === "spirit" ? 2.4 : .6) }), .18, .7, 0, .26, .26, .26);
    eyes(.4, .78, .12, .055);
  }
  g.userData = { ...parts, eyeColor: new THREE.Color(eyeHex), form, ribbons: g.userData.figure?.userData.ribbons || [] };
  // 包围尺寸统一：身高约 2.2
  const box = new THREE.Box3().setFromObject(g), size = box.getSize(V());
  const k = 2.3 / Math.max(size.y, size.x * .7);
  const inner = new THREE.Group(); inner.add(...g.children.slice()); inner.scale.setScalar(k);
  const center = box.getCenter(V()).multiplyScalar(k);
  inner.position.sub(center);
  g.add(inner);
  g.userData.inner = inner;
  [sphere, cone, cyl].forEach((x) => kit.track(x));
  return g;
}

// ------------------------------------------------------------------ 主体
/**
 * @param {THREE.WebGLRenderer} renderer 由 fx3d.js 创建的唯一渲染器
 * @param {HTMLElement} host 舞台容器
 * @param {{report, tier, root, skill, form, boss}} ctx 战报与本方/敌方外观线索（只取展示用信息）
 */
export function buildArena(renderer, host, ctx) {
  const report = ctx.report;
  const pal = ELEMENTS[ctx.root] || ELEMENTS.jade;
  const style = ctx.skill === "flame" ? "flame" : ctx.skill === "mountain" ? "palm" : "crescent";
  const sky = SKIES[ctx.tier >= 6 ? 3 : ctx.tier >= 4 ? 2 : ctx.tier >= 2 ? 1 : 0];
  const boss = !!ctx.boss || BOSS_KINDS.has(report.enemy.kind);
  const form = ctx.form || "spirit";
  const disposables = new Set();
  const track = (x) => { disposables.add(x); return x; };
  const tex = makeTextures();
  Object.values(tex).flat().forEach(track);
  const C = (hex) => new THREE.Color(hex);
  let tierIndex = (navigator.hardwareConcurrency || 4) >= 8 ? 2 : 1;

  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = .95;
  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(C(sky.horizon), 70, 280);
  const camera = new THREE.PerspectiveCamera(40, 2, .1, 900);

  // 天穹
  const skyU = { top: { value: C(sky.top) }, horizon: { value: C(sky.horizon) }, bottom: { value: C(sky.bottom) }, sunColor: { value: C(sky.sun) }, sunDir: { value: V(...sky.dir).normalize() }, stars: { value: sky.stars }, time: { value: 0 }, storm: { value: boss ? .55 : 0 }, flash: { value: 0 } };
  const skyMesh = new THREE.Mesh(new THREE.SphereGeometry(500, 32, 16), new THREE.ShaderMaterial({ uniforms: skyU, vertexShader: SKY_VERT, fragmentShader: SKY_FRAG, side: THREE.BackSide, depthWrite: false, depthTest: false, fog: false }));
  skyMesh.renderOrder = -10; skyMesh.frustumCulled = false; scene.add(skyMesh);

  // 云海
  const seaU = { time: { value: 0 }, light: { value: C(sky.light) }, shade: { value: C(sky.shade) }, horizon: { value: C(sky.horizon) }, camPos: { value: V() }, sunColor: { value: C(sky.sun) } };
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(700, 700, 1, 1), new THREE.ShaderMaterial({ uniforms: seaU, vertexShader: SEA_VERT, fragmentShader: SEA_FRAG, transparent: true, depthWrite: false, fog: false }));
  sea.rotation.x = -Math.PI / 2; sea.position.y = -7; sea.renderOrder = -5; scene.add(sea);

  // 远山：多层程序山峰，雾中渐隐
  const mountainMat = std(new THREE.Color(sky.shade).multiplyScalar(.55).getHex(), { flatShading: true, roughness: 1 });
  const mountainGeo = new THREE.ConeGeometry(1, 1, 7, 4);
  { const p = mountainGeo.attributes.position; for (let i = 0; i < p.count; i++) { const y = p.getY(i); if (y > -.49 && y < .49) { p.setX(i, p.getX(i) * rand(.75, 1.25)); p.setZ(i, p.getZ(i) * rand(.75, 1.25)); } } mountainGeo.computeVertexNormals(); }
  const peaks = new THREE.InstancedMesh(mountainGeo, mountainMat, 34);
  { const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = V(), p = V();
    for (let i = 0; i < 34; i++) { const layer = i % 3, h = rand(26, 62) * (1 - layer * .15); p.set(rand(-260, 260), -7 + h * .32 - 6, -90 - layer * 45 - rand(0, 30)); s.set(h * rand(.32, .5), h, h * rand(.32, .5)); q.setFromAxisAngle(V(0, 1, 0), rand(0, 6)); m.compose(p, q, s); peaks.setMatrixAt(i, m); } }
  scene.add(peaks);

  // 浮空仙岛与亭台
  const isles = new THREE.Group();
  const islandGeo = new THREE.ConeGeometry(1, 2.2, 7, 2); islandGeo.rotateX(Math.PI); islandGeo.translate(0, -1.1, 0);
  const grassGeo = new THREE.CylinderGeometry(1.05, 1, .25, 7);
  const roofGeo = new THREE.ConeGeometry(.9, .55, 4); const pillarGeo = new THREE.BoxGeometry(.9, .7, .9);
  const rockMat = std(0x5a5e66, { flatShading: true }), grassMat = std(0x4f8a5c, { flatShading: true }), roofMat = std(0x8a2a22, { flatShading: true }), wallMat = std(0xe8e2d0);
  for (const [x, y, z, s, hut] of [[-30, 5, -55, 3.2, true], [34, 9, -75, 4.2, true], [16, -2, -40, 1.6, false], [-14, 12, -95, 2.4, false], [52, 2, -48, 2, false]]) {
    const isle = new THREE.Group();
    isle.add(new THREE.Mesh(islandGeo, rockMat), new THREE.Mesh(grassGeo, grassMat));
    if (hut) { const w = new THREE.Mesh(pillarGeo, wallMat); w.position.y = .48; const r = new THREE.Mesh(roofGeo, roofMat); r.position.y = 1.08; r.rotation.y = Math.PI / 4; isle.add(w, r); }
    isle.position.set(x, y, z); isle.scale.setScalar(s); isle.userData.phase = rand(0, 6); isle.userData.y = y; isles.add(isle);
  }
  scene.add(isles);

  // 远云团（实例化公告板，沿 z 循环流动 → 御空前行感）
  const puffCount = 70;
  const puffGeo = new THREE.InstancedBufferGeometry();
  const quad = new THREE.PlaneGeometry(1, .62);
  puffGeo.index = quad.index; puffGeo.setAttribute("position", quad.attributes.position); puffGeo.setAttribute("uv", quad.attributes.uv);
  const puffData = new Float32Array(puffCount * 4), puffShade = new Float32Array(puffCount);
  for (let i = 0; i < puffCount; i++) {
    const near = i % 9 === 0;
    puffData[i * 4] = rand(-140, 140); puffData[i * 4 + 1] = near ? rand(-7.5, -5) : rand(-7, 6); puffData[i * 4 + 2] = near ? rand(-14, -2) : rand(-150, -25); puffData[i * 4 + 3] = near ? rand(7, 12) : rand(18, 46);
    puffShade[i] = rand(.55, 1);
  }
  puffGeo.setAttribute("puff", new THREE.InstancedBufferAttribute(puffData, 4));
  puffGeo.setAttribute("shadeK", new THREE.InstancedBufferAttribute(puffShade, 1));
  puffGeo.instanceCount = TIERS[tierIndex].puffs;
  const puffU = { map: { value: tex.puff }, light: { value: C(sky.light) }, shade: { value: C(sky.shade) }, horizon: { value: C(sky.horizon) }, opacity: { value: .5 }, time: { value: 0 }, wind: { value: 6 }, span: { value: 140 } };
  const puffs = new THREE.Mesh(puffGeo, new THREE.ShaderMaterial({ uniforms: puffU, vertexShader: PUFF_VERT, fragmentShader: PUFF_FRAG, transparent: true, depthWrite: false, fog: false }));
  puffs.frustumCulled = false; puffs.renderOrder = -4; scene.add(puffs);
  track(quad);

  // 灯光
  const hemi = new THREE.HemisphereLight(C(sky.light), C(sky.shade), sky.hemi * .85); scene.add(hemi);
  const sun = new THREE.DirectionalLight(C(sky.sun), 1.7); sun.position.set(-sky.dir[0] * -20 + 6, 14, 10); scene.add(sun);
  const rim = new THREE.DirectionalLight(C(pal.main), 2.2); rim.position.set(-8, 4, -10); scene.add(rim);
  const playerLight = new THREE.PointLight(C(pal.main), 3, 7, 1.8); scene.add(playerLight);
  const enemyLight = new THREE.PointLight(C(0xff4040), 4, 9, 1.6); scene.add(enemyLight);
  const flashLights = [0, 1].map(() => { const l = new THREE.PointLight(0xffffff, 0, 16, 1.4); l.userData.life = 0; scene.add(l); return l; });

  // 共享几何
  const kit = {
    swordGeo: track(swordGeometry(2)), eyeGeo: track(new THREE.SphereGeometry(.06, 8, 6)), track,
  };
  const ringGeo = track(new THREE.RingGeometry(.82, 1, 48));
  const discGeo = track(new THREE.PlaneGeometry(1, 1));
  const crescentGeo = track(new THREE.RingGeometry(.55, 1, 32, 1, -Math.PI * .45, Math.PI * .9));
  const sphereGeo = track(new THREE.SphereGeometry(1, 24, 16));
  const shieldGeo = track(new THREE.IcosahedronGeometry(1, 4));
  const rockGeo = track(new THREE.DodecahedronGeometry(1, 0));
  const bellGeo = track(new THREE.LatheGeometry([[0, 1.2], [.35, 1.15], [.5, .8], [.6, .1], [.95, -.9], [1.05, -1.05]].map(([x, y]) => new THREE.Vector2(x, y)), 32));
  const chainGeo = track(new THREE.CylinderGeometry(.035, .035, 1, 6)); chainGeo.translate(0, .5, 0); chainGeo.rotateX(Math.PI / 2);
  const shaftGeo = track(new THREE.CylinderGeometry(.25, 1.5, 40, 16, 1, true)); shaftGeo.translate(0, -20, 0);
  // 金色掌印：掌心 + 五指
  const palmGeo = (() => {
    const parts = [new THREE.BoxGeometry(1.6, 1.8, .35)];
    [[-.6, 1.55, .95], [-.2, 1.75, 1.15], [.2, 1.7, 1.08], [.58, 1.45, .88]].forEach(([x, y, l]) => { const f = new THREE.CapsuleGeometry(.17, l, 3, 8); f.translate(x, y, 0); parts.push(f); });
    const thumb = new THREE.CapsuleGeometry(.19, .75, 3, 8); thumb.rotateZ(.9); thumb.translate(-1.05, .2, 0); parts.push(thumb);
    const merged = mergeGeometries(parts); parts.forEach((p) => p.dispose()); return merged;
  })();
  track(palmGeo);

  // 粒子与拖尾
  const sparks = new Particles(1800, tex.dot, THREE.AdditiveBlending, 1.8);
  const smoke = new Particles(420, tex.smoke, THREE.NormalBlending, 1);
  const motes = new Particles(220, tex.dot, THREE.AdditiveBlending, 1.6);
  scene.add(sparks.points, smoke.points, motes.points);
  const trails = Array.from({ length: 34 }, () => { const t = new Trail(30); scene.add(t.mesh); return t; });
  const getTrail = (color, width, boost, limit) => { const t = trails.find((x) => !x.active) || trails.find((x) => !x.persistent && x.releasing) || trails.find((x) => !x.persistent); t.start(color, width, boost, limit); return t; };

  // ---------------------------------------------------------------- 角色
  const actors = {};
  const actor = (id, group, base) => { actors[id] = { id, group, base: base.clone(), off: V(), vel: V(), shake: 0, tint: 0, frozen: 0, alive: true, gone: 0 }; scene.add(group); group.position.copy(base); return actors[id]; };

  const playerGroup = new THREE.Group();
  const figure = makeCultivator(pal, false); playerGroup.add(figure);
  const ride = makeSword(kit.swordGeo, pal.main, 1); ride.scale.setScalar(1.25); ride.rotation.x = -Math.PI / 2; ride.position.set(.1, -1.42, 0); playerGroup.add(ride);
  const rideGlow = new THREE.Mesh(discGeo, new THREE.MeshBasicMaterial({ map: tex.dot, color: C(pal.main).multiplyScalar(2.2), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  rideGlow.scale.set(5.2, .55, 1); rideGlow.position.set(-1.6, -1.42, 0); playerGroup.add(rideGlow);
  const aura = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.dot, color: C(pal.main).multiplyScalar(1.3), transparent: true, opacity: .3, blending: THREE.AdditiveBlending, depthWrite: false }));
  aura.scale.set(2.6, 3.6, 1); aura.position.set(0, .1, -.4); playerGroup.add(aura);
  const player = actor("player", playerGroup, POS.player);
  player.center = V(0, .1, 0); player.figure = figure; player.ride = ride; player.aura = aura;
  const rideTrail = getTrail(pal.main, .16, 1.6); rideTrail.persistent = true;

  const enemyGroup = makeEnemy(form, kit);
  enemyGroup.rotation.y = Math.PI;
  const enemy = actor("enemy", enemyGroup, POS.enemy);
  enemy.center = V(0, 0, 0);
  const enemyScale = boss ? 1.55 : 1;
  enemyGroup.scale.setScalar(enemyScale);
  enemy.mats = []; enemyGroup.traverse((m) => { if (m.isMesh && m.material.isMeshStandardMaterial) enemy.mats.push(m.material); });
  const halo = new THREE.Mesh(ringGeo, glow(C(0xff7030).multiplyScalar(1.8), .7));
  halo.scale.setScalar(1.2); halo.position.set(0, .35, .9); halo.visible = boss; enemyGroup.add(halo);
  const haloInner = new THREE.Mesh(discGeo, new THREE.MeshBasicMaterial({ map: tex.circle, color: C(0xc02818).multiplyScalar(1.4), transparent: true, opacity: .35, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
  haloInner.scale.setScalar(2.7); haloInner.position.set(0, .35, 1); haloInner.visible = boss; enemyGroup.add(haloInner);
  const enemyAura = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.dot, color: enemy.group.userData.eyeColor.clone().multiplyScalar(.9), transparent: true, opacity: .45, blending: THREE.AdditiveBlending, depthWrite: false }));
  enemyAura.scale.set(3.4, 3.4, 1); enemyAura.position.z = .6; enemyGroup.add(enemyAura);
  enemyLight.color.copy(enemy.group.userData.eyeColor);

  // 敌方护盾
  const barrierU = { color: { value: C(0xffb347) }, time: { value: 0 }, crack: { value: 0 }, flash: { value: 0 }, opacity: { value: 0 }, hit: { value: V(-1, 0, 0) } };
  const barrier = new THREE.Mesh(shieldGeo, new THREE.ShaderMaterial({ uniforms: barrierU, vertexShader: SHIELD_VERT, fragmentShader: SHIELD_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  barrier.scale.setScalar(1.75 * enemyScale); barrier.visible = false; scene.add(barrier);
  // 本方回护六角罩
  const wardU = { color: { value: C(0x5ab8ff) }, time: { value: 0 }, crack: { value: 0 }, flash: { value: 0 }, opacity: { value: 0 }, hit: { value: V(1, 0, 0) } };
  const ward = new THREE.Mesh(shieldGeo, new THREE.ShaderMaterial({ uniforms: wardU, vertexShader: SHIELD_VERT, fragmentShader: SHIELD_FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  ward.scale.setScalar(1.75); ward.visible = false; scene.add(ward);

  // 本命 / 护持法宝
  const treasures = report.treasures || {};
  let mainSword = null, guardDisc = null;
  if (treasures.main) {
    const glowK = .8 + .15 * (Object.keys(QUALITY_SWORDS).indexOf(treasures.main.quality) + 1);
    mainSword = actor("main", makeSword(kit.swordGeo, 0xffc95a, glowK), V(-6.2, 1.4, .8));
    mainSword.count = QUALITY_SWORDS[treasures.main.quality] || 3;
    mainSword.trail = getTrail(0xffd36a, .12, 1.8); mainSword.trail.persistent = true;
  }
  if (treasures.guard) {
    const disc = new THREE.Group();
    const plate = new THREE.Mesh(discGeo, new THREE.MeshBasicMaterial({ map: tex.bagua, color: C(0x7cc8ff).multiplyScalar(1.8), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    plate.scale.setScalar(.9); disc.add(plate);
    const edge = new THREE.Mesh(ringGeo, glow(C(0x9ad8ff).multiplyScalar(2), .9)); edge.scale.setScalar(.48); disc.add(edge);
    guardDisc = actor("guard", disc, V(-4.2, -.7, 1.1));
    guardDisc.plate = plate;
  }
  const hasNpc = report.frames.some((f) => (f.events || []).some((e) => e.source === "npc"));
  if (hasNpc) {
    const npcFig = makeCultivator(ELEMENTS.wood, false); npcFig.scale.setScalar(.72);
    const npcGroup = new THREE.Group(); npcGroup.add(npcFig);
    const s = makeSword(kit.swordGeo, 0x6fe0b0, .6); s.rotation.x = -Math.PI / 2; s.position.set(.05, -1.0, 0); s.scale.setScalar(.85); npcGroup.add(s);
    actor("npc", npcGroup, POS.npc).center = V(0, 0, 0);
  }
  const maxBarrier = Math.max(1, ...report.frames.map((f) => f.enemy?.barrier || 0));

  // ---------------------------------------------------------------- 后期
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), .6, .35, 1.0);
  composer.addPass(bloom);
  const finalPass = new ShaderPass(FINAL_SHADER);
  composer.addPass(finalPass);
  composer.addPass(new OutputPass());
  const post = finalPass.uniforms;

  // ---------------------------------------------------------------- 时钟、时间线、导演
  let clock = 0, real = 0, speed = 1, frameId = 0, last = 0, disposed = false, timeScale = 1, hitstop = 0, outcomeMode = null, outcomeT = 0, defeatT = 0;
  const timeline = [];
  const fx = [];                                   // 活动特效：{ update(dt) → bool }
  const at = (ms, run) => timeline.push({ at: clock + ms / 1000, run });
  const add = (effect) => { fx.push(effect); return effect; };
  const transient = new Set();                    // 特效临时物体：clear() 时统一移除
  const addT = (o) => { scene.add(o); transient.add(o); return o; };
  const dropT = (o) => { if (!transient.delete(o)) return; scene.remove(o); o.traverse((x) => { if (x.material) x.material.dispose(); }); };

  const cam = { pos: V(0, 1.6, 15), look: V(0, .4, 0), focus: V(), focusW: 0, focusUntil: 0, push: 0, trauma: 0, intro: 0, orbit: 0 };
  const camPos = V(), camLook = V(), tmp = V(), tmp2 = V();
  let aspect = 2, baseDist = 15;

  function centerOf(id) {
    const a = actors[id] || actors.enemy;
    tmp.copy(a.center || V()).multiplyScalar(a.group.scale.x);
    if (a === enemy) tmp.applyAxisAngle(V(0, 1, 0), Math.PI);
    return tmp.add(a.group.position).clone();
  }
  function focus(point, weight, seconds, push = 0) {
    cam.focus.copy(point); cam.focusW = Math.max(cam.focusW, weight); cam.focusUntil = real + seconds; cam.push = Math.max(cam.push, push);
  }
  function shake(amount) { cam.trauma = Math.min(1, cam.trauma + amount); }
  function stop(ms) { hitstop = Math.max(hitstop, ms / 1000); }
  function flashLight(p, color, power, life = .35) { const l = flashLights.find((x) => x.userData.life <= 0) || flashLights[0]; l.position.copy(p); l.color.setHex(color); l.userData.peak = power; l.userData.life = l.userData.span = life; }
  function screenFlash(hex, amount) { post.flashColor.value.set(...C(hex).toArray()); post.flash.value = Math.max(post.flash.value, amount); }
  function kick(id, x, y = 0, z = 0) { const a = actors[id]; if (a) a.vel.add(V(x, y, z)); }

  // ---------------------------------------------------------------- 特效积木
  const col = (hex) => C(hex);
  function burst(p, hex, n, power, opts = {}) {
    const c = col(hex), white = col(0xfff6e0), k = TIERS[tierIndex].sparks;
    for (let i = 0; i < Math.round(n * k); i++) {
      const d = V(rand(-1, 1), rand(-1, 1) + (opts.up || 0), rand(-1, 1)).normalize().multiplyScalar(power * rand(.3, 1));
      sparks.spawn(p, d, rand(.35, .8) * (opts.life || 1), rand(.12, .32) * (opts.size || 1), Math.random() < .3 ? white : c, { gravity: opts.gravity ?? 2.5, drag: 2.2 });
    }
  }
  function puffSmoke(p, hex, n, spread = 1, rise = .6) {
    const c = col(hex);
    for (let i = 0; i < n; i++) smoke.spawn(V(p.x + rand(-.4, .4) * spread, p.y + rand(-.3, .3) * spread, p.z + rand(-.4, .4) * spread), V(rand(-.6, .6) * spread, rand(0, rise) + .2, rand(-.6, .6) * spread), rand(.9, 1.6), rand(1.2, 2.2) * spread, c, { size1: rand(2.4, 3.4) * spread, alpha: .55, drag: 1.2 });
  }
  function shockRing(p, hex, from, to, life = .5, axis = "camera") {
    const m = new THREE.Mesh(ringGeo, glow(col(hex).multiplyScalar(2.2), .95));
    m.position.copy(p); if (axis === "ground") m.rotation.x = -Math.PI / 2;
    addT(m); let t = 0;
    add({ update(dt) { t += dt / life; if (axis === "camera") m.quaternion.copy(camera.quaternion); const s = lerp(from, to, easeOut(Math.min(1, t))); m.scale.setScalar(s); m.material.opacity = .95 * (1 - t); if (t >= 1) { dropT(m); return false; } return true; } });
  }
  function glowSprite(p, hex, size, life, map = tex.dot, grow = 1.6) {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map, color: col(hex).multiplyScalar(1.15), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    s.position.copy(p); s.scale.setScalar(size); addT(s); let t = 0;
    add({ update(dt) { t += dt / life; s.scale.setScalar(size * lerp(1, grow, easeOut(Math.min(1, t)))); s.material.opacity = 1 - t; if (t >= 1) { dropT(s); return false; } return true; } });
    return s;
  }
  function slashMark(p, hex, n = 3, size = 2.2, tilt = .6) {
    for (let i = 0; i < n; i++) {
      const m = new THREE.Mesh(crescentGeo, glow(col(hex).multiplyScalar(2.6), 1));
      m.position.copy(p).add(V(0, (i - (n - 1) / 2) * .38, .3)); m.rotation.set(0, 0, tilt + i * .08); m.scale.set(size, size * .35, 1);
      addT(m); let t = -i * .05;
      add({ update(dt) { t += dt / .42; const k = clamp(t, 0, 1); m.scale.set(size * (.6 + k * .6), size * .35 * (1 - k * .6), 1); m.material.opacity = t < 0 ? 0 : 1 - k; if (t >= 1) { dropT(m); return false; } return true; } });
    }
  }
  // 抛射体：沿二次贝塞尔从 a 飞向 b，用时 dur 秒；每帧回调 step(p, t)
  function projectile(a, b, dur, arc, step, done) {
    const c = a.clone().add(b).multiplyScalar(.5).add(V(0, arc, rand(-.6, .6))); let t = 0;
    const p = V();
    add({ update(dt) {
      t = Math.min(1, t + dt / dur); const u = t;
      p.set((1 - u) ** 2 * a.x + 2 * (1 - u) * u * c.x + u * u * b.x, (1 - u) ** 2 * a.y + 2 * (1 - u) * u * c.y + u * u * b.y, (1 - u) ** 2 * a.z + 2 * (1 - u) * u * c.z + u * u * b.z);
      step(p, t);
      if (t >= 1) { done?.(p.clone()); return false; } return true;
    } });
  }
  function chargeAt(p, hex, dur = .22, radius = 1.4, n = 22) {
    const c = col(hex);
    for (let i = 0; i < n; i++) { const d = V(rand(-1, 1), rand(-1, 1), rand(-1, 1)).normalize().multiplyScalar(radius); sparks.spawn(V().copy(p).add(d), d.clone().multiplyScalar(-1 / dur * 1.6), dur, rand(.1, .2), c, { drag: 0, size1: .05 }); }
    glowSprite(p, hex, .6, dur * 1.4, tex.dot, 3);
  }
  function magicCircle(p, hex, size, life, facing = "x", spin = 1.6) {
    const m = new THREE.Mesh(discGeo, new THREE.MeshBasicMaterial({ map: tex.circle, color: col(hex).multiplyScalar(2.2), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    m.position.copy(p); if (facing === "x") m.rotation.y = Math.PI / 2; else if (facing === "y") m.rotation.x = -Math.PI / 2;
    addT(m); let t = 0;
    add({ update(dt) { t += dt / life; const k = Math.min(1, t * 4); m.scale.setScalar(size * easeOut(k)); m.rotateZ(dt * spin); m.material.opacity = t < .75 ? 1 : (1 - t) / .25; if (t >= 1) { dropT(m); return false; } return true; } });
    return m;
  }
  function impact(p, hex, k, opts = {}) {
    burst(p, hex, 30 + 50 * k, 5 + 8 * k, { gravity: 3 });
    shockRing(p, hex, .4, 2.2 + 3 * k, .45 + .2 * k);
    if (k > .45) shockRing(p, 0xffffff, .3, 1.4 + 2 * k, .3);
    glowSprite(p, hex, 1.2 + 1.5 * k, .3, tex.dot, 1.6);
    flashLight(p, hex, 14 + 30 * k, .4);
    shake(.18 + .5 * k);
    if (k > .35) stop(50 + 110 * k);
    if (opts.smoke) puffSmoke(p, opts.smoke, Math.round(6 + 10 * k), .8 + k);
  }
  function hurtFlash(id, hex = 0xff3030) { const a = actors[id]; if (a) a.tint = 1, a.tintColor = col(hex); }

  // ---------------------------------------------------------------- 招式
  function playerStrike(event, k, action) {
    const strong = /强攻/.test(action || "") || /强攻/.test(event.label || "");
    const talisman = /焚火符/.test(action || "") || /焚火/.test(event.label || "");
    const from = centerOf("player").add(V(.6, .4, 0)), to = centerOf("enemy");
    const kk = clamp(k * (strong ? 1.4 : 1), .2, 1);
    kick("player", strong ? 1.6 : .9, .3, 0);
    if (strong) {
      magicCircle(centerOf("player").add(V(-.7, .2, 0)), pal.main, 4.2, 1.1, "x", 2.4);
      focus(centerOf("player"), .8, .5, 3.5);
      at(320, () => focus(to, 1, .7, 4));
    } else focus(to, .45, .7, 1.2);
    const wait = strong ? 340 : 160;
    chargeAt(from, pal.main, wait / 1000, strong ? 2.2 : 1.3, strong ? 40 : 20);
    if (talisman) return at(wait, () => throwTalisman(from, to, 0xff7a2e, () => { impact(to, 0xff7a2e, kk, { smoke: 0x3a2a24 }); fireBloom(to, kk); hurtFlash("enemy", 0xff8a3a); kick("enemy", .9, 0, 0); }));
    if (style === "flame") at(wait, () => fireball(from, to, kk, strong));
    else if (style === "palm") at(wait, () => goldenPalm(to, kk, strong));
    else at(wait, () => crescent(from, to, pal.main, kk, strong));
  }

  function crescent(from, to, hex, k, strong, enemySide = false) {
    const n = strong ? 3 : 1;
    for (let i = 0; i < n; i++) at(i * 90, () => {
      const m = new THREE.Mesh(crescentGeo, glow(col(hex).multiplyScalar(3), 1));
      const size = (strong ? 2.4 : 1.6) * (1 + k * .3);
      m.scale.set(size, size, 1); addT(m);
      const trail = getTrail(hex, .5 * size, 2.4);
      const off = V(0, (i - (n - 1) / 2) * .7, 0);
      projectile(from.clone().add(off), to.clone().add(off.multiplyScalar(.3)), .32, enemySide ? .6 : .9, (p) => { m.position.copy(p); m.lookAt(camera.position); m.rotateZ(enemySide ? Math.PI : 0); trail.push(p); if (Math.random() < .7) sparks.spawn(p, V(rand(-1, 1), rand(-1, 1), rand(-1, 1)), .4, .14, col(0xffffff)); }, (p) => {
        dropT(m); trail.release();
        const target = enemySide ? "player" : "enemy";
        impact(p, hex, k); slashMark(p, hex, strong ? 3 : 2, 2 + k * 1.6, enemySide ? -.6 : .6);
        hurtFlash(target, enemySide ? 0xff3030 : 0xffffff); kick(target, enemySide ? -1.6 * k - .5 : 1.6 * k + .5, 0, 0);
      });
    });
  }

  function fireball(from, to, k, strong) {
    const core = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.dot, color: col(0xffb050).multiplyScalar(1.5), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    const size = (strong ? 1.8 : 1.2) * (1 + k * .3); core.scale.setScalar(size); addT(core);
    const tA = getTrail(0xff6a1a, .45 * size, 1.8), tB = getTrail(0xffb040, .25 * size, 1.8);
    let spin = 0;
    projectile(from, to, strong ? .5 : .42, 1.4, (p, t) => {
      spin += .35; core.position.copy(p);
      tA.push(tmp2.copy(p).add(V(0, Math.sin(spin) * .35, Math.cos(spin) * .35)));
      tB.push(tmp2.copy(p).add(V(0, -Math.sin(spin) * .35, -Math.cos(spin) * .35)));
      // 火凤双翼：两侧扇形火羽
      for (let i = 0; i < 4; i++) { const w = (i % 2 ? 1 : -1); sparks.spawn(p, V(rand(-2.5, -1), w * rand(1.5, 3.2) * (1 - t * .5), rand(-.6, .6)), rand(.25, .45), rand(.25, .5) * size * .5, col(i < 2 ? 0xff5a1a : 0xffc04a), { gravity: -1.5, drag: 3 }); }
    }, (p) => {
      dropT(core); tA.release(); tB.release();
      impact(p, 0xff6a1a, k, { smoke: 0x2f2420 }); fireBloom(p, k);
      hurtFlash("enemy", 0xff8a3a); kick("enemy", 1.4 * k + .6, .2, 0);
    });
  }
  function fireBloom(p, k) {
    const ball = new THREE.Mesh(sphereGeo, glow(col(0xff6a1a).multiplyScalar(1.1), .55)); ball.position.copy(p); addT(ball); let t = 0;
    add({ update(dt) { t += dt / .55; ball.scale.setScalar(lerp(.3, 1.6 + 1.4 * k, easeOut(Math.min(1, t)))); ball.material.opacity = .55 * (1 - t) ** 2; if (t >= 1) { dropT(ball); return false; } return true; } });
    for (let i = 0; i < 30 * TIERS[tierIndex].sparks; i++) sparks.spawn(p, V(rand(-4, 4), rand(1, 6), rand(-3, 3)), rand(.6, 1.2), rand(.08, .16), col(0xffb05a), { gravity: 4, drag: .8 });
  }

  function goldenPalm(to, k, strong) {
    const m = new THREE.Mesh(palmGeo, glow(col(0xffa828).multiplyScalar(.75), .0));
    const edge = new THREE.Mesh(palmGeo, new THREE.MeshBasicMaterial({ color: col(0xffe08a).multiplyScalar(1.6), wireframe: true, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
    const g = new THREE.Group(); g.add(m, edge); addT(g);
    const size = (strong ? 2.2 : 1.5) * (1 + k * .3);
    const start = to.clone().add(V(-.5, 9, 0)), end = to.clone().add(V(0, .9, 0));
    g.rotation.set(-.25, 0, .08); g.scale.setScalar(size * .4);
    magicCircle(start.clone().add(V(0, 1, 0)), 0xffc24a, 4 * size / 1.5, .9, "y", 1.2);
    focus(to.clone().add(V(0, 2.5, 0)), .7, .9, strong ? 3 : 1.6);
    let t = 0;
    add({ update(dt) {
      t += dt / (strong ? .62 : .5); const k1 = Math.min(1, t);
      g.position.lerpVectors(start, end, easeIn(k1)); g.scale.setScalar(size * lerp(.4, 1, easeOut(Math.min(1, t * 2))));
      m.material.opacity = Math.min(.5, t * 3); edge.material.opacity = Math.min(.55, t * 2);
      if (Math.random() < .8) sparks.spawn(g.position, V(rand(-1, 1), 2, rand(-1, 1)), .4, .25, col(0xffd36a), { gravity: -2 });
      if (t >= 1) {
        impact(end, 0xffc24a, Math.min(1, k * 1.2), { smoke: 0xb89a6a });
        shockRing(end.clone().add(V(0, -1.8, 0)), 0xffd36a, 1, 6 + 4 * k, .7, "ground");
        hurtFlash("enemy", 0xffe0a0); kick("enemy", .4, -2.2 * k - .6, 0);
        let f = 0; add({ update(d) { f += d / .35; m.material.opacity = .5 * (1 - f); edge.material.opacity = .55 * (1 - f); g.scale.multiplyScalar(1 + d * .6); if (f >= 1) { dropT(g); return false; } return true; } });
        return false;
      }
      return true;
    } });
  }

  function throwTalisman(from, to, hex, done) {
    const m = new THREE.Mesh(discGeo, new THREE.MeshBasicMaterial({ map: tex.talisman, transparent: true, side: THREE.DoubleSide, depthWrite: false }));
    m.scale.set(.42, 1.1, 1); addT(m);
    let spin = 0;
    projectile(from, to, .45, 1.2, (p) => { m.position.copy(p); spin += .4; m.rotation.set(spin * .3, spin, .4); sparks.spawn(p, V(rand(-1, 0), rand(0, 1.5), rand(-.5, .5)), .45, .22, col(hex), { gravity: -1 }); }, (p) => { dropT(m); glowSprite(p, 0xfff0c0, 2, .3); done(p); });
  }

  // 本命法宝：万剑归宗——剑影分化、扇形列阵、依次俯冲
  function swordRain(k) {
    if (!mainSword) return;
    const n = mainSword.count, to = centerOf("enemy"), origin = mainSword.group.position.clone();
    const rise = origin.clone().add(V(.4, 2.2, 0));
    focus(to.clone().add(V(-2, 1.5, 0)), .6, 1.1, 1.8);
    glowSprite(origin, 0xffd36a, 1.4, .4, tex.dot, 3);
    for (let i = 0; i < n; i++) {
      const s = new THREE.Mesh(kit.swordGeo, new THREE.MeshBasicMaterial({ color: col(0xffd36a).multiplyScalar(2.6), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false }));
      addT(s);
      const a = (i / Math.max(1, n - 1) - .5) * 2.2, slot = rise.clone().add(V(Math.sin(a) * .9 - .6, Math.cos(a) * 1.4, (i % 2 ? 1 : -1) * i * .12));
      const trail = getTrail(0xffd36a, .14, 2); let t = -i * .045, hit = false;
      add({ update(dt) {
        t += dt;
        if (t < 0) return true;
        if (t < .28) { const u = easeOut(t / .28); s.position.lerpVectors(origin, slot, u); s.material.opacity = u; s.lookAt(to); s.rotateY(-Math.PI / 2); return true; }
        const u = Math.min(1, (t - .28 - i * .03) / .22);
        if (u < 0) return true;
        s.position.lerpVectors(slot, to.clone().add(V(rand(-.15, .15), rand(-.3, .3), rand(-.3, .3))), easeIn(u)); trail.push(s.position);
        if (u >= 1 && !hit) {
          hit = true; trail.release(); dropT(s);
          burst(s.position, 0xffd36a, 14, 6); flashLight(s.position, 0xffd36a, 8, .2); shake(.08 + .05 * k);
          if (i === n - 1) { impact(to, 0xffd36a, k); hurtFlash("enemy", 0xffe8a0); kick("enemy", 1.2, 0, 0); }
          return false;
        }
        return true;
      } });
    }
    kick("main", 0, 1.2, 0);
  }

  function npcBolt(k) {
    if (!actors.npc) return;
    const from = centerOf("npc"), to = centerOf("enemy");
    chargeAt(from, 0x6fe0b0, .15, .8, 10);
    at(150, () => { const tr = getTrail(0x6fe0b0, .22, 2); projectile(from, to, .45, 2.2, (p) => { tr.push(p); sparks.spawn(p, V(), .3, .3, col(0xbfffe6)); }, (p) => { tr.release(); impact(p, 0x6fe0b0, k * .6); hurtFlash("enemy", 0xc8ffe6); }); });
  }

  function enemyStrike(event, k, heavy) {
    const from = centerOf("enemy"), to = centerOf("player"), red = boss ? 0xff3a24 : 0xff4a3a;
    const kk = clamp(k * (heavy ? 1.3 : 1), .2, 1);
    if (heavy) { magicCircle(from.clone().add(V(.6, .2, 0)), red, 3.6 * enemyScale, .9, "x", -2); focus(from, .7, .45, 2.4); at(380, () => focus(to, .9, .6, 2.6)); }
    else focus(to, .35, .6, .8);
    const wait = heavy ? 380 : 180;
    chargeAt(from, red, wait / 1000, 1.6 * enemyScale, heavy ? 36 : 18);
    const hitPlayer = (p, color) => {
      impact(p, color, kk); hurtFlash("player"); kick("player", -1.4 * kk - .5, .1, 0);
      if (heavy) { screenFlash(0x8a0000, .2); post.aberration.value = Math.max(post.aberration.value, .02); }
    };
    at(wait, () => {
      if (form === "beast" || form === "ape" || form === "fox") {
        kick("enemy", -5.5 * (heavy ? 1.3 : 1), .5, 0);
        at(160, () => { slashMark(to, form === "fox" ? 0xd65cff : red, 3, 2.4 + kk, -.7); hitPlayer(to, form === "fox" ? 0xd65cff : red); if (form === "fox") { for (let i = 0; i < 3; i++) at(i * 60, () => glowSprite(to.clone().add(V(rand(-.6, .6), rand(-.6, .6), 0)), 0xd65cff, 1.2, .4)); } });
      } else if (form === "golem") {
        const rock = new THREE.Mesh(rockGeo, std(0x6a665e, { flatShading: true, emissive: new THREE.Color(0xff6a2a), emissiveIntensity: .3 }));
        rock.scale.setScalar(.5 + .4 * kk); addT(rock);
        projectile(from.clone().add(V(-.4, 1, 0)), to, .5, 3.4, (p) => { rock.position.copy(p); rock.rotation.x += .2; rock.rotation.z += .15; if (Math.random() < .6) smoke.spawn(p, V(0, .3, 0), .7, .6, col(0x8a8070), { size1: 1.4, alpha: .5 }); }, (p) => { dropT(rock); hitPlayer(p, 0xff8a3a); puffSmoke(p, 0x8a8070, 8, 1); for (let i = 0; i < 10; i++) sparks.spawn(p, V(rand(-4, 4), rand(1, 5), rand(-2, 2)), .7, .2, col(0xffa060), { gravity: 9 }); });
      } else if (form === "serpent") {
        const head = from.clone().add(V(-.8, .2, 0));
        for (let i = 0; i < 26; i++) at(i * 14, () => { const d = to.clone().sub(head).normalize().multiplyScalar(rand(9, 12)); smoke.spawn(head, d.clone().add(V(rand(-1, 1), rand(-1, 1), rand(-1, 1))), .55, .5, col(0x2a8a6a), { size1: 1.6, alpha: .6, drag: 1 }); sparks.spawn(head, d, .5, .25, col(0x7cff6a), { drag: .5 }); });
        at(380, () => hitPlayer(to, 0x7cff6a));
      } else if (form === "human") {
        crescent(from.clone().add(V(-.6, .4, 0)), to, red, kk, heavy, true);
      } else {
        // 魂影：三道暗影触须
        for (let i = 0; i < 3; i++) {
          const tr = getTrail(form === "spirit" ? 0x7ad8ff : 0xa040ff, .3, 1.8);
          const a = from.clone().add(V(0, (i - 1) * .7, 0));
          projectile(a, to.clone().add(V(0, (i - 1) * .2, 0)), .4 + i * .05, (i - 1) * 2.4, (p) => { tr.push(p); smoke.spawn(p, V(0, .2, 0), .5, .5, col(0x1a1024), { size1: 1, alpha: .5 }); }, (p) => { tr.release(); if (i === 1) hitPlayer(p, form === "spirit" ? 0x7ad8ff : 0xa040ff); });
        }
      }
    });
  }

  function absorbWard(k) {
    const p = centerOf("player");
    ward.position.copy(p); ward.visible = true; wardU.opacity.value = 1; wardU.flash.value = 1;
    if (guardDisc) { kick("guard", 2, .8, 0); glowSprite(guardDisc.group.position, 0x7cc8ff, 1.5, .4); }
    magicCircle(p.clone().add(V(1.6, 0, 0)), 0x7cc8ff, 3.2, .8, "x", 3);
    burst(p.clone().add(V(1.6, 0, 0)), 0x7cc8ff, 30, 5);
    flashLight(p.clone().add(V(1.6, 0, 0)), 0x7cc8ff, 16, .5);
    shake(.12);
  }

  function healSpiral() {
    const p = centerOf("player"), c = col(0x6fe0a0), w = col(0xe6fff0);
    glowSprite(p.clone().add(V(0, 2.5, 0)), 0x9fffd0, .8, .5, tex.dot, 1);
    for (let i = 0; i < 46; i++) at(i * 16, () => { const a = i * .55, r = 1.1; sparks.spawn(V(p.x + Math.cos(a) * r, p.y - 1.4 + i * .05, p.z + Math.sin(a) * r), V(-Math.sin(a) * 1.5, 2.4, Math.cos(a) * 1.5), .7, rand(.14, .26), i % 3 ? c : w, { drag: .6 }); });
    flashLight(p, 0x6fe0a0, 10, .9); hurtFlash("player", 0x6fe0a0);
  }

  function runeOrbit(hex, count, radius, life, center = centerOf("player")) {
    const sprites = Array.from({ length: count }, (_, i) => {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex.runes[i % tex.runes.length], color: col(hex).multiplyScalar(2.4), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
      s.scale.setScalar(.5); addT(s); return s;
    });
    let t = 0;
    add({ update(dt) {
      t += dt / life;
      sprites.forEach((s, i) => { const a = i / count * 6.283 + t * 5, r = radius * (t < .8 ? easeOut(Math.min(1, t * 3)) : lerp(1, .1, (t - .8) / .2)); s.position.set(center.x + Math.cos(a) * r, center.y + Math.sin(t * 6 + i) * .2, center.z + Math.sin(a) * r); s.material.opacity = t < .8 ? 1 : (1 - t) / .2; });
      if (t >= 1) { sprites.forEach((s) => { dropT(s); }); return false; }
      return true;
    } });
  }

  function goldenBell() {
    const p = centerOf("player");
    const m = new THREE.Mesh(bellGeo, glow(col(0xffcf5a).multiplyScalar(1.6), 0)); m.position.copy(p).add(V(0, 5, 0)); m.scale.setScalar(1.5); addT(m);
    const w = new THREE.Mesh(bellGeo, new THREE.MeshBasicMaterial({ color: col(0xfff0b0).multiplyScalar(2), wireframe: true, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false })); m.add(w);
    let t = 0, rung = false;
    add({ update(dt) {
      t += dt / .95; const d = Math.min(1, t * 2.6);
      m.position.y = lerp(p.y + 5, p.y + .2, easeOut(d)); m.material.opacity = Math.min(.42, d * .6) * (t > .7 ? (1 - t) / .3 : 1); w.material.opacity = m.material.opacity * .6; m.rotation.y += dt;
      if (d >= 1 && !rung) { rung = true; shockRing(p, 0xffd36a, 1, 3.6, .5); shockRing(p.clone().add(V(0, -1.2, 0)), 0xffd36a, 1, 4.5, .6, "ground"); flashLight(p, 0xffcf5a, 10, .5); }
      if (t >= 1) { dropT(m); return false; }
      return true;
    } });
    // 回灵：蓝色灵息汇入
    for (let i = 0; i < 22; i++) at(i * 20, () => { const d = V(rand(-1, 1), rand(-.6, 1), rand(-1, 1)).normalize().multiplyScalar(3); sparks.spawn(p.clone().add(d), d.clone().multiplyScalar(-1.6), .6, .18, col(0x6ab8ff), { drag: 0, size1: .05 }); });
  }

  function sealEnemy() {
    const from = centerOf("player").add(V(.6, .4, 0)), to = centerOf("enemy");
    focus(to, .6, 1.2, 1.8);
    throwTalisman(from, to, 0xffd36a, (p) => {
      const top = to.clone().add(V(0, 2.4 * enemyScale, 0));
      const disc = magicCircle(top, 0xffd36a, 3.2 * enemyScale, 1.2, "y", 2);
      disc.material.map = tex.bagua;
      const chains = [0, 1, 2, 3].map((i) => { const c = new THREE.Mesh(chainGeo, glow(col(0xffe08a).multiplyScalar(2.4), .9)); c.userData.a = i * Math.PI / 2; addT(c); return c; });
      let t = 0;
      add({ update(dt) {
        t += dt / 1.15;
        chains.forEach((c) => { const a = c.userData.a + t * 2; const s = V(top.x + Math.cos(a) * 1.4 * enemyScale, top.y, top.z + Math.sin(a) * 1.4 * enemyScale); c.position.copy(s); c.lookAt(to); c.scale.set(1, 1, s.distanceTo(to) * Math.min(1, t * 4)); c.material.opacity = .9 * (t > .75 ? (1 - t) / .25 : 1); });
        if (t >= 1) { chains.forEach((c) => { dropT(c); }); return false; }
        return true;
      } });
      enemy.frozen = 1.1; hurtFlash("enemy", 0xffe08a); runeOrbit(0xffd36a, 6, 1.6 * enemyScale, 1.1, to);
      burst(p, 0xffd36a, 30, 5);
    });
  }

  function poisonCloud() {
    const p = centerOf("player");
    puffSmoke(p, 0x3a8a3a, 14, 1.1, .8);
    for (let i = 0; i < 18; i++) sparks.spawn(p.clone().add(V(rand(-.7, .7), rand(-1, .5), rand(-.7, .7))), V(0, rand(.8, 1.8), 0), rand(.6, 1), .16, col(0x8aff5a), { drag: .5 });
    hurtFlash("player", 0x6aff4a);
  }
  function manaDrain() {
    const from = centerOf("player"), to = centerOf("enemy");
    for (let i = 0; i < 30; i++) at(i * 12, () => { const s = from.clone().add(V(rand(-.5, .5), rand(-.5, .8), rand(-.5, .5))); sparks.spawn(s, to.clone().sub(s).multiplyScalar(rand(1.6, 2.2)), .55, .2, col(0x5aa9ff), { drag: 0 }); });
    at(380, () => glowSprite(to, 0x5aa9ff, 2.5, .5));
    hurtFlash("player", 0x5aa9ff);
  }
  function breakBarrier(event, k) {
    const to = centerOf("enemy");
    barrierU.flash.value = 1; barrierU.hit.value.set(-1, rand(-.3, .3), rand(-.3, .3));
    burst(to.clone().add(V(-1.6 * enemyScale, 0, 0)), 0xffb347, 30, 6);
    shake(.15);
  }

  // ---------------------------------------------------------------- 对外：事件驱动
  function play(event, opts = {}) {
    if (disposed) return;
    const k = clamp(opts.intensity ?? .4, .15, 1), action = opts.action || "";
    const src = event.source;
    switch (event.type) {
      case "damage":
        if (src === "player") playerStrike(event, k, action);
        else if (src === "main") swordRain(k);
        else if (src === "npc") npcBolt(k);
        else if (src === "enemy") enemyStrike(event, k, /重击/.test(event.label || "") || k > .55);
        break;
      case "shield":
        if (src === "main") swordRain(k); else if (src === "npc") npcBolt(k); else playerStrike(event, k, action);
        at(src === "player" ? 520 : 600, () => breakBarrier(event, k));
        break;
      case "shield_absorb": absorbWard(k); break;
      case "heal": healSpiral(); break;
      case "buff":
        at(0, () => { const p = centerOf("player"); throwTalisman(p.clone().add(V(.8, 1.4, 0)), p.clone().add(V(0, 1.6, 0)), 0xffd36a, () => runeOrbit(0xffd36a, 8, 1.5, 1.1)); });
        break;
      case "defend": goldenBell(); break;
      case "control": sealEnemy(); break;
      case "poison": poisonCloud(); break;
      case "mana": manaDrain(); break;
      default: break;
    }
    wake();
  }

  // 帧状态：气血、护盾、倒下与终局演出
  let lastCursorDown = false;
  function setFrame(frame, info = {}) {
    if (disposed || !frame) return;
    const hpRatio = frame.enemy.hp / Math.max(1, report.enemy.max_hp);
    enemy.wounded = hpRatio < .3 ? 1 - hpRatio / .3 : 0;
    const bar = frame.enemy.barrier || 0;
    barrier.visible = bar > 0 || barrierU.opacity.value > .02;
    barrier.userData.target = bar > 0 ? 1 : 0;
    barrierU.crack.value = bar > 0 ? 1 - bar / maxBarrier : 1;
    const down = frame.enemy.hp <= 0;
    if (down && !lastCursorDown) { if (info.animate) dissolveEnemy(); else { enemy.gone = 1; enemyGroup.visible = false; } }
    if (!down && lastCursorDown) { enemy.gone = 0; enemyGroup.visible = true; enemyGroup.scale.setScalar(enemyScale); }
    lastCursorDown = down;
    const playerDown = info.last && info.outcome === "defeat" && frame.player.hp <= 0;
    defeatT = playerDown ? (info.animate ? Math.max(defeatT, .001) : 1) : 0;
    if (!playerDown) post.desat.value = 0;
    outcomeMode = info.last ? info.outcome : null;
    if (!info.last) { outcomeT = 0; shafts.visible = false; }
    if (info.last && info.outcome === "victory") { shafts.visible = true; if (!info.animate) outcomeT = 1; }
    wake();
  }
  function dissolveEnemy() {
    const c = centerOf("enemy"), eyeHex = enemy.group.userData.eyeColor.getHex();
    focus(c, .9, 1.6, 3);
    stop(160); shake(.5);
    let t = 0;
    add({ update(dt) {
      t += dt / 1.3;
      const k = Math.min(1, t);
      enemyGroup.scale.setScalar(enemyScale * (1 - easeIn(k) * .35));
      enemy.gone = k;
      for (let i = 0; i < 6 * TIERS[tierIndex].sparks; i++) {
        const p = c.clone().add(V(rand(-1, 1), rand(-1.1, 1.1), rand(-.6, .6)).multiplyScalar(enemyScale));
        (Math.random() < .5 ? smoke : sparks).spawn(p, V(rand(.2, 1.6), rand(.6, 2.2), rand(-.5, .5)), rand(.7, 1.4), Math.random() < .5 ? rand(.5, 1) : rand(.08, .18), Math.random() < .5 ? col(0x1a1418) : col(Math.random() < .5 ? eyeHex : 0xffc07a), { size1: .05, alpha: .7, gravity: -.6 });
      }
      if (t >= 1) { enemyGroup.visible = false; burst(c, 0xfff0c0, 60, 7, { up: .4 }); glowSprite(c, 0xfff0c0, 4, .8, tex.dot, 2); flashLight(c, 0xfff0c0, 30, .8); return false; }
      return true;
    } });
  }
  // 胜局光柱
  const shafts = new THREE.Group();
  for (let i = 0; i < 5; i++) {
    const s = new THREE.Mesh(shaftGeo, new THREE.MeshBasicMaterial({ color: col(0xfff0c8).multiplyScalar(1.2), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide, fog: false }));
    s.position.set(-6 + i * 3.4 + rand(-1, 1), 24, -4 - rand(0, 6)); s.rotation.z = rand(-.25, .25); s.userData.phase = rand(0, 6); shafts.add(s);
  }
  shafts.visible = false; scene.add(shafts);

  // ---------------------------------------------------------------- 尺寸与质量
  function resize() {
    const rect = host.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratio = Math.min(TIERS[tierIndex].ratio, globalThis.devicePixelRatio || 1);
    renderer.setPixelRatio(ratio);
    renderer.setSize(rect.width, rect.height, false);
    composer.setPixelRatio(ratio); composer.setSize(rect.width, rect.height);
    bloom.enabled = TIERS[tierIndex].bloom;
    aspect = rect.width / rect.height;
    camera.aspect = aspect;
    // 横屏左右对阵；竖屏改为斜对站位，镜头只后撤到双方都清晰可辨
    const half = Math.tan(camera.fov * Math.PI / 360), portrait = aspect < 1;
    const layout = portrait ? PORTRAIT : POS;
    player.base.copy(layout.player); enemy.base.copy(layout.enemy);
    baseDist = portrait ? Math.min(26, Math.max(13, (boss ? 4.4 : 3.6) / (half * aspect))) : Math.max(boss ? 12 : 10.5, (boss ? 9.2 : 7.8) / (half * aspect));
    camera.updateProjectionMatrix();
    const scale = rect.height * ratio * .5 / half;
    for (const p of [sparks, smoke, motes]) p.material.uniforms.scale.value = scale;
    puffGeo.instanceCount = TIERS[tierIndex].puffs;
  }
  const observer = globalThis.ResizeObserver ? new ResizeObserver(() => { resize(); wake(); }) : null;
  observer?.observe(host);
  resize();

  const frames = [];
  function adapt(ms) {
    frames.push(ms); if (frames.length > 90) frames.shift();
    if (frames.length < 90) return;
    const avg = frames.reduce((a, b) => a + b, 0) / frames.length;
    if (avg > 30 && tierIndex > 0) { tierIndex -= 1; frames.length = 0; resize(); }
  }

  // ---------------------------------------------------------------- 主循环
  const visible = () => !disposed && host.isConnected && !document.hidden && host.getClientRects().length > 0 && !host.closest("[hidden]");
  function animateActors(dt, t) {
    for (const a of Object.values(actors)) {
      // 弹簧回位：被击退/突进后回到站位
      a.vel.addScaledVector(a.off, -38 * dt); a.vel.multiplyScalar(Math.exp(-7 * dt)); a.off.addScaledVector(a.vel, dt);
      if (a.frozen > 0) a.frozen -= dt;
      const bob = a.frozen > 0 ? 0 : Math.sin(t * 1.3 + (a.id === "enemy" ? 1.7 : 0)) * .16;
      a.group.position.copy(a.base).add(a.off); a.group.position.y += bob;
      if (a.tint > 0) a.tint = Math.max(0, a.tint - dt * 4);
    }
    // 本方：衣袂飘带、御剑微倾
    figure.rotation.z = Math.sin(t * .9) * .035 - player.off.x * .05;
    player.ride.rotation.z = Math.sin(t * 1.3) * .03;
    aura.material.opacity = .22 + .08 * Math.sin(t * 2.2) + player.tint * .35;
    aura.material.color.copy(player.tint > 0 && player.tintColor ? player.tintColor : C(pal.main));
    for (const r of [...figure.userData.ribbons, ...(enemy.group.userData.ribbons || []), ...(actors.npc ? actors.npc.group.children[0].userData.ribbons : [])]) waveRibbon(r, t);
    rideTrail.push(tmp.copy(player.group.position).add(V(-1.6, -1.42, 0)));
    if (rideTrail.pts.length > 2) for (const p of rideTrail.pts) p.x -= dt * 9;      // 剑尾光迹向后流，御空前行
    playerLight.position.copy(player.group.position).add(V(.5, .5, 1.5));
    playerLight.intensity = 2.5 + Math.sin(t * 3) * .6 + player.tint * 8;
    // 敌方
    if (enemy.group.visible) {
      const ud = enemy.group.userData;
      ud.tails?.forEach((tail, i) => { tail.rotation.x = Math.sin(t * 2.2 + i) * .25; });
      ud.segs?.forEach((seg, i) => { const [x, y, z] = serpentAt(i, t); seg.position.set(x, y, z); });
      if (ud.head && ud.form === "serpent") ud.head.position.x = .45 + Math.sin(-t * 1.6) * .2;
      if (ud.core) ud.core.scale.setScalar((ud.form === "golem" ? .16 : .26) * (1 + .15 * Math.sin(t * 5)));
      const hurt = enemy.tint, wound = enemy.wounded || 0, frozen = enemy.frozen > 0;
      for (const m of enemy.mats) { if (!m.userData.base) m.userData.base = { e: m.emissive.clone(), i: m.emissiveIntensity }; m.emissive.copy(hurt > 0 && enemy.tintColor ? enemy.tintColor : frozen ? C(0xffd36a) : C(0xff2a2a)); m.emissiveIntensity = hurt * 1.4 + (frozen ? .5 : 0) + wound * (.25 + .2 * Math.sin(t * 8)); if (!hurt && !frozen && !wound) { m.emissive.copy(m.userData.base.e); m.emissiveIntensity = m.userData.base.i; } }
      halo.rotation.z += dt * .6; haloInner.rotation.z -= dt * .3;
      enemyAura.material.opacity = .2 + .08 * Math.sin(t * 2) + hurt * .3;
      enemyLight.position.copy(enemy.group.position).add(V(-.5, .6, 1.5));
      enemyLight.intensity = 3 + Math.sin(t * 2.5) + (boss ? 3 : 0);
      if (ud.form === "shade" || ud.form === "spirit") if (Math.random() < .5) smoke.spawn(centerOf("enemy").add(V(rand(-.5, .5), -1 * enemyScale, rand(-.4, .4))), V(rand(-.3, .3), -.4, 0), 1.2, .8, col(ud.form === "spirit" ? 0x2a3a6a : 0x120c18), { size1: 1.8, alpha: .45 });
    } else enemyLight.intensity = 0;
    // 护盾与回护罩
    const bt = barrier.userData.target || 0;
    barrierU.opacity.value += (bt - barrierU.opacity.value) * Math.min(1, dt * 6);
    barrierU.flash.value = Math.max(0, barrierU.flash.value - dt * 2.2);
    barrier.visible = barrierU.opacity.value > .02 && enemy.group.visible;
    barrier.position.copy(centerOf("enemy")); barrier.rotation.y += dt * .2;
    wardU.flash.value = Math.max(0, wardU.flash.value - dt * 1.6);
    wardU.opacity.value = Math.max(0, wardU.opacity.value - dt * 1.1);
    ward.visible = wardU.opacity.value > .01; ward.position.copy(centerOf("player"));
    barrierU.time.value = wardU.time.value = t;
    // 法宝环绕
    if (mainSword) {
      const a = t * 1.1, base = player.group.position;
      mainSword.base.set(base.x - .2 + Math.cos(a) * 1.5, base.y + 1 + Math.sin(a * 2) * .25, base.z + Math.sin(a) * 1.2);
      mainSword.group.lookAt(tmp.set(base.x - .2 + Math.cos(a + .3) * 1.5, mainSword.base.y, base.z + Math.sin(a + .3) * 1.2)); mainSword.group.rotateY(-Math.PI / 2);
      mainSword.trail.push(mainSword.group.position);
    }
    if (guardDisc) { guardDisc.base.copy(player.group.position).add(V(1.1, -.8 + Math.sin(t * 1.7) * .1, 1.1)); guardDisc.group.lookAt(camera.position); guardDisc.plate.rotation.z += dt * 1.4; }
    if (actors.npc) actors.npc.base.set(player.base.x - 2.4, player.base.y - 1.1, -2.6);
    // 败局：御剑失衡下坠、灯火渐暗
    if (defeatT > 0) {
      defeatT = Math.min(1, defeatT + dt * .6);
      player.off.y = lerp(0, -1.6, easeInOut(defeatT)); figure.rotation.z = -defeatT * .5; player.ride.rotation.z = Math.sin(t * 9) * .12 * defeatT;
      post.desat.value = .75 * defeatT; aura.material.opacity *= 1 - defeatT * .8;
    }
  }
  function waveRibbon(mesh, t) {
    const base = mesh.userData.base, p = mesh.geometry.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const x = base[i * 3], u = -x / 2.6;
      p.setY(i, base[i * 3 + 1] + Math.sin(t * 4.2 - u * 7 + mesh.userData.k) * .22 * u - u * u * .5);
      p.setZ(i, base[i * 3 + 2] + Math.cos(t * 3.1 - u * 5) * .3 * u);
    }
    p.needsUpdate = true;
  }

  function director(dt, t) {
    // 入场：自云层高处俯冲而下
    cam.intro = Math.min(1, cam.intro + dt / 1.8);
    const intro = easeInOut(cam.intro);
    const orbitA = Math.sin(t * .11) * .14 + (outcomeMode === "victory" ? outcomeT * .55 : 0);
    const dist = baseDist - cam.push * .55;
    const wide = V(Math.sin(orbitA) * dist, 1.8 + Math.sin(t * .23) * .3, Math.cos(orbitA) * dist);
    const lookWide = V(0, .4, 0);
    if (real > cam.focusUntil) { cam.focusW = Math.max(0, cam.focusW - dt * 1.4); cam.push = Math.max(0, cam.push - dt * 2.5); }
    const w = cam.focusW * .55;
    const targetPos = wide.clone(); targetPos.x += cam.focus.x * w * .35; targetPos.y += cam.focus.y * w * .25;
    const targetLook = lookWide.clone().lerp(cam.focus, w * .6);
    if (outcomeMode === "victory") { outcomeT = Math.min(1, outcomeT + dt * .25); targetLook.lerp(V(2.5, 1.2, 0), outcomeT * .6); targetPos.y += outcomeT * 1.2; }
    if (outcomeMode === "defeat") { targetLook.lerp(centerOf("player"), .4); targetPos.add(V(-2, 1.2, -2)); }
    const startPos = V(-26, 16, 46), startLook = V(0, -4, -10);
    const goalPos = startPos.lerp(targetPos, intro), goalLook = startLook.lerp(targetLook, intro);
    const k = 1 - Math.exp(-dt * (cam.intro < 1 ? 30 : 4.2));
    camPos.lerp(goalPos, k); camLook.lerp(goalLook, k);
    camera.position.copy(camPos); camera.lookAt(camLook);
    // 震屏（trauma²）
    cam.trauma = Math.max(0, cam.trauma - dt * 1.8);
    const s = cam.trauma * cam.trauma;
    if (s > 0) { camera.position.add(V(Math.sin(real * 61) * .45 * s, Math.sin(real * 47 + 1) * .35 * s, 0)); camera.rotateZ(Math.sin(real * 39) * .03 * s); }
  }

  function tick(now) {
    frameId = 0;
    if (disposed || !visible()) return;
    const ms = last ? now - last : 16; last = now;
    const rdt = Math.min(.05, ms / 1000);
    real += rdt;
    if (hitstop > 0) { hitstop -= rdt; timeScale = .12; } else timeScale += (1 - timeScale) * Math.min(1, rdt * 12);
    const dt = rdt * speed * timeScale;
    clock += dt;
    for (let i = timeline.length - 1; i >= 0; i--) if (timeline[i].at <= clock) timeline.splice(i, 1)[0].run();
    for (let i = fx.length - 1; i >= 0; i--) if (!fx[i].update(dt)) fx.splice(i, 1);
    const t = clock;
    animateActors(dt, t);
    sparks.update(dt); smoke.update(dt); motes.update(dt);
    // 漂浮灵尘
    if (Math.random() < .5 * TIERS[tierIndex].sparks) motes.spawn(V(rand(-14, 14), rand(-5, -2), rand(-6, 4)), V(rand(-.2, .2), rand(.4, 1.1), 0), rand(3, 5), rand(.06, .14), C(pal.main), { drag: .1, alpha: .8 });
    // 掠空风线
    if (Math.random() < rdt * 4) { const tr = getTrail(0xffffff, .025, .45, 9); const y = rand(-3, 5), z = rand(-4, 3); const a = V(16, y, z); let k = 0; add({ update(d) { k += d; a.x -= d * 48; tr.push(a); if (k > .7) { tr.release(); return false; } return true; } }); }
    for (const tr of trails) tr.update(dt, camera);
    for (const l of flashLights) { if (l.userData.life > 0) { l.userData.life -= dt; l.intensity = l.userData.peak * Math.max(0, l.userData.life / l.userData.span); } else l.intensity = 0; }
    isles.children.forEach((isle) => { isle.position.y = isle.userData.y + Math.sin(t * .4 + isle.userData.phase) * .8; isle.rotation.y += dt * .03; });
    shafts.children.forEach((s) => { s.material.opacity = shafts.visible ? outcomeT * (.05 + .03 * Math.sin(t * 1.5 + s.userData.phase)) : 0; });
    // 天象：Boss 雷暴
    skyU.time.value = t; seaU.time.value = t; puffU.time.value = t;
    skyU.flash.value = Math.max(0, skyU.flash.value - rdt * 3);
    if (boss && Math.random() < rdt * .35) { skyU.flash.value = .5; flashLight(V(rand(-10, 10), 12, -10), 0xc8d8ff, 30, .25); }
    seaU.camPos.value.copy(camera.position);
    post.flash.value = Math.max(0, post.flash.value - rdt * 2.2);
    post.aberration.value = Math.min(.025, Math.max(.002, cam.trauma * cam.trauma * .03, post.aberration.value * Math.exp(-rdt * 6)));
    director(rdt, t);
    composer.render(rdt);
    adapt(ms);
    frameId = requestAnimationFrame(tick);
  }
  function wake() { if (!frameId && !disposed && visible()) { last = 0; frameId = requestAnimationFrame(tick); } }
  const onVisibility = () => wake();
  document.addEventListener("visibilitychange", onVisibility);
  camPos.set(-26, 16, 46); camLook.set(0, -4, -10);
  wake();

  // 屏幕投影：给 DOM 飘字定位（0..1，左上为原点）
  function project(id) {
    const p = centerOf(id).add(V(0, id === "enemy" ? 1.2 * enemyScale : 1.2, 0)).project(camera);
    return { x: (p.x + 1) / 2, y: (1 - p.y) / 2, visible: p.z < 1 };
  }

  function clear() {
    timeline.length = 0; fx.length = 0;
    for (const o of [...transient]) dropT(o);
    enemy.frozen = 0; wardU.opacity.value = 0; barrierU.flash.value = 0; post.flash.value = 0; hitstop = 0;
    if (lastCursorDown) enemyGroup.visible = false;
    sparks.clear(); smoke.clear();
    for (const tr of trails) if (!tr.persistent) { tr.active = false; tr.mesh.visible = false; }
    cam.focusW = 0; cam.push = 0;
  }

  function stats() {
    const avg = frames.length ? frames.reduce((a, b) => a + b, 0) / frames.length : 0;
    return { fps: avg ? Math.round(1000 / avg) : 0, frameMs: Math.round(avg * 10) / 10, quality: tierIndex, bloom: bloom.enabled, form, boss, style, drawCalls: renderer.info.render.calls, geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures, particles: sparks.list.length + smoke.list.length };
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    if (frameId) cancelAnimationFrame(frameId);
    observer?.disconnect();
    document.removeEventListener("visibilitychange", onVisibility);
    timeline.length = 0; fx.length = 0;
    const geos = new Set(), mats = new Set();
    scene.traverse((o) => {
      if (o.geometry) geos.add(o.geometry);
      if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => mats.add(m));
    });
    geos.forEach((g) => g.dispose());
    mats.forEach((m) => { m.map?.dispose?.(); m.dispose(); });
    disposables.forEach((x) => x.dispose?.());
    bloom.dispose(); composer.dispose();
  }

  return { play, setFrame, project, clear, resize, setSpeed: (v) => { speed = v; }, stats, dispose };
}
