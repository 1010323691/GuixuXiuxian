// 青玄剑宗 rotatable 3D sect hub. createSect() builds the procedural sect into a host element and returns a
// controller; it never talks to the server: the page passes clicks on buildings back out via onSelect and the
// game's own UI opens the matching page. Mountains, buildings, vegetation, water/clouds and effects are kept in
// separate groups so each can be budgeted, toggled and disposed on its own.
import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { BlendFunction, EffectComposer, EffectPass, KernelSize, OutlineEffect, RenderPass, SMAAEffect, ToneMappingEffect, ToneMappingMode } from 'postprocessing';
import { caveEntrance, gate, hall, hexPavilion, mainHall, marketPavilion, portal, scripturePavilion, stele, swordPlatform } from './buildings';
import { SectCamera } from './camera';
import { buildAtmosphere } from './env';
import { buildFlora } from './flora';
import { lantern, railing, stair } from './kit';
import { AXIS_W, BRIDGES, COURTS, ENTRIES, FLIGHTS, HOME_VIEW, LEVEL, MESAS, type EntryDef } from './layout';
import { makeMaterials } from './materials';
import { buildMesa, distantRanges, heightAt, type Peak } from './terrain';
import { GeoBucket, V, clamp } from './util';

export { ENTRIES } from './layout';

export interface SectOptions {
  quality?: 0 | 1 | 2;
  reducedMotion?: boolean;
  onSelect?: (entry: EntryDef) => void;
  onHover?: (entry: EntryDef | null) => void;
  onFrame?: () => void;
  onLost?: () => void;
}

export interface Marker { id: string; label: string; page: string; priority: number; x: number; y: number; onScreen: boolean; occluded: boolean; distance: number }

interface Site { def: EntryDef; group: THREE.Group; box: THREE.Box3; anchor: THREE.Vector3; size: THREE.Vector3 }

const ASSEMBLE: Record<string, () => { bucket: GeoBucket; size: THREE.Vector3 }> = {
  'main-hall': mainHall,
  gate,
  plaza: stele,
  scripture: scripturePavilion,
  alchemy: () => hall(32, 24, 7.5, [7, 5], { chimneys: [-9, -3, 3, 9] }),
  portal,
  forge: () => hall(36, 28, 8, [7, 5], { eaves: 2, chimneys: [12] }),
  'sword-platform': swordPlatform,
  pavilion: hexPavilion,
  disciples: () => hall(20, 18, 5.4, [5, 4], { plinthH: 1.6 }),
  elders: () => hall(26, 24, 6, [6, 5], { eaves: 2, plinthH: 2 }),
  cave: caveEntrance,
  market: marketPavilion,
};

export function createSect(host: HTMLElement, opts: SectOptions = {}) {
  const quality = opts.quality ?? 2, reduced = !!opts.reducedMotion;
  const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'high-performance', stencil: false });
  renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio || 1, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = quality > 0;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.shadowMap.autoUpdate = false;                 // the sect is static: render the shadow map once
  renderer.info.autoReset = false;
  const canvas = renderer.domElement;
  canvas.className = 'sect3d-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  host.append(canvas);

  const scene = new THREE.Scene();
  const mats = makeMaterials();
  const groups = { terrain: new THREE.Group(), architecture: new THREE.Group(), vegetation: new THREE.Group(), paths: new THREE.Group() };
  for (const [name, g] of Object.entries(groups)) { g.name = name; scene.add(g); }
  const atmosphere = buildAtmosphere(scene, quality, reduced);

  // ---------------------------------------------------------------- terrain
  const peaks: Peak[] = [];
  const sides: THREE.BufferGeometry[] = [], tops: THREE.BufferGeometry[] = [], bare: THREE.BufferGeometry[] = [];
  for (const m of MESAS) { const built = buildMesa(m); peaks.push(built.peak); sides.push(built.side); (m.rocky ? bare : tops).push(built.top); }
  const rock = new THREE.Mesh(mergeGeometries(sides)!, mats.rock);
  const grass = new THREE.Mesh(mergeGeometries(tops)!, mats.ground);
  const ledges = new THREE.Mesh(mergeGeometries(bare)!, mats.rockTop);           // stair spines: bare rock ledges
  [...sides, ...tops, ...bare].forEach((g) => g.dispose());
  rock.castShadow = rock.receiveShadow = grass.receiveShadow = ledges.receiveShadow = true;
  rock.name = 'peaks'; grass.name = 'peak-tops'; ledges.name = 'spine-ledges';
  const ranges = new THREE.Mesh(distantRanges(), new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide, fog: true }));
  ranges.name = 'distant-ranges';
  groups.terrain.add(rock, grass, ledges, ranges);
  const ground = (x: number, z: number) => heightAt(peaks, x, z);

  // ---------------------------------------------------------------- paths: courts, axis flights, roads, bridges
  const paths = new GeoBucket();
  for (const c of COURTS) {
    if (c.round) {
      paths.add('jadeDark', new THREE.CylinderGeometry(c.w / 2 + .8, c.w / 2 + 1.6, 3, 56), new THREE.Matrix4().makeTranslation(c.cx, c.y - 1.2, c.cz));
      paths.add('paving', new THREE.CircleGeometry(c.w / 2, 56).rotateX(-Math.PI / 2), new THREE.Matrix4().makeTranslation(c.cx, c.y + .35, c.cz));
      paths.add('gold', new THREE.RingGeometry(c.w * .2, c.w * .215, 48).rotateX(-Math.PI / 2), new THREE.Matrix4().makeTranslation(c.cx, c.y + .4, c.cz));
      paths.add('jade', new THREE.RingGeometry(c.w * .32, c.w * .34, 48).rotateX(-Math.PI / 2), new THREE.Matrix4().makeTranslation(c.cx, c.y + .4, c.cz));
    } else {
      paths.box('jadeDark', c.w + 1.2, 2.4, c.d + 1.2, c.cx, c.y - .9, c.cz);
      paths.add('paving', new THREE.PlaneGeometry(c.w, c.d).rotateX(-Math.PI / 2), new THREE.Matrix4().makeTranslation(c.cx, c.y + .32, c.cz));
    }
  }
  // the straight south axis: three long flights with landings, plus the level roads between them
  const north = V(0, 0, -1);
  for (const f of FLIGHTS) {
    const run = f.z0 - f.z1, rise = f.y1 - f.y0, seg = f.landings + 1;
    const land = 6, flightRun = (run - land * f.landings) / seg, flightRise = rise / seg;
    for (let i = 0; i < seg; i++) {
      const z = f.z0 - i * (flightRun + land), y = f.y0 + i * flightRise;
      stair(paths, 0, y, z, f.width, flightRise, flightRun, north, flightRise + 14, true);
      if (i < seg - 1) {
        const lz = z - flightRun - land / 2, ly = y + flightRise;
        paths.box('jade', f.width + 2, 3, land, 0, ly - 1.5 + .02, lz);
        railing(paths, [V(-f.width / 2 - .5, ly, lz + land / 2), V(-f.width / 2 - .5, ly, lz - land / 2)], 1);
        railing(paths, [V(f.width / 2 + .5, ly, lz + land / 2), V(f.width / 2 + .5, ly, lz - land / 2)], 1);
        lantern(paths, -f.width / 2 - 2.5, ly, lz);
        lantern(paths, f.width / 2 + 2.5, ly, lz);
      }
    }
  }
  // grand stair foot: a jade forecourt meeting the cloud sea
  paths.box('jade', 30, 4, 14, 0, 8, FLIGHTS[0].z0 + 7);
  for (const x of [-12, 12]) { paths.box('jade', 2.2, 14, 2.2, x, 17, FLIGHTS[0].z0 + 12); paths.box('gold', 2.6, .5, 2.6, x, 24.2, FLIGHTS[0].z0 + 12); }
  // axis roads at plaza and middle-terrace level
  for (const [z0, z1, y] of [[124, 100, LEVEL.south], [-12, -104, LEVEL.middle], [-236, -244, LEVEL.north]] as const) {
    paths.add('paving', new THREE.PlaneGeometry(AXIS_W, z0 - z1).rotateX(-Math.PI / 2), new THREE.Matrix4().makeTranslation(0, y + .36, (z0 + z1) / 2));
  }
  for (const b of BRIDGES) {
    const a = V(b.a[0], b.y, b.a[1]), c = V(b.b[0], b.y, b.b[1]);
    const len = a.distanceTo(c), mid = a.clone().lerp(c, .5), yaw = Math.atan2(c.x - a.x, c.z - a.z);
    const rot = new THREE.Matrix4().makeRotationY(yaw);
    paths.add('jade', new THREE.BoxGeometry(b.width, 1.4, len + 8), rot.clone().setPosition(mid.x, b.y - .5, mid.z));
    // shallow arch ribs and piers into the chasm
    for (const k of [-.33, 0, .33]) {
      const p = mid.clone().addScaledVector(c.clone().sub(a).normalize(), k * len);
      paths.add('jadeDark', new THREE.BoxGeometry(b.width * .7, 46, 3.4), rot.clone().setPosition(p.x, b.y - 24, p.z));
    }
    const side = V(Math.cos(yaw), 0, -Math.sin(yaw));
    for (const s of [-1, 1]) {
      const off = side.clone().multiplyScalar(s * (b.width / 2 - .2));
      railing(paths, [a.clone().add(off).setY(b.y + .2), c.clone().add(off).setY(b.y + .2)], 1.1);
    }
    for (const p of [a, c]) for (const s of [-1, 1]) lantern(paths, p.x + side.x * s * (b.width / 2 + 1.6), b.y, p.z + side.z * s * (b.width / 2 + 1.6));
  }
  groups.paths.add(paths.build(mats as unknown as Record<string, THREE.Material>));

  // ---------------------------------------------------------------- buildings (one merged mesh per material each)
  const sites: Site[] = [];
  const blockers: THREE.Box3[] = [];
  for (const def of ENTRIES) {
    const built = ASSEMBLE[def.id]?.();
    if (!built) continue;
    const group = built.bucket.build(mats as unknown as Record<string, THREE.Material>);
    group.name = def.id;
    group.position.set(def.x, def.y + .3, def.z);
    group.rotation.y = def.ry ?? 0;
    group.userData.entry = def.id;
    groups.architecture.add(group);
    group.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(group);
    // the plaza entry is the whole welcome plaza, not just its small notice stele
    if (def.id === 'plaza') box.union(new THREE.Box3(V(def.x - 30, def.y, def.z - 30), V(def.x + 30, def.y + 4, def.z + 30)));
    sites.push({ def, group, box, anchor: V((box.min.x + box.max.x) / 2, box.max.y + 3, (box.min.z + box.max.z) / 2), size: box.getSize(V()) });
    blockers.push(box.clone().expandByScalar(5));
  }
  // cave entrance faces south out of the cave rock; ensure the outcrop's flank stays behind it
  const flora = buildFlora(peaks, mats, quality);
  groups.vegetation.add(...flora.meshes);

  // ---------------------------------------------------------------- camera, post, picking
  const cam = new SectCamera(1, ground, blockers, reduced);
  const camera = cam.camera;
  let composer: EffectComposer | null = null, outline: OutlineEffect | null = null;
  if (quality > 0) {
    renderer.toneMapping = THREE.NoToneMapping;
    composer = new EffectComposer(renderer, { frameBufferType: THREE.HalfFloatType });
    composer.addPass(new RenderPass(scene, camera));
    outline = new OutlineEffect(scene, camera, { blendFunction: BlendFunction.SCREEN, edgeStrength: 3.2, visibleEdgeColor: 0xf6d68a, hiddenEdgeColor: 0x000000, kernelSize: KernelSize.SMALL, blur: true, xRay: false, resolutionScale: .75 });
    composer.addPass(new EffectPass(camera, outline, new SMAAEffect(), new ToneMappingEffect({ mode: ToneMappingMode.ACES_FILMIC })));
  } else {
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
  }
  renderer.toneMappingExposure = 1.05;

  const raycaster = new THREE.Raycaster();
  const ndc = new THREE.Vector2();
  /** Building under a screen point, rejecting hits hidden behind a peak (coarse height-field march). */
  function pick(clientX: number, clientY: number): Site | null {
    const rect = canvas.getBoundingClientRect();
    ndc.set((clientX - rect.left) / rect.width * 2 - 1, -(clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObjects(sites.map((s) => s.group), true);
    for (const hit of hits) {
      let o: THREE.Object3D | null = hit.object;
      while (o && !o.userData.entry) o = o.parent;
      const site = sites.find((s) => s.group === o);
      if (site && !terrainBlocks(camera.position, hit.point)) return site;
    }
    // small/far buildings: accept a click inside the projected bounding box (+8px), nearest first
    let best: Site | null = null, bestDist = Infinity;
    const px = clientX - rect.left, py = clientY - rect.top, corner = V();
    for (const site of sites) {
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, behind = false;
      for (let i = 0; i < 8; i++) {
        corner.set(i & 1 ? site.box.max.x : site.box.min.x, i & 2 ? site.box.max.y : site.box.min.y, i & 4 ? site.box.max.z : site.box.min.z).project(camera);
        if (corner.z > 1) behind = true;
        const sx = (corner.x + 1) / 2 * rect.width, sy = (1 - corner.y) / 2 * rect.height;
        x0 = Math.min(x0, sx); x1 = Math.max(x1, sx); y0 = Math.min(y0, sy); y1 = Math.max(y1, sy);
      }
      if (behind || px < x0 - 8 || px > x1 + 8 || py < y0 - 8 || py > y1 + 8) continue;
      const centre = site.box.getCenter(V());
      const d = camera.position.distanceTo(centre);
      if (d < bestDist && !terrainBlocks(camera.position, centre)) { best = site; bestDist = d; }
    }
    return best;
  }
  function terrainBlocks(from: THREE.Vector3, to: THREE.Vector3) {
    const steps = 48, p = V();
    for (let i = 2; i < steps - 1; i++) {
      p.lerpVectors(from, to, i / steps);
      if (ground(p.x, p.z) > p.y + 6) return true;
    }
    return false;
  }

  let hovered: Site | null = null;
  function setHover(site: Site | null) {
    if (site === hovered) return;
    hovered = site;
    if (outline) {
      outline.selection.clear();
      if (site) site.group.traverse((o) => { if ((o as THREE.Mesh).isMesh) outline!.selection.add(o); });
    }
    canvas.style.cursor = site ? 'pointer' : '';
    opts.onHover?.(site?.def ?? null);
  }

  function focus(id: string, open = true) {
    const site = sites.find((s) => s.def.id === id);
    if (!site) return false;
    const size = Math.max(site.size.x, site.size.y * 1.4, site.size.z);
    cam.flyTo({ target: V(site.anchor.x, site.box.min.y + site.size.y * .4, site.anchor.z), azimuth: site.def.ry ?? 0, elevation: .42, distance: clamp(size * 2.6, 110, 420) });
    if (open) setTimeout(() => { if (!destroyed) opts.onSelect?.(site.def); }, reduced ? 0 : 650);
    return true;
  }

  // ---------------------------------------------------------------- input: drag vs click are told apart by travel/time
  let press: { x: number; y: number; t: number; button: number; shift: boolean; dragging: boolean } | null = null;
  let last = { x: 0, y: 0 };
  const onDown = (e: PointerEvent) => {
    if (e.button > 2) return;
    canvas.setPointerCapture(e.pointerId);
    press = { x: e.clientX, y: e.clientY, t: performance.now(), button: e.button, shift: e.shiftKey, dragging: false };
    last = { x: e.clientX, y: e.clientY };
  };
  const onMove = (e: PointerEvent) => {
    if (press) {
      if (!press.dragging && Math.hypot(e.clientX - press.x, e.clientY - press.y) > 5) { press.dragging = true; setHover(null); }
      if (press.dragging) {
        const dx = e.clientX - last.x, dy = e.clientY - last.y;
        if (press.button === 2 || press.shift) cam.pan(dx, dy); else cam.orbit(dx, dy);
        canvas.style.cursor = 'grabbing';
      }
      last = { x: e.clientX, y: e.clientY };
      return;
    }
    pendingHover = { x: e.clientX, y: e.clientY };
  };
  const onUp = (e: PointerEvent) => {
    if (!press) return;
    const wasClick = !press.dragging && press.button === 0 && performance.now() - press.t < 450;
    press = null;
    canvas.style.cursor = '';
    if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
    if (wasClick) { const site = pick(e.clientX, e.clientY); if (site) focus(site.def.id); }
  };
  const onLeave = () => { pendingHover = null; if (!press) setHover(null); };
  const onWheel = (e: WheelEvent) => { e.preventDefault(); cam.zoom(e.deltaY * (e.deltaMode === 1 ? 30 : 1)); };
  const onMenu = (e: Event) => e.preventDefault();
  let pendingHover: { x: number; y: number } | null = null;
  canvas.addEventListener('pointerdown', onDown);
  canvas.addEventListener('pointermove', onMove);
  canvas.addEventListener('pointerup', onUp);
  canvas.addEventListener('pointercancel', onUp);
  canvas.addEventListener('pointerleave', onLeave);
  canvas.addEventListener('wheel', onWheel, { passive: false });
  canvas.addEventListener('contextmenu', onMenu);

  // ---------------------------------------------------------------- sizing, loop, stats
  let width = 1, height = 1;
  function resize() {
    width = Math.max(1, host.clientWidth); height = Math.max(1, host.clientHeight);
    renderer.setSize(width, height, false);
    composer?.setSize(width, height);
    camera.aspect = width / height;
    applyShift();
  }
  // A detail window on the right covers part of the view: slide the projection so the scene's centre sits in the free space.
  let shift = 0, shiftGoal = 0;
  function applyShift() {
    if (Math.abs(shift) < .5) camera.clearViewOffset(); else camera.setViewOffset(width, height, shift, 0, width, height);
    camera.updateProjectionMatrix();
  }
  const observer = new ResizeObserver(resize);
  observer.observe(host);
  resize();
  renderer.shadowMap.needsUpdate = true;

  let destroyed = false, paused = false, frameId = 0, lost = false;
  let prev = performance.now(), clock = 0, fpsFrames = 0, fpsTime = 0, fps = 0;
  const frameInfo = { calls: 0, triangles: 0 };
  function frame(now: number) {
    frameId = 0;
    if (destroyed || paused || lost) return;
    const dt = Math.min(.1, (now - prev) / 1000);
    prev = now;
    clock += reduced ? 0 : dt;
    fpsFrames++; fpsTime += dt;
    if (fpsTime >= 1) { fps = fpsFrames / fpsTime; fpsFrames = 0; fpsTime = 0; }
    cam.update(dt);
    if (shift !== shiftGoal) { shift = Math.abs(shiftGoal - shift) < .5 || reduced ? shiftGoal : shift + (shiftGoal - shift) * Math.min(1, dt * 7); applyShift(); }
    atmosphere.update(clock, camera);
    if (pendingHover && !press && !cam.moving) { setHover(pick(pendingHover.x, pendingHover.y)); pendingHover = null; }
    renderer.info.reset();
    if (composer) composer.render(dt); else renderer.render(scene, camera);
    frameInfo.calls = renderer.info.render.calls; frameInfo.triangles = renderer.info.render.triangles;
    opts.onFrame?.();
    frameId = requestAnimationFrame(frame);
  }
  const start = () => { if (!frameId && !destroyed && !paused && !lost && !document.hidden) { prev = performance.now(); frameId = requestAnimationFrame(frame); } };
  const onVisibility = () => { if (document.hidden) { cancelAnimationFrame(frameId); frameId = 0; } else start(); };
  document.addEventListener('visibilitychange', onVisibility);
  const onLostCtx = (e: Event) => { e.preventDefault(); lost = true; cancelAnimationFrame(frameId); frameId = 0; opts.onLost?.(); };
  canvas.addEventListener('webglcontextlost', onLostCtx);
  start();

  const projected = V(), sight = new THREE.Ray(), hitPoint = V();
  /** True when another building's box sits between the camera and this site's marker anchor. */
  function buildingBlocks(site: Site, distance: number) {
    sight.origin.copy(camera.position);
    sight.direction.subVectors(site.anchor, camera.position).normalize();
    return sites.some((other) => other !== site && other.def.id !== 'plaza' && sight.intersectBox(other.box, hitPoint) !== null && camera.position.distanceTo(hitPoint) < distance - 6);
  }
  return {
    canvas,
    entries: sites.map((s) => s.def),
    /** Screen positions of every entry marker (css px relative to the host), with occlusion and edge state. */
    markers(): Marker[] {
      return sites.map((s) => {
        projected.copy(s.anchor).project(camera);
        const behind = projected.z > 1;
        const x = (projected.x + 1) / 2 * width, y = (1 - projected.y) / 2 * height;
        const onScreen = !behind && x > -40 && x < width + 40 && y > -40 && y < height + 40;
        const distance = camera.position.distanceTo(s.anchor);
        return { id: s.def.id, label: s.def.label, page: s.def.page, priority: s.def.priority, x, y, onScreen, occluded: onScreen && (terrainBlocks(camera.position, s.anchor) || buildingBlocks(s, distance)), distance };
      });
    },
    focus,
    home() { cam.home(); },
    /** Shift the rendered view left by px (css px) so content centred on screen lands in the space left of a detail window. */
    setViewShift(px: number) { shiftGoal = Math.round(px); if (paused || !frameId) { shift = shiftGoal; applyShift(); } },
    setPaused(value: boolean) { paused = value; if (value) { cancelAnimationFrame(frameId); frameId = 0; setHover(null); } else start(); },
    /** Orbit-state setter for tests and the "views" diagnostics (azimuth 0 = from the south). */
    view(azimuth: number, elevation: number, distance: number, target?: [number, number, number]) {
      cam.flyTo({ target: target ? V(...target) : V(...HOME_VIEW.target), azimuth, elevation, distance }, .01);
    },
    /** Diagnostics: which entry a screen point (client px) would select, ignoring drag state. */
    pickAt(x: number, y: number) { return pick(x, y)?.def.id ?? null; },
    /** Diagnostics: raw building hits under a point before the terrain occlusion test. */
    rawHits(x: number, y: number) {
      const rect = canvas.getBoundingClientRect();
      ndc.set((x - rect.left) / rect.width * 2 - 1, -(y - rect.top) / rect.height * 2 + 1);
      raycaster.setFromCamera(ndc, camera);
      return raycaster.intersectObjects(sites.map((s) => s.group), true).slice(0, 3).map((h) => ({ name: h.object.name, parent: h.object.parent?.name, y: Math.round(h.point.y), blocked: terrainBlocks(camera.position, h.point) }));
    },
    orbitBy(dx: number, dy: number) { cam.orbit(dx, dy); },
    zoomBy(delta: number) { cam.zoom(delta); },
    stats() {
      const mem = renderer.info.memory;
      return { fps: Math.round(fps * 10) / 10, calls: frameInfo.calls, triangles: frameInfo.triangles, geometries: mem.geometries, textures: mem.textures, pines: flora.count, camera: cam.clearance(), cameraPosition: camera.position.toArray().map((v) => Math.round(v)), quality };
    },
    dispose() {
      destroyed = true;
      cancelAnimationFrame(frameId);
      observer.disconnect();
      document.removeEventListener('visibilitychange', onVisibility);
      canvas.removeEventListener('webglcontextlost', onLostCtx);
      for (const [type, fn] of [['pointerdown', onDown], ['pointermove', onMove], ['pointerup', onUp], ['pointercancel', onUp], ['pointerleave', onLeave], ['contextmenu', onMenu]] as const) canvas.removeEventListener(type, fn as EventListener);
      canvas.removeEventListener('wheel', onWheel);
      const materials = new Set<THREE.Material>(), textures = new Set<THREE.Texture>();
      scene.traverse((o) => {
        if ((o as THREE.Light).isLight) (o as THREE.Light).dispose();           // releases the sun's shadow map
        const mesh = o as THREE.Mesh;
        mesh.geometry?.dispose();
        const m = mesh.material;
        if (m) (Array.isArray(m) ? m : [m]).forEach((x) => materials.add(x));
      });
      for (const m of materials) { for (const v of Object.values(m)) if ((v as THREE.Texture)?.isTexture) textures.add(v as THREE.Texture); m.dispose(); }
      mats.textures.forEach((t) => textures.add(t));
      textures.forEach((t) => t.dispose());
      outline?.dispose();
      composer?.dispose();
      const after = { geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures };
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
      return after;
    },
  };
}



export type SectController = ReturnType<typeof createSect>;
