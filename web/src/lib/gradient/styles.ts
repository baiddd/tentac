// Catalog of the 13 gradient styles: each pairs a compiled-shader-ready
// fragment source with a `randomize()` that produces parameters tuned
// to that style's aesthetic. Keeping the tuning here (not in engine.ts)
// means a single style can be adjusted in isolation while iterating.
//
// Feedback round 1: every style's colors now come from one shared
// "galaxy" hue palette (deep blue / violet / magenta-pink / nebula teal,
// with a rare warm gold for star accents) instead of each style picking
// its own arbitrary hue range — see galaxyHue()/galaxyFive() below.

import meshFrag from "./shaders/mesh.frag?raw";
import landscapeFrag from "./shaders/landscape.frag?raw";
import nonRegularBlendingFrag from "./shaders/non-regular-blending.frag?raw";
import retroFrag from "./shaders/retro.frag?raw";
import trippyFrag from "./shaders/trippy.frag?raw";
import neonFlowFrag from "./shaders/neon-flow.frag?raw";
import windowFrag from "./shaders/window.frag?raw";
import auroraFrag from "./shaders/aurora.frag?raw";
import crystalLightFrag from "./shaders/crystal-light.frag?raw";
import galaxyFrag from "./shaders/galaxy.frag?raw";
import glassFractalFrag from "./shaders/glass-fractal.frag?raw";
import bubbleFrag from "./shaders/bubble.frag?raw";
import prismaticFrag from "./shaders/prismatic.frag?raw";
import glassStructureFrag from "./shaders/glass-structure.frag?raw";

export interface GradientParams {
  colors: [number, number, number][]; // 5 RGB triples, 0..1
  warp: number;
  scale: number;
  speed: number;
  grain: number;
  blend: number;
  paramA: number;
  paramB: number;
  paramC: number;
  seed: number;
}

// Fills in any numeric field missing from a saved/preset params object
// (e.g. a save made before a new param existed, like paramC) so an old
// file never sends `undefined` to a WebGL uniform call.
const NUMERIC_KEYS: (keyof Omit<GradientParams, "colors">)[] = [
  "warp", "scale", "speed", "grain", "blend", "paramA", "paramB", "paramC", "seed",
];
export function withParamDefaults(raw: Partial<GradientParams>): GradientParams {
  const filled = { ...raw } as GradientParams;
  for (const key of NUMERIC_KEYS) {
    if (typeof filled[key] !== "number" || !isFinite(filled[key])) filled[key] = 0.5;
  }
  return filled;
}

// Committed presets: drop a "<style-id>.json" here (the shape the lab's
// Save button downloads) to bake in a chosen set of params as that
// style's default for everyone — not just the browser that saved it via
// localStorage. See presets/README.md.
const presetModules = import.meta.glob<Record<string, unknown>>("./presets/*.json", { eager: true });
const PRESETS: Record<string, GradientParams> = {};
for (const path in presetModules) {
  const id = path.split("/").pop()!.replace(/\.json$/, "");
  const mod = presetModules[path] as { default?: GradientParams } & GradientParams;
  PRESETS[id] = withParamDefaults((mod.default ?? mod) as GradientParams);
}
export { PRESETS };

export interface GradientStyle {
  id: string;
  label: string;
  fragSource: string;
  randomize: () => GradientParams;
}

// One slider per generic uniform every style's shader reads from
// (uWarp/uScale/uSpeed/uGrain/uBlend/uParamA/uParamB/uParamC) — the same
// set used to adjust the visuals while tuning each style, so exposing
// sliders for exactly these covers every knob without style-specific UI.
export interface ParamDef {
  key: "warp" | "scale" | "speed" | "grain" | "blend" | "paramA" | "paramB" | "paramC";
  label: string;
  min: number;
  max: number;
  step: number;
}

export const PARAM_DEFS: ParamDef[] = [
  { key: "warp", label: "Warp", min: 0, max: 3, step: 0.01 },
  { key: "scale", label: "Scale", min: 0.2, max: 4, step: 0.01 },
  { key: "speed", label: "Speed", min: 0, max: 3, step: 0.01 },
  { key: "grain", label: "Grain", min: 0, max: 1, step: 0.01 },
  { key: "blend", label: "Blend", min: 0, max: 2, step: 0.01 },
  { key: "paramA", label: "Param A", min: 0, max: 1, step: 0.01 },
  { key: "paramB", label: "Param B", min: 0, max: 1, step: 0.01 },
  { key: "paramC", label: "Param C", min: 0, max: 1, step: 0.01 },
];

// Deterministic RNG (mulberry32) for generating a reproducible gradient for
// a given issue week. Every randomize() below is built on rand()/pick()/
// galaxyHue(), which all call Math.random() directly — swapping the global
// out for the duration of the callback seeds all of them at once without
// touching each call site individually.
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function withSeededRandom<T>(seed: number, fn: () => T): T {
  const original = Math.random;
  Math.random = mulberry32(seed);
  try {
    return fn();
  } finally {
    Math.random = original;
  }
}

function rand(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

// Interpolates hue along the shorter way round the color wheel — a plain
// numeric rand(a, b)/lerp(a, b) crosses whatever hues sit between the two
// numbers (e.g. gold=45 to blue=220 cuts straight through green/yellow),
// which reads as a wrong, unintended color band.
function lerpHue(a: number, b: number, t: number): number {
  const diff = (((b - a + 540) % 360) - 180);
  return (a + diff * t + 360) % 360;
}

// h in [0,360), s/l in [0,1] -> [r,g,b] in [0,1]
function hsl(h: number, s: number, l: number): [number, number, number] {
  h = ((h % 360) + 360) % 360;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0, g = 0, b = 0;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [r + m, g + m, b + m];
}

// -------------------------------------------------------- galaxy palette
//
// Every style draws its colors from this shared pool: deep blue, violet,
// magenta/pink and nebula teal cover the "gas cloud" body of the look;
// a rare warm gold stands in for a distant star and is only ever a small
// accent, never a dominant hue.

const GALAXY_HUE_BANDS: [number, number][] = [
  [205, 240], // deep blue
  [250, 285], // violet
  [290, 330], // magenta / pink
  [170, 200], // nebula teal / cyan
];
const STAR_ACCENT_HUE: [number, number] = [35, 55]; // warm gold, sparing use

function galaxyHue(allowStar = true): number {
  if (allowStar && Math.random() < 0.12) return rand(STAR_ACCENT_HUE[0], STAR_ACCENT_HUE[1]);
  const [lo, hi] = pick(GALAXY_HUE_BANDS);
  return rand(lo, hi);
}

function galaxyColor(s: [number, number] = [0.55, 0.85], l: [number, number] = [0.35, 0.6], allowStar = true): [number, number, number] {
  return hsl(galaxyHue(allowStar), rand(s[0], s[1]), rand(l[0], l[1]));
}

function galaxyFive(s: [number, number] = [0.55, 0.85], l: [number, number] = [0.35, 0.6]): [number, number, number][] {
  return [galaxyColor(s, l), galaxyColor(s, l), galaxyColor(s, l), galaxyColor(s, l), galaxyColor(s, l, false)];
}

function baseParams(): Omit<GradientParams, "colors"> {
  return {
    warp: rand(0.6, 1.8),
    scale: rand(1.0, 2.4),
    speed: rand(0.5, 1.6),
    grain: rand(0.0, 0.08),
    blend: rand(0.3, 0.9),
    paramA: rand(0.2, 0.8),
    paramB: rand(0.2, 0.8),
    paramC: rand(0.2, 0.8),
    seed: rand(0, 1000),
  };
}

export const GRADIENT_STYLES: GradientStyle[] = [
  {
    id: "mesh",
    label: "Mesh",
    fragSource: meshFrag,
    randomize: () => {
      // One majority hue for c0-c3 (the gradient's dominant color, with
      // only slight jitter so it still reads as one color family) plus
      // one true complementary accent (hue+180°) on c4 — c4 sits in the
      // noise field's high range, which is the range most exposed by
      // the black-dominant mask, so the accent actually shows up rather
      // than getting buried.
      const majorHue = galaxyHue(false);
      const complementHue = (majorHue + 180) % 360;
      return {
        ...baseParams(),
        colors: [
          hsl(majorHue + rand(-8, 8), rand(0.5, 0.8), rand(0.3, 0.45)),
          hsl(majorHue + rand(-8, 8), rand(0.55, 0.85), rand(0.4, 0.55)),
          hsl(majorHue + rand(-12, 12), rand(0.5, 0.8), rand(0.35, 0.5)),
          hsl(majorHue + rand(-8, 8), rand(0.55, 0.85), rand(0.45, 0.6)),
          hsl(complementHue, rand(0.7, 0.95), rand(0.5, 0.65)), // complementary accent
        ],
      };
    },
  },
  {
    id: "landscape",
    label: "Landscape",
    fragSource: landscapeFrag,
    randomize: () => {
      const skyHue = rand(...pick([[205, 240], [250, 285]] as [number, number][]));
      const horizonHue = rand(STAR_ACCENT_HUE[0], STAR_ACCENT_HUE[1]);
      return {
        ...baseParams(),
        warp: rand(0.2, 0.8), // vertical drift amplitude
        speed: rand(0.2, 0.7), // drift speed
        // c0 = bottom of screen (horizon glow) -> c4 = top (zenith),
        // since vUv.y=1 is the top of the viewport.
        colors: [
          hsl(horizonHue, rand(0.55, 0.75), rand(0.45, 0.6)), // c0 horizon glow
          hsl(lerpHue(horizonHue, skyHue, rand(0.3, 0.6)), rand(0.5, 0.7), rand(0.22, 0.32)),
          hsl(skyHue, rand(0.5, 0.7), rand(0.12, 0.2)),
          hsl(skyHue + rand(-10, 15), rand(0.4, 0.6), rand(0.06, 0.1)),
          hsl(skyHue, rand(0.3, 0.5), rand(0.03, 0.06)), // c4 zenith — near-black
        ],
      };
    },
  },
  {
    id: "non-regular-blending",
    label: "Non-regular blending",
    fragSource: nonRegularBlendingFrag,
    randomize: () => ({
      ...baseParams(),
      warp: rand(1.2, 2.4),
      grain: rand(0.0, 0.05),
      colors: galaxyFive([0.55, 0.9], [0.3, 0.55]),
    }),
  },
  {
    id: "retro",
    label: "Retro style",
    fragSource: retroFrag,
    randomize: () => {
      const hue = rand(290, 330); // magenta/purple anchor, galaxy family
      return {
        ...baseParams(),
        warp: rand(0.3, 0.8),
        speed: rand(0.2, 0.6),
        paramA: rand(3, 6),
        colors: [
          hsl(hue, 0.65, 0.06),
          hsl(hue + 15, 0.7, 0.16),
          hsl(hue + 40, 0.75, 0.32),
          hsl(hue + 60, 0.85, 0.5),
          hsl(rand(STAR_ACCENT_HUE[0], STAR_ACCENT_HUE[1]), 0.9, 0.65),
        ],
      };
    },
  },
  {
    id: "trippy",
    label: "Trippy gradient",
    fragSource: trippyFrag,
    randomize: () => ({
      ...baseParams(),
      warp: rand(1.6, 3.0),
      speed: rand(1.2, 2.5),
      scale: rand(1.5, 3.0),
      colors: galaxyFive([0.7, 1.0], [0.3, 0.55]),
    }),
  },
  {
    id: "neon-flow",
    label: "Neon flow",
    fragSource: neonFlowFrag,
    randomize: () => ({
      ...baseParams(),
      warp: rand(1.2, 2.6), // beam curvature
      grain: rand(0.0, 0.06), // base beam thickness at the vanishing point
      blend: rand(0.6, 1.3),
      paramA: rand(0.1, 0.9), // vanishing point x position (random, not centered)
      paramB: rand(0.1, 0.9), // vanishing point y position
      paramC: rand(0.8, 1.0), // perspective strength — always strong on randomize
      colors: galaxyFive([0.75, 1.0], [0.5, 0.68]),
    }),
  },
  {
    id: "window",
    label: "Window",
    fragSource: windowFrag,
    randomize: () => {
      const wallHue = rand(...pick([[205, 240], [250, 285]] as [number, number][]));
      const lightHue = rand(STAR_ACCENT_HUE[0], STAR_ACCENT_HUE[1]);
      return {
        ...baseParams(),
        speed: rand(0.15, 0.4), // door-breathing period
        blend: rand(0.5, 1.0),
        paramA: rand(0.3, 0.7), // door width
        paramB: rand(0.3, 0.6), // door position along the wall
        colors: [
          hsl(wallHue, 0.35, 0.05), // c0 wall
          hsl(wallHue, 0.3, 0.09), // c1 floor
          hsl(lightHue, 0.8, 0.75), // c2 light trapezoid
          hsl(lightHue, 0.9, 0.9), // c3 door opening itself
          hsl(wallHue, 0.4, 0.02), // c4 deep shadow
        ],
      };
    },
  },
  {
    id: "aurora",
    label: "Aurora",
    fragSource: auroraFrag,
    randomize: () => ({
      ...baseParams(),
      warp: rand(0.8, 1.6),
      speed: rand(0.3, 0.9),
      blend: rand(0.4, 0.9),
      colors: [
        galaxyColor([0.6, 0.85], [0.4, 0.55], false),
        galaxyColor([0.6, 0.85], [0.4, 0.55], false),
        galaxyColor([0.6, 0.85], [0.4, 0.55], false),
        hsl(0, 0, 0),
        hsl(235, 0.6, 0.02), // near-black navy base
      ],
    }),
  },
  {
    id: "crystal-light",
    label: "Crystal light",
    fragSource: crystalLightFrag,
    randomize: () => ({
      ...baseParams(),
      warp: rand(0.2, 0.6),
      grain: rand(0.4, 1.0),
      colors: galaxyFive([0.5, 0.8], [0.45, 0.65]),
    }),
  },
  {
    id: "galaxy",
    label: "Galaxy",
    fragSource: galaxyFrag,
    randomize: () => ({
      ...baseParams(),
      warp: rand(0.6, 2.0), // ring thickness
      speed: rand(0.3, 1.2), // orbit rotation speed
      paramA: rand(0.15, 0.85), // inner halo intensity
      colors: galaxyFive([0.6, 0.9], [0.4, 0.6]),
    }),
  },
  {
    id: "glass-fractal",
    label: "Glass fractal",
    fragSource: glassFractalFrag,
    randomize: () => ({
      ...baseParams(),
      warp: rand(0.4, 1.6), // per-band parallax shift amount
      paramA: rand(0.15, 1.0), // band count
      paramB: rand(0.1, 0.8), // chromatic split
      colors: galaxyFive([0.45, 0.7], [0.3, 0.5]),
    }),
  },
  {
    id: "bubble",
    label: "Bubble",
    fragSource: bubbleFrag,
    randomize: () => ({
      ...baseParams(),
      warp: rand(0.4, 1.0),
      blend: rand(0.4, 1.0),
      colors: galaxyFive([0.55, 0.85], [0.4, 0.6]),
    }),
  },
  {
    id: "prismatic",
    label: "Prismatique",
    fragSource: prismaticFrag,
    randomize: () => ({
      ...baseParams(),
      warp: rand(0.8, 1.6), // angular sweep range
      blend: rand(0.6, 1.1),
      paramA: rand(0.0, 1.0), // origin position along the top edge
      paramB: rand(0.3, 1.0), // beam width
      colors: galaxyFive([0.7, 0.95], [0.4, 0.6]),
    }),
  },
  {
    id: "glass-structure",
    label: "Glass structure",
    fragSource: glassStructureFrag,
    randomize: () => ({
      ...baseParams(),
      warp: rand(0.6, 1.8), // oblique angle range
      paramA: rand(0.3, 1.0), // reveal/stagger speed
      paramB: rand(0.2, 0.8), // grid line density
      blend: rand(0.3, 0.8), // base rectangle opacity
      grain: rand(0.15, 0.5), // grid line visibility
      colors: galaxyFive([0.4, 0.7], [0.2, 0.4]),
    }),
  },
];
