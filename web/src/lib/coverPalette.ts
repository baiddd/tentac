import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";

// Automatically derives one accent color per section from a week's cover
// image — no manual color picking. "Search the image with an eyedropper":
// bucket every pixel by hue, keep the most saturated/populous well-
// separated hues, darken each until it's readable under white text, then
// assign them to sections in a stable hue-sorted order so the palette
// reads as a natural sweep down the page. A week with no cover image gets
// no per-section palette — sections just use the site's default accent,
// same as before this feature existed.

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

// Resolved from the project root (Astro always runs `astro build`/`astro
// dev` with cwd set to the project — see package.json's scripts and
// deploy.yml's `working-directory: web`), not from import.meta.url: Vite
// bundles this module into a build-time chunk under dist/.prerender/ during
// `astro build`, which would silently move an import.meta.url-relative path
// away from the real src/assets/covers/ and make every week's cover
// undiscoverable in production (it still worked in `astro dev`, where this
// module runs unbundled from its source location — that's how this went
// unnoticed).
const COVERS_DIR = path.join(process.cwd(), "src/assets/covers/");
const COVER_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];

const BUCKET_SIZE_DEG = 15;
const MIN_HUE_SEPARATION_DEG = 12;
const MIN_SATURATION = 0.25;
const MIN_LIGHTNESS = 0.12;
const MAX_LIGHTNESS = 0.85;
const MIN_CONTRAST_VS_WHITE = 3.0;
const STARTING_LIGHTNESS = 0.42;
const MAX_ACCENT_SATURATION = 0.85;

function findCoverFile(week: string): string | null {
  for (const ext of COVER_EXTENSIONS) {
    const candidate = path.join(COVERS_DIR, `${week}${ext}`);
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  r /= 255;
  g /= 255;
  b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;
  const d = max - min;
  if (d !== 0) {
    s = d / (1 - Math.abs(2 * l - 1));
    switch (max) {
      case r:
        h = ((g - b) / d) % 6;
        break;
      case g:
        h = (b - r) / d + 2;
        break;
      default:
        h = (r - g) / d + 4;
    }
    h *= 60;
    if (h < 0) h += 360;
  }
  return [h, s, l];
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r: number, g: number, b: number;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
}

function toHex(r: number, g: number, b: number): string {
  return "#" + [r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("");
}

// WCAG relative luminance / contrast ratio against white (#fff) — used to
// make sure white heading/body text stays readable on each accent color.
function relativeLuminance(r: number, g: number, b: number): number {
  const channel = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}
function contrastVsWhite(r: number, g: number, b: number): number {
  return 1.05 / (relativeLuminance(r, g, b) + 0.05);
}

interface HueCandidate {
  hue: number;
  saturation: number;
  weight: number;
}

async function extractHueCandidates(imagePath: string): Promise<HueCandidate[]> {
  const { data, info } = await sharp(imagePath)
    .resize(80, 80, { fit: "inside" })
    .raw()
    .toBuffer({ resolveWithObject: true });

  const buckets = new Map<number, { count: number; satSum: number; hueSum: number }>();
  for (let i = 0; i < data.length; i += info.channels) {
    const [h, s, l] = rgbToHsl(data[i], data[i + 1], data[i + 2]);
    if (s < MIN_SATURATION || l < MIN_LIGHTNESS || l > MAX_LIGHTNESS) continue;
    const bucket = Math.floor(h / BUCKET_SIZE_DEG);
    const entry = buckets.get(bucket) ?? { count: 0, satSum: 0, hueSum: 0 };
    entry.count += 1;
    entry.satSum += s;
    entry.hueSum += h;
    buckets.set(bucket, entry);
  }

  return [...buckets.values()]
    .map((e) => ({
      hue: e.hueSum / e.count,
      saturation: e.satSum / e.count,
      weight: e.count * (e.satSum / e.count),
    }))
    .sort((a, b) => b.weight - a.weight);
}

function hueDistance(a: number, b: number): number {
  const d = Math.abs(a - b);
  return Math.min(d, 360 - d);
}

function pickDistinctHues(candidates: HueCandidate[], count: number): HueCandidate[] {
  const chosen: HueCandidate[] = [];
  for (const candidate of candidates) {
    if (chosen.length >= count) break;
    const tooClose = chosen.some((c) => hueDistance(c.hue, candidate.hue) < MIN_HUE_SEPARATION_DEG);
    if (!tooClose) chosen.push(candidate);
  }
  // An image with a narrow hue range (e.g. all warm tones) may not offer
  // `count` well-separated hues — cycle through what's genuinely present
  // rather than fabricate a hue that isn't in the source image.
  for (let i = 0; chosen.length < count && candidates.length > 0; i++) {
    chosen.push(candidates[i % candidates.length]);
  }
  return chosen.sort((a, b) => a.hue - b.hue);
}

function toAccentColor({ hue, saturation }: HueCandidate): string {
  let lightness = STARTING_LIGHTNESS;
  let [r, g, b] = hslToRgb(hue, Math.min(saturation, MAX_ACCENT_SATURATION), lightness);
  while (contrastVsWhite(r, g, b) < MIN_CONTRAST_VS_WHITE && lightness > 0.08) {
    lightness -= 0.02;
    [r, g, b] = hslToRgb(hue, Math.min(saturation, MAX_ACCENT_SATURATION), lightness);
  }
  return toHex(r, g, b);
}

const paletteCache = new Map<string, Promise<SectionPalette>>();

export function getSectionPalette(week: string): Promise<SectionPalette> {
  const cached = paletteCache.get(week);
  if (cached) return cached;

  const promise = (async (): Promise<SectionPalette> => {
    const coverPath = findCoverFile(week);
    if (!coverPath) return {};

    const candidates = await extractHueCandidates(coverPath);
    if (candidates.length === 0) return {};

    const chosen = pickDistinctHues(candidates, SECTION_ORDER.length);
    const palette: SectionPalette = {};
    chosen.forEach((candidate, i) => {
      palette[SECTION_ORDER[i]] = toAccentColor(candidate);
    });
    return palette;
  })();

  paletteCache.set(week, promise);
  return promise;
}
