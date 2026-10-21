// Director camera: named shots computed live from the fighters' positions, eased blends or hard cuts,
// trauma-based shake and FOV kicks. The default shot is over the hero's right shoulder toward the foe.
import * as THREE from 'three';
import { V, clamp, easeInOut, lerp } from './util';

export type ShotName = 'establish' | 'shoulder' | 'castView' | 'side' | 'heroClose' | 'demonClose' | 'impact' | 'low' | 'wide';
interface ShotPose { pos: THREE.Vector3; look: THREE.Vector3; fov: number }

const UP = V(0, 1, 0);

export class CameraRig {
  readonly camera: THREE.PerspectiveCamera;
  shot: ShotName = 'establish';
  private from: ShotPose = { pos: V(), look: V(), fov: 45 };
  private blend = 1;
  private blendDur = 1;
  private trauma = 0;
  private kick = 0;
  private t = 0;
  private current: ShotPose = { pos: V(0, 5, 20), look: V(), fov: 45 };
  /** Portrait screens need a wider lens and a little more distance. */
  aspectBoost = 1;

  constructor(private reduced: boolean) {
    this.camera = new THREE.PerspectiveCamera(45, 16 / 9, .1, 2400);
  }

  cut(shot: ShotName) { this.shot = shot; this.blend = 1; this.blendDur = 0; }
  go(shot: ShotName, seconds: number) {
    this.from = { pos: this.current.pos.clone(), look: this.current.look.clone(), fov: this.current.fov };
    this.shot = shot; this.blend = 0; this.blendDur = seconds;
  }
  shake(amount: number) { this.trauma = Math.min(1, this.trauma + amount * (this.reduced ? .25 : 1)); }
  fovKick(degrees: number) { if (!this.reduced) this.kick = Math.max(this.kick, degrees); }

  private compose(shot: ShotName, hero: THREE.Vector3, foe: THREE.Vector3): ShotPose {
    const dir = V().subVectors(foe, hero).setY(0).normalize();
    const right = V().crossVectors(dir, UP).normalize();
    const mid = V().lerpVectors(hero, foe, .5);
    const drift = Math.sin(this.t * .23) * .35;
    const far = this.aspectBoost;
    switch (shot) {
      case 'shoulder': return { pos: hero.clone().addScaledVector(dir, -4.3 * far).addScaledVector(right, 1.9 + drift * .3).add(V(0, .7, 0)), look: V().lerpVectors(hero, foe, .6).add(V(0, 1.9, 0)), fov: 46 };
      case 'castView': return { pos: hero.clone().addScaledVector(dir, -4.4 * far).addScaledVector(right, -2.6).add(V(0, .6, 0)), look: hero.clone().addScaledVector(dir, 5).add(V(0, 1.6, 0)), fov: 46 };
      case 'side': if (far > 1.3) return { pos: mid.clone().addScaledVector(right, 8).addScaledVector(dir, -15).add(V(0, 4 + drift, 0)), look: mid.clone().add(V(0, 2.4, 0)), fov: 44 }; // portrait: diagonal keeps both fighters in frame
        return { pos: mid.clone().addScaledVector(right, 17 * far).addScaledVector(dir, -3).add(V(0, 3 + drift, 0)), look: mid.clone().add(V(0, 2.4, 0)), fov: 40 };
      case 'heroClose': return { pos: hero.clone().addScaledVector(dir, 4.6 * far).addScaledVector(right, .9 + drift * .4).add(V(0, .5, 0)), look: hero.clone().add(V(0, .35, 0)), fov: 38 };
      case 'demonClose': return { pos: foe.clone().addScaledVector(dir, -10.5 * far).addScaledVector(right, -3.5).add(V(0, .8, 0)), look: foe.clone().add(V(0, 5.6, 0)), fov: 42 };
      case 'impact': return { pos: foe.clone().addScaledVector(dir, -8 * far).addScaledVector(right, 4).add(V(0, 4.2, 0)), look: foe.clone().add(V(0, 4.2, 0)), fov: 50 };
      case 'low': return { pos: hero.clone().addScaledVector(dir, -4.5 * far).addScaledVector(right, 2.4).add(V(0, -2.2, 0)), look: hero.clone().add(V(0, 5, 0)).addScaledVector(dir, 4), fov: 48 };
      case 'wide': {
        const a = this.t * .05;
        const orbit = V().addScaledVector(dir, -Math.cos(a) * 26 * far).addScaledVector(right, Math.sin(a) * 26 * far + 10);
        return { pos: mid.clone().add(orbit).add(V(0, 8, 0)), look: mid.clone().add(V(0, 2, 0)), fov: 46 };
      }
      default: return { pos: hero.clone().addScaledVector(dir, -16 * far).addScaledVector(right, 11 * far).add(V(0, 7 + drift, 0)), look: mid.clone().add(V(0, 2.5, 0)), fov: 48 };
    }
  }

  update(dt: number, hero: THREE.Vector3, foe: THREE.Vector3) {
    this.t += dt;
    const target = this.compose(this.shot, hero, foe);
    if (this.blend < 1 && this.blendDur > 0) {
      this.blend = Math.min(1, this.blend + dt / this.blendDur);
      const k = easeInOut(this.blend);
      this.current.pos.lerpVectors(this.from.pos, target.pos, k);
      this.current.look.lerpVectors(this.from.look, target.look, k);
      this.current.fov = lerp(this.from.fov, target.fov, k);
    } else {
      // gentle follow so moving fighters do not jerk the frame
      const f = 1 - Math.exp(-dt * 6);
      if (this.blendDur === 0) { this.current.pos.copy(target.pos); this.current.look.copy(target.look); this.current.fov = target.fov; this.blendDur = -1; }
      else { this.current.pos.lerp(target.pos, f); this.current.look.lerp(target.look, f); this.current.fov = lerp(this.current.fov, target.fov, f); }
    }
    const cam = this.camera;
    cam.position.copy(this.current.pos);
    const s = this.trauma * this.trauma;
    if (s > 0) {
      const n = (k: number) => Math.sin(this.t * 47 + k) * .6 + Math.sin(this.t * 83 + k * 2.3) * .4;
      cam.position.add(V(n(1), n(2), n(3)).multiplyScalar(s * .9));
    }
    cam.lookAt(this.current.look);
    if (s > 0) cam.rotateZ(Math.sin(this.t * 61) * s * .05);
    this.trauma = Math.max(0, this.trauma - dt * 1.6);
    this.kick = Math.max(0, this.kick - dt * 30);
    cam.fov = clamp(this.current.fov * (this.aspectBoost > 1 ? 1.12 : 1) + this.kick, 20, 80);
    cam.updateProjectionMatrix();
  }
}
