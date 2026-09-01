// Resolves a specific issue's cover style+params, and makes it permanent
// the first time it's resolved.
//
// Rule: if `presets/issues/<week>.json` already exists, that file is the
// issue's cover — forever, unchanged by any later edit to the generator or
// to any style's randomize(). If it doesn't exist yet, one is generated
// deterministically (seeded from the week string, so the same week always
// produces the same result even before the file exists) and written to
// disk immediately, which is what makes it permanent: the next build finds
// the file and just reads it. Once committed to git, that's the issue's
// history — exactly like data/<week>.json.
//
// Runs server-side only (Astro frontmatter/build, Node has fs) — never
// import this from a client <script>.
import fs from "node:fs";
import path from "node:path";
import { GRADIENT_STYLES, withSeededRandom, withParamDefaults, type GradientParams } from "./styles";

// Resolved from the Astro project root (process.cwd() when `astro build`/
// `astro dev` runs), not from import.meta.url — Vite bundles this module
// into a build-specific output location, so a path derived from its own
// URL would silently stop pointing at the real source tree once bundled,
// making every build re-generate instead of reading back what was saved.
const ISSUES_DIR = path.join(process.cwd(), "src/lib/gradient/presets/issues");

export interface IssueCover {
  styleId: string;
  params: GradientParams;
}

// FNV-1a string hash -> 32-bit seed. Same week string always hashes the
// same way, so the generated cover is reproducible even before its file
// is written (e.g. across a `astro build` that runs pages in parallel).
function seedFromWeek(week: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < week.length; i++) {
    h ^= week.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

function generate(week: string): IssueCover {
  const seed = seedFromWeek(week);
  return withSeededRandom(seed, () => {
    const style = GRADIENT_STYLES[seed % GRADIENT_STYLES.length];
    return { styleId: style.id, params: style.randomize() };
  });
}

export function getIssueCover(week: string): IssueCover {
  const file = path.join(ISSUES_DIR, `${week}.json`);
  if (fs.existsSync(file)) {
    const raw = JSON.parse(fs.readFileSync(file, "utf-8")) as IssueCover;
    return { styleId: raw.styleId, params: withParamDefaults(raw.params) };
  }
  const cover = generate(week);
  fs.mkdirSync(ISSUES_DIR, { recursive: true });
  fs.writeFileSync(file, JSON.stringify(cover, null, 2) + "\n");
  return cover;
}
