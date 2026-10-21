// Free flight for the replay arena (stage 4): steering agents on a fixed 30 Hz AI tick, rendered with
// interpolation. Each flier circles its anchor with a per-form program and a seeded personality, keeps
// apart from the others and steers around the stone pillars with a look-ahead capsule probe. Presentation
// only: positions never feed back into the battle report.
import * as THREE from 'three';
import { V, clamp, rng } from './util';

export interface Obstacle { x: number; z: number; r: number; top: number }

/** How a form moves while it waits for its turn: orbit size/speed, vertical bob, sideways weave, top speed. */
export interface FlightProgram { orbit: number; speed: number; bob: number; weave: number; maxSpeed: number; bounce?: boolean; dart?: number }
export const PROGRAMS: Record<string, FlightProgram> = {
  beast: { orbit: 2.6, speed: .45, bob: .35, weave: 0, maxSpeed: 7 },                 // 兽：绕圈逡巡
  ape: { orbit: 1.8, speed: .4, bob: 1.1, weave: 0, maxSpeed: 6, bounce: true },     // 猿：上下蹿跃
  fox: { orbit: 3.2, speed: .7, bob: .4, weave: .6, maxSpeed: 10, dart: .35 },       // 狐：忽左忽右急掠
  serpent: { orbit: 2.8, speed: .32, bob: .5, weave: 1.4, maxSpeed: 6 },             // 蛟：蛇形游走
  golem: { orbit: .9, speed: .16, bob: .12, weave: 0, maxSpeed: 2.5 },               // 傀：沉稳缓移
  shade: { orbit: 2.2, speed: .22, bob: 1, weave: .3, maxSpeed: 5 },                 // 影：飘忽起伏
  spirit: { orbit: 2.2, speed: .26, bob: .9, weave: .4, maxSpeed: 5 },
  human: { orbit: 2.4, speed: .38, bob: .25, weave: .2, maxSpeed: 7 },               // 人：游斗绕步
  hero: { orbit: .7, speed: .3, bob: .15, weave: 0, maxSpeed: 6 },                   // 主角：御剑悬停
};

export interface Agent {
  id: string;
  pos: THREE.Vector3; vel: THREE.Vector3; prev: THREE.Vector3;
  radius: number;
  anchor: () => THREE.Vector3;
  program: FlightProgram;
  /** Seeded personality: phase, speed and orbit multipliers, orbit tilt. */
  phase: number; tempo: number; reach: number; tilt: number;
  /** Paused agents hold still (dying, scattering or scripted moves). */
  paused: boolean;
}

const H = 1 / 30;
const LOOKAHEAD = .9;

export class Flock {
  readonly agents: Agent[] = [];
  private acc = 0;
  private t = 0;
  ticks = 0;
  /** Ticks on which some agent's probe met a pillar and steered off it. */
  avoids = 0;
  /** Smallest (distance to pillar axis − pillar radius − agent radius) seen on any tick; ≥ 0 means no contact. */
  minClearance = Infinity;
  constructor(private obstacles: Obstacle[]) {}

  add(id: string, pos: THREE.Vector3, radius: number, anchor: () => THREE.Vector3, program: FlightProgram, seed: number) {
    const r = rng(seed);
    const agent: Agent = { id, pos: pos.clone(), vel: V(), prev: pos.clone(), radius, anchor, program, phase: r.range(0, Math.PI * 2), tempo: r.range(.8, 1.25), reach: r.range(.8, 1.3), tilt: r.range(.35, .8), paused: false };
    this.agents.push(agent);
    return agent;
  }

  /** Put every agent on its current anchor (a replay jump), clearing velocity and interpolation. */
  settle() {
    for (const a of this.agents) { a.pos.copy(this.goal(a)); a.prev.copy(a.pos); a.vel.set(0, 0, 0); }
    this.acc = 0;
  }

  /** Advance by dt seconds of arena time on the fixed AI tick; returns the interpolation factor for rendering. */
  step(dt: number) {
    this.acc += dt;
    let n = 0;
    while (this.acc >= H && n < 12) { this.tick(); this.acc -= H; n++; }
    if (n === 12) this.acc = 0;  // a long stall: drop the backlog rather than spiral
    return this.acc / H;
  }

  /** Rendered position: between the last two ticks. */
  at(a: Agent, alpha: number, out = V()) { return out.lerpVectors(a.prev, a.pos, alpha); }

  private goal(a: Agent) {
    const p = a.program, t = this.t * p.speed * a.tempo + a.phase, r = p.orbit * a.reach;
    const lift = p.bounce ? Math.abs(Math.sin(t * 2.2)) * p.bob * 1.6 : Math.sin(t * 1.7) * p.bob;
    const weave = Math.sin(t * 3.1) * p.weave;
    const dart = p.dart ? Math.sign(Math.sin(t * .9)) * p.dart * r : 0;
    return a.anchor().add(V(Math.cos(t) * r + weave + dart, lift, Math.sin(t) * r * a.tilt));
  }

  private tick() {
    this.t += H; this.ticks++;
    const force = V(), want = V(), away = V(), ahead = V();
    let steered = false;
    for (const a of this.agents) {
      a.prev.copy(a.pos);
      if (a.paused) { a.vel.set(0, 0, 0); continue; }
      const p = a.program, maxForce = p.maxSpeed * 3;
      // arrive at the orbit point
      want.subVectors(this.goal(a), a.pos);
      const d = want.length();
      want.setLength(Math.min(p.maxSpeed, d * 2.2));
      force.subVectors(want, a.vel);
      // separation from the other fliers
      for (const b of this.agents) {
        if (b === a || b.paused) continue;
        away.subVectors(a.pos, b.pos);
        const gap = away.length(), room = a.radius + b.radius + .6;
        if (gap > 1e-4 && gap < room) force.addScaledVector(away.normalize(), (room - gap) * 9);
      }
      // pillars: probe the capsule from here to where the velocity carries us, push off sideways
      ahead.copy(a.pos).addScaledVector(a.vel, LOOKAHEAD);
      for (const o of this.obstacles) {
        if (a.pos.y > o.top + a.radius) continue;
        const near = closestOnSegmentXZ(a.pos, ahead, o.x, o.z);
        const dx = near.x - o.x, dz = near.z - o.z, dist = Math.hypot(dx, dz), room = o.r + a.radius + 1.5;
        if (dist < room) {
          const k = (room - dist) / room;
          steered = true;
          force.x += (dx / (dist || 1)) * k * maxForce * 2.5;
          force.z += (dz / (dist || 1)) * k * maxForce * 2.5;
        }
      }
      if (force.length() > maxForce) force.setLength(maxForce);
      a.vel.addScaledVector(force, H);
      if (a.vel.length() > p.maxSpeed) a.vel.setLength(p.maxSpeed);
      a.pos.addScaledVector(a.vel, H);
      // last resort: never end a tick inside a pillar
      for (const o of this.obstacles) {
        if (a.pos.y > o.top + a.radius) continue;
        const dx = a.pos.x - o.x, dz = a.pos.z - o.z, dist = Math.hypot(dx, dz), room = o.r + a.radius;
        if (dist < room) { const s = room / (dist || 1); a.pos.x = o.x + dx * s; a.pos.z = o.z + dz * s; }
      }
    }
    if (steered) this.avoids++;
  }

  /** Clearance of a rendered point (positions after scripted lunges are checked by the arena). */
  clearance(p: THREE.Vector3, radius: number) {
    let best = Infinity;
    for (const o of this.obstacles) if (p.y <= o.top + radius) best = Math.min(best, Math.hypot(p.x - o.x, p.z - o.z) - o.r - radius);
    return best;
  }

  record(p: THREE.Vector3, radius: number) { this.minClearance = Math.min(this.minClearance, this.clearance(p, radius)); }
}

function closestOnSegmentXZ(a: THREE.Vector3, b: THREE.Vector3, x: number, z: number) {
  const ex = b.x - a.x, ez = b.z - a.z, len = ex * ex + ez * ez;
  const u = len > 1e-6 ? clamp(((x - a.x) * ex + (z - a.z) * ez) / len) : 0;
  return { x: a.x + ex * u, z: a.z + ez * u };
}
