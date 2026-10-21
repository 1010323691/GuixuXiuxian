// 「云海御空」 arena, stage 1: a single-foe duel staged from action templates on a fixed timeline.
// Rules never live here: in stage 2 the Python battle report will drive the same templates.
import * as THREE from 'three';
import { makeCultivator, makeDemon, type Actor } from './actors';
import { CameraRig, type ShotName } from './camera';
import { buildEnvironment } from './env';
import { FxSystem } from './fx';
import { buildPost } from './post';
import { V, disposeOutlines, disposeShared, lerp, easeInOut, easeOut } from './util';

export interface ArenaOptions { quality?: 0 | 1 | 2; reducedMotion?: boolean; skill?: THREE.ColorRepresentation }

const HERO_HOME = V(0, 0, 6);
const FOE_HOME = V(0, 1.2, -11);

/** Timed one-shot callbacks plus per-frame tweens, all advanced by simulation time. */
class Timeline {
  private events: { at: number; fn: () => void }[] = [];
  private tweens: { start: number; dur: number; fn: (u: number) => void }[] = [];
  t = 0;
  at(t: number, fn: () => void) { this.events.push({ at: t, fn }); }
  tween(t: number, dur: number, fn: (u: number) => void) { this.tweens.push({ start: t, dur, fn }); }
  reset() { this.t = 0; }
  advance(dt: number) {
    const before = this.t;
    this.t += dt;
    for (const e of this.events) if (e.at >= before && e.at < this.t) e.fn();
    for (const tw of this.tweens) { const u = (this.t - tw.start) / tw.dur; if (u >= 0 && (u <= 1 || (before - tw.start) / tw.dur < 1)) tw.fn(Math.min(1, u)); }
  }
}

export function createArena(renderer: THREE.WebGLRenderer, opts: ArenaOptions = {}) {
  const quality = opts.quality ?? 2, reduced = !!opts.reducedMotion, skill = opts.skill ?? 0x5fd0ff;
  const scene = new THREE.Scene();
  const rig = new CameraRig(reduced);
  const camera = rig.camera;
  const env = buildEnvironment(scene, quality);
  const post = buildPost(renderer, scene, camera, quality, reduced);
  let hitstop = 0;
  const fx = new FxSystem(scene, camera, {
    shake: (a) => rig.shake(a),
    hitstop: (s) => { if (!reduced) hitstop = Math.max(hitstop, s); },
    flash: (a, c) => post.flash(a, c),
    aberrate: (a) => post.aberrate(a),
  }, reduced);

  const hero = makeCultivator(skill), foe = makeDemon();
  scene.add(hero.root, foe.root);
  fx.attachAura(foe.root, { color: 0x1a1012, rate: 14, radius: 3, rise: 1.5, size: [2.5, 5], smoke: true, offset: V(-.5, 3, 0) });
  fx.attachAura(foe.root, { color: 0xff3a12, rate: 26, radius: 3.4, rise: 4, size: [.15, .4], offset: V(0, 3.5, 0) });
  fx.attachAura(hero.root, { color: skill, rate: 16, radius: .5, rise: -.5, size: [.08, .2], offset: V(-.6, -1.5, 0) });

  // ---------------------------------------------------------------- the lab duel, beat by beat
  const tl = new Timeline();
  const LOOP = 18;
  const shot = (t: number, name: ShotName, blend = 0) => tl.at(t, () => (blend ? rig.go(name, blend) : rig.cut(name)));
  const chest = (a: Actor) => () => a.anchor('chest');
  const jitter = (p: THREE.Vector3, k: number) => p.add(V(Math.sin(k * 7.3) * 1.2, Math.cos(k * 3.1) * 1.4, Math.sin(k * 2.2) * .8));
  const heroFrom = V(-16, 5, 20);

  tl.at(0, () => { hero.reset(); foe.reset(); fx.clear(); hero.root.position.copy(heroFrom); foe.root.position.copy(FOE_HOME); hero.moves.play('dash', 2.2); });
  shot(0, 'establish');
  tl.tween(0, 2.2, (u) => { const k = easeOut(u); hero.root.position.set(lerp(heroFrom.x, HERO_HOME.x, k), lerp(heroFrom.y, HERO_HOME.y, k) + Math.sin(u * Math.PI) * 3, lerp(heroFrom.z, HERO_HOME.z, k)); });
  tl.at(.9, () => { foe.moves.play('roar', 2); fx.embers(foe.anchor('head'), 0xff4a1a, 1.5); rig.shake(.35); });
  shot(2.1, 'shoulder', 1.1);
  // 剑阵 sword formation
  tl.at(2.4, () => { hero.moves.play('charge', 1.4); fx.gather(() => hero.anchor('hand'), skill, 1.3, 3.5); });
  tl.at(3.1, () => {
    hero.moves.play('cast', .9);
    fx.swordSwarm(() => hero.anchor('hand'), () => hero.anchor('back'), chest(foe), skill, 12, (i) => {
      const p = jitter(foe.anchor('chest'), i);
      fx.impact(p, skill, .55); foe.flash(0xbfefff, .8); if (i % 3 === 0) foe.moves.play('hit', .45);
    });
  });
  // 符箓 talisman volley
  shot(5.3, 'side', .9);
  tl.at(5.5, () => { hero.moves.play('thrust', .8); fx.talismans(() => hero.anchor('hand'), chest(foe), 5, (i) => {
    const p = jitter(foe.anchor('chest'), i + 20);
    fx.impact(p, 0xffc040, .9); fx.embers(p, 0xffc040, .8); foe.flash(0xffe0a0, 1); foe.moves.play('hit', .5);
  }); });
  // 法阵 rune circle charge and release
  shot(7.1, 'castView', .8);
  let circle: ReturnType<FxSystem['runeCircle']> | null = null;
  const circleAt = () => hero.anchor('hand').addScaledVector(V().subVectors(foe.root.position, hero.root.position).setY(0).normalize(), 2.4);
  tl.at(7.2, () => { hero.moves.play('charge', 1.7); circle = fx.runeCircle(circleAt, () => foe.anchor('chest'), skill, 3.4, 2.9); fx.gather(circleAt, skill, 1.6, 5); });
  tl.tween(7.4, 1.4, (u) => { if (circle) circle.charge = easeInOut(u); });
  shot(8.85, 'shoulder');
  tl.at(8.9, () => {
    hero.moves.play('thrust', 1);
    const from = circleAt();
    fx.beam(from, chest(foe), skill, 1.3, 1);
    fx.stream(from, V().subVectors(foe.anchor('chest'), from), skill, .7);
    rig.fovKick(6); rig.shake(.25); post.flash(.15, skill);
  });
  tl.at(9.05, () => { fx.impact(foe.anchor('chest'), skill, 1.6); foe.moves.play('hit', .8); foe.flash(0xffffff, 1.2); });
  // the demon answers: roar, wind-up, lunge, 八卦镜 blocks
  shot(10, 'demonClose', .6);
  tl.at(10.1, () => { foe.moves.play('roar', 1.3); fx.embers(foe.anchor('chest'), 0xff3010, 2); fx.smoke(foe.anchor('chest'), 0x1e1416, 1.6); rig.shake(.3); });
  tl.at(10.9, () => foe.moves.play('windup', 1.6, { attack: .5 }));
  const lungeTo = () => V().lerpVectors(FOE_HOME, HERO_HOME, .58).setY(FOE_HOME.y - .5);
  shot(11.35, 'side');
  let ward: ReturnType<FxSystem['baguaWard']> | null = null;
  tl.at(11.3, () => { hero.moves.play('guard', 1.8); ward = fx.baguaWard(() => hero.anchor('chest'), () => foe.anchor('chest'), 2.3); });
  tl.tween(11.45, .3, (u) => foe.root.position.lerpVectors(FOE_HOME, lungeTo(), easeOut(u)));
  tl.at(11.45, () => foe.moves.play('strike', .9));
  tl.at(11.68, () => {
    const contact = hero.anchor('chest').addScaledVector(V().subVectors(foe.root.position, hero.root.position).normalize(), 2.2);
    fx.clawSlash(contact, camera.position, 0xff2a1a, 3.2);
    ward?.strike(contact);
    fx.impact(contact, 0xffc860, 1.4); fx.sparks(contact, 0xff3a1a, 1.2);
    hero.moves.play('recoil', .8); hero.flash(0xffd080, .6);
  });
  tl.tween(11.7, .5, (u) => { const back = V().subVectors(hero.root.position, foe.root.position).setY(0).normalize(); hero.root.position.copy(HERO_HOME).addScaledVector(back, Math.sin(u * Math.PI) * 1.6); });
  tl.tween(12.4, .9, (u) => foe.root.position.lerpVectors(lungeTo(), FOE_HOME, easeInOut(u)));
  // finishing blow: 天剑 descends
  shot(13, 'low', .8);
  tl.at(13, () => hero.moves.play('rise', 2.4));
  tl.at(13.2, () => fx.heavenSword(() => hero.anchor('head').add(V(0, 3, 0)), () => foe.anchor('chest'), skill, 1.3, .42, () => {
    const p = foe.anchor('chest');
    fx.impact(p, skill, 2.2); fx.embers(p, 0xff7a3a, 2.4); fx.smoke(p, 0x3a3034, 2);
    post.flash(.55, 0xffffff); rig.fovKick(10); foe.moves.play('die', 2, { hold: true });
  }));
  shot(14.5, 'impact');
  shot(15.4, 'wide', 1.6);

  let simTime = 0;
  const wind = V();
  const stats = { frames: 0, fps: 0, acc: 0, accFrames: 0, calls: 0, triangles: 0 };
  renderer.info.autoReset = false;
  let paused = false, speed = 1;

  function step(dt: number) {
    if (hitstop > 0) { hitstop -= dt; dt *= .05; }
    simTime += dt;
    tl.advance(dt);
    if (tl.t >= LOOP) tl.reset();
    hero.face(foe.root.position, .2); foe.face(hero.root.position, .08);
    wind.subVectors(hero.root.position, foe.root.position).setY(0).normalize().multiplyScalar(5).add(V(0, .6, 0));
    const ctx = { camera, wind, time: simTime, dt };
    hero.update(ctx); foe.update(ctx);
    fx.update(dt);
    env.update(simTime, dt);
  }

  return {
    scene, camera, rig, hero, foe, fx,
    get time() { return tl.t; },
    setPaused(v: boolean) { paused = v; },
    setSpeed(v: number) { speed = v; },
    /** Restart and fast-forward to t seconds (deterministic screenshots). */
    seek(t: number) {
      tl.reset(); simTime = 0; hitstop = 0;
      const h = 1 / 60;
      step(1e-6);
      for (let s = 0; s < t; s += h) { step(h); rig.update(h, hero.root.position, foe.root.position); post.update(h); }
    },
    resize(w: number, h: number) {
      renderer.setSize(w, h, false);
      post.setSize(w, h);
      camera.aspect = w / h;
      rig.aspectBoost = w / h < 1 ? 1.6 : w / h < 1.3 ? 1.2 : 1;
      camera.updateProjectionMatrix();
    },
    frame(realDt: number) {
      const dt = paused ? 0 : Math.min(realDt, 1 / 20) * speed;
      if (dt > 0) step(dt);
      rig.update(paused ? 0 : Math.min(realDt, 1 / 20), hero.root.position, foe.root.position);
      post.update(Math.min(realDt, 1 / 20));
      renderer.info.reset();
      post.composer.render(dt);
      stats.calls = renderer.info.render.calls; stats.triangles = renderer.info.render.triangles;
      stats.frames++; stats.acc += realDt; stats.accFrames++;
      if (stats.acc >= 1) { stats.fps = stats.accFrames / stats.acc; stats.acc = 0; stats.accFrames = 0; }
    },
    stats() {
      const info = renderer.info;
      return { fps: Math.round(stats.fps), frames: stats.frames, calls: stats.calls, triangles: stats.triangles, geometries: info.memory.geometries, textures: info.memory.textures, effects: fx.count, shot: rig.shot, t: +tl.t.toFixed(2) };
    },
    dispose() {
      fx.dispose();
      post.dispose();
      scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        mesh.geometry?.dispose();
        const mats = mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : [];
        for (const m of mats) { for (const v of Object.values(m)) if (v instanceof THREE.Texture) v.dispose(); m.dispose(); }
      });
      disposeOutlines();
      disposeShared();
    },
  };
}
export type Arena = ReturnType<typeof createArena>;

// ------------------------------------------------------------------ standalone lab page
declare global { interface Window { __lab?: { ready: boolean; arena: Arena; stats: () => ReturnType<Arena['stats']> & { contexts: number } } } }

export function runLab(host: HTMLElement) {
  const params = new URLSearchParams(location.search);
  const reduced = params.has('reduced') || matchMedia('(prefers-reduced-motion: reduce)').matches;
  const quality = Math.max(0, Math.min(2, Number(params.get('q') ?? 2))) as 0 | 1 | 2;
  const canvas = document.createElement('canvas');
  Object.assign(canvas.style, { position: 'absolute', inset: '0', width: '100%', height: '100%', display: 'block' });
  host.appendChild(canvas);
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: false, stencil: false, powerPreference: 'high-performance' });
  } catch {
    host.dataset.state = 'nowebgl';
    host.textContent = '此设备不支持 WebGL，斗法台以平面战报呈现。';
    return;
  }
  renderer.setPixelRatio(Math.min(devicePixelRatio, quality >= 2 ? 2 : 1.25));
  const arena = createArena(renderer, { quality, reducedMotion: reduced });
  const resize = () => arena.resize(host.clientWidth, host.clientHeight);
  addEventListener('resize', resize);
  resize();
  const seekTo = params.get('t');
  if (seekTo !== null) { arena.seek(Number(seekTo)); arena.setPaused(params.has('hold')); }
  let last = performance.now();
  const loop = (now: number) => { arena.frame((now - last) / 1000); last = now; requestAnimationFrame(loop); };
  requestAnimationFrame(loop);
  window.__lab = { ready: true, arena, stats: () => ({ ...arena.stats(), contexts: document.querySelectorAll('canvas').length }) };
  host.dataset.state = 'ready';
  return arena;
}
