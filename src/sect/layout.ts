// Site plan of 青玄剑宗 (A02 v4 top plan, A03 v3 section, A04 v4 grand stairs). Metres; x east, y up, z south.
// The plan images are design references, not survey data: every coordinate here is this round's estimate
// that keeps the A02 topology (one straight south axis: stairs → plaza → gate → middle stairs → crossroads →
// north stairs → main hall; east/west terraces by straight bridges; lower east/west terraces off the plaza).

export type Pt = [number, number];

export interface Mesa { id: string; top: number; outline: Pt[]; flare?: number; seed: number; rocky?: boolean }

/** Platform levels (A03: south 80 / middle 140 / north 220). */
export const LEVEL = { cloud: 0, south: 80, middle: 140, north: 220 } as const;
export const AXIS_W = 16;           // grand stair / axis width (C01 12m widened per the "wide" ruling)

/** Stair flights on the axis: bottom (z, y) → top (z, y); all run north (−z). */
export const FLIGHTS = [
  { id: 'grand', z0: 352, y0: 10, z1: 210, y1: LEVEL.south, width: AXIS_W, landings: 4 },
  { id: 'middle', z0: 100, y0: LEVEL.south, z1: -12, y1: LEVEL.middle, width: AXIS_W, landings: 3 },
  { id: 'north', z0: -104, y0: LEVEL.middle, z1: -236, y1: LEVEL.north, width: AXIS_W, landings: 3 },
] as const;

const ellipse = (cx: number, cz: number, rx: number, rz: number, n = 12, wobble = 0, seed = 1): Pt[] =>
  Array.from({ length: n }, (_, i) => {
    const a = i / n * Math.PI * 2, k = 1 + wobble * Math.sin(a * 3 + seed) * .5 + wobble * Math.cos(a * 5 + seed * 2) * .5;
    return [cx + Math.cos(a) * rx * k, cz + Math.sin(a) * rz * k] as Pt;
  });

export const MESAS: Mesa[] = [
  // main peaks carrying the axis
  { id: 'south', top: LEVEL.south, seed: 11, outline: [[-78, 96], [-30, 104], [30, 104], [80, 98], [92, 140], [86, 196], [44, 218], [10, 222], [-10, 222], [-46, 216], [-88, 192], [-94, 140]] },
  { id: 'middle', top: LEVEL.middle, seed: 23, outline: [[-60, -8], [-14, -14], [14, -14], [62, -8], [66, -44], [60, -96], [14, -104], [-14, -104], [-62, -96], [-68, -44]] },
  { id: 'north', top: LEVEL.north, seed: 37, flare: 1.2, outline: [[-74, -232], [-14, -240], [14, -240], [76, -232], [86, -290], [64, -340], [0, -352], [-66, -340], [-88, -290]] },
  // east / west functional terraces (secondary peaks)
  { id: 'west', top: LEVEL.middle, seed: 41, outline: ellipse(-182, -48, 72, 62, 14, .12, 2) },
  { id: 'east', top: LEVEL.middle, seed: 53, outline: ellipse(182, -48, 72, 62, 14, .12, 5) },
  // lower terraces off the plaza (disciples west, elders + cave east)
  { id: 'southwest', top: LEVEL.south - 4, seed: 61, outline: ellipse(-168, 112, 52, 44, 12, .1, 1) },
  { id: 'southeast', top: LEVEL.south - 4, seed: 67, outline: ellipse(168, 112, 52, 44, 12, .1, 4) },
  // rock spines under the long flights: each top sits just under the stair surface at that segment's low (south) end,
  // so the stair always rides above the rock and its jade body walls stay under ~20m
  { id: 'spine-g1', top: 8, seed: 71, rocky: true, outline: [[-24, 360], [24, 360], [26, 318], [-26, 318]] },
  { id: 'spine-g2', top: 23, seed: 72, rocky: true, outline: [[-26, 322], [26, 322], [27, 284], [-27, 284]] },
  { id: 'spine-g3', top: 40, seed: 73, rocky: true, outline: [[-27, 288], [27, 288], [28, 250], [-28, 250]] },
  { id: 'spine-g4', top: 56, seed: 74, rocky: true, outline: [[-28, 254], [28, 254], [30, 214], [-30, 214]] },
  { id: 'spine-m1', top: 78, seed: 75, rocky: true, outline: [[-30, 102], [30, 102], [32, 66], [-32, 66]] },
  { id: 'spine-m2', top: 94, seed: 76, rocky: true, outline: [[-32, 70], [32, 70], [34, 34], [-34, 34]] },
  { id: 'spine-m3', top: 111, seed: 77, rocky: true, outline: [[-34, 38], [34, 38], [36, -6], [-36, -6]] },
  { id: 'spine-n1', top: 138, seed: 78, rocky: true, outline: [[-32, -100], [32, -100], [34, -142], [-34, -142]] },
  { id: 'spine-n2', top: 158, seed: 79, rocky: true, outline: [[-34, -138], [34, -138], [36, -182], [-36, -182]] },
  { id: 'spine-n3', top: 182, seed: 80, rocky: true, outline: [[-36, -178], [36, -178], [38, -230], [-38, -230]] },
  // the cave outcrop on the south-east terrace and companion pillars
  { id: 'cave-rock', top: 122, seed: 81, outline: ellipse(172, 62, 34, 22, 10, .15, 3) },
  { id: 'pillar-1', top: 160, seed: 91, outline: ellipse(-120, 40, 16, 14, 9, .2, 1) },
  { id: 'pillar-2', top: 172, seed: 92, outline: ellipse(116, -150, 18, 16, 9, .2, 2) },
  { id: 'pillar-3', top: 186, seed: 93, outline: ellipse(-128, -170, 20, 18, 9, .2, 3) },
  { id: 'pillar-4', top: 120, seed: 94, outline: ellipse(-250, 70, 22, 20, 9, .2, 4) },
  { id: 'pillar-5', top: 132, seed: 95, outline: ellipse(262, 30, 20, 18, 9, .2, 5) },
  { id: 'pillar-6', top: 96, seed: 96, outline: ellipse(-90, 270, 16, 14, 9, .2, 6) },
  { id: 'pillar-7', top: 104, seed: 97, outline: ellipse(96, 290, 18, 16, 9, .2, 7) },
  { id: 'pillar-8', top: 240, seed: 98, outline: ellipse(150, -300, 26, 22, 10, .2, 8) },
  { id: 'pillar-9', top: 230, seed: 99, outline: ellipse(-160, -300, 24, 22, 10, .2, 9) },
];

/** Straight jade bridges (C05): deck from a → b at constant height. */
export const BRIDGES = [
  { id: 'west', a: [-58, -48] as Pt, b: [-116, -48] as Pt, y: LEVEL.middle, width: 7 },
  { id: 'east', a: [58, -48] as Pt, b: [116, -48] as Pt, y: LEVEL.middle, width: 7 },
  { id: 'southwest', a: [-84, 150] as Pt, b: [-124, 128] as Pt, y: LEVEL.south - 4, width: 6 },
  { id: 'southeast', a: [84, 150] as Pt, b: [124, 128] as Pt, y: LEVEL.south - 4, width: 6 },
];

/**
 * Clickable buildings and the world page (卷目 id) each opens. `page` must be an id the server returns in
 * view.world.pages; `focus` optionally names a section/action group the hub reveals inside that page.
 */
export interface EntryDef { id: string; label: string; page: string; focus?: string; x: number; z: number; y: number; ry?: number; priority: number }

export const ENTRIES: EntryDef[] = [
  { id: 'main-hall', label: '主殿 · 宗门', page: 'sects', x: 0, z: -292, y: LEVEL.north, priority: 10 },
  { id: 'gate', label: '山门 · 九州行旅', page: 'world', x: 0, z: 128, y: LEVEL.south, priority: 9 },
  { id: 'plaza', label: '迎仙广场 · 闻道', page: 'quests', x: 0, z: 172, y: LEVEL.south, priority: 6 },
  { id: 'scripture', label: '藏经阁 · 功法', page: 'character', focus: 'skills', x: -200, z: -78, y: LEVEL.middle, priority: 8 },
  { id: 'alchemy', label: '炼丹阁 · 四艺', page: 'craft', x: -160, z: -14, y: LEVEL.middle, ry: Math.PI / 2, priority: 7 },
  { id: 'portal', label: '秘境传送阵 · 副本', page: 'exploration', x: -214, z: -14, y: LEVEL.middle, priority: 8 },
  { id: 'forge', label: '炼器阁 · 四艺', page: 'craft', x: 206, z: -86, y: LEVEL.middle, priority: 6 },
  { id: 'sword-platform', label: '试剑台 · NPC演武', page: 'arena', x: 166, z: -30, y: LEVEL.middle, priority: 8 },
  { id: 'pavilion', label: '观剑亭 · 名录', page: 'achievements', x: 222, z: -22, y: LEVEL.middle, priority: 5 },
  { id: 'disciples', label: '弟子居所 · 人物', page: 'character', x: -172, z: 116, y: LEVEL.south - 4, priority: 6 },
  { id: 'elders', label: '长老居所 · 同道', page: 'social', x: 150, z: 126, y: LEVEL.south - 4, priority: 6 },
  { id: 'cave', label: '修炼洞府 · 洞府', page: 'estate', x: 176, z: 84, y: LEVEL.south - 4, priority: 7 },
  { id: 'market', label: '坊市亭 · NPC坊市', page: 'market', x: -56, z: 164, y: LEVEL.south, priority: 5 },
];

/** Paved courts on the mesa tops (rect: cx, cz, w, d) — keeps trees off and reads as built ground. */
export const COURTS: { cx: number; cz: number; w: number; d: number; y: number; round?: boolean }[] = [
  { cx: 0, cz: 172, w: 66, d: 66, y: LEVEL.south, round: true },
  { cx: 0, cz: 118, w: 30, d: 34, y: LEVEL.south },
  { cx: 0, cz: 130, w: 64, d: 20, y: LEVEL.south },
  { cx: -56, cz: 164, w: 22, d: 22, y: LEVEL.south },
  { cx: 0, cz: -50, w: 116, d: 26, y: LEVEL.middle },
  { cx: 0, cz: -58, w: 30, d: 90, y: LEVEL.middle },
  { cx: 0, cz: -288, w: 120, d: 92, y: LEVEL.north },
  { cx: -186, cz: -46, w: 96, d: 90, y: LEVEL.middle },
  { cx: 186, cz: -52, w: 104, d: 96, y: LEVEL.middle },
  { cx: -168, cz: 112, w: 46, d: 40, y: LEVEL.south - 4 },
  { cx: 160, cz: 112, w: 52, d: 40, y: LEVEL.south - 4 },
];

/** Spirit springs (C09) on the middle terrace flanking the axis, and in the east lower terrace. */
export const POOLS = [
  { x: -34, z: -78, w: 22, d: 14, y: LEVEL.middle },
  { x: 34, z: -78, w: 22, d: 14, y: LEVEL.middle },
  { x: 140, z: 92, w: 16, d: 10, y: LEVEL.south - 4 },
];

/** Waterfalls (D08): lip point on a cliff edge, outward direction (radians in xz), height and width. */
export const FALLS = [
  { x: -64, z: -70, dir: Math.PI, top: LEVEL.middle, h: 120, w: 7 },
  { x: 64, z: -70, dir: 0, top: LEVEL.middle, h: 120, w: 7 },
  { x: -84, z: -300, dir: Math.PI, top: LEVEL.north - 2, h: 170, w: 9 },
  { x: 84, z: -296, dir: 0, top: LEVEL.north - 2, h: 170, w: 9 },
  { x: -240, z: -60, dir: Math.PI, top: LEVEL.middle - 2, h: 110, w: 6 },
  { x: 240, z: -40, dir: 0, top: LEVEL.middle - 2, h: 110, w: 6 },
  { x: 150, z: 154, dir: Math.PI / 2, top: LEVEL.south - 6, h: 70, w: 5 },
];

/** Default south high-altitude view (A01): orbit target, azimuth (0 = from south), elevation, distance. */
export const HOME_VIEW = { target: [0, 118, -48] as [number, number, number], azimuth: 0, elevation: .4, distance: 780 };
export const LIMITS = { minDist: 90, maxDist: 980, minElev: .2, maxElev: 1.25, minCamY: 46, target: { x: 300, zMin: -360, zMax: 360, yMin: 70, yMax: 240 } };
