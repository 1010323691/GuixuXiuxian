// Material family of the sect: ink-teal glazed tiles, white jade, dark xuan wood, restrained gold,
// mountain rock and moss. Textures are painted on canvases at start-up (no image files), see E01–E07.
import * as THREE from 'three';
import { canvasTexture, rng } from './util';

export interface SectMaterials {
  tile: THREE.MeshStandardMaterial; ridge: THREE.MeshStandardMaterial; jade: THREE.MeshStandardMaterial; jadeDark: THREE.MeshStandardMaterial;
  wood: THREE.MeshStandardMaterial; lattice: THREE.MeshStandardMaterial; gold: THREE.MeshStandardMaterial; beam: THREE.MeshStandardMaterial;
  rock: THREE.MeshStandardMaterial; rockTop: THREE.MeshStandardMaterial; ground: THREE.MeshStandardMaterial; paving: THREE.MeshStandardMaterial; pine: THREE.MeshStandardMaterial;
  bark: THREE.MeshStandardMaterial; glow: THREE.MeshBasicMaterial; dark: THREE.MeshStandardMaterial;
  all: THREE.Material[]; textures: THREE.Texture[];
}

export function makeMaterials(): SectMaterials {
  const r = rng(7);
  const textures: THREE.Texture[] = [];
  const tex = (t: THREE.Texture) => { textures.push(t); return t; };

  // E01 glazed tile: alternating barrel (convex) and pan rows running down the slope, glossy highlights.
  const tileMap = tex(canvasTexture(256, (g, s) => {
    g.fillStyle = '#1f4f53'; g.fillRect(0, 0, s, s);
    const cols = 8, w = s / cols;
    for (let i = 0; i < cols; i++) {
      const grad = g.createLinearGradient(i * w, 0, (i + 1) * w, 0);
      grad.addColorStop(0, '#173c40'); grad.addColorStop(.35, '#3c8584'); grad.addColorStop(.55, '#58a39d'); grad.addColorStop(1, '#163a3e');
      g.fillStyle = grad; g.fillRect(i * w + w * .12, 0, w * .76, s);
      for (let y = 0; y < s; y += s / 6) { g.fillStyle = 'rgba(8,24,26,.55)'; g.fillRect(i * w, y, w, 2); }
    }
  }));
  const jadeMap = tex(canvasTexture(256, (g, s) => {
    g.fillStyle = '#ece9e0'; g.fillRect(0, 0, s, s);
    for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(${150 + r.next() * 60},${150 + r.next() * 60},${140 + r.next() * 60},${r.next() * .08})`; g.fillRect(r.next() * s, r.next() * s, 2 + r.next() * 8, 1 + r.next() * 3); }
    g.strokeStyle = 'rgba(120,118,110,.35)'; g.lineWidth = 2;
    for (let y = 0; y <= s; y += s / 4) { g.beginPath(); g.moveTo(0, y); g.lineTo(s, y); g.stroke(); }
    for (let row = 0; row < 4; row++) for (let x = (row % 2) * s / 4; x <= s; x += s / 2) { g.beginPath(); g.moveTo(x, row * s / 4); g.lineTo(x, (row + 1) * s / 4); g.stroke(); }
  }));
  const woodMap = tex(canvasTexture(128, (g, s) => {
    g.fillStyle = '#3b2a22'; g.fillRect(0, 0, s, s);
    for (let i = 0; i < 70; i++) { g.strokeStyle = `rgba(${20 + r.next() * 40},${12 + r.next() * 20},${8 + r.next() * 14},.5)`; g.beginPath(); const x = r.next() * s; g.moveTo(x, 0); g.bezierCurveTo(x + 4, s * .3, x - 4, s * .7, x + 2, s); g.stroke(); }
  }));
  // Lattice doors/windows (格扇): a gold-framed panel per texture repeat, latticed upper part.
  const latticeMap = tex(canvasTexture(256, (g, s) => {
    g.fillStyle = '#2c1d17'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#4a3226'; g.fillRect(s * .08, s * .06, s * .84, s * .88);
    g.strokeStyle = '#8d6a3c'; g.lineWidth = 3; g.strokeRect(s * .08, s * .06, s * .84, s * .88);
    g.strokeStyle = 'rgba(210,180,120,.75)'; g.lineWidth = 2;
    for (let i = 1; i < 9; i++) { const x = s * .12 + i * s * .076; g.beginPath(); g.moveTo(x, s * .1); g.lineTo(x, s * .6); g.stroke(); }
    for (let i = 1; i < 7; i++) { const y = s * .1 + i * s * .07; g.beginPath(); g.moveTo(s * .12, y); g.lineTo(s * .88, y); g.stroke(); }
    g.fillStyle = '#3a271e'; g.fillRect(s * .12, s * .66, s * .76, s * .24);
    g.strokeStyle = '#8d6a3c'; g.strokeRect(s * .16, s * .7, s * .68, s * .16);
  }));
  const beamMap = tex(canvasTexture(256, (g, s) => {
    // painted beam (额枋): dark wood band with teal/gold cartouches
    g.fillStyle = '#2f221c'; g.fillRect(0, 0, s, s);
    g.fillStyle = '#245a5a'; g.fillRect(s * .1, s * .25, s * .8, s * .5);
    g.strokeStyle = '#c4a04e'; g.lineWidth = 4; g.strokeRect(s * .1, s * .25, s * .8, s * .5);
    g.fillStyle = '#c4a04e'; for (const x of [.25, .5, .75]) { g.beginPath(); g.arc(s * x, s * .5, s * .07, 0, 6.3); g.fill(); }
  }));
  const rockMap = tex(canvasTexture(256, (g, s) => {
    g.fillStyle = '#8f938f'; g.fillRect(0, 0, s, s);
    for (let i = 0; i < 1400; i++) { const v = 90 + r.next() * 90; g.fillStyle = `rgba(${v},${v + 4},${v},${.08 + r.next() * .15})`; g.fillRect(r.next() * s, r.next() * s, 2 + r.next() * 14, 1 + r.next() * 4); }
    g.strokeStyle = 'rgba(40,44,42,.35)';
    for (let i = 0; i < 26; i++) { g.lineWidth = .6 + r.next() * 1.4; g.beginPath(); let x = r.next() * s, y = r.next() * s; g.moveTo(x, y); for (let k = 0; k < 5; k++) { x += (r.next() - .5) * 40; y += r.next() * 30; g.lineTo(x, y); } g.stroke(); }
  }));
  const groundMap = tex(canvasTexture(128, (g, s) => {
    g.fillStyle = '#5b7a45'; g.fillRect(0, 0, s, s);
    for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(${50 + r.next() * 60},${90 + r.next() * 60},${40 + r.next() * 40},.35)`; g.fillRect(r.next() * s, r.next() * s, 1 + r.next() * 3, 1 + r.next() * 3); }
  }));
  const pavingMap = tex(canvasTexture(256, (g, s) => {
    g.fillStyle = '#d9d6cc'; g.fillRect(0, 0, s, s);
    for (let y = 0; y < 8; y++) for (let x = 0; x < 8; x++) { const v = 205 + r.next() * 30; g.fillStyle = `rgb(${v},${v - 2},${v - 8})`; g.fillRect(x * s / 8 + 1, y * s / 8 + 1, s / 8 - 2, s / 8 - 2); }
  }));
  rockMap.repeat.set(1, 1);

  const std = (p: THREE.MeshStandardMaterialParameters) => new THREE.MeshStandardMaterial(p);
  const m: Omit<SectMaterials, 'all' | 'textures'> = {
    tile: std({ map: tileMap, color: 0xffffff, roughness: .38, metalness: .15, side: THREE.DoubleSide }),
    ridge: std({ color: 0x1b3d40, roughness: .45, metalness: .1 }),
    jade: std({ map: jadeMap, color: 0xffffff, roughness: .55 }),
    jadeDark: std({ map: jadeMap, color: 0xc9c6bc, roughness: .7 }),
    wood: std({ map: woodMap, color: 0xffffff, roughness: .7 }),
    lattice: std({ map: latticeMap, color: 0xffffff, roughness: .65 }),
    gold: std({ color: 0xc9a24a, roughness: .32, metalness: .85, emissive: 0x2a1d06 }),
    beam: std({ map: beamMap, color: 0xffffff, roughness: .6 }),
    rock: std({ map: rockMap, vertexColors: true, roughness: .92 }),
    rockTop: std({ map: rockMap, color: 0xa3aaa2, roughness: .95 }),
    ground: std({ map: groundMap, color: 0xc9d2b4, roughness: .95 }),
    paving: std({ map: pavingMap, color: 0xffffff, roughness: .7 }),
    pine: std({ color: 0x2e5a3a, roughness: .9, flatShading: true }),
    bark: std({ color: 0x5a4636, roughness: .95 }),
    glow: new THREE.MeshBasicMaterial({ color: 0x9ff3ff, transparent: true, opacity: .85, depthWrite: false, blending: THREE.AdditiveBlending }),
    dark: std({ color: 0x151b1d, roughness: 1 }),
  };
  return { ...m, all: Object.values(m), textures };
}
