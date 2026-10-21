// 三维特效管理器：同一页面同一时刻只持有一个 WebGL 上下文。
//  - battle：斗法战报特效，由战报事件驱动（蓄力 → 飞行 → 命中 → 伤害冲击 → 收尾），不推进任何规则、不决定胜负；
//  - stage ：舞台氛围（真透视视差的云雾 + 境界色灵气，洞府页按洞府等级点亮灯笼），绑定境界与洞府数据。
// 战报打开时让出舞台上下文，合上后自动恢复。加载或创建失败时返回 null，调用方继续用原有 SVG/Canvas2D 演出。
import * as THREE from "/vendor/three.module.min.js";

const liveRenderers = new Set();      // 当前存活的渲染器（用于核对“单上下文”与泄漏检测）
let stageInstance = null, stageSpec = null, battleDepth = 0;

const VIEW_W = 1000, VIEW_H = 340;     // 与战报舞台 SVG 的 viewBox 一致
const MAX_PARTICLES = 520;
const MAX_RINGS = 8;

// 各类事件的阶段配置（毫秒，按 1× 速度；速度倍率在 schedule 时统一折算）
const PHASES = {
  damage: { charge: 170, fly: 380, hit: 420 },
  shield: { charge: 120, fly: 320, hit: 360 },
  shield_absorb: { charge: 0, fly: 0, hit: 520 },
  heal: { charge: 0, fly: 0, hit: 760 },
  buff: { charge: 0, fly: 0, hit: 560 },
  defend: { charge: 0, fly: 0, hit: 560 },
  control: { charge: 120, fly: 300, hit: 520 },
  poison: { charge: 0, fly: 260, hit: 520 },
  mana: { charge: 0, fly: 0, hit: 560 },
};
const COLORS = { player: 0x3fa585, main: 0xe8b84a, guard: 0x4a8fb8, enemy: 0xc8452f, npc: 0x8a7bb8 };
const EVENT_COLORS = { heal: 0x6fd1a4, shield_absorb: 0x5aa9e6, shield: 0x5aa9e6, buff: 0xe8b84a, defend: 0x5aa9e6, control: 0x8a7bb8, poison: 0x7aa84a, mana: 0x5aa9e6 };

const SPRITE = (() => {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const g = canvas.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(.35, "rgba(255,255,255,.55)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad; g.fillRect(0, 0, 64, 64);
  return canvas;
})();

const VERT = `
attribute float size; attribute float alpha; attribute vec3 tint;
varying float vAlpha; varying vec3 vTint;
uniform float scale;
void main() {
  vAlpha = alpha; vTint = tint;
  gl_PointSize = size * scale;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;
const FRAG = `
uniform sampler2D map; varying float vAlpha; varying vec3 vTint;
void main() { vec4 t = texture2D(map, gl_PointCoord); gl_FragColor = vec4(vTint, t.a * vAlpha); }`;

/** 能否创建 WebGL 上下文（不计入正式渲染器，探测后立即释放）。 */
let webglProbe = null;
function webglAvailable() {
  if (webglProbe !== null) return webglProbe;     // 只探测一次：重复建临时上下文会挤占浏览器的上下文名额
  try {
    const probe = document.createElement("canvas");
    const gl = probe.getContext("webgl2") || probe.getContext("webgl");
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    webglProbe = !!gl;
  } catch { webglProbe = false; }
  return webglProbe;
}

/**
 * @param {HTMLElement} host 战报舞台容器（须为定位元素）
 * @returns {null | {play, clear, resize, setSpeed, dispose}}
 */
export function create(host) {
  if (!host || !webglAvailable()) return null;
  suspendStage();
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, powerPreference: "low-power" });
  } catch { resumeStage(); return null; }
  liveRenderers.add(renderer);
  const canvas = renderer.domElement;
  canvas.className = "fx3d-canvas";
  canvas.setAttribute("aria-hidden", "true");
  host.append(canvas);
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(0, VIEW_W, 0, VIEW_H, -10, 10);
  camera.position.z = 5;

  // 粒子池：单个 Points，CPU 更新属性
  const geometry = new THREE.BufferGeometry();
  const pos = new Float32Array(MAX_PARTICLES * 3), tint = new Float32Array(MAX_PARTICLES * 3);
  const size = new Float32Array(MAX_PARTICLES), alpha = new Float32Array(MAX_PARTICLES);
  geometry.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geometry.setAttribute("tint", new THREE.BufferAttribute(tint, 3));
  geometry.setAttribute("size", new THREE.BufferAttribute(size, 1));
  geometry.setAttribute("alpha", new THREE.BufferAttribute(alpha, 1));
  const texture = new THREE.CanvasTexture(SPRITE);
  const material = new THREE.ShaderMaterial({ uniforms: { map: { value: texture }, scale: { value: 1 } }, vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  scene.add(points);

  // 冲击环池
  const ringGeometry = new THREE.RingGeometry(.86, 1, 40);
  const rings = Array.from({ length: MAX_RINGS }, () => {
    const mat = new THREE.MeshBasicMaterial({ transparent: true, depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending, opacity: 0 });
    const mesh = new THREE.Mesh(ringGeometry, mat);
    mesh.visible = false; mesh.userData = { life: 0, span: 1, from: 10, to: 60 };
    scene.add(mesh);
    return mesh;
  });

  const parts = [];            // 活动粒子
  const timeline = [];         // { at, run }：以毫秒时钟推进，暂停/倍速自然生效
  let clock = 0, speed = 1, frameId = 0, last = 0, disposed = false, lost = false;

  canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); lost = true; canvas.classList.add("lost"); });
  canvas.addEventListener("webglcontextrestored", () => { lost = false; canvas.classList.remove("lost"); });

  function resize() {
    const rect = host.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratio = Math.min(1.5, globalThis.devicePixelRatio || 1);
    renderer.setPixelRatio(ratio);
    renderer.setSize(rect.width, rect.height, false);
    canvas.style.width = "100%"; canvas.style.height = "100%";
    // 与 SVG 的 meet 适配一致：viewBox 等比居中
    const aspect = rect.width / rect.height, view = VIEW_W / VIEW_H;
    let w = VIEW_W, h = VIEW_H;
    if (aspect > view) w = VIEW_H * aspect; else h = VIEW_W / aspect;
    const cx = VIEW_W / 2, cy = VIEW_H / 2;
    camera.left = cx - w / 2; camera.right = cx + w / 2; camera.top = cy - h / 2; camera.bottom = cy + h / 2;
    camera.updateProjectionMatrix();
    material.uniforms.scale.value = ratio * rect.width / w;
  }
  const observer = globalThis.ResizeObserver ? new ResizeObserver(resize) : null;
  observer?.observe(host);
  resize();

  const rgb = (hex) => [(hex >> 16 & 255) / 255, (hex >> 8 & 255) / 255, (hex & 255) / 255];

  function spawn(x, y, vx, vy, life, sz, hex, gain = 1) {
    if (parts.length >= MAX_PARTICLES) parts.shift();
    parts.push({ x, y, vx, vy, life, span: life, sz, c: rgb(hex), gain });
  }
  function ring(x, y, hex, from, to, life) {
    const mesh = rings.find((r) => !r.visible) || rings[0];
    mesh.position.set(x, y, 0); mesh.material.color.setHex(hex);
    Object.assign(mesh.userData, { life, span: life, from, to });
    mesh.visible = true;
  }

  const at = (delay, run) => { timeline.push({ at: clock + delay, run }); wake(); };
  const bez = (a, c, b, t) => (1 - t) * (1 - t) * a + 2 * (1 - t) * t * c + t * t * b;

  // 一次事件 → 若干阶段。intensity 0..1 由逻辑数值（伤害 / 敌方气血上限）决定。
  function play(event, from, to, intensity = .4) {
    if (disposed || lost) return;
    const ph = PHASES[event.type];
    if (!ph) return;
    const hex = EVENT_COLORS[event.type] || COLORS[event.source] || COLORS.player;
    const k = Math.max(.25, Math.min(1, intensity));
    const self = event.source === event.target || ["heal", "buff", "defend", "shield_absorb", "mana"].includes(event.type);
    const [x0, y0] = from, [x1, y1] = self ? from : to;
    const cx = (x0 + x1) / 2, cy = Math.min(y0, y1) - 50;
    // 蓄力：施放者处聚拢光点
    if (ph.charge) at(0, () => { for (let i = 0; i < 14; i++) { const a = Math.random() * 6.283, r = 38 + Math.random() * 20; spawn(x0 + Math.cos(a) * r, y0 + Math.sin(a) * r, -Math.cos(a) * r / (ph.charge / 1000), -Math.sin(a) * r / (ph.charge / 1000), ph.charge / 1000, 8 + Math.random() * 6, hex, .8); } });
    if (ph.fly) {
      // 飞行：弹头沿贝塞尔轨迹，每帧留尾迹
      const t0 = ph.charge, steps = Math.max(8, Math.round(ph.fly / 22));
      for (let i = 0; i <= steps; i++) {
        const t = i / steps;
        at(t0 + ph.fly * t, () => {
          const x = bez(x0, cx, x1, t), y = bez(y0, cy, y1, t);
          spawn(x, y, 0, 0, .34, 20 + 8 * k, hex, 1.1);
          spawn(x, y, (Math.random() - .5) * 40, (Math.random() - .5) * 40, .5, 9, 0xfffdf0, .8);
        });
      }
    }
    // 命中：爆发粒子 + 冲击环（强度随真实伤害占比）
    at(ph.charge + ph.fly, () => {
      const count = Math.round(18 + 46 * k);
      const power = event.type === "heal" ? 40 : 90 + 120 * k;
      for (let i = 0; i < count; i++) {
        const a = event.type === "heal" ? -1.57 + (Math.random() - .5) * 1.4 : Math.random() * 6.283;
        const v = power * (.3 + Math.random() * .7);
        spawn(x1 + (Math.random() - .5) * 14, y1 + (Math.random() - .5) * 14, Math.cos(a) * v, Math.sin(a) * v, (ph.hit / 1000) * (.5 + Math.random() * .6), 8 + Math.random() * 10 * k, Math.random() < .3 ? 0xfffdf0 : hex, 1);
      }
      if (!["heal", "mana"].includes(event.type)) ring(x1, y1, hex, 8, 40 + 60 * k, ph.hit / 1000);
    });
  }

  function clear() {
    timeline.length = 0; parts.length = 0;
    for (const r of rings) r.visible = false;
    flush();
    if (!disposed && !lost) renderer.render(scene, camera);
  }

  function flush() {
    const n = parts.length;
    for (let i = 0; i < MAX_PARTICLES; i++) {
      if (i < n) {
        const p = parts[i], life = Math.max(0, p.life / p.span);
        pos[i * 3] = p.x; pos[i * 3 + 1] = p.y; pos[i * 3 + 2] = 0;
        tint[i * 3] = p.c[0]; tint[i * 3 + 1] = p.c[1]; tint[i * 3 + 2] = p.c[2];
        size[i] = p.sz * (.5 + .5 * life); alpha[i] = Math.min(1, life * 1.6) * p.gain * .85;
      } else alpha[i] = 0;
    }
    for (const name of ["position", "tint", "size", "alpha"]) geometry.attributes[name].needsUpdate = true;
  }

  function frame(now) {
    frameId = 0;
    if (disposed) return;
    const dt = Math.min(.05, (now - last) / 1000); last = now;
    clock += dt * 1000 * speed;
    for (let i = timeline.length - 1; i >= 0; i--) if (timeline[i].at <= clock) timeline.splice(i, 1)[0].run();
    const step = dt * speed;
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i];
      p.life -= step;
      if (p.life <= 0) { parts.splice(i, 1); continue; }
      p.x += p.vx * step; p.y += p.vy * step; p.vx *= .96; p.vy *= .96;
    }
    let ringsLive = false;
    for (const r of rings) {
      if (!r.visible) continue;
      r.userData.life -= step;
      if (r.userData.life <= 0) { r.visible = false; continue; }
      ringsLive = true;
      const t = 1 - r.userData.life / r.userData.span, s = r.userData.from + (r.userData.to - r.userData.from) * (1 - (1 - t) ** 3);
      r.scale.set(s, s, 1); r.material.opacity = .85 * (1 - t);
    }
    flush();
    if (!lost) renderer.render(scene, camera);
    if (timeline.length || parts.length || ringsLive) wake();
  }
  function wake() { if (!frameId && !disposed && !document.hidden) { last = performance.now(); frameId = requestAnimationFrame(frame); } }

  function dispose() {
    if (disposed) return;
    disposed = true;
    if (frameId) cancelAnimationFrame(frameId);
    observer?.disconnect();
    geometry.dispose(); material.dispose(); texture.dispose(); ringGeometry.dispose();
    for (const r of rings) r.material.dispose();
    renderer.dispose();
    renderer.forceContextLoss();
    liveRenderers.delete(renderer);
    canvas.remove();
    resumeStage();
  }

  return { play, clear, resize, setSpeed: (value) => { speed = value; }, dispose, get lost() { return lost; } };
}

// ------------------------------------------------------------------ 舞台氛围（stage）

const STAGE_VERT = `
attribute float size; attribute float alpha; attribute vec3 tint;
varying float vAlpha; varying vec3 vTint;
uniform float scale;
void main() {
  vAlpha = alpha; vTint = tint;
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = size * scale / -mv.z;
  gl_Position = projectionMatrix * mv;
}`;

const MIST = (() => {
  const canvas = document.createElement("canvas");
  canvas.width = 256; canvas.height = 64;
  const g = canvas.getContext("2d");
  const grad = g.createRadialGradient(128, 32, 0, 128, 32, 128);
  grad.addColorStop(0, "rgba(255,255,255,.9)");
  grad.addColorStop(.5, "rgba(255,255,255,.35)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.setTransform(1, 0, 0, .25, 0, 24);
  g.fillStyle = grad; g.fillRect(0, -96, 256, 384);
  return canvas;
})();

// 质量档：0 最低 … 2 最高；帧时间持续偏高时自动降档
const QUALITY = [
  { motes: .35, mist: 3, ratio: 1 },
  { motes: .65, mist: 4, ratio: 1.25 },
  { motes: 1, mist: 6, ratio: 1.5 },
];

function initialQuality() {
  const cores = navigator.hardwareConcurrency || 4;
  return cores >= 8 ? 2 : cores >= 4 ? 1 : 0;
}

function suspendStage() {
  battleDepth += 1;
  if (stageInstance) { stageInstance.destroy(); stageInstance = null; }
}

function resumeStage() {
  battleDepth = Math.max(0, battleDepth - 1);
  if (!battleDepth && stageSpec && !stageInstance) stageInstance = buildStage(stageSpec);
}

/**
 * 舞台氛围。spec = { host, tier(0-8), color(hex 字符串), page, estate:{garden,workshop,chamber} }。
 * 同一页面只保留一个舞台实例：再次调用会更新参数（或换宿主）；战报期间暂不渲染，合上后恢复。
 */
export function mountStage(spec) {
  if (!spec?.host || !webglAvailable()) return false;
  stageSpec = spec;
  if (battleDepth) return true;
  if (stageInstance && stageInstance.host === spec.host) { stageInstance.update(spec); return true; }
  stageInstance?.destroy();
  stageInstance = buildStage(spec);
  return !!stageInstance;
}

export function unmountStage() {
  stageSpec = null;
  if (stageInstance) { stageInstance.destroy(); stageInstance = null; }
}

/** 监测数据：存活渲染器数、舞台实例的帧率与 GPU 对象计数（用于泄漏检查与验收取证）。 */
export function stats() {
  return { renderers: liveRenderers.size, stage: stageInstance?.stats() || null, battleDepth };
}

function buildStage(spec) {
  const host = spec.host;
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, powerPreference: "low-power" }); } catch { return null; }
  liveRenderers.add(renderer);
  const canvas = renderer.domElement;
  canvas.className = "aura-canvas stage3d-canvas";
  canvas.setAttribute("aria-hidden", "true");
  const banner = host.querySelector(":scope > .scene-banner");
  if (banner) banner.after(canvas); else host.prepend(canvas);
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const FOV = 38, HEIGHT = 100;                       // z=0 平面上可视高度 100 单位
  const camZ = HEIGHT / 2 / Math.tan(FOV * Math.PI / 360);
  const camera = new THREE.PerspectiveCamera(FOV, 2, 1, 400);
  camera.position.set(0, 0, camZ);

  // 灵气粒子（透视大小衰减）
  const MAX = 160;
  const geometry = new THREE.BufferGeometry();
  const pos = new Float32Array(MAX * 3), tint = new Float32Array(MAX * 3), size = new Float32Array(MAX), alpha = new Float32Array(MAX);
  geometry.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  geometry.setAttribute("tint", new THREE.BufferAttribute(tint, 3));
  geometry.setAttribute("size", new THREE.BufferAttribute(size, 1));
  geometry.setAttribute("alpha", new THREE.BufferAttribute(alpha, 1));
  const spriteTex = new THREE.CanvasTexture(SPRITE);
  const moteMat = new THREE.ShaderMaterial({ uniforms: { map: { value: spriteTex }, scale: { value: 300 } }, vertexShader: STAGE_VERT, fragmentShader: FRAG, transparent: true, depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending });
  const points = new THREE.Points(geometry, moteMat);
  points.frustumCulled = false;
  scene.add(points);

  // 云雾：不同深度的柔光平面，产生真实视差
  const mistTex = new THREE.CanvasTexture(MIST);
  const mistGeo = new THREE.PlaneGeometry(1, 1);
  const mists = Array.from({ length: 6 }, (_, i) => {
    const mat = new THREE.MeshBasicMaterial({ map: mistTex, transparent: true, opacity: .16 + .05 * (i % 3), depthTest: false, depthWrite: false, color: 0xf4fbf6 });
    const mesh = new THREE.Mesh(mistGeo, mat);
    mesh.userData = { z: -45 + i * 18, y: -28 + (i % 3) * 14 + Math.random() * 6, speed: (3 + i) * (i % 2 ? -1 : 1) * .35, x: Math.random() * 160 - 80 };
    scene.add(mesh);
    return mesh;
  });

  // 洞府灯笼：数据绑定洞府设施等级
  const lanternGeo = new THREE.BufferGeometry();
  const LANTERN_MAX = 9;
  const lpos = new Float32Array(LANTERN_MAX * 3), ltint = new Float32Array(LANTERN_MAX * 3), lsize = new Float32Array(LANTERN_MAX), lalpha = new Float32Array(LANTERN_MAX);
  lanternGeo.setAttribute("position", new THREE.BufferAttribute(lpos, 3));
  lanternGeo.setAttribute("tint", new THREE.BufferAttribute(ltint, 3));
  lanternGeo.setAttribute("size", new THREE.BufferAttribute(lsize, 1));
  lanternGeo.setAttribute("alpha", new THREE.BufferAttribute(lalpha, 1));
  const lanterns = new THREE.Points(lanternGeo, moteMat);
  lanterns.frustumCulled = false;
  scene.add(lanterns);

  let quality = initialQuality(), tier = 0, color = [.25, .65, .52], lanternCount = 0, aspect = 2;
  const motes = Array.from({ length: MAX }, () => ({ x: 0, y: 0, z: 0, vy: 0, vx: 0, phase: 0, tw: 1, s: 1 }));
  let activeMotes = 0;

  function hexToRgb(value) {
    const v = String(value || "#3FA585").replace("#", "");
    const full = v.length === 3 ? [...v].map((c) => c + c).join("") : v.padEnd(6, "0");
    return [0, 2, 4].map((i) => (parseInt(full.slice(i, i + 2), 16) || 0) / 255);
  }
  function halfWidth() { return HEIGHT * aspect / 2; }
  function respawn(m, anywhere) {
    const hw = halfWidth() * 1.4;
    m.x = (Math.random() * 2 - 1) * hw; m.y = anywhere ? (Math.random() - .5) * HEIGHT : -HEIGHT / 2 - 2;
    m.z = -30 + Math.random() * 60; m.vy = 4 + Math.random() * 8 + tier * .8; m.vx = (Math.random() - .5) * 3;
    m.phase = Math.random() * 6.283; m.tw = 1.2 + Math.random() * 2; m.s = .7 + Math.random() * 1.1;
  }
  function applySpec(next) {
    tier = Math.max(0, Math.min(8, next.tier | 0));
    color = hexToRgb(next.color);
    const e = next.page === "estate" ? next.estate : null;
    lanternCount = e ? Math.min(LANTERN_MAX, (e.garden | 0) + (e.workshop | 0) + (e.chamber | 0)) : 0;
    for (let i = 0; i < LANTERN_MAX; i++) {
      const f = LANTERN_MAX > 1 ? i / (LANTERN_MAX - 1) : .5;
      lpos[i * 3] = (f * 2 - 1) * halfWidth() * .8; lpos[i * 3 + 1] = -HEIGHT * .3 + Math.sin(f * 9) * 4; lpos[i * 3 + 2] = -6 + (i % 3) * 5;
      ltint[i * 3] = 1; ltint[i * 3 + 1] = .78; ltint[i * 3 + 2] = .36; lsize[i] = 26;
    }
  }
  function resize() {
    const rect = host.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const q = QUALITY[quality], ratio = Math.min(q.ratio, globalThis.devicePixelRatio || 1);
    renderer.setPixelRatio(ratio);
    renderer.setSize(rect.width, rect.height, false);
    canvas.style.width = "100%"; canvas.style.height = "100%";
    aspect = rect.width / rect.height;
    camera.aspect = aspect; camera.updateProjectionMatrix();
    moteMat.uniforms.scale.value = rect.height * ratio * 1.6;
    activeMotes = Math.min(MAX, Math.round((24 + tier * 12) * q.motes * Math.max(.6, aspect / 3)));
    mists.forEach((m, i) => { m.visible = i < q.mist; });
    applySpec(spec);
  }
  function applyParams() {
    resize();
    for (let i = 0; i < MAX; i++) respawn(motes[i], true);
  }

  let clock = 0, last = 0, frameId = 0, destroyed = false, lost = false;
  const frames = [];                                   // 帧耗时滑窗（毫秒）
  const visible = () => !destroyed && !lost && host.isConnected && !document.hidden && host.getClientRects().length > 0 && !host.closest("[hidden]");

  function tickFrame(now) {
    frameId = 0;
    if (destroyed || !visible()) return;               // 不可见即停帧；可见性变化时由 wake 重启
    if (now - last < 32) { frameId = requestAnimationFrame(tickFrame); return; }   // ≈30fps 上限
    const dtMs = now - last, dt = Math.min(.07, dtMs / 1000);
    if (last) { frames.push(dtMs); if (frames.length > 90) frames.shift(); }
    last = now; clock += dt;
    for (let i = 0; i < MAX; i++) {
      if (i >= activeMotes) { alpha[i] = 0; continue; }
      const m = motes[i];
      m.phase += dt * m.tw; m.y += m.vy * dt; m.x += (m.vx + Math.sin(m.phase) * 2) * dt;
      if (m.y > HEIGHT / 2 + 2) respawn(m, false);
      const edge = Math.min(1, (m.y + HEIGHT / 2) / (HEIGHT * .3));
      pos[i * 3] = m.x; pos[i * 3 + 1] = m.y; pos[i * 3 + 2] = m.z;
      tint[i * 3] = color[0]; tint[i * 3 + 1] = color[1]; tint[i * 3 + 2] = color[2];
      size[i] = m.s * 7; alpha[i] = (.3 + .5 * Math.sin(m.phase) ** 2) * Math.max(0, edge);
    }
    for (const name of ["position", "tint", "size", "alpha"]) geometry.attributes[name].needsUpdate = true;
    mists.forEach((mesh) => {
      const u = mesh.userData, hw = halfWidth() * 1.6;
      u.x += u.speed * dt; if (u.x > hw) u.x = -hw; if (u.x < -hw) u.x = hw;
      const scale = 90 + (u.z + 45) * .5;
      mesh.position.set(u.x, u.y, u.z); mesh.scale.set(scale, scale * .28, 1);
    });
    for (let i = 0; i < LANTERN_MAX; i++) lalpha[i] = i < lanternCount ? .75 + .25 * Math.sin(clock * 2 + i * 1.7) : 0;
    for (const name of ["position", "tint", "size", "alpha"]) lanternGeo.attributes[name].needsUpdate = true;
    camera.position.x = Math.sin(clock * .18) * 5;     // 缓慢横移：近处粒子与远处云雾产生视差
    camera.lookAt(0, 0, 0);
    renderer.render(scene, camera);
    adapt();
    frameId = requestAnimationFrame(tickFrame);
  }

  // 连续 90 帧平均耗时 > 45ms（≈22fps）则降一档质量，并清空滑窗
  function adapt() {
    if (frames.length < 90) return;
    const avg = frames.reduce((a, b) => a + b, 0) / frames.length;
    if (avg > 45 && quality > 0) { quality -= 1; frames.length = 0; applyParams(); }
  }

  function wake() { if (!frameId && !destroyed && visible()) { last = 0; frameId = requestAnimationFrame(tickFrame); } }
  const observer = globalThis.ResizeObserver ? new ResizeObserver(() => { resize(); wake(); }) : null;
  observer?.observe(host);
  const onVisibility = () => wake();
  document.addEventListener("visibilitychange", onVisibility);
  canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); if (destroyed) return; lost = true; canvas.classList.add("lost"); document.body.classList.remove("stage3d-on"); });
  canvas.addEventListener("webglcontextrestored", () => { if (destroyed) return; lost = false; canvas.classList.remove("lost"); document.body.classList.add("stage3d-on"); wake(); });

  applyParams();
  document.body.classList.add("stage3d-on");
  wake();

  return {
    host,
    update(next) { spec = next; applySpec(next); resize(); wake(); },
    stats() {
      const avg = frames.length ? frames.reduce((a, b) => a + b, 0) / frames.length : 0;
      return { fps: avg ? Math.round(1000 / avg) : 0, frameMs: Math.round(avg * 10) / 10, quality, motes: activeMotes, lanterns: lanternCount, geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures, drawCalls: renderer.info.render.calls, lost };
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      if (frameId) cancelAnimationFrame(frameId);
      observer?.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      geometry.dispose(); lanternGeo.dispose(); mistGeo.dispose(); moteMat.dispose(); spriteTex.dispose(); mistTex.dispose();
      for (const m of mists) m.material.dispose();
      renderer.dispose(); renderer.forceContextLoss();
      liveRenderers.delete(renderer);
      canvas.remove();
      document.body.classList.remove("stage3d-on");
    },
  };
}
