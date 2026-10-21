// 「云海御空」 stage 2: the arena driven by the Python battle_report. Every number, hit and outcome comes from the
// report; this file only stages it. Timing contract with static/battle_replay.js: play(event) is called when the
// replay reaches the event, and the blow must land when the replay drops its damage floater (hitDelay below,
// scaled by setSpeed). setFrame() carries the beat's settled state; without animation it snaps straight to it.
import * as THREE from 'three';
import { LION_COLOR, disposeTextures, loadArt, loadLionArt, makeArtCultivator, makeArtLion } from './art';
import { CameraRig, type ShotName } from './camera';
import type { Actor } from './actors';
import { buildEnvironment } from './env';
import { FxSystem } from './fx';
import { buildPost } from './post';
import { C, V, clamp, disposeOutlines, disposeShared, easeInOut, easeOut, lerp } from './util';

/** unit: the minion hit (target enemy) or striking (source enemy); absent = the leader. aoe: part of a group attack. */
export interface ReportEvent { type: string; source: string; target: string; label?: string; amount?: number; unit?: string; aoe?: boolean }
export interface ReportFrame { round: number; player: { hp: number; mp: number }; enemy: { hp: number; barrier?: number }; units?: { id: string; hp: number }[]; action?: string; events?: ReportEvent[] }
interface Treasure { name: string; quality: string }
export interface BattleReport {
  outcome: string; rounds: number; frames: ReportFrame[];
  enemy: { name: string; max_hp: number; kind: string; units?: { id: string; name: string; max_hp: number }[] }; player: { max_hp: number; max_mp: number };
  treasures?: { main?: Treasure | null; guard?: Treasure | null };
}
/** Presentation hints from the page (realm tier, spirit root, technique, enemy form); never used to settle anything. */
export interface ArenaContext { report: BattleReport; tier?: number; root?: string | null; skill?: string; form?: string; boss?: boolean }
export interface FrameInfo { last?: boolean; outcome?: string; animate?: boolean }

// 灵根 → sword light; 功法 → spell style; 法宝品质 → sword count
const ELEMENT: Record<string, number> = { fire: 0xff7a2e, wood: 0x3fe39a, earth: 0xf0b040 };
const QUALITY_SWORDS: Record<string, number> = { 凡品: 3, 下品: 4, 中品: 5, 上品: 7, 极品: 9 };
const BOSS_KINDS = new Set(['guard', 'world_boss', 'elite']);
const P = { mist: 0x8a7ab8, ember: 0xd8b0ff, roar: 0xc890ff, claw: 0xb46cff, death: 0xe0c0ff, deathSmoke: 0x6a5a8a };
const GOLD = 0xffc860, HEAL = 0x7dffb0, POISON = 0x7adf4a, MANA = 0x7ab8ff, NPC = 0xbfe8ff;
const HERO_HOME = V(0, 0, 6);
const HERO_FROM = V(-16, 5, 20);
/** Minion slots around the leader: [side, rank]; rank 0 flanks it, later ranks step toward the hero. */
const SLOTS = [[-1, 0], [1, 0], [-1, 1], [1, 1], [-.45, 2], [.45, 2]];

/** Seconds from play() until the blow lands; mirrors the floater delays in battle_replay.js show3d(). */
export function hitDelay(event: ReportEvent, action = '') {
  if (event.source === 'main') return .62;
  if (event.source === 'enemy') return /重击/.test(event.label || '') ? .76 : .56;
  return /强攻/.test(action) ? .76 : .52;
}

/** One-shot callbacks and tweens on the arena clock; cleared whenever the replay jumps. */
class Schedule {
  t = 0;
  private items: { at: number; fn: () => void }[] = [];
  private tweens: { start: number; dur: number; fn: (u: number) => void }[] = [];
  after(seconds: number, fn: () => void) { if (seconds <= 0) fn(); else this.items.push({ at: this.t + seconds, fn }); }
  tween(delay: number, dur: number, fn: (u: number) => void) { this.tweens.push({ start: this.t + delay, dur, fn }); }
  clear() { this.items = []; this.tweens = []; }
  advance(dt: number) {
    this.t += dt;
    const due = this.items.filter((e) => e.at <= this.t);
    this.items = this.items.filter((e) => e.at > this.t);
    due.sort((a, b) => a.at - b.at).forEach((e) => e.fn());
    this.tweens = this.tweens.filter((tw) => {
      const u = (this.t - tw.start) / tw.dur;
      if (u >= 0) tw.fn(Math.min(1, u));
      return u < 1;
    });
  }
}

export function buildArena(renderer: THREE.WebGLRenderer, host: HTMLElement, ctx: ArenaContext) {
  const report = ctx.report;
  const quality = ((navigator.hardwareConcurrency || 4) >= 8 ? 2 : 1) as 1 | 2;
  const reduced = !!globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const tier = clamp(ctx.tier ?? 0, 0, 8);
  const color = ELEMENT[ctx.root ?? ''] ?? 0x5fd0ff;
  const style = ctx.skill === 'flame' ? 'flame' : ctx.skill === 'mountain' ? 'palm' : 'sword';
  const boss = !!ctx.boss || BOSS_KINDS.has(report.enemy.kind);
  const form = ctx.form || 'spirit';
  const foeScale = boss ? 1 : .72;
  const foeHome = V(0, boss ? 1.2 : .8, boss ? -11 : -9.5);
  const maxBarrier = Math.max(1, ...report.frames.map((f) => f.enemy.barrier || 0));

  const scene = new THREE.Scene();
  const rig = new CameraRig(reduced);
  rig.foeScale = foeScale;
  const camera = rig.camera;
  const env = buildEnvironment(scene, quality);
  const post = buildPost(renderer, scene, camera, quality, reduced);
  // hit-stop only slows the fighters: the schedule and the projectiles keep wall-clock time so blows stay on the floaters
  let hitstop = 0, foeFrozen = 0;
  const fx = new FxSystem(scene, camera, {
    shake: (a) => rig.shake(a),
    hitstop: (s) => { if (!reduced) hitstop = Math.max(hitstop, s); },
    flash: (a, c) => post.flash(a, c),
    aberrate: (a) => post.aberrate(a),
  }, reduced);

  const art = loadArt(), lionArt = loadLionArt();
  fx.setArt(art);
  const hero = makeArtCultivator(art, color), foe = makeArtLion(lionArt);
  foe.root.scale.setScalar(foeScale);
  scene.add(hero.root, foe.root);
  fx.attachAura(foe.root, { color: P.mist, rate: boss ? 8 : 5, radius: 3, rise: 1.5, size: [2.5, 5], smoke: true, offset: V(-.5, 3, 0) });
  fx.attachAura(foe.root, { color: LION_COLOR, rate: boss ? 30 : 18, radius: 3.4, rise: 4, size: [.15, .4], offset: V(0, 3.5, 0) });
  fx.attachAura(hero.root, { color, rate: 10 + tier * 2, radius: .5, rise: -.5, size: [.08, .2], offset: V(-.6, -1.5, 0) });

  // 随行小怪: the report's minions, each a small painted lion in a fan before the leader (all forms share the lion art for now)
  interface Minion { id: string; actor: Actor; home: THREE.Vector3; side: number; lunge: number; flee: number; gone: boolean; armed: boolean; pending: number }
  const minions: Minion[] = (report.enemy.units || []).map((u, i) => {
    const actor = makeArtLion(lionArt);
    actor.root.scale.setScalar(.3);
    const [side, rank] = SLOTS[i] ?? [0, 0];
    const home = foeHome.clone().add(V(side * (5.5 + rank * 1.5) * foeScale, -1.4 + rank * .5, 3 + rank * 2.4));
    actor.root.position.copy(home);
    scene.add(actor.root);
    return { id: u.id, actor, home, side, lunge: 0, flee: 0, gone: false, armed: false, pending: 0 };
  });
  const unitOf = (id?: string) => (id ? minions.find((m) => m.id === id) ?? null : null);

  // the foe's 护体 barrier: a crystal shell that cracks as the report's barrier drains
  const barrierMat = new THREE.ShaderMaterial({
    uniforms: { color: { value: C(LION_COLOR).multiplyScalar(1.5) }, alpha: { value: 0 }, crack: { value: 0 }, time: { value: 0 } },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    vertexShader: 'varying vec3 vP, vN, vV; void main(){ vP = normalize(position); vec4 mv = modelViewMatrix * vec4(position, 1.); vN = normalize(normalMatrix * normal); vV = normalize(-mv.xyz); gl_Position = projectionMatrix * mv; }',
    fragmentShader: `uniform vec3 color; uniform float alpha, crack, time; varying vec3 vP, vN, vV;
      float h(vec2 p){ return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
      void main(){ vec2 uv = vec2(atan(vP.z, vP.x) * 3., vP.y * 3.); vec2 cell = floor(uv * 3.); vec2 f = fract(uv * 3.);
        float edge = 1. - smoothstep(.0, .06, min(min(f.x, f.y), min(1. - f.x, 1. - f.y)));
        float broken = step(1. - crack, h(cell));
        float rim = pow(clamp(1. - abs(dot(vN, vV)), 0., 1.), 2.2);
        float a = (rim * .6 + edge * (.05 + broken * .7) + .03 * sin(time * 3. + vP.y * 8.)) * alpha;
        gl_FragColor = vec4(color * (1. + broken * edge * 1.5), a); }`,
  });
  const barrier = new THREE.Mesh(new THREE.SphereGeometry(1, 40, 24), barrierMat);
  barrier.visible = false;
  scene.add(barrier);
  let barrierTarget = 0;

  const sched = new Schedule();
  let speed = 1, lunge = 0, heroFall = 0, foeGone = false;
  let pendingFoe = 0, pendingHero = 0, foeDeathArmed = false, heroFallArmed = false;
  let wardUntil = -1, ward: ReturnType<FxSystem['baguaWard']> | null = null;
  let shotToken = 0;
  const lungeTo = () => V().lerpVectors(foeHome, HERO_HOME, .55).setY(foeHome.y - .5);
  const foeChest = () => foe.anchor('chest'), leaderChest = foeChest;
  const npcAt = () => hero.root.position.clone().add(V(-3.4, -.4, 2.6));
  const jitter = (p: THREE.Vector3, k: number) => p.add(V(Math.sin(k * 7.3), Math.cos(k * 3.1) * 1.2, Math.sin(k * 2.2) * .6).multiplyScalar(foeScale));

  /** Cut or blend to a shot, then drift back to the over-the-shoulder view unless a later event takes over. */
  function direct(shot: ShotName, blend = 0, hold = 1.2) {
    if (blend) rig.go(shot, blend); else rig.cut(shot);
    const token = ++shotToken;
    sched.after(hold, () => { if (token === shotToken && !foeGone && !heroFall) rig.go('shoulder', .7); });
  }

  // ---------------------------------------------------------------- landing blows
  /** k = 0 is the counted blow (full impact); trailing swords only spark so volleys never white out the frame. */
  function foeHit(power: number, tint: number, k = 0) {
    const p = jitter(foeChest(), k);
    if (k) { fx.sparks(p, tint, .5 + power * .4); fx.glowBurst(p, tint, 2.2 * foeScale, .3); } else fx.impact(p, tint, power);
    foe.flash(0xffffff, .9);
    if (!foeGone) foe.moves.play('hit', .5);
  }
  function landOnFoe(power: number, tint: number) {
    foeHit(power, tint);
    if (foeDeathArmed && --pendingFoe <= 0) killFoe();
  }
  function landOnUnit(m: Minion, power: number, tint: number) {
    const p = m.actor.anchor('chest');
    fx.sparks(p, tint, .5 + power * .5); fx.glowBurst(p, tint, 2.4, .35); fx.shockwave(p, tint, 1.6 + power, .4);
    m.actor.flash(0xffffff, .9);
    if (!m.gone) m.actor.moves.play('hit', .45);
    if (m.armed && --m.pending <= 0) killUnit(m);
  }
  function killUnit(m: Minion) {
    if (m.gone) return;
    m.gone = true; m.armed = false;
    m.actor.moves.play('die', 1.4, { hold: true });
    fx.embers(m.actor.anchor('chest'), P.death, .9);
  }
  function landOnHero() {
    if (heroFallArmed && --pendingHero <= 0) felled();
  }

  /** m: a single-target hit on that minion instead of the leader. */
  function heroStrike(event: ReportEvent, k: number, action: string, after?: () => void, m?: Minion) {
    const T = hitDelay(event, action), strong = /强攻/.test(action), talisman = /符/.test(event.label || '');
    const n = Math.round(clamp(2 + k * 4 + tier / 3 + (strong ? 2 : 0), 2, m ? 4 : 9));
    const foeChest = m ? () => m.actor.anchor('chest') : leaderChest;
    const land = (i: number) => {
      if (m) { if (!i) landOnUnit(m, .5 + k * .5, color); return; }
      if (i) foeHit(.35 + k * .3, color, i); else { landOnFoe(.5 + k * .6, color); after?.(); }
    };
    direct(strong ? 'heroClose' : talisman || style === 'flame' ? 'side' : 'shoulder', strong ? 0 : .3, T + .5);
    if (strong) { hero.moves.play('charge', T * .7); fx.gather(() => hero.anchor('hand'), color, T * .6, 3); sched.after(T * .45, () => rig.go('shoulder', .25)); }
    const hand = () => hero.anchor('hand');
    if (talisman || style === 'flame') {
      const lead = strong ? T * .4 : .08, fire = style === 'flame' ? 0xff7a2e : GOLD;
      sched.after(lead, () => {
        hero.moves.play('thrust', .7);
        fx.talismans(hand, foeChest, Math.min(n, 6), (i) => { land(i); fx.embers(foeChest(), fire, .6); }, { fly: T - lead, stagger: .05 });
      });
    } else if (style === 'palm') {
      const at = () => hand().addScaledVector(V().subVectors(foe.root.position, hero.root.position).setY(0).normalize(), 2.2);
      hero.moves.play('charge', T);
      const circle = fx.runeCircle(at, foeChest, color, 2.4 + k * 1.4, T + .5);
      sched.tween(0, T, (u) => { circle.charge = easeInOut(u); });
      sched.after(T - .12, () => { hero.moves.play('thrust', .8); const from = at(); fx.beam(from, foeChest, color, 1 + k * .7, .55); fx.stream(from, V().subVectors(foeChest(), from), color, .4); rig.fovKick(5); });
      sched.after(T, () => land(0));
    } else {
      hero.moves.play('cast', T + .3);
      const form0 = strong ? T * .5 : T * .38;
      fx.swordSwarm(hand, () => hero.anchor('back'), foeChest, color, n, land, { form: form0, fly: T - form0, stagger: .045 });
    }
  }

  function treasureStrike(k: number, after?: () => void) {
    const T = hitDelay({ type: 'damage', source: 'main', target: 'enemy' });
    const quality = report.treasures?.main?.quality || '下品';
    const land = (i: number) => { if (i) foeHit(.4, color, i); else { landOnFoe(.6 + k * .5, color); after?.(); } };
    if (QUALITY_SWORDS[quality] >= 7 && k > .45) {
      direct('low', .25, T + .6);
      hero.moves.play('rise', T + .6);
      fx.heavenSword(() => hero.anchor('head').add(V(0, 2.5, 0)), foeChest, color, T * .45, T * .55, () => { land(0); post.flash(.3, 0xffffff); rig.fovKick(8); });
    } else {
      direct('shoulder', .3, T + .4);
      const count = QUALITY_SWORDS[quality] ?? 4;
      fx.swordSwarm(() => hero.anchor('back'), () => hero.anchor('back'), foeChest, color, count, land, { form: T * .4, fly: T * .6, stagger: .035 });
    }
  }

  function companionStrike(after?: () => void) {
    const T = .52, at = npcAt();
    fx.glowBurst(at, NPC, 2.4, .5);
    fx.swordSwarm(npcAt, () => npcAt().add(V(0, 1, 0)), foeChest, NPC, 2, (i) => { if (i) foeHit(.3, NPC, i); else { landOnFoe(.45, NPC); after?.(); } }, { form: .2, fly: T - .2, stagger: .06 });
  }

  /** One sword (or talisman) of a group attack peeling off to a minion, landing with its floater. */
  function sweep(event: ReportEvent, m: Minion, action: string) {
    const T = hitDelay(event, action), aim = () => m.actor.anchor('chest');
    const from = event.source === 'main' ? () => hero.anchor('back') : () => hero.anchor('hand');
    const land = (i: number) => { if (!i) landOnUnit(m, .4, color); };
    if (/符/.test(event.label || '')) fx.talismans(from, aim, 1, (i) => { land(i); fx.embers(aim(), 0xff7a2e, .4); }, { fly: T, stagger: 0 });
    else fx.swordSwarm(from, () => hero.anchor('back'), aim, color, 1, land, { form: T * .3, fly: T * .7, stagger: 0 });
  }

  function minionStrike(event: ReportEvent, m: Minion) {
    const T = hitDelay(event);
    m.actor.moves.play('windup', T * .5, { attack: .5 });
    sched.after(T * .4, () => m.actor.moves.play('strike', .6));
    sched.tween(T * .35, T * .65, (u) => { m.lunge = Math.max(m.lunge, easeOut(u)); });
    sched.after(T, () => {
      const contact = hero.anchor('chest').addScaledVector(V().subVectors(m.actor.root.position, hero.root.position).normalize(), 1.4);
      fx.clawSlash(contact, camera.position, P.claw, 1.3);
      if (ward && sched.t < wardUntil) ward.strike(contact);
      fx.sparks(contact, LION_COLOR, .6);
      hero.flash(0xffc0c8, .15); hero.moves.play('hit', .4);
      landOnHero();
    });
    sched.tween(T + .1, .6, (u) => { m.lunge = Math.min(m.lunge, 1 - easeInOut(u)); });
  }

  function foeStrike(event: ReportEvent, k: number) {
    const heavy = /重击/.test(event.label || ''), T = hitDelay(event);
    direct(heavy ? 'demonClose' : 'side', heavy ? 0 : .25, T + .5);
    if (heavy) sched.after(T * .5, () => rig.cut('side'));
    foe.moves.play('windup', T * .55, { attack: .5 });
    fx.embers(foe.anchor('head'), P.roar, heavy ? 1.4 : .7);
    sched.after(T * .45, () => foe.moves.play('strike', .7));
    sched.tween(T * .45, T * .55, (u) => { lunge = Math.max(lunge, easeOut(u)); });
    sched.after(T, () => {
      const contact = hero.anchor('chest').addScaledVector(V().subVectors(foe.root.position, hero.root.position).normalize(), 2.2);
      fx.clawSlash(contact, camera.position, P.claw, heavy ? 3.6 : 2.6);
      if (ward && sched.t < wardUntil) { ward.strike(contact); fx.impact(contact, GOLD, .5 + k * .4); }
      else { fx.impact(contact, P.claw, .4 + k * .5); hero.flash(0xff9aa8, .45); }
      fx.sparks(contact, LION_COLOR, 1 + k);
      hero.moves.play(heavy ? 'recoil' : 'hit', .7);
      landOnHero();
    });
    sched.tween(T + .15, .8, (u) => { lunge = Math.min(lunge, 1 - easeInOut(u)); });
  }

  function raiseWard(seconds: number) {
    hero.moves.play('guard', seconds);
    ward = fx.baguaWard(() => hero.anchor('chest'), foeChest, seconds);
    wardUntil = sched.t + seconds;
  }

  function breakBarrier() {
    const p = foeChest();
    fx.shockwave(p, LION_COLOR, 6 * foeScale, .6);
    fx.glowBurst(p, 0xe8d0ff, 7 * foeScale, .5);
    fx.sparks(p, 0xe8d0ff, 1.6);
    rig.shake(.35);
    barrierTarget = 0;
  }

  // ---------------------------------------------------------------- report events
  function play(event: ReportEvent, opts: { intensity?: number; action?: string } = {}) {
    if (disposed) return;
    const k = clamp(opts.intensity ?? .4, .15, 1), action = opts.action || '';
    switch (event.type) {
      case 'damage': case 'shield': {
        const after = event.type === 'shield' ? () => sched.after(.08, breakBarrier) : undefined;
        const m = unitOf(event.unit);
        if (event.source === 'enemy') { if (m) minionStrike(event, m); else if (!event.unit) foeStrike(event, k); }
        else if (event.unit) { if (m && event.aoe) sweep(event, m, action); else if (m) heroStrike(event, k, action, undefined, m); }
        else if (event.source === 'main') treasureStrike(k, after);
        else if (event.source === 'npc') companionStrike(after);
        else heroStrike(event, k, action, after);
        break;
      }
      case 'shield_absorb': raiseWard(1.6); break;
      case 'defend':
        raiseWard(1.8);
        fx.shockwave(hero.anchor('feet'), GOLD, 3.5, .7, true);
        direct('heroClose', .3, 1.1);
        break;
      case 'heal':
        hero.moves.play('charge', .8);
        fx.gather(() => hero.anchor('chest'), HEAL, .7, 3);
        sched.after(.2, () => { const p = hero.anchor('chest'); fx.glowBurst(p, HEAL, 4, .6); fx.embers(p, HEAL, 1.2); hero.flash(HEAL, .6); });
        direct('heroClose', .3, 1.1);
        break;
      case 'buff': {
        hero.moves.play('rise', 1.2);
        const feet = () => hero.anchor('feet');
        fx.runeCircle(feet, () => feet().add(V(0, 5, 0)), GOLD, 3, 1.4);
        sched.after(.3, () => { fx.embers(hero.anchor('chest'), GOLD, 1); hero.flash(GOLD, .5); });
        direct('heroClose', .3, 1.1);
        break;
      }
      case 'control':
        hero.moves.play('thrust', .7);
        fx.talismans(() => hero.anchor('hand'), foeChest, 3, (i) => {
          if (i) return;
          fx.runeCircle(foeChest, () => camera.position.clone(), GOLD, 5 * foeScale, 1.6);
          foe.flash(0xa0d8ff, 1.2);
          foeFrozen = 1.3;
        }, { fly: .3, stagger: .06 });
        direct('side', .3, 1.4);
        break;
      case 'poison': {
        const p = hero.anchor('chest');
        fx.smoke(p, POISON, 1.2); fx.sparks(p, POISON, .7);
        hero.flash(POISON, .7); hero.moves.play('hit', .6);
        break;
      }
      case 'mana': {
        const p = hero.anchor('chest');
        fx.stream(p, V(0, 2, 0).add(V().subVectors(foeChest(), p).normalize()), MANA, .6);
        hero.flash(MANA, .4);
        break;
      }
      default: break;
    }
  }

  // ---------------------------------------------------------------- beat state
  function killFoe() {
    if (foeGone) return;
    foeGone = true; foeDeathArmed = false;
    foe.moves.play('die', 2, { hold: true });
    const p = foeChest();
    fx.impact(p, color, 1.3); fx.embers(p, P.death, 2.4); fx.smoke(p, P.deathSmoke, 2);
    post.flash(.5, 0xffffff); rig.fovKick(8);
    rig.go('impact', .3);
    for (const k of [0, 1, 2]) sched.after(.5 + k * .4, () => { const q = foeChest().add(V(0, k - 1, 0)); fx.embers(q, P.death, 1.4); fx.smoke(q, P.deathSmoke, 1); });
    sched.after(1.5, () => { rig.go('heroClose', 1.6); hero.moves.play('rise', 2.4); });
    // the leader is down: whatever is left of the pack scatters into the clouds
    for (const m of minions) if (!m.gone) {
      m.armed = false;
      sched.tween(.3 + Math.abs(m.side) * .2, 1.6, (u) => { m.flee = u * u; });
      sched.after(2, () => { m.gone = true; m.actor.root.visible = false; });
    }
  }
  function felled() {
    if (heroFall) return;
    heroFallArmed = false;
    hero.moves.play('hit', 3, { hold: true });
    sched.tween(0, 1.4, (u) => { heroFall = Math.max(.001, easeInOut(u)); post.desaturate(heroFall * .7); });
    rig.go('wide', 1.4);
  }

  function setFrame(frame: ReportFrame, info: FrameInfo = {}) {
    if (disposed || !frame) return;
    const events = frame.events || [];
    const foeDown = frame.enemy.hp <= 0;
    const heroDown = !!info.last && info.outcome === 'defeat' && frame.player.hp <= 0;
    const bar = frame.enemy.barrier || 0;
    barrierMat.uniforms.crack.value = bar > 0 ? 1 - bar / maxBarrier : 1;
    if (!info.animate) {
      // a jump (open, scrub, skip, restore): land straight on this beat's state
      sched.clear(); fx.clear(); hero.reset(); foe.reset();
      lunge = 0; foeFrozen = 0; hitstop = 0; ward = null; wardUntil = -1;
      foeDeathArmed = heroFallArmed = false;
      foeGone = foeDown; foe.root.visible = !foeDown;
      for (const m of minions) {
        const hp = frame.units?.find((u) => u.id === m.id)?.hp ?? 1;
        m.actor.reset(); m.lunge = 0; m.flee = 0; m.armed = false;
        m.gone = hp <= 0 || foeDown; m.actor.root.visible = !m.gone;
      }
      heroFall = heroDown ? 1 : 0; post.desaturate(heroFall * .7);
      barrierTarget = bar > 0 ? 1 : 0; barrierMat.uniforms.alpha.value = barrierTarget * .6;
      foe.root.position.copy(foeHome);
      if (frame.round === 0 && !info.last) intro();
      else { hero.root.position.copy(HERO_HOME); rig.cut(!info.last ? 'shoulder' : foeDown ? 'heroClose' : 'wide'); }
      return;
    }
    // an animated beat: the state changes land with the blows that cause them
    if (bar > 0) barrierTarget = 1;
    else if (!events.some((e) => e.type === 'shield')) barrierTarget = 0;
    else sched.after(1.6, () => { barrierTarget = 0; });
    if (foeDown && !foeGone && !foeDeathArmed) {
      foeDeathArmed = true;
      pendingFoe = events.filter((e) => e.target === 'enemy' && !e.unit && (e.type === 'damage' || e.type === 'shield') && e.source !== 'enemy').length;
      sched.after(2.6, () => { if (foeDeathArmed) killFoe(); });
    }
    for (const m of minions) {
      const hp = frame.units?.find((u) => u.id === m.id)?.hp ?? 1;
      if (hp > 0 || m.gone || m.armed) continue;
      m.armed = true;
      m.pending = events.filter((e) => e.unit === m.id && e.type === 'damage' && e.target === 'enemy').length;
      sched.after(2.6, () => { if (m.armed) killUnit(m); });
    }
    if (heroDown && !heroFall && !heroFallArmed) {
      heroFallArmed = true;
      pendingHero = events.filter((e) => e.source === 'enemy' && e.type === 'damage').length;
      sched.after(2.6, () => { if (heroFallArmed) felled(); });
    }
  }

  function intro() {
    hero.root.position.copy(HERO_FROM);
    hero.moves.play('dash', 2);
    rig.cut('establish');
    sched.tween(0, 2, (u) => { const k = easeOut(u); hero.root.position.set(lerp(HERO_FROM.x, HERO_HOME.x, k), lerp(HERO_FROM.y, HERO_HOME.y, k) + Math.sin(u * Math.PI) * 3, lerp(HERO_FROM.z, HERO_HOME.z, k)); });
    sched.after(.9, () => { foe.moves.play('roar', 1.8); fx.embers(foe.anchor('head'), P.ember, 1.4); rig.shake(.3); });
    sched.after(1.4, () => rig.go('heroClose', .4));
    sched.after(2, () => rig.go('shoulder', .5));
  }

  function clear() {
    sched.clear(); fx.clear();
    lunge = 0; foeFrozen = 0; hitstop = 0; ward = null; wardUntil = -1;
    foeDeathArmed = heroFallArmed = false;
  }

  /** Where the DOM floaters go: 0..1 viewport fractions, top-left origin. */
  function project(id: string) {
    const m = unitOf(id);
    const p = m ? m.actor.anchor('head').add(V(0, .3, 0))
      : id === 'enemy' ? foe.anchor('head').add(V(0, .8 * foeScale, 0))
      : id === 'npc' ? npcAt().add(V(0, 1, 0))
      : id === 'main' ? hero.anchor('back')
      : hero.anchor('head').add(V(0, .5, 0));
    p.project(camera);
    return { x: (p.x + 1) / 2, y: (1 - p.y) / 2, visible: p.z < 1 };
  }

  // ---------------------------------------------------------------- loop, size, quality
  let width = 0, height = 0, ratio = Math.min(globalThis.devicePixelRatio || 1, quality >= 2 ? 1.5 : 1);
  function resize() {
    const w = host.clientWidth, h = host.clientHeight;
    if (!w || !h) return;
    width = w; height = h;
    renderer.setPixelRatio(ratio);
    renderer.setSize(w, h, false);
    post.setSize(w, h);
    camera.aspect = w / h;
    rig.aspectBoost = w / h < 1 ? 1.6 : w / h < 1.3 ? 1.2 : 1;
    camera.updateProjectionMatrix();
  }
  const observer = globalThis.ResizeObserver ? new ResizeObserver(() => resize()) : null;
  observer?.observe(host);
  resize();

  renderer.info.autoReset = false;
  let disposed = false, frameId = 0, last = 0, simTime = 0;
  const frameMs: number[] = [];
  const wind = V();
  const counters = { calls: 0, triangles: 0 };
  /** Slow frames are split into substeps so the arena clock keeps pace with the replay's wall-clock floaters. */
  function step(realDt: number) {
    const total = Math.min(realDt, .25) * speed, n = Math.max(1, Math.ceil(total / (1 / 20)));
    for (let i = 0; i < n; i++) substep(total / n);
    rig.update(total, hero.root.position, foe.root.position);
    post.update(total);
  }
  function substep(dt: number) {
    sched.advance(dt);
    let actorDt = dt;
    if (hitstop > 0) { hitstop -= dt; actorDt *= .1; }
    simTime += actorDt;
    foeFrozen = Math.max(0, foeFrozen - dt);
    foe.root.position.lerpVectors(foeHome, lungeTo(), lunge);
    if (heroFall) hero.root.position.copy(HERO_HOME).add(V(-.6 * heroFall, -3.2 * heroFall, 0));
    hero.face(foe.root.position, .2); foe.face(hero.root.position, .08);
    wind.subVectors(hero.root.position, foe.root.position).setY(0).normalize().multiplyScalar(5).add(V(0, .6, 0));
    hero.update({ camera, wind, time: simTime, dt: actorDt });
    foe.update({ camera, wind, time: simTime, dt: foeFrozen > 0 ? actorDt * .12 : actorDt });
    for (const m of minions) {
      if (!m.actor.root.visible) continue;
      m.actor.root.position.lerpVectors(m.home, hero.root.position, m.lunge * .55).add(V(m.side * m.flee * 14, m.flee * 9, -m.flee * 10));
      m.actor.face(hero.root.position, .1);
      m.actor.update({ camera, wind, time: simTime + m.side, dt: foeFrozen > 0 ? actorDt * .12 : actorDt });
    }
    const bTarget = foeGone ? 0 : barrierTarget * .6, ba = barrierMat.uniforms.alpha;
    ba.value += (bTarget - ba.value) * Math.min(1, dt * 6);
    barrier.visible = ba.value > .01;
    barrier.position.copy(foeChest());
    barrier.scale.setScalar(3.8 * foeScale);
    barrierMat.uniforms.time.value = simTime;
    fx.update(dt);
    env.update(simTime, dt);
  }
  function tick(now: number) {
    frameId = 0;
    if (disposed || document.hidden) return;
    const ms = last ? now - last : 16; last = now;
    step(ms / 1000);
    renderer.info.reset();
    post.composer.render();
    counters.calls = renderer.info.render.calls; counters.triangles = renderer.info.render.triangles;
    adapt(ms);
    frameId = requestAnimationFrame(tick);
  }
  /** Drop the pixel ratio when frames stay slow; quality never decides anything but sharpness. */
  function adapt(ms: number) {
    frameMs.push(ms); if (frameMs.length > 90) frameMs.shift();
    if (frameMs.length < 90) return;
    const avg = frameMs.reduce((a, b) => a + b, 0) / frameMs.length;
    if (avg > 34 && ratio > .75) { ratio = Math.max(.75, ratio - .25); frameMs.length = 0; resize(); }
  }
  function wake() { if (!frameId && !disposed && !document.hidden) { last = 0; frameId = requestAnimationFrame(tick); } }
  const onVisibility = () => wake();
  document.addEventListener('visibilitychange', onVisibility);
  hero.root.position.copy(HERO_HOME); foe.root.position.copy(foeHome);
  intro();
  wake();

  function stats() {
    const avg = frameMs.length ? frameMs.reduce((a, b) => a + b, 0) / frameMs.length : 0;
    const info = renderer.info;
    return {
      fps: avg ? Math.round(1000 / avg) : 0, frameMs: Math.round(avg * 10) / 10, quality, ratio, size: [width, height],
      form, boss, style, tier, drawCalls: counters.calls, triangles: counters.triangles,
      geometries: info.memory.geometries, textures: info.memory.textures, effects: fx.count, shot: rig.shot, foeGone, heroFall,
      units: minions.length, unitsUp: minions.filter((m) => !m.gone).length,
    };
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    if (frameId) cancelAnimationFrame(frameId);
    observer?.disconnect();
    document.removeEventListener('visibilitychange', onVisibility);
    sched.clear();
    fx.dispose();
    post.dispose();
    scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      mesh.geometry?.dispose();
      const mats = mesh.material ? (Array.isArray(mesh.material) ? mesh.material : [mesh.material]) : [];
      for (const m of mats) { for (const v of Object.values(m)) if (v instanceof THREE.Texture) v.dispose(); m.dispose(); }
    });
    disposeTextures(art); disposeTextures(lionArt);
    disposeOutlines(); disposeShared();
  }

  return { play, setFrame, project, clear, resize, setSpeed: (v: number) => { speed = v; }, stats, dispose };
}
export type ReplayArena = ReturnType<typeof buildArena>;
