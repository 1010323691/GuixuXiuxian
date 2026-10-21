// Painted characters from the owner's concept sheets (assets/char_protagonist_turnaround_v001,
// assets/mon_amethyst_winged_lion_king_sheet_v001; cut by scripts/cutout_turnaround.py into static/art/).
// Each character is a 2.5D card that switches front/side/back by camera angle; the hero's sheet also
// supplies the painted sword, talisman, glyph circle and jade pendant used by the effects.
import * as THREE from 'three';
import { Moves, type Actor } from './actors';
import { Ribbon } from './cloth';
import { C, V, clamp, softDot, toon } from './util';

type Px = [number, number];
/** Native pixel sizes of the cut-outs, so geometry is right before the images load. */
const SIZES = {
  hero: { front: [331, 624], side: [248, 620], back: [275, 623], sword: [115, 393], talisman: [102, 162], circle: [187, 169], jade: [69, 165] },
  lion: { front: [348, 415], side: [523, 445], back: [242, 408], sigil: [117, 94] },
} satisfies Record<string, Record<string, Px>>;

function loadTextures<K extends string>(base: string, names: readonly K[]) {
  const loader = new THREE.TextureLoader();
  const out = {} as Record<K, THREE.Texture>;
  for (const name of names) {
    const tex = loader.load(base + name + '.png');
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    out[name] = tex;
  }
  return out;
}

export type ArtSet = Record<keyof typeof SIZES.hero, THREE.Texture> & { aspect: Record<string, number> };
export type LionArt = Record<keyof typeof SIZES.lion, THREE.Texture>;

export function loadArt(base = '/art/hero/'): ArtSet {
  const aspect = Object.fromEntries(Object.entries(SIZES.hero).map(([k, [w, h]]) => [k, w / h]));
  return { ...loadTextures(base, Object.keys(SIZES.hero) as (keyof typeof SIZES.hero)[]), aspect };
}
export function loadLionArt(base = '/art/lion/'): LionArt { return loadTextures(base, Object.keys(SIZES.lion) as (keyof typeof SIZES.lion)[]); }
export function disposeTextures(set: object) { for (const v of Object.values(set)) if (v instanceof THREE.Texture) v.dispose(); }

let glowTex: THREE.Texture | null = null;

/** The painted sword as two crossed cards along +x (tip at +x), readable from any angle. */
export function artSword(art: ArtSet, glow: THREE.ColorRepresentation, length = 2.4) {
  const g = new THREE.Group();
  const width = length * art.aspect.sword;
  const geo = new THREE.PlaneGeometry(length, width);
  // the image is vertical with the hilt on top: map image v (top→bottom) onto x (−→+)
  const uv = geo.attributes.uv as THREE.BufferAttribute, pos = geo.attributes.position as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, pos.getY(i) / width + .5, .5 - pos.getX(i) / length);
  const mat = new THREE.MeshBasicMaterial({ map: art.sword, transparent: true, depthWrite: false, side: THREE.DoubleSide, color: C(0xffffff).multiplyScalar(1.35) });
  const a = new THREE.Mesh(geo, mat), b = new THREE.Mesh(geo, mat);
  b.rotation.x = Math.PI / 2;
  g.add(a, b);
  const light = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex ??= softDot(), color: C(glow).multiplyScalar(1.8), transparent: true, opacity: .55, blending: THREE.AdditiveBlending, depthWrite: false }));
  light.scale.set(length * 1.3, width * 1.2, 1);
  g.add(light);
  return g;
}

// ------------------------------------------------------------------ the painted card
type View = 'front' | 'side' | 'back';

/**
 * An upright, camera-facing card that shows the painted view matching where the camera stands relative to
 * the character's facing (+x local). All views share one world scale (units per sheet pixel) and stand on
 * the card's bottom edge, so switching views never changes the character's size. The side view in the
 * sheets faces screen-left and is mirrored when the character faces screen-right.
 */
class PaintedCard {
  readonly billboard = new THREE.Group();
  readonly card: THREE.Mesh;
  readonly u;
  private shown: View = 'front';
  private flipShown = 0;
  private fade = 1;
  private fwd = V(); private toCam = V(); private camRight = V();
  screenSide = 1;

  constructor(private views: Record<View, THREE.Texture>, private px: Record<View, Px>, unitsPerPx: number, glow: THREE.ColorRepresentation, opts: { flap?: number } = {}) {
    const maxW = Math.max(px.front[0], px.side[0], px.back[0]), maxH = Math.max(px.front[1], px.side[1], px.back[1]);
    const geo = new THREE.PlaneGeometry(maxW * unitsPerPx, maxH * unitsPerPx, 10, 18).translate(0, maxH * unitsPerPx / 2, 0);
    this.u = {
      mapA: { value: views.front }, mapB: { value: views.front }, sizeA: { value: new THREE.Vector2(...px.front) }, sizeB: { value: new THREE.Vector2(...px.front) },
      flipA: { value: 0 }, flipB: { value: 0 }, mixAB: { value: 0 }, plane: { value: new THREE.Vector2(maxW, maxH) },
      time: { value: 0 }, sway: { value: 1 }, lean: { value: 0 }, flap: { value: opts.flap ?? 0 },
      flash: { value: 0 }, flashColor: { value: C(0xffffff) }, glow: { value: 0 }, glowColor: { value: C(glow) },
      burn: { value: 0 }, burnColor: { value: C(glow).multiplyScalar(2.6) },
      fogColor: { value: C(0xffffff) }, fogDensity: { value: 0 },
    };
    const mat = new THREE.ShaderMaterial({
      uniforms: this.u, transparent: true, depthWrite: false, side: THREE.DoubleSide,
      vertexShader: `uniform float time, sway, lean, flap; varying vec2 vUv; varying float vDepth;
        void main(){ vUv = uv; vec3 p = position;
          float k = pow(1. - uv.y, 2.2);             // hems and tails move most
          p.x += (sin(time * 2.6 + uv.y * 6.) * .07 + sin(time * 4.1 + uv.y * 11.) * .025) * k * sway + lean * k;
          float wing = smoothstep(.35, .95, uv.y) * smoothstep(.12, .5, abs(uv.x - .5));   // outer upper area: wings
          p.x *= 1. + flap * sin(time * 2.2) * wing; p.y += flap * cos(time * 2.2) * wing * 1.2;
          vec4 mv = modelViewMatrix * vec4(p, 1.); vDepth = -mv.z; gl_Position = projectionMatrix * mv; }`,
      fragmentShader: `uniform sampler2D mapA, mapB; uniform vec2 sizeA, sizeB, plane; uniform float flipA, flipB, mixAB, flash, glow, burn, fogDensity;
        uniform vec3 flashColor, glowColor, burnColor, fogColor; varying vec2 vUv; varying float vDepth;
        vec4 sampleView(sampler2D m, vec2 size, float flip){
          vec2 q = vec2((vUv.x - .5) * plane.x / size.x + .5, vUv.y * plane.y / size.y);
          if (flip > .5) q.x = 1. - q.x;
          if (q.x < 0. || q.x > 1. || q.y > 1.) return vec4(0.);
          return texture2D(m, q); }
        float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        float n(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f*f*(3.-2.*f); return mix(mix(h(i),h(i+vec2(1,0)),u.x), mix(h(i+vec2(0,1)),h(i+vec2(1,1)),u.x), u.y); }
        void main(){
          vec4 c = mix(sampleView(mapA, sizeA, flipA), sampleView(mapB, sizeB, flipB), mixAB);
          float edge = 0.;
          if (burn > 0.) { float z = n(vUv * 9.) * .65 + n(vUv * 31.) * .35 + (1. - vUv.y) * .25; if (z < burn * 1.3) discard; edge = smoothstep(.12, 0., z - burn * 1.3); }
          if (c.a < .01) discard;
          c.rgb = mix(c.rgb, flashColor, flash * .55) + glowColor * glow * (.25 + .75 * (1. - c.a)) + burnColor * edge;
          float f = 1. - exp(-fogDensity * fogDensity * vDepth * vDepth);
          gl_FragColor = vec4(mix(c.rgb, fogColor, f), c.a); }`,
    });
    this.card = new THREE.Mesh(geo, mat);
    this.card.renderOrder = 2;
    this.billboard.add(this.card);
  }

  update(root: THREE.Object3D, camera: THREE.Camera, dt: number, t: number) {
    const u = this.u;
    this.fwd.set(1, 0, 0).applyQuaternion(root.quaternion).setY(0).normalize();
    this.toCam.subVectors(camera.position, root.position).setY(0).normalize();
    this.camRight.crossVectors(this.toCam, V(0, 1, 0)).negate();
    const c = this.fwd.dot(this.toCam);
    const want: View = c > .68 ? 'front' : c < -.68 ? 'back' : 'side'; // ~47° cones: side reads best for profile shots
    const flip = want === 'side' && this.fwd.dot(this.camRight) > 0 ? 1 : 0;
    if (want !== this.shown || flip !== this.flipShown) {
      const keepB = u.mixAB.value > .5;
      u.mapA.value = keepB ? u.mapB.value : u.mapA.value; u.sizeA.value.copy(keepB ? u.sizeB.value : u.sizeA.value); u.flipA.value = keepB ? u.flipB.value : u.flipA.value;
      u.mapB.value = this.views[want]; u.sizeB.value.set(...this.px[want]); u.flipB.value = flip;
      this.fade = 0; this.shown = want; this.flipShown = flip;
    }
    this.fade = Math.min(1, this.fade + dt / .22);
    u.mixAB.value = this.fade;
    this.billboard.rotation.y = Math.atan2(this.toCam.x, this.toCam.z) - root.rotation.y;
    this.screenSide = Math.sign(this.fwd.dot(this.camRight)) || 1;
    u.time.value = t;
    const fog = (root.parent as THREE.Scene | null)?.fog as THREE.FogExp2 | undefined;
    if (fog) { u.fogColor.value.copy(fog.color); u.fogDensity.value = fog.density; }
  }
}

// ------------------------------------------------------------------ hero
export function makeArtCultivator(art: ArtSet, skill: THREE.ColorRepresentation = 0x5fd0ff): Actor {
  const root = new THREE.Group();
  const px = SIZES.hero as Record<View, Px>;
  const painted = new PaintedCard({ front: art.front, side: art.side, back: art.back }, px, 3.0 / 624, skill);
  const { billboard, card, u: uniforms } = painted;
  billboard.position.y = -1.48;
  root.add(billboard);

  const mount = artSword(art, skill, 2.9);
  mount.position.set(.1, -1.52, 0);
  root.add(mount);
  const mountGlow = new THREE.PointLight(C(skill), 3, 6, 2); mountGlow.position.set(0, -1.4, 0); root.add(mountGlow);

  // a few live ribbons keep the painted figure breathing: shawl ends and waist tassels
  const clothRoot = new THREE.Group();
  const shawlMat = toon(0xc7e6fb, { side: THREE.DoubleSide, transparent: true, opacity: .55, rim: 0xffffff });
  const sashMat = toon(0x4f86d0, { side: THREE.DoubleSide, transparent: true, opacity: .8, rim: 0xd8ecff });
  const strands = [
    { ribbon: new Ribbon({ segments: 24, length: .14, width: .12, taper: .5, gravity: .5, flutter: 3 }, shawlMat), at: V(-.05, .55, .42) },
    { ribbon: new Ribbon({ segments: 24, length: .14, width: .12, taper: .5, gravity: .5, flutter: 3 }, shawlMat), at: V(-.05, .55, -.42) },
    { ribbon: new Ribbon({ segments: 14, length: .12, width: .06, taper: .6, gravity: 1.2, flutter: 2.4 }, sashMat), at: V(-.05, -.05, .2) },
    { ribbon: new Ribbon({ segments: 14, length: .12, width: .06, taper: .6, gravity: 1.2, flutter: 2.4 }, sashMat), at: V(-.05, -.05, -.2) },
  ];
  strands.forEach((s) => clothRoot.add(s.ribbon.mesh));

  const moves = new Moves();
  let flashAmt = 0, attached = false;
  const lastPos = V(), velocity = V(), wind = V(), tmp = V(), side = V();
  const local = (x: number, y: number, z: number) => { root.updateMatrixWorld(); return V(x, y, z).applyMatrix4(root.matrixWorld); };

  return {
    root, moves, height: 2.9, radius: .8,
    anchor(name) {
      switch (name) {
        case 'hand': return local(.6, .55, .25);
        case 'head': return local(0, 1.3, 0);
        case 'feet': return local(0, -1.5, 0);
        case 'back': return local(-.8, .9, 0);
        default: return local(0, .45, 0);
      }
    },
    face(target, rate = 1) { faceToward(root, target, rate); },
    flash(color = 0xffffff, strength = 1) { uniforms.flashColor.value.set(color); flashAmt = strength; },
    reset() { moves.clear(); strands.forEach((s) => s.ribbon.invalidate()); attached = false; },
    update({ camera, time: t, dt, wind: baseWind }) {
      if (!attached && root.parent) { root.parent.add(clothRoot); attached = true; }
      moves.update(dt);
      const w = moves.w;
      velocity.subVectors(root.position, lastPos).divideScalar(Math.max(dt, 1e-3));
      if (velocity.length() > 60) velocity.set(0, 0, 0);
      lastPos.copy(root.position);
      painted.update(root, camera, dt, t);
      // screen-space lean: forward on dash, back on recoil/hit, toward the foe's side of the frame
      const lean = (w.dash * .32 + w.thrust * .14 - w.recoil * .3 - w.hit * .22) * painted.screenSide;
      card.rotation.z = -lean * .5;
      uniforms.lean.value = -lean * .6 - clamp(velocity.length() / 30) * .25 * painted.screenSide;
      billboard.position.y = -1.48 + Math.sin(t * 1.6) * .05 + w.rise * .3;
      card.scale.set(1 + w.hit * .03, 1 - w.hit * .04 + w.charge * .02, 1);
      uniforms.sway.value = 1 + clamp(velocity.length() / 20) * 1.5 + w.dash;
      uniforms.glow.value = w.charge * .9 + w.cast * .35 + w.rise * .6;
      flashAmt = Math.max(0, flashAmt - dt * 4);
      uniforms.flash.value = flashAmt;
      mount.rotation.y = Math.sin(t * 1.2) * .03 + w.dash * .1;
      mountGlow.intensity = 3 + w.charge * 6 + w.dash * 4;

      root.updateMatrixWorld(true);
      wind.copy(baseWind).addScaledVector(velocity, -.9);
      side.set(0, 0, 1).transformDirection(root.matrixWorld);
      for (const s of strands) s.ribbon.step(tmp.copy(s.at).applyMatrix4(root.matrixWorld), side, wind, dt, t, camera);
    },
  };
}

function faceToward(root: THREE.Object3D, target: THREE.Vector3, rate: number) {
  const want = Math.atan2(-(target.z - root.position.z), target.x - root.position.x);
  let d = want - root.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d));
  root.rotation.y += d * Math.min(1, rate);
}

// ------------------------------------------------------------------ 紫晶翼狮王 (amethyst winged lion king)
/** Sheet scale: the lion stands ~6–8 m with wings against a 1.8 m cultivator, i.e. about 2.6× the hero card. */
const LION_UNITS_PER_PX = 7.6 / 415;
export const LION_COLOR = 0xb27cff;

export function makeArtLion(lion: LionArt): Actor {
  const root = new THREE.Group();
  const painted = new PaintedCard({ front: lion.front, side: lion.side, back: lion.back }, SIZES.lion as Record<View, Px>, LION_UNITS_PER_PX, LION_COLOR, { flap: .05 });
  const { billboard, card, u } = painted;
  billboard.position.y = -.6;
  root.add(billboard);
  // the 灵气凝聚 sigil turns beneath it while it hovers
  const sigilMat = new THREE.MeshBasicMaterial({ map: lion.sigil, color: C(0xffffff).multiplyScalar(1.6), transparent: true, opacity: .55, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
  const sigil = new THREE.Mesh(new THREE.PlaneGeometry(7, 7 * 94 / 117), sigilMat);
  sigil.rotation.x = -Math.PI / 2; sigil.position.y = -.8;
  root.add(sigil);
  const aura = new THREE.PointLight(C(LION_COLOR), 6, 18, 2); aura.position.set(0, 3.5, 0); root.add(aura);

  const moves = new Moves();
  let flashAmt = 0;
  const local = (x: number, y: number, z: number) => { root.updateMatrixWorld(); return V(x, y, z).applyMatrix4(root.matrixWorld); };

  return {
    root, moves, height: 7.6, radius: 3.2,
    anchor(name) {
      switch (name) {
        case 'claw': return local(2.4, .4, .4);
        case 'head': return local(1.8, 4.6, 0);
        case 'hand': return local(2.2, .9, 0);
        case 'feet': return local(0, -.6, 0);
        case 'back': return local(-1.5, 5, 0);
        default: return local(.9, 3.2, 0);
      }
    },
    face(target, rate = 1) { faceToward(root, target, rate); },
    flash(color = 0xffffff, strength = 1) { u.flashColor.value.set(color); flashAmt = strength; },
    reset() { moves.clear(); u.burn.value = 0; root.visible = true; sigil.visible = true; },
    update({ camera, time: t, dt }) {
      moves.update(dt);
      const w = moves.w;
      painted.update(root, camera, dt, t);
      const side = painted.screenSide;
      // hover and breathe; rear back on the roar and wind-up, drive in on the strike
      billboard.position.y = -.6 + Math.sin(t * .9) * .3 + w.roar * .4 - w.die * 1.5;
      card.rotation.z = (w.windup * .14 + w.roar * .08 - w.strike * .2 + w.hit * .1) * side;
      const swell = 1 + w.roar * .06 + Math.sin(t * 1.1) * .008;
      card.scale.set(swell * (1 + w.strike * .05), swell, 1);
      u.lean.value = (-w.strike * .5 + w.hit * .3) * side;
      u.flap.value = .05 + w.roar * .06 + w.windup * .04;
      u.sway.value = 1.2;
      u.glow.value = .12 + w.roar * .6 + w.windup * .45 + .05 * Math.sin(t * 2.2);
      flashAmt = Math.max(0, flashAmt - dt * 4);
      u.flash.value = flashAmt;
      aura.intensity = 6 + w.roar * 18 + w.windup * 10;
      sigil.rotation.z += dt * (.3 + w.roar * 2 + w.windup * 1.5);
      sigilMat.opacity = .45 + w.roar * .5 + w.windup * .4;
      sigil.scale.setScalar(1 + w.roar * .25);
      const dieU = moves.progress('die');
      u.burn.value = dieU >= 0 ? clamp(dieU / .8) : 0;
      sigil.visible = u.burn.value < .3;
      if (u.burn.value >= .999) root.visible = false;
    },
  };
}
