// Verlet ribbons for sashes, sleeves, robe tails and hair. Each ribbon is a chain of particles whose root
// follows an anchor on the body; wind, gravity and the actor's own motion make it stream behind.
import * as THREE from 'three';
import { V } from './util';

export interface RibbonOptions {
  segments: number;
  length: number;          // rest length of one segment
  width: number;
  taper?: number;          // tip width as a fraction of root width
  drag?: number;           // velocity retained per step
  gravity?: number;
  flutter?: number;
  /** 'face' turns the ribbon toward the camera; 'axis' spans it along a body axis (hair sheets, robe tails). */
  mode?: 'face' | 'axis';
}

let ribbonSeed = 0;
const tmpA = V(), tmpB = V(), side = V(), dir = V(), toCam = V(), vel = V(), force = V();

export class Ribbon {
  readonly mesh: THREE.Mesh;
  private p: THREE.Vector3[];
  private o: THREE.Vector3[];
  private geo: THREE.BufferGeometry;
  private ready = false;
  private seed = (ribbonSeed++ * 2.39) % 10;

  constructor(private opt: RibbonOptions, material: THREE.Material) {
    const n = opt.segments + 1;
    this.p = Array.from({ length: n }, () => V());
    this.o = Array.from({ length: n }, () => V());
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 2 * 3), 3));
    const uv = new Float32Array(n * 2 * 2);
    for (let i = 0; i < n; i++) uv.set([0, i / (n - 1), 1, i / (n - 1)], i * 4);
    geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
    const index: number[] = [];
    for (let i = 0; i < n - 1; i++) { const k = i * 2; index.push(k, k + 1, k + 2, k + 1, k + 3, k + 2); }
    geo.setIndex(index);
    this.geo = geo;
    this.mesh = new THREE.Mesh(geo, material);
    this.mesh.frustumCulled = false;
  }

  /** Re-seed the chain on the next step (after teleports or a replay restart). */
  invalidate() { this.ready = false; }

  /** Snap the chain behind the anchor (after teleports or on first frame). */
  reset(anchor: THREE.Vector3, back: THREE.Vector3) {
    this.p.forEach((q, i) => { q.copy(anchor).addScaledVector(back, i * this.opt.length); this.o[i].copy(q); });
    this.ready = true;
  }

  step(anchor: THREE.Vector3, axis: THREE.Vector3, wind: THREE.Vector3, dt: number, time: number, camera: THREE.Camera) {
    const { segments, length, drag = .965, gravity = 3, flutter = 2.4 } = this.opt;
    if (!this.ready) this.reset(anchor, tmpA.copy(wind).normalize());
    this.p[0].copy(anchor); this.o[0].copy(anchor);
    const dt2 = Math.min(dt, 1 / 30) ** 2;
    for (let i = 1; i <= segments; i++) {
      const q = this.p[i];
      vel.subVectors(q, this.o[i]).multiplyScalar(drag);
      this.o[i].copy(q);
      const gust = Math.sin(time * 4.2 + i * .55 + this.seed) * flutter, k = i / segments;
      force.set(wind.x, wind.y - gravity, wind.z).addScaledVector(axis, gust * k).add(tmpA.set(0, Math.cos(time * 3.1 + i * .7 + this.seed) * flutter * .5 * k, 0));
      q.add(vel).addScaledVector(force, dt2);
    }
    for (let it = 0; it < 4; it++) for (let i = 1; i <= segments; i++) {
      const a = this.p[i - 1], b = this.p[i];
      dir.subVectors(b, a);
      const l = dir.length() || 1;
      b.copy(a).addScaledVector(dir, length / l);
    }
    const pos = this.geo.attributes.position as THREE.BufferAttribute, taper = this.opt.taper ?? .35;
    for (let i = 0; i <= segments; i++) {
      tmpA.copy(this.p[Math.max(0, i - 1)]); tmpB.copy(this.p[Math.min(segments, i + 1)]);
      dir.subVectors(tmpB, tmpA).normalize();
      if (this.opt.mode === 'axis') side.copy(axis).addScaledVector(dir, -axis.dot(dir)).normalize();
      else { toCam.subVectors(camera.position, this.p[i]); side.crossVectors(dir, toCam).normalize(); }
      const w = this.opt.width * (1 - (1 - taper) * (i / segments)) * .5;
      const q = this.p[i];
      pos.setXYZ(i * 2, q.x - side.x * w, q.y - side.y * w, q.z - side.z * w);
      pos.setXYZ(i * 2 + 1, q.x + side.x * w, q.y + side.y * w, q.z + side.z * w);
    }
    pos.needsUpdate = true;
    this.geo.computeVertexNormals();
  }
}
