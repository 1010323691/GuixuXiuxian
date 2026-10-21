// Orbit camera for the sect: drag to orbit, wheel to zoom, right-drag/shift-drag to pan, smooth focus tweens.
// Constraints: limited pitch and distance, the eye never sinks into the cloud sea (minCamY), never ends up
// inside a peak (coarse height field) or a building box (pulled in along the view ray), target kept on site.
import * as THREE from 'three';
import { HOME_VIEW, LIMITS } from './layout';
import { clamp, easeInOut, lerp } from './util';

export interface OrbitState { target: THREE.Vector3; azimuth: number; elevation: number; distance: number }

export class SectCamera {
  readonly camera: THREE.PerspectiveCamera;
  state: OrbitState;
  private goal: OrbitState;
  private tween: { from: OrbitState; to: OrbitState; t: number; dur: number } | null = null;
  constructor(aspect: number, private ground: (x: number, z: number) => number, private boxes: THREE.Box3[], private reduced: boolean) {
    this.camera = new THREE.PerspectiveCamera(38, aspect, 2, 9000);
    this.state = SectCamera.home();
    this.goal = SectCamera.home();
    this.apply();
  }

  static home(): OrbitState {
    return { target: new THREE.Vector3(...HOME_VIEW.target), azimuth: HOME_VIEW.azimuth, elevation: HOME_VIEW.elevation, distance: HOME_VIEW.distance };
  }

  private clampGoal(s: OrbitState) {
    s.elevation = clamp(s.elevation, LIMITS.minElev, LIMITS.maxElev);
    s.distance = clamp(s.distance, LIMITS.minDist, LIMITS.maxDist);
    const t = LIMITS.target;
    s.target.set(clamp(s.target.x, -t.x, t.x), clamp(s.target.y, t.yMin, t.yMax), clamp(s.target.z, t.zMin, t.zMax));
  }

  orbit(dx: number, dy: number) { this.tween = null; this.goal.azimuth -= dx * .0055; this.goal.elevation += dy * .0045; this.clampGoal(this.goal); }
  zoom(delta: number) { this.tween = null; this.goal.distance *= Math.exp(delta * .0011); this.clampGoal(this.goal); }
  pan(dx: number, dy: number) {
    this.tween = null;
    const k = this.goal.distance * .0016, a = this.goal.azimuth;
    // screen-right and screen-forward projected on the ground plane
    this.goal.target.x += (-Math.cos(a) * dx + -Math.sin(a) * dy) * k;
    this.goal.target.z += (Math.sin(a) * dx + -Math.cos(a) * dy) * k;
    this.clampGoal(this.goal);
  }

  /** Smoothly moves to a framed view of a point (building focus) or home. */
  flyTo(to: OrbitState, dur = .9) {
    this.clampGoal(to);
    if (this.reduced) { this.state = cloneState(to); this.goal = cloneState(to); this.tween = null; this.apply(); return; }
    // take the short way round
    let az = to.azimuth;
    while (az - this.state.azimuth > Math.PI) az -= Math.PI * 2;
    while (az - this.state.azimuth < -Math.PI) az += Math.PI * 2;
    this.tween = { from: cloneState(this.state), to: { ...cloneState(to), azimuth: az }, t: 0, dur };
    this.goal = cloneState(this.tween.to);
  }
  home() { this.flyTo(SectCamera.home(), 1.1); }
  get moving() { return !!this.tween; }

  update(dt: number) {
    if (this.tween) {
      const tw = this.tween;
      tw.t = Math.min(1, tw.t + dt / tw.dur);
      const e = easeInOut(tw.t);
      this.state.target.lerpVectors(tw.from.target, tw.to.target, e);
      this.state.azimuth = lerp(tw.from.azimuth, tw.to.azimuth, e);
      this.state.elevation = lerp(tw.from.elevation, tw.to.elevation, e);
      // dolly out a little mid-flight so long hops do not skim the terrain
      this.state.distance = lerp(tw.from.distance, tw.to.distance, e) * (1 + Math.sin(e * Math.PI) * .12);
      if (tw.t >= 1) this.tween = null;
    } else {
      const k = 1 - Math.exp(-dt * 10);
      this.state.target.lerp(this.goal.target, k);
      this.state.azimuth = lerp(this.state.azimuth, this.goal.azimuth, k);
      this.state.elevation = lerp(this.state.elevation, this.goal.elevation, k);
      this.state.distance = lerp(this.state.distance, this.goal.distance, k);
    }
    this.apply();
  }

  /** Eye position for an orbit state, before collision. */
  private eye(s: OrbitState, distance = s.distance) {
    const ce = Math.cos(s.elevation);
    return new THREE.Vector3(s.target.x + Math.sin(s.azimuth) * ce * distance, s.target.y + Math.sin(s.elevation) * distance, s.target.z + Math.cos(s.azimuth) * ce * distance);
  }

  private apply() {
    const s = this.state;
    let dist = s.distance, eye = this.eye(s);
    // buildings: pull in along the ray until the eye is outside every (padded) box
    for (let i = 0; i < 12; i++) {
      if (!this.boxes.some((b) => b.containsPoint(eye))) break;
      dist *= .85;
      eye = this.eye(s, dist);
    }
    // peaks and cloud sea: lift the eye (raise pitch) instead of passing through rock
    const floor = Math.max(LIMITS.minCamY, this.ground(eye.x, eye.z) + 14);
    if (eye.y < floor) eye.y = floor;
    this.camera.position.copy(eye);
    this.camera.lookAt(s.target);
  }

  /** For tests/diagnostics: the eye clearance above terrain and cloud floor. */
  clearance() { const p = this.camera.position; return { y: p.y, ground: this.ground(p.x, p.z), inBox: this.boxes.some((b) => b.containsPoint(p)) }; }
}

export const cloneState = (s: OrbitState): OrbitState => ({ target: s.target.clone(), azimuth: s.azimuth, elevation: s.elevation, distance: s.distance });
