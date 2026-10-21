// Painted assets from the protagonist turnaround sheet (assets/…turnaround_v001): the hero as a 2.5D
// billboard that switches front/side/back by camera angle, plus the painted sword, talisman, glyph circle
// and jade pendant used by the effects. Same-origin PNGs under /art/hero/.
import * as THREE from 'three';
import { Moves, type Actor } from './actors';
import { Ribbon } from './cloth';
import { C, V, clamp, softDot, toon } from './util';

export interface ArtSet { front: THREE.Texture; side: THREE.Texture; back: THREE.Texture; sword: THREE.Texture; talisman: THREE.Texture; circle: THREE.Texture; jade: THREE.Texture; aspect: Record<string, number> }

/** Native pixel sizes of the cut-outs (width / height), so geometry matches before the images load. */
const ASPECT: Record<string, number> = { front: 331 / 624, side: 248 / 620, back: 275 / 623, sword: 115 / 393, talisman: 102 / 162, circle: 187 / 169, jade: 69 / 165 };

export function loadArt(base = '/art/hero/'): ArtSet {
  const loader = new THREE.TextureLoader();
  const load = (name: string) => {
    const tex = loader.load(base + name + '.png');
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    return tex;
  };
  return { front: load('front'), side: load('side'), back: load('back'), sword: load('sword'), talisman: load('talisman'), circle: load('circle'), jade: load('jade'), aspect: ASPECT };
}

let glowTex: THREE.Texture | null = null;

/** The painted sword as two crossed cards along +x (tip at +x), readable from any angle. */
export function artSword(art: ArtSet, glow: THREE.ColorRepresentation, length = 2.4) {
  const g = new THREE.Group();
  const width = length * ASPECT.sword;
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

// ------------------------------------------------------------------ 2.5D hero
const VIEWS = ['front', 'side', 'back'] as const;
type View = typeof VIEWS[number];

export function makeArtCultivator(art: ArtSet, skill: THREE.ColorRepresentation = 0x5fd0ff): Actor {
  const root = new THREE.Group();
  const H = 3.0, planeAspect = Math.max(ASPECT.front, ASPECT.side, ASPECT.back);
  const geo = new THREE.PlaneGeometry(H * planeAspect, H, 8, 16).translate(0, H / 2, 0);
  const uniforms = {
    mapA: { value: art.front }, mapB: { value: art.front }, aspA: { value: ASPECT.front }, aspB: { value: ASPECT.front },
    flipA: { value: 0 }, flipB: { value: 0 }, mixAB: { value: 0 }, planeAsp: { value: planeAspect },
    time: { value: 0 }, sway: { value: 1 }, lean: { value: 0 },
    flash: { value: 0 }, flashColor: { value: C(0xffffff) }, glow: { value: 0 }, glowColor: { value: C(skill) },
    fogColor: { value: C(0xffffff) }, fogDensity: { value: 0 },
  };
  const mat = new THREE.ShaderMaterial({
    uniforms, transparent: true, depthWrite: false, side: THREE.DoubleSide,
    vertexShader: `uniform float time, sway, lean; varying vec2 vUv; varying float vDepth;
      void main(){ vUv = uv; vec3 p = position;
        float k = pow(1. - uv.y, 2.2);             // robe hem moves most, shoulders least
        p.x += (sin(time * 2.6 + uv.y * 6.) * .07 + sin(time * 4.1 + uv.y * 11.) * .025) * k * sway + lean * k;
        vec4 mv = modelViewMatrix * vec4(p, 1.); vDepth = -mv.z; gl_Position = projectionMatrix * mv; }`,
    fragmentShader: `uniform sampler2D mapA, mapB; uniform float aspA, aspB, flipA, flipB, mixAB, planeAsp, flash, glow, fogDensity;
      uniform vec3 flashColor, glowColor, fogColor; varying vec2 vUv; varying float vDepth;
      vec4 sampleView(sampler2D m, float asp, float flip){ float x = (vUv.x - .5) * planeAsp / asp + .5; if (flip > .5) x = 1. - x;
        if (x < 0. || x > 1.) return vec4(0.); return texture2D(m, vec2(x, vUv.y)); }
      void main(){ vec4 c = mix(sampleView(mapA, aspA, flipA), sampleView(mapB, aspB, flipB), mixAB);
        if (c.a < .01) discard;
        c.rgb = mix(c.rgb, flashColor, flash * .55) + glowColor * glow * (.25 + .75 * (1. - c.a));
        float f = 1. - exp(-fogDensity * fogDensity * vDepth * vDepth);
        gl_FragColor = vec4(mix(c.rgb, fogColor, f), c.a); }`,
  });
  const card = new THREE.Mesh(geo, mat);
  card.renderOrder = 2;
  const billboard = new THREE.Group();
  billboard.position.y = -1.48;
  billboard.add(card);
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
  let shown: View = 'front', flashAmt = 0, attached = false, fade = 1;
  let flipShown = 0;
  const fwd = V(), toCam = V(), camRight = V(), lastPos = V(), velocity = V(), wind = V(), tmp = V(), side = V();
  const up = V(0, 1, 0);

  const forward = () => fwd.set(1, 0, 0).applyQuaternion(root.quaternion).setY(0).normalize();
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
    face(target, rate = 1) {
      const want = Math.atan2(-(target.z - root.position.z), target.x - root.position.x);
      let d = want - root.rotation.y; d = Math.atan2(Math.sin(d), Math.cos(d));
      root.rotation.y += d * Math.min(1, rate);
    },
    flash(color = 0xffffff, strength = 1) { uniforms.flashColor.value.set(color); flashAmt = strength; },
    reset() { moves.clear(); strands.forEach((s) => s.ribbon.invalidate()); attached = false; },
    update({ camera, time: t, dt, wind: baseWind }) {
      if (!attached && root.parent) { root.parent.add(clothRoot); attached = true; }
      moves.update(dt);
      const w = moves.w;
      velocity.subVectors(root.position, lastPos).divideScalar(Math.max(dt, 1e-3));
      if (velocity.length() > 60) velocity.set(0, 0, 0);
      lastPos.copy(root.position);

      // pick the painted view from where the camera stands relative to the hero's facing
      forward();
      toCam.subVectors(camera.position, root.position).setY(0).normalize();
      camRight.crossVectors(toCam, up).negate(); // camera's screen-right on the ground plane
      const c = fwd.dot(toCam);
      const want: View = c > .5 ? 'front' : c < -.45 ? 'back' : 'side';
      const flip = want === 'side' && fwd.dot(camRight) > 0 ? 1 : 0; // the painted side view faces screen-left
      if (want !== shown || flip !== flipShown) {
        uniforms.mapA.value = uniforms.mixAB.value > .5 ? uniforms.mapB.value : uniforms.mapA.value;
        uniforms.aspA.value = uniforms.mixAB.value > .5 ? uniforms.aspB.value : uniforms.aspA.value;
        uniforms.flipA.value = uniforms.mixAB.value > .5 ? uniforms.flipB.value : uniforms.flipA.value;
        uniforms.mapB.value = art[want]; uniforms.aspB.value = ASPECT[want]; uniforms.flipB.value = flip;
        uniforms.mixAB.value = 0; fade = 0; shown = want; flipShown = flip;
      }
      fade = Math.min(1, fade + dt / .22);
      uniforms.mixAB.value = fade;

      // the card always stands upright and turns to the camera
      billboard.rotation.y = Math.atan2(toCam.x, toCam.z) - root.rotation.y;
      // screen-space lean: forward on dash, back on recoil/hit, toward the foe's side of the frame
      const screenSide = Math.sign(fwd.dot(camRight)) || 1;
      const lean = (w.dash * .32 + w.thrust * .14 - w.recoil * .3 - w.hit * .22) * screenSide;
      card.rotation.z = -lean * .5;
      uniforms.lean.value = -lean * .6 - clamp(velocity.length() / 30) * .25 * screenSide;
      billboard.position.y = -1.48 + Math.sin(t * 1.6) * .05 + w.rise * .3;
      card.scale.set(1 + w.hit * .03, 1 - w.hit * .04 + w.charge * .02, 1);
      uniforms.time.value = t;
      uniforms.sway.value = 1 + clamp(velocity.length() / 20) * 1.5 + w.dash;
      uniforms.glow.value = w.charge * .9 + w.cast * .35 + w.rise * .6;
      flashAmt = Math.max(0, flashAmt - dt * 4);
      uniforms.flash.value = flashAmt;
      const fog = (root.parent as THREE.Scene | null)?.fog as THREE.FogExp2 | undefined;
      if (fog) { uniforms.fogColor.value.copy(fog.color); uniforms.fogDensity.value = fog.density; }
      mount.rotation.y = Math.sin(t * 1.2) * .03 + w.dash * .1;
      mountGlow.intensity = 3 + w.charge * 6 + w.dash * 4;

      root.updateMatrixWorld(true);
      wind.copy(baseWind).addScaledVector(velocity, -.9);
      side.set(0, 0, 1).transformDirection(root.matrixWorld);
      for (const s of strands) s.ribbon.step(tmp.copy(s.at).applyMatrix4(root.matrixWorld), side, wind, dt, t, camera);
    },
  };
}
