import type { ImageMetadata } from "astro";
import weekThemesData from "../data/week-themes.json";

// See web/src/assets/covers/README.md for the naming convention and the
// week-themes.json schema. Both are optional per week — everything here
// falls back to "nothing customized for this week" so a week with no
// cover image and no theme entry renders identically to before this
// feature existed.
const coverModules = import.meta.glob<{ default: ImageMetadata }>(
  "../assets/covers/*.{jpg,jpeg,png,webp}",
  { eager: true }
);

export interface WeekTheme {
  /** Overrides --accent (links, hover states). */
  accent?: string;
  /** Overrides --text (body text color). */
  text?: string;
  /** Overrides --bar (the vertical accent bar on cards). Defaults to
   * whatever --accent resolves to if not set, same as before this field
   * existed — set this explicitly when you want the bar to differ from
   * the accent color used elsewhere (e.g. for links). */
  bar?: string;
}

const weekThemes = weekThemesData as Record<string, WeekTheme>;

function weekFromCoverPath(path: string): string | null {
  const match = path.match(/(\d{4}-W\d{2})\.[a-zA-Z]+$/);
  return match ? match[1] : null;
}

const coverByWeek = new Map<string, ImageMetadata>();
for (const [path, mod] of Object.entries(coverModules)) {
  const week = weekFromCoverPath(path);
  if (week) coverByWeek.set(week, mod.default);
}

export function getCoverImage(week: string): ImageMetadata | undefined {
  return coverByWeek.get(week);
}

export function getWeekTheme(week: string): WeekTheme {
  return weekThemes[week] ?? {};
}
