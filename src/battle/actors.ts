// The two combatants, built procedurally in the toon + ink style: a white-robed sword cultivator riding a
// flying sword, and a towering horned demon. Motion comes from weighted move templates, not physics.
import * as THREE from 'three';
import { Ribbon } from './cloth';
import { C, V, TAU, canvasTexture, clamp, inked, lerp, pulse, rng, smoothLathe, taperTube, toon, easeOut } from './util';

export type MoveName = 'charge' | 'cast' | 'thrust' | 'dash' | 'hit' | 'guard' | 'recoil' | 'rise' | 'roar' | 'windup' | 'strike' | 'die';

/** Weighted move templates: each play() is an envelope; poses blend by weight. */
export class Moves {
  private active = new Map<MoveName, { t: number; dur: number; hold: boolean; attack: number }>();
  readonly w: Record<MoveName, number> = { charge: 0, cast: 0, thrust: 0, dash: 0, hit: 0, guard: 0, recoil: 0, rise: 0, roar: 0, windup: 0, strike: 0, die: 0 };
  play(name: MoveName, dur: number, { hold = false, attack = .25 } = {}) { this.active.set(name, { t: 0, dur, hold, attack }); }
  stop(name: MoveName) { this.active.delete(name); this.w[name] = 0; }
  clear() { this.active.clear(); for (const k in this.w) this.w[k as MoveName] = 0; }
  /** 0..1 progress of a move, or -1 when it is not playing. */
  progress(name: MoveName) { const m = this.active.get(name); return m ? Math.min(1, m.t / m.dur) : -1; }
  update(dt: number) {
    for (const [name, m] of this.active) {
      m.t += dt;
      const u = m.t / m.dur;
      if (m.hold && u >= m.attack) this.w[name] = 1;
      else this.w[name] = pulse(u, m.attack);
      if (u >= 1 && !m.hold) { this.active.delete(name); this.w[name] = 0; }
    }
  }
}

export interface FrameContext { camera: THREE.Camera; wind: THREE.Vector3; time: number; dt: number }

export interface Actor {
  root: THREE.Group;
  moves: Moves;
  height: number;
  radius: number;
  /** World-space points effects attach to. */
  anchor(name: 'hand' | 'chest' | 'head' | 'feet' | 'claw' | 'back'): THREE.Vector3;
  face(target: THREE.Vector3, rate?: number): void;
  flash(color?: THREE.ColorRepresentation, strength?: number): void;
  update(ctx: FrameContext): void;
  reset(): void;
}

const yawTo = (from: THREE.Vector3, to: THREE.Vector3) => Math.atan2(-(to.z - from.z), to.x - from.x);
function turn(root: THREE.Object3D, target: THREE.Vector3, rate: number) {
  const want = yawTo(root.position, target);
  let d = want - root.rotation.y;
  d = Math.atan2(Math.sin(d), Math.cos(d));
  root.rotation.y += d * Math.min(1, rate);
}

// ------------------------------------------------------------------ flying sword mesh (shared with fx)
export function swordGeometry(len = 2.2) {
  const s = new THREE.Shape();
  s.moveTo(0, -.075); s.lineTo(len * .8, -.06); s.lineTo(len, 0); s.lineTo(len * .8, .06); s.lineTo(0, .075); s.closePath();
  const g = new THREE.ExtrudeGeometry(s, { depth: .025, bevelEnabled: true, bevelThickness: .018, bevelSize: .018, bevelSegments: 2 });
  g.translate(-len * .35, 0, -.0125);
  return g;
}
export function makeSword(color: THREE.ColorRepresentation, scale = 1) {
  const g = new THREE.Group();
  const blade = inked(new THREE.Mesh(swordGeometry(), toon(0xe6f4fa, { emissive: C(color), emissiveIntensity: .55, rim: 0xffffff })), .018);
  const guard = inked(new THREE.Mesh(new THREE.BoxGeometry(.09, .44, .1), toon(0xd9b04a, { emissive: C(0x6a4a10), emissiveIntensity: .4 })), .014);
  guard.position.x = -.77;
  const hilt = new THREE.Mesh(new THREE.CylinderGeometry(.04, .045, .5, 10), toon(0x2a3b4a));
  hilt.rotation.z = Math.PI / 2; hilt.position.x = -1.05;
  const tassel = new THREE.Mesh(new THREE.ConeGeometry(.05, .3, 8), toon(0x3fa0d8));
  tassel.rotation.z = Math.PI / 2; tassel.position.x = -1.42;
  g.add(blade, guard, hilt, tassel);
  g.scale.setScalar(scale);
  return g;
}

// ------------------------------------------------------------------ cultivator
export function makeCultivator(skill: THREE.ColorRepresentation = 0x5fd0ff): Actor {
  const root = new THREE.Group(), body = new THREE.Group();
  root.add(body);
  const white = toon(0xf6f4ee), whiteSide = toon(0xf6f4ee, { side: THREE.DoubleSide }), sky = toon(0x6fb3df), gold = toon(0xd9b04a, { emissive: C(0x5a3c08), emissiveIntensity: .35 });
  const skin = toon(0xf7dccb, { rim: 0xffe6d0 }), hair = toon(0x15171d, { rim: 0x8fb8e8, rimPower: 2.5 }), jade = toon(0x48b89a, { emissive: C(0x0a3a2a), emissiveIntensity: .4 });

  // robe: upper body lathe and a flared skirt that swings separately with speed
  body.add(inked(new THREE.Mesh(smoothLathe([[0, -.45], [.42, -.42], [.33, .05], [.28, .36], [.35, .6], [.19, .79], [0, .83]], 40), white), .022));
  const skirt = new THREE.Group(); skirt.position.y = -.4; body.add(skirt);
  const skirtGeo = smoothLathe([[.4, 0], [.48, -.35], [.6, -.75], [.74, -1.05]], 44);
  { const p = skirtGeo.attributes.position; for (let i = 0; i < p.count; i++) { const a = Math.atan2(p.getZ(i), p.getX(i)), y = p.getY(i), k = 1 + .08 * Math.sin(a * 6) * (-y); p.setX(i, p.getX(i) * k); p.setZ(i, p.getZ(i) * k); } skirtGeo.computeVertexNormals(); }
  skirt.add(inked(new THREE.Mesh(skirtGeo, whiteSide), .02));
  const underskirt = new THREE.Mesh(smoothLathe([[.36, 0], [.42, -.4], [.5, -.95]], 32), sky); underskirt.scale.setScalar(.94); skirt.add(underskirt);
  // lapels, belt, pendant
  const lapel = new THREE.Mesh(new THREE.TorusGeometry(.27, .035, 8, 24, Math.PI), sky); lapel.position.set(.05, .55, 0); lapel.rotation.set(0, Math.PI / 2, -.5); body.add(lapel);
  const belt = inked(new THREE.Mesh(new THREE.TorusGeometry(.32, .055, 10, 32), sky), .014); belt.rotation.x = Math.PI / 2; belt.position.y = .02; body.add(belt);
  const buckle = new THREE.Mesh(new THREE.SphereGeometry(.07, 12, 8), gold); buckle.position.set(.33, .02, 0); body.add(buckle);
  const pendant = new THREE.Mesh(new THREE.TorusGeometry(.06, .025, 8, 16), jade); pendant.position.set(.3, -.28, .12); body.add(pendant);

  // head
  const head = new THREE.Group(); head.position.y = 1.03; body.add(head);
  head.add(inked(new THREE.Mesh(new THREE.SphereGeometry(.2, 32, 24), skin), .016));
  const eyeMat = new THREE.MeshBasicMaterial({ color: 0x1a1d24 });
  for (const s of [-1, 1]) {
    const eye = new THREE.Mesh(new THREE.SphereGeometry(.026, 12, 8), eyeMat); eye.scale.set(.7, 1.25, .7); eye.position.set(.185, .015, s * .07); head.add(eye);
    const brow = new THREE.Mesh(new THREE.BoxGeometry(.012, .014, .07), eyeMat); brow.position.set(.19, .08, s * .075); brow.rotation.x = s * .28; head.add(brow);
  }
  const cap = new THREE.Mesh(new THREE.SphereGeometry(.215, 32, 16, 0, TAU, 0, Math.PI * .56), hair); cap.rotation.z = .4; cap.position.x = -.02; head.add(inked(cap, .014));
  const backHair = new THREE.Mesh(new THREE.SphereGeometry(.22, 24, 16), hair); backHair.scale.set(.9, 1.05, 1); backHair.position.set(-.05, -.04, 0); head.add(backHair);
  const bun = inked(new THREE.Mesh(new THREE.SphereGeometry(.1, 20, 14), hair), .012); bun.position.set(-.07, .23, 0); head.add(bun);
  const crown = inked(new THREE.Mesh(new THREE.CylinderGeometry(.065, .085, .11, 16), gold), .012); crown.position.set(-.07, .29, 0); head.add(crown);
  const pin = new THREE.Mesh(new THREE.CylinderGeometry(.011, .011, .52, 8), gold); pin.rotation.x = Math.PI / 2; pin.position.set(-.07, .29, 0); head.add(pin);

  // arms with wide sleeves; the right (+z) arm forms the sword-finger gesture
  const arm = (side: number) => {
    const shoulder = new THREE.Group(); shoulder.position.set(0, .62, side * .3); body.add(shoulder);
    shoulder.add(inked(new THREE.Mesh(new THREE.CapsuleGeometry(.075, .34, 6, 14), white), .014).translateY(-.2));
    const elbow = new THREE.Group(); elbow.position.y = -.42; shoulder.add(elbow);
    elbow.add(new THREE.Mesh(new THREE.CapsuleGeometry(.062, .28, 6, 14), white).translateY(-.16));
    const sleeve = new THREE.Mesh(smoothLathe([[.07, .08], [.12, -.08], [.2, -.3], [.23, -.42], [.13, -.47]], 32), whiteSide); elbow.add(inked(sleeve, .012));
    const cuff = new THREE.Mesh(new THREE.TorusGeometry(.2, .022, 6, 24), sky); cuff.rotation.x = Math.PI / 2; cuff.position.y = -.42; elbow.add(cuff);
    const hand = new THREE.Group(); hand.position.y = -.48; elbow.add(hand);
    hand.add(new THREE.Mesh(new THREE.SphereGeometry(.055, 14, 10), skin));
    const fingers = new THREE.Mesh(new THREE.CapsuleGeometry(.018, .12, 4, 8), skin); fingers.position.y = -.09; hand.add(fingers);
    return { shoulder, elbow, hand };
  };
  const armF = arm(1), armB = arm(-1);

  // the flying sword under the feet
  const mount = makeSword(skill, 1.2);
  mount.rotation.x = -Math.PI / 2; mount.position.set(.05, -1.5, 0);
  root.add(mount);
  const mountGlow = new THREE.PointLight(C(skill), 3, 6, 2); mountGlow.position.set(0, -1.4, 0); root.add(mountGlow);

  // cloth: hair sheets, sashes, the floating shawl (披帛), sleeve tails, robe tails
  const clothRoot = new THREE.Group();
  const sashMat = toon(0x7cc4ec, { side: THREE.DoubleSide, rim: 0xe0f4ff });
  const shawlMat = toon(0xbfe6fa, { side: THREE.DoubleSide, transparent: true, opacity: .82, rim: 0xffffff });
  const hairMat = toon(0x15171d, { side: THREE.DoubleSide, rim: 0x6f98c8, rimPower: 2.5 });
  const robeMat = toon(0xf6f4ee, { side: THREE.DoubleSide });
  type Strand = { ribbon: Ribbon; anchor: THREE.Vector3; axis: 'side' | 'up' };
  const strands: Strand[] = [];
  const add = (ribbon: Ribbon, anchor: THREE.Vector3, axis: Strand['axis']) => { clothRoot.add(ribbon.mesh); strands.push({ ribbon, anchor, axis }); };
  add(new Ribbon({ segments: 16, length: .1, width: .2, taper: .3, mode: 'axis', gravity: 2.4, flutter: 1.6 }, hairMat), V(-.16, 1.05, 0), 'side');
  add(new Ribbon({ segments: 12, length: .1, width: .1, taper: .25, mode: 'face', gravity: 2.4, flutter: 2 }, hairMat), V(-.12, 1.12, .12), 'side');
  add(new Ribbon({ segments: 12, length: .1, width: .1, taper: .25, mode: 'face', gravity: 2.4, flutter: 2 }, hairMat), V(-.12, 1.12, -.12), 'side');
  add(new Ribbon({ segments: 9, length: .06, width: .025, taper: .5, mode: 'face', gravity: 1, flutter: 1.2 }, toon(0x3fa0d8, { side: THREE.DoubleSide })), V(-.07, 1.32, .26), 'side');
  add(new Ribbon({ segments: 20, length: .14, width: .1, taper: .5, gravity: 1.2, flutter: 2.6 }, sashMat), V(-.1, .02, .3), 'side');
  add(new Ribbon({ segments: 20, length: .14, width: .1, taper: .5, gravity: 1.2, flutter: 2.6 }, sashMat), V(-.1, .02, -.3), 'side');
  add(new Ribbon({ segments: 26, length: .15, width: .16, taper: .55, gravity: .6, flutter: 3 }, shawlMat), V(-.05, .66, .36), 'side');
  add(new Ribbon({ segments: 26, length: .15, width: .16, taper: .55, gravity: .6, flutter: 3 }, shawlMat), V(-.05, .66, -.36), 'side');
  add(new Ribbon({ segments: 12, length: .1, width: .26, taper: .4, mode: 'axis', gravity: 1.6 }, robeMat), V(-.42, -1.3, .18), 'side');
  add(new Ribbon({ segments: 12, length: .1, width: .26, taper: .4, mode: 'axis', gravity: 1.6 }, robeMat), V(-.42, -1.3, -.18), 'side');
  const sleeveTails = [armF, armB].map((a) => {
    const ribbon = new Ribbon({ segments: 10, length: .09, width: .3, taper: .5, mode: 'axis', gravity: 1.8, flutter: 2 }, robeMat);
    clothRoot.add(ribbon.mesh);
    return { ribbon, elbow: a.elbow };
  });

  const moves = new Moves();
  const flashColor = C(0xffffff);
  let flashAmt = 0, attached = false;
  const lastPos = V(), velocity = V(), tmp = V(), axisSide = V(), axisUp = V(), wind = V();
  const flashTargets = [white, whiteSide, skin];

  return {
    root, moves, height: 2.7, radius: .8,
    anchor(name) {
      root.updateMatrixWorld();
      switch (name) {
        case 'hand': return armF.hand.getWorldPosition(V());
        case 'head': return head.getWorldPosition(V());
        case 'feet': return mount.getWorldPosition(V());
        case 'back': return V(-.8, .9, 0).applyMatrix4(root.matrixWorld);
        default: return V(0, .45, 0).applyMatrix4(root.matrixWorld);
      }
    },
    face(target, rate = 1) { turn(root, target, rate); },
    flash(color = 0xffffff, strength = 1) { flashColor.set(color); flashAmt = strength; },
    reset() { moves.clear(); strands.forEach((s) => s.ribbon.invalidate()); sleeveTails.forEach((s) => s.ribbon.invalidate()); attached = false; },
    update({ camera, time: t, dt, wind: baseWind }) {
      if (!attached && root.parent) { root.parent.add(clothRoot); attached = true; }
      moves.update(dt);
      const w = moves.w;
      velocity.subVectors(root.position, lastPos).divideScalar(Math.max(dt, 1e-3));
      if (velocity.length() > 60) velocity.set(0, 0, 0);
      lastPos.copy(root.position);
      // pose: blend each template's target onto the idle stance
      const breathe = Math.sin(t * 1.4);
      const lean = -.08 - w.dash * .38 - w.thrust * .2 + w.recoil * .42 + w.hit * .3 - w.charge * .05;
      body.rotation.z = lean + breathe * .015;
      body.rotation.x = Math.sin(t * .9) * .025 + w.hit * .12;
      body.position.y = Math.sin(t * 1.6) * .06 + w.rise * .3;
      head.rotation.z = Math.sin(t * .7) * .04 - w.cast * .12 + w.recoil * .25;
      head.rotation.y = w.charge * -.15;
      const sF = armF.shoulder.rotation, eF = armF.elbow.rotation, sB = armB.shoulder.rotation, eB = armB.elbow.rotation;
      // idle: sword-finger raised before the chest, other hand behind the back
      sF.set(-.25, 0, .55 + breathe * .03); eF.set(0, 0, 1.55);
      sB.set(.2, 0, -.35); eB.set(0, 0, -.9);
      const castW = Math.max(w.cast, w.thrust);
      sF.z = lerp(sF.z, 1.62, castW); sF.x = lerp(sF.x, -.08, castW); eF.z = lerp(eF.z, .08, castW);
      sF.x = lerp(sF.x, -1.4, w.charge); sF.z = lerp(sF.z, .5, w.charge); eF.z = lerp(eF.z, .5, w.charge);
      sB.x = lerp(sB.x, 1.4, w.charge); sB.z = lerp(sB.z, .5, w.charge); eB.z = lerp(eB.z, .5, w.charge);
      sF.z = lerp(sF.z, 1.35, w.guard); sF.x = lerp(sF.x, .35, w.guard); eF.z = lerp(eF.z, .6, w.guard);
      sB.z = lerp(sB.z, 1.25, w.guard); sB.x = lerp(sB.x, -.35, w.guard); eB.z = lerp(eB.z, .7, w.guard);
      sF.z = lerp(sF.z, 2.7, w.rise); eF.z = lerp(eF.z, 0, w.rise);
      sB.z = lerp(sB.z, -.6, w.hit + w.recoil); sF.z = lerp(sF.z, -.2, w.hit * .5);
      // skirt swings back with speed; sword under the feet tilts into turns
      const speed = clamp(velocity.length() / 25);
      skirt.rotation.z = .12 + speed * .35 + Math.sin(t * 2.3) * .03 + w.dash * .25;
      mount.rotation.y = Math.sin(t * 1.2) * .03 + w.dash * .1;
      mountGlow.intensity = 3 + w.charge * 6 + w.dash * 4;
      // flash on hit
      flashAmt = Math.max(0, flashAmt - dt * 4);
      for (const mat of flashTargets) mat.emissive.copy(flashColor).multiplyScalar(flashAmt * .8);
      // cloth follows anchors with wind relative to motion
      root.updateMatrixWorld(true);
      wind.copy(baseWind).addScaledVector(velocity, -.9);
      axisSide.set(0, 0, 1).transformDirection(root.matrixWorld);
      axisUp.set(0, 1, 0).transformDirection(root.matrixWorld);
      for (const s of strands) s.ribbon.step(tmp.copy(s.anchor).applyMatrix4(body.matrixWorld), s.axis === 'side' ? axisSide : axisUp, wind, dt, t, camera);
      for (const s of sleeveTails) s.ribbon.step(s.elbow.localToWorld(tmp.set(-.12, -.38, 0)), axisSide, wind, dt, t + 2, camera);
    },
  };
}

// ------------------------------------------------------------------ demon
function runeTexture() {
  return canvasTexture(512, 256, (g, w, h) => {
    g.fillStyle = '#000'; g.fillRect(0, 0, w, h);
    const r = rng(66);
    g.strokeStyle = '#ffffff'; g.lineCap = 'round'; g.shadowColor = '#fff'; g.shadowBlur = 6;
    for (let i = 0; i < 22; i++) { // branching lava veins
      let x = r.range(0, w), y = r.range(0, h);
      g.lineWidth = r.range(.8, 2.2);
      g.beginPath(); g.moveTo(x, y);
      for (let k = 0; k < 6; k++) { x += r.range(-26, 26); y += r.range(8, 24); g.lineTo(x, y); }
      g.stroke();
    }
    g.font = 'bold 40px serif'; g.fillStyle = '#fff'; g.textAlign = 'center';
    for (let i = 0; i < 10; i++) { g.globalAlpha = .9; g.fillText('卍㐅亖彐冂丩卄乂'[i % 8], 40 + i * 48, 70 + (i % 3) * 60); }
  });
}

/** Adds a noise dissolve (with a burning edge) to a toon material. */
function dissolvable(mat: THREE.MeshToonMaterial, amount: { value: number }) {
  const base = mat.onBeforeCompile;
  mat.onBeforeCompile = (shader, renderer) => {
    base.call(mat, shader, renderer);
    shader.uniforms.dissolve = amount;
    shader.vertexShader = shader.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vObj;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvObj = position;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>\nvarying vec3 vObj; uniform float dissolve;
        float dh(vec3 p){ return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
        float dn(vec3 p){ vec3 i = floor(p), f = fract(p); f = f*f*(3.-2.*f);
          return mix(mix(mix(dh(i), dh(i+vec3(1,0,0)), f.x), mix(dh(i+vec3(0,1,0)), dh(i+vec3(1,1,0)), f.x), f.y),
                     mix(mix(dh(i+vec3(0,0,1)), dh(i+vec3(1,0,1)), f.x), mix(dh(i+vec3(0,1,1)), dh(i+vec3(1,1,1)), f.x), f.y), f.z); }`)
      .replace('#include <clipping_planes_fragment>', `#include <clipping_planes_fragment>
        float dz = dn(vObj * 3.1) * .7 + dn(vObj * 9.) * .3;
        if (dz < dissolve) discard;`)
      .replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n  totalEmissiveRadiance += vec3(3., 1.1, .3) * smoothstep(.08, 0., dz - dissolve) * step(.001, dissolve);');
  };
  mat.customProgramCacheKey = () => 'toon-rim-dissolve';
  return mat;
}

export function makeDemon(): Actor {
  const root = new THREE.Group(), body = new THREE.Group();
  root.add(body);
  const dissolve = { value: 0 };
  const runes = runeTexture();
  const skinMat = dissolvable(toon(0x4a1214, { emissiveMap: runes, emissive: C(0xff3a12), emissiveIntensity: .6, rim: 0xff8a5a, rimPower: 2.6 }), dissolve);
  const darkMat = dissolvable(toon(0x3a1414, { rim: 0xff7a4a }), dissolve);
  const hornMat = dissolvable(toon(0x2b2321, { rim: 0xffd0a0, rimPower: 2 }), dissolve);
  const clawMat = dissolvable(toon(0x161112, { rim: 0xff6040 }), dissolve);
  const wingMat = dissolvable(toon(0x2a0c10, { side: THREE.DoubleSide, transparent: true, opacity: .92, rim: 0x5a1610, rimPower: 3 }), dissolve);
  const eyeMat = new THREE.MeshBasicMaterial({ color: C(0xffd040).multiplyScalar(4) });
  const T = (mesh: THREE.Mesh, thick = .05) => inked(mesh, thick);

  // torso hunched forward over a narrow waist
  const torso = new THREE.Group(); torso.position.y = 2.2; torso.rotation.z = -.35; body.add(torso);
  const chest = T(new THREE.Mesh(new THREE.SphereGeometry(1, 40, 28), skinMat)); chest.scale.set(1.6, 1.7, 2.1); chest.position.y = 1.4; torso.add(chest);
  const belly = T(new THREE.Mesh(new THREE.SphereGeometry(1, 32, 20), skinMat)); belly.scale.set(1.15, 1.1, 1.45); belly.position.set(.1, 0, 0); torso.add(belly);
  for (const s of [-1, 1]) { // pectoral plates
    const plate = T(new THREE.Mesh(new THREE.SphereGeometry(.8, 20, 14), darkMat), .04); plate.scale.set(.55, .7, .9); plate.position.set(1.05, 1.55, s * .7); torso.add(plate);
  }
  for (let i = 0; i < 6; i++) { // dorsal spikes
    const spike = T(new THREE.Mesh(new THREE.ConeGeometry(.22, .9 - i * .08, 8), hornMat), .03);
    spike.position.set(-1.2 + i * .1, 2.7 - i * .45, 0); spike.rotation.z = .9 + i * .1; torso.add(spike);
  }

  // head: low-slung skull, heavy brow, jaw, fangs, burning eyes, great curling horns
  const neck = new THREE.Group(); neck.position.set(1.25, 2.55, 0); torso.add(neck);
  const head = new THREE.Group(); head.position.set(.55, .1, 0); neck.add(head);
  const skull = T(new THREE.Mesh(new THREE.SphereGeometry(.75, 32, 24), skinMat)); skull.scale.set(1.15, .95, 1.0); head.add(skull);
  const brow = T(new THREE.Mesh(new THREE.BoxGeometry(.5, .22, 1.3), darkMat), .03); brow.position.set(.5, .3, 0); brow.rotation.z = -.3; head.add(brow);
  const snout = T(new THREE.Mesh(new THREE.SphereGeometry(.45, 20, 14), skinMat), .04); snout.scale.set(1.2, .7, .9); snout.position.set(.72, -.1, 0); head.add(snout);
  const jaw = new THREE.Group(); jaw.position.set(.2, -.35, 0); head.add(jaw);
  const jawMesh = T(new THREE.Mesh(new THREE.SphereGeometry(.55, 20, 14), skinMat), .04); jawMesh.scale.set(1.3, .45, .95); jawMesh.position.set(.45, -.12, 0); jaw.add(jawMesh);
  const fangMat = toon(0xf2e6d0);
  for (const s of [-1, 1]) {
    const fang = new THREE.Mesh(new THREE.ConeGeometry(.07, .45, 8), fangMat); fang.position.set(.95, .15, s * .3); jaw.add(fang);
    const top = new THREE.Mesh(new THREE.ConeGeometry(.06, .32, 8), fangMat); top.rotation.z = Math.PI; top.position.set(1.0, -.3, s * .22); head.add(top);
    const eye = new THREE.Mesh(new THREE.SphereGeometry(.1, 12, 8), eyeMat); eye.scale.set(.6, .55, 1.2); eye.position.set(.75, .2, s * .36); head.add(eye);
    // ram horn: up, back, then curling forward
    const horn = taperTube(30, 12, hornMat);
    horn.build(new THREE.CatmullRomCurve3([V(.1, .45, s * .45), V(-.2, 1.2, s * .9), V(-.9, 1.6, s * 1.25), V(-1.4, 1.0, s * 1.5), V(-1.0, .35, s * 1.65), V(-.3, .55, s * 1.75)]), (u) => .26 * (1 - u) ** .8 + .02);
    head.add(T(horn.mesh, .03));
    const small = taperTube(10, 8, hornMat);
    small.build(new THREE.CatmullRomCurve3([V(.45, .5, s * .2), V(.5, .85, s * .28), V(.35, 1.15, s * .3)]), (u) => .08 * (1 - u) + .01);
    head.add(small.mesh);
  }

  // arms: massive shoulders, long forearms, four hooked claws
  const arm = (side: number) => {
    const shoulder = new THREE.Group(); shoulder.position.set(.3, 2.1, side * 1.85); torso.add(shoulder);
    const pauldron = T(new THREE.Mesh(new THREE.SphereGeometry(.85, 24, 16), darkMat)); pauldron.scale.set(1, .9, 1); shoulder.add(pauldron);
    for (let k = 0; k < 3; k++) { const spike = T(new THREE.Mesh(new THREE.ConeGeometry(.16, .8, 8), hornMat), .025); spike.position.set(-.2 + k * .3, .65, side * .3); spike.rotation.set(side * -.5, 0, .3 - k * .3); shoulder.add(spike); }
    const upper = T(new THREE.Mesh(new THREE.CapsuleGeometry(.48, 1.3, 8, 18), skinMat)); upper.position.y = -1.0; shoulder.add(upper);
    const elbow = new THREE.Group(); elbow.position.y = -1.9; shoulder.add(elbow);
    const fore = T(new THREE.Mesh(new THREE.CapsuleGeometry(.52, 1.3, 8, 18), skinMat)); fore.position.y = -.85; fore.scale.set(1, 1, 1.05); elbow.add(fore);
    const bracer = T(new THREE.Mesh(new THREE.CylinderGeometry(.6, .55, .5, 16), darkMat), .03); bracer.position.y = -1.2; elbow.add(bracer);
    const hand = new THREE.Group(); hand.position.y = -1.9; elbow.add(hand);
    const palm = T(new THREE.Mesh(new THREE.SphereGeometry(.5, 16, 12), skinMat), .04); palm.scale.set(1, .8, 1.1); hand.add(palm);
    for (let k = 0; k < 4; k++) {
      const claw = taperTube(10, 8, clawMat);
      const z = (k - 1.5) * .28;
      claw.build(new THREE.CatmullRomCurve3([V(.2, -.2, z), V(.55, -.55, z * 1.2), V(.75, -1.0, z * 1.3), V(.55, -1.35, z * 1.3)]), (u) => .11 * (1 - u) + .01);
      hand.add(claw.mesh);
    }
    return { shoulder, elbow, hand };
  };
  const armR = arm(1), armL = arm(-1);

  // legs folded beneath (it hovers), and a tail
  for (const s of [-1, 1]) {
    const hip = new THREE.Group(); hip.position.set(-.1, 1.4, s * .85); body.add(hip);
    const thigh = T(new THREE.Mesh(new THREE.CapsuleGeometry(.5, 1.1, 6, 14), skinMat)); thigh.position.y = -.7; thigh.rotation.z = .9; hip.add(thigh);
    const shin = T(new THREE.Mesh(new THREE.CapsuleGeometry(.36, 1.1, 6, 14), darkMat)); shin.position.set(-.9, -1.5, 0); shin.rotation.z = -.5; hip.add(shin);
    const hoof = T(new THREE.Mesh(new THREE.ConeGeometry(.35, .6, 10), hornMat), .03); hoof.position.set(-.55, -2.25, 0); hoof.rotation.z = Math.PI + .4; hip.add(hoof);
  }
  const tail = taperTube(36, 10, skinMat);
  body.add(T(tail.mesh, .03));
  const tailTip = T(new THREE.Mesh(new THREE.ConeGeometry(.35, .9, 4), hornMat), .03); body.add(tailTip);
  const tailCurve = new THREE.CatmullRomCurve3([V(), V(), V(), V(), V(), V()]);

  // tattered wings
  const wings = [-1, 1].map((s) => {
    const pivot = new THREE.Group(); pivot.position.set(-1.0, 2.6, s * 1.0); torso.add(pivot);
    const shape = new THREE.Shape();
    shape.moveTo(0, 0); shape.lineTo(-.5, 3.2); shape.lineTo(-2.2, 4.4); shape.lineTo(-2.4, 3.0); shape.lineTo(-3.5, 3.5); shape.lineTo(-3.4, 2.0); shape.lineTo(-4.6, 2.2); shape.lineTo(-4.0, .9); shape.lineTo(-5.0, .5); shape.lineTo(-2.5, -.2); shape.closePath();
    const membrane = new THREE.Mesh(new THREE.ShapeGeometry(shape, 6), wingMat);
    membrane.rotation.x = s * -Math.PI / 2 + s * .3;
    pivot.add(membrane);
    return { pivot, side: s };
  });

  const moves = new Moves();
  const flashColor = C(0xffffff);
  let flashAmt = 0;

  return {
    root, moves, height: 8.5, radius: 3.2,
    anchor(name) {
      root.updateMatrixWorld(true);
      switch (name) {
        case 'claw': return armR.hand.localToWorld(V(.6, -.9, 0));
        case 'head': return head.getWorldPosition(V());
        case 'hand': return armR.hand.getWorldPosition(V());
        case 'feet': return V(0, 0, 0).applyMatrix4(root.matrixWorld);
        case 'back': return V(-2, 4, 0).applyMatrix4(root.matrixWorld);
        default: return chest.getWorldPosition(V());
      }
    },
    face(target, rate = 1) { turn(root, target, rate); },
    flash(color = 0xffffff, strength = 1) { flashColor.set(color); flashAmt = strength; },
    reset() { moves.clear(); dissolve.value = 0; root.visible = true; },
    update({ time: t, dt }) {
      moves.update(dt);
      const w = moves.w;
      const breathe = Math.sin(t * 1.1);
      body.position.y = Math.sin(t * .8) * .25 - w.die * 2;
      torso.rotation.z = -.35 + breathe * .03 - w.roar * .35 + w.hit * .25 - w.windup * .1 + w.strike * .25 + w.die * .4;
      torso.rotation.y = w.windup * .45 - w.strike * .5;
      torso.scale.setScalar(1 + breathe * .012 + w.roar * .04);
      neck.rotation.z = -w.roar * .5 + w.hit * .3 + Math.sin(t * .6) * .05;
      jaw.rotation.z = -.08 - w.roar * .55 - w.strike * .3 + Math.sin(t * 2.3) * .03;
      const sR = armR.shoulder.rotation, eR = armR.elbow.rotation, sL = armL.shoulder.rotation, eL = armL.elbow.rotation;
      sR.set(-.25, 0, .45 + breathe * .05); eR.set(0, 0, .55);
      sL.set(.25, 0, .4 - breathe * .05); eL.set(0, 0, .6);
      sR.z = lerp(sR.z, -2.5, w.windup); eR.z = lerp(eR.z, 1.3, w.windup); sR.x = lerp(sR.x, -.6, w.windup);
      const strikeU = moves.progress('strike');
      if (strikeU >= 0) { const k = easeOut(strikeU / .45); sR.z = lerp(-2.5, 1.35, k) * w.strike + sR.z * (1 - w.strike); eR.z = lerp(1.3, .1, k) * w.strike + eR.z * (1 - w.strike); }
      sR.x = lerp(sR.x, -1.2, w.roar); sL.x = lerp(sL.x, 1.2, w.roar); sR.z = lerp(sR.z, -.2, w.roar); sL.z = lerp(sL.z, -.2, w.roar);
      sL.z = lerp(sL.z, -.5, w.hit); sR.z = lerp(sR.z, -.4, w.hit);
      wings.forEach(({ pivot, side }) => { pivot.rotation.x = side * (.25 + Math.sin(t * 1.6) * .22 + w.roar * .5 - w.die * .6); pivot.rotation.z = -.2 + Math.sin(t * 1.6 + .5) * .1; });
      // tail
      const sway = Math.sin(t * 1.3);
      tailCurve.points[0].set(-1.0, 1.6, 0); tailCurve.points[1].set(-2.2, 1.0, sway * .4); tailCurve.points[2].set(-3.4, .2, sway * 1.0);
      tailCurve.points[3].set(-4.4, -.4, sway * 1.4 + Math.sin(t * 2) * .3); tailCurve.points[4].set(-5.2, .2, sway * 1.2); tailCurve.points[5].set(-5.6, 1.1, sway * .8);
      tail.build(tailCurve, (u) => .45 * (1 - u) + .05);
      tailTip.position.copy(tailCurve.points[5]); tailTip.rotation.set(sway * .3, 0, .5);
      // runes breathe and blaze with rage
      const glow = .35 + .15 * Math.sin(t * 2.2) + w.roar * 1.1 + w.windup * .6;
      skinMat.emissiveIntensity = glow;
      flashAmt = Math.max(0, flashAmt - dt * 4);
      skinMat.emissive.setRGB(1, .23 + flashAmt * .7, .07 + flashAmt * .9);
      if (flashAmt > 0) skinMat.emissiveIntensity += flashAmt * 3 * (flashColor.r + flashColor.g + flashColor.b) / 3;
      const dieU = moves.progress('die');
      dissolve.value = dieU >= 0 ? clamp(dieU / .85) : 0;
      if (dissolve.value >= .999) root.visible = false;
    },
  };
}
