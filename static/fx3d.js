// 三维特效管理器：同一页面同一时刻只持有一个 WebGL 上下文。
//  - battle：三维斗法台「云海御空」（arena3d.js，源码 src/battle/replay.ts），由战报事件驱动，招式命中与飘字同拍，不推进任何规则、不决定胜负；
//  - stage ：舞台氛围（真透视视差的云雾 + 境界色灵气，洞府页按洞府等级点亮灯笼），绑定境界与洞府数据。
// 战报打开时让出舞台上下文，合上后自动恢复。加载或创建失败时返回 null，调用方继续用原有 SVG/Canvas2D 演出。
import * as THREE from "/vendor/three.module.min.js";
import { buildArena } from "/arena3d.js";

const liveRenderers = new Set();      // 当前存活的渲染器（用于核对“单上下文”与泄漏检测）
let stageInstance = null, stageSpec = null, battleDepth = 0, battleInstance = null;

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
 * 三维斗法台。ctx = { report, tier, root, skill, form, boss, onLost, onRestore }。
 * @param {HTMLElement} host 战报舞台容器（须为定位元素）
 * @returns {null | {play, setFrame, project, clear, resize, setSpeed, dispose, lost}}
 */
export function create(host, ctx = {}) {
  if (!host || !ctx.report || !webglAvailable()) return null;
  suspendStage();
  let renderer, arena;
  try {
    renderer = new THREE.WebGLRenderer({ alpha: false, antialias: false, powerPreference: "high-performance" });
  } catch { resumeStage(); return null; }
  liveRenderers.add(renderer);
  const canvas = renderer.domElement;
  canvas.className = "fx3d-canvas";
  canvas.setAttribute("aria-hidden", "true");
  host.append(canvas);
  try { arena = buildArena(renderer, host, ctx); } catch (error) {
    console.warn("三维斗法台创建失败，改用平面演出", error);
    renderer.dispose(); renderer.forceContextLoss(); liveRenderers.delete(renderer); canvas.remove(); resumeStage();
    return null;
  }
  let disposed = false, lost = false;
  canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); if (disposed) return; lost = true; canvas.classList.add("lost"); ctx.onLost?.(); });
  canvas.addEventListener("webglcontextrestored", () => { if (disposed) return; lost = false; canvas.classList.remove("lost"); ctx.onRestore?.(); });
  battleInstance = arena;

  function dispose() {
    if (disposed) return;
    disposed = true;
    arena.dispose();
    renderer.dispose();
    renderer.forceContextLoss();
    liveRenderers.delete(renderer);
    if (battleInstance === arena) battleInstance = null;
    canvas.remove();
    resumeStage();
  }

  const guard = (fn) => (...args) => (disposed || lost ? undefined : fn(...args));
  return {
    play: guard(arena.play), setFrame: guard(arena.setFrame), project: guard(arena.project), clear: guard(arena.clear),
    resize: guard(arena.resize), setSpeed: (v) => arena.setSpeed(v), dispose, get lost() { return lost; },
  };
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
  return { renderers: liveRenderers.size, stage: stageInstance?.stats() || null, battle: battleInstance?.stats() || null, battleDepth };
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
