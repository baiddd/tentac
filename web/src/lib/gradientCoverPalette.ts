// Section accent colors derived from the generated WebGL cover gradient
// (src/lib/gradient/) instead of extracting them from a static cover
// image (see coverPalette.ts, now unused by the homepage hero) — keeps
// the section accents visually consistent with whatever gradient style
// is actually painted behind that issue's own cover (each issue can have
// a different style/palette — see gradient/issueCover.ts).
import type { GradientParams } from "./gradient/styles";

const SECTION_ORDER = [
  "llm",
  "vision",
  "multimodal",
  "systems",
  "science",
  "security",
  "safety",
  "industry",
] as const;

export type SectionPalette = Partial<Record<(typeof SECTION_ORDER)[number], string>>;

function toHex(r: number, g: number, b: number): string {
  const channel = (v: number) => Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16).padStart(2, "0");
  return `#${channel(r)}${channel(g)}${channel(b)}`;
}

// Hue in degrees [0, 360) for an RGB triple in [0,1].
function hue(r: number, g: number, b: number): number {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  if (d === 0) return 0;
  let h: number;
  if (max === r) h = ((g - b) / d) % 6;
  else if (max === g) h = (b - r) / d + 2;
  else h = (r - g) / d + 4;
  h *= 60;
  return h < 0 ? h + 360 : h;
}

// A gradient's color list always includes near-black "base" stops (the
// shader's background layer, not a highlight) and sometimes a near-white/
// grey stop — neither reads as a usable section accent. Teal/cyan
// (~150-210°) is excluded on top of that: it reads as cold/technical and
// clashes with the warm editorial look, a call already made explicitly
// for aurora's palette — kept as a general rule (not aurora-specific)
// since any style can produce a stop in that range.
function isUsableAccent([r, g, b]: [number, number, number]): boolean {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  if (max <= 0.15) return false; // near-black base stop
  if (max - min <= 0.06) return false; // near-grey/white, not a real color accent
  const h = hue(r, g, b);
  if (h >= 150 && h <= 210) return false; // teal/cyan
  return true;
}

// One single accent for the whole issue, applied to every section — not
// cycled per section. A style's palette can hold several genuinely
// different hues at once (e.g. non-regular-blending's violet/blue/pink/
// cyan/magenta), and cycling through all of them per-section reads as
// arbitrary/multicolor rather than "this issue's color"; picking the most
// saturated usable stop gives one representative, consistent accent
// instead. Falls back to an empty palette (caller's default accent) if
// the style's palette has no usable color at all.
function saturation([r, g, b]: [number, number, number]): number {
  return Math.max(r, g, b) - Math.min(r, g, b);
}

export function getGradientCoverPalette(params: GradientParams): SectionPalette {
  const colors = params.colors.filter(isUsableAccent);
  if (colors.length === 0) return {};
  const [r, g, b] = [...colors].sort((a, b) => saturation(b) - saturation(a))[0];
  const accent = toHex(r, g, b);
  const palette: SectionPalette = {};
  for (const key of SECTION_ORDER) palette[key] = accent;
  return palette;
}
