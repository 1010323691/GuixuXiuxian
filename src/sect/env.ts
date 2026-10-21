// Atmosphere (G02 noon, D09/D10, F05–F07): sky dome, sun/hemisphere light, animated cloud sea, cloud banks
// around the peaks, spirit-spring pools, waterfalls and a light drift of spirit motes. Motion stays slow.
import * as THREE from 'three';
import { FALLS, POOLS } from './layout';
import { rng, V } from './util';

const NOISE = `
  float h21(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float n2(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f*f*(3.-2.*f);
    return mix(mix(h21(i), h21(i+vec2(1,0)), u.x), mix(h21(i+vec2(0,1)), h21(i+vec2(1,1)), u.x), u.y); }
  float fbm(vec2 p){ float v = 0., a = .5; for (int i = 0; i < 5; i++){ v += a*n2(p); p = p*2.03 + 3.1; a *= .5; } return v; }`;

export const SUN_DIR = V(-.42, .74, .52).normalize();          // late-morning sun from the south-west
export const FOG = new THREE.Color(0xd3e3ec);

export interface Atmosphere { group: THREE.Group; sun: THREE.DirectionalLight; update(t: number, camera: THREE.Camera): void; uniforms: { time: { value: number } }[] }

export function buildAtmosphere(scene: THREE.Scene, quality: number, reduced: boolean): Atmosphere {
  const group = new THREE.Group();
  group.name = 'atmosphere';
  const time = { value: 0 };
  const uniforms = [{ time }];

  scene.fog = new THREE.Fog(FOG, 700, 3200);
  const sky = new THREE.Mesh(new THREE.SphereGeometry(4000, 32, 16), new THREE.ShaderMaterial({
    uniforms: { time, dir: { value: SUN_DIR } },
    vertexShader: 'varying vec3 d; void main(){ d = position; vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.); gl_Position = p.xyww; }',
    fragmentShader: `uniform float time; uniform vec3 dir; varying vec3 d; ${NOISE}
      void main(){ vec3 v = normalize(d); float h = v.y;
        vec3 zen = vec3(.30,.55,.84), hor = vec3(.84,.91,.95);
        vec3 c = mix(hor, zen, pow(smoothstep(-.02, .7, h), .75));
        vec2 q = v.xz / max(h, .06) * .7 + vec2(time * .003, 0.);
        float cl = smoothstep(.5, .82, fbm(q * vec2(1., 2.4))) * smoothstep(.02, .3, h);
        c = mix(c, vec3(1.), cl * .55);
        float s = max(dot(v, dir), 0.); c += vec3(1., .95, .85) * (pow(s, 900.) * 6. + pow(s, 40.) * .22);
        gl_FragColor = vec4(c, 1.); }`,
    side: THREE.BackSide, depthWrite: false, fog: false,
  }));
  sky.renderOrder = -10;
  sky.frustumCulled = false;
  group.add(sky);

  const hemi = new THREE.HemisphereLight(0xe4f1ff, 0x55605a, 1.25);
  const sun = new THREE.DirectionalLight(0xfff3df, 2.6);
  sun.position.copy(SUN_DIR).multiplyScalar(700);
  sun.target.position.set(0, 100, -40);
  if (quality > 0) {
    sun.castShadow = true;
    const size = quality > 1 ? 4096 : 2048;
    sun.shadow.mapSize.set(size, size);
    const c = sun.shadow.camera;
    c.left = -430; c.right = 430; c.top = 430; c.bottom = -430; c.near = 100; c.far = 1500;
    sun.shadow.bias = -.0006;
    sun.shadow.normalBias = .6;
  }
  group.add(hemi, sun, sun.target);

  // Cloud sea (D09 low dense layer): large plane with scrolling fbm, opaque-ish below the peaks.
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(7000, 7000, 1, 1).rotateX(-Math.PI / 2), new THREE.ShaderMaterial({
    uniforms: { time, fogColor: { value: FOG } },
    vertexShader: 'varying vec3 w; void main(){ vec4 p = modelMatrix * vec4(position,1.); w = p.xyz; gl_Position = projectionMatrix * viewMatrix * p; }',
    fragmentShader: `uniform float time; uniform vec3 fogColor; varying vec3 w; ${NOISE}
      void main(){ vec2 q = w.xz * .004 + vec2(time * .006, time * .002);
        float n = fbm(q) * .65 + fbm(q * 3.1 - time * .004) * .35;
        float lit = smoothstep(.3, .8, n);
        vec3 c = mix(vec3(.62,.7,.79), vec3(.99,1.,1.), lit);
        float dist = length(w.xz) / 3400.;
        c = mix(c, fogColor, smoothstep(.15, 1., dist));
        gl_FragColor = vec4(c, .97); }`,
    transparent: true, depthWrite: false, fog: false,
  }));
  sea.position.y = 2;
  sea.renderOrder = 2;
  group.add(sea);

  // Cloud banks hugging the cliffs (soft billboards, depth-tested, no depth write).
  const puffTex = (() => {
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d')!, q = rng(3);
    for (let i = 0; i < 9; i++) {
      const x = 30 + q.next() * 68, y = 40 + q.next() * 40, r = 22 + q.next() * 26;
      const grad = g.createRadialGradient(x, y, 0, x, y, r);
      grad.addColorStop(0, 'rgba(255,255,255,.9)'); grad.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = grad; g.fillRect(0, 0, 128, 128);
    }
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  })();
  const puffMat = new THREE.SpriteMaterial({ map: puffTex, color: 0xffffff, transparent: true, opacity: .85, depthWrite: false, fog: true });
  const r = rng(19);
  const banks = quality > 1 ? 110 : 60;
  const puffs: THREE.Sprite[] = [];
  for (let i = 0; i < banks; i++) {
    const a = r.next() * Math.PI * 2, d = 60 + r.next() * 520;
    const s = new THREE.Sprite(puffMat);
    s.position.set(Math.cos(a) * d * 1.15, 10 + r.next() * 34, Math.sin(a) * d - 20);
    const k = 60 + r.next() * 120;
    s.scale.set(k * 1.8, k * .7, 1);
    s.userData.drift = (r.next() - .5) * 2;
    s.renderOrder = 3;
    puffs.push(s);
    group.add(s);
  }

  // Spirit springs (C09/F07): glowing water with a slow caustic shimmer.
  const water = new THREE.ShaderMaterial({
    uniforms: { time },
    vertexShader: 'varying vec2 vUv; varying vec3 w; void main(){ vUv = uv; vec4 p = modelMatrix * vec4(position,1.); w = p.xyz; gl_Position = projectionMatrix * viewMatrix * p; }',
    fragmentShader: `uniform float time; varying vec2 vUv; varying vec3 w; ${NOISE}
      void main(){ float n = fbm(w.xz * .18 + vec2(time * .25, -time * .18));
        float caus = smoothstep(.55, .75, n);
        vec3 c = mix(vec3(.12,.56,.58), vec3(.55,.95,.92), caus);
        float edge = smoothstep(0., .12, min(min(vUv.x, 1.-vUv.x), min(vUv.y, 1.-vUv.y)));
        gl_FragColor = vec4(mix(vec3(.85,.96,.93), c, edge), .92); }`,
    transparent: true,
  });
  for (const p of POOLS) {
    const rim = new THREE.Mesh(new THREE.BoxGeometry(p.w + 2, 1.2, p.d + 2), new THREE.MeshStandardMaterial({ color: 0xe6e2d6, roughness: .6 }));
    rim.position.set(p.x, p.y + .3, p.z);
    rim.receiveShadow = true;
    const surf = new THREE.Mesh(new THREE.PlaneGeometry(p.w, p.d).rotateX(-Math.PI / 2), water);
    surf.position.set(p.x, p.y + .95, p.z);
    group.add(rim, surf);
  }

  // Waterfalls (D08): scrolling streaks on a slightly curved ribbon plus a mist puff at the bottom.
  const fallMat = new THREE.ShaderMaterial({
    uniforms: { time },
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.); }',
    fragmentShader: `uniform float time; varying vec2 vUv; ${NOISE}
      void main(){ float streak = n2(vec2(vUv.x * 18., vUv.y * 3. + time * 1.6)) * .6 + n2(vec2(vUv.x * 40., vUv.y * 6. + time * 2.4)) * .4;
        float side = smoothstep(0., .25, vUv.x) * smoothstep(1., .75, vUv.x);
        float a = side * (.55 + streak * .45) * smoothstep(0., .08, vUv.y);
        gl_FragColor = vec4(mix(vec3(.78,.9,.94), vec3(1.), streak), a * .92); }`,
    transparent: true, depthWrite: false, side: THREE.DoubleSide,
  });
  for (const f of FALLS) {
    const geo = new THREE.PlaneGeometry(f.w, f.h, 1, 12);
    const pos = geo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) { const t = (f.h / 2 - pos.getY(i)) / f.h; pos.setZ(i, Math.sqrt(t) * 10 + t * 6); }
    geo.computeVertexNormals();
    const m = new THREE.Mesh(geo, fallMat);
    m.position.set(f.x, f.top - f.h / 2, f.z);
    m.rotation.y = -f.dir + Math.PI / 2;
    m.renderOrder = 4;
    group.add(m);
    const mist = new THREE.Sprite(puffMat);
    mist.position.set(f.x + Math.cos(f.dir) * 16, Math.max(12, f.top - f.h + 10), f.z + Math.sin(f.dir) * 16);
    mist.scale.set(46, 24, 1);
    group.add(mist);
  }

  // Spirit motes (F05): a few hundred additive points spiralling slowly over the terraces.
  const count = reduced ? 0 : quality > 1 ? 420 : 200;
  const mp = new Float32Array(count * 3), seeds = new Float32Array(count);
  for (let i = 0; i < count; i++) { mp[i * 3] = (r.next() - .5) * 520; mp[i * 3 + 1] = 90 + r.next() * 170; mp[i * 3 + 2] = (r.next() - .5) * 600 - 60; seeds[i] = r.next() * 100; }
  const mg = new THREE.BufferGeometry();
  mg.setAttribute('position', new THREE.BufferAttribute(mp, 3));
  mg.setAttribute('seed', new THREE.BufferAttribute(seeds, 1));
  const motes = new THREE.Points(mg, new THREE.ShaderMaterial({
    uniforms: { time },
    vertexShader: `uniform float time; attribute float seed; varying float a;
      void main(){ vec3 p = position; float t = time * .15 + seed;
        p += vec3(sin(t) * 6., mod(time * 2. + seed * 7., 40.), cos(t * 1.3) * 6.);
        a = sin(mod(time * 2. + seed * 7., 40.) / 40. * 3.14159);
        vec4 mv = modelViewMatrix * vec4(p, 1.); gl_PointSize = clamp(900. / -mv.z, 1.5, 6.); gl_Position = projectionMatrix * mv; }`,
    fragmentShader: 'varying float a; void main(){ float d = length(gl_PointCoord - .5); gl_FragColor = vec4(.75,1.,.95, smoothstep(.5,.1,d) * a * .8); }',
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  }));
  motes.frustumCulled = false;
  if (count) group.add(motes);

  scene.add(group);
  return {
    group, sun, uniforms,
    update(t) {
      time.value = t;
      for (const s of puffs) s.position.x += s.userData.drift * .016;
    },
  };
}
