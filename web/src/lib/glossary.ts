const glossaryModules = import.meta.glob<{ default: Record<string, string> }>(
  "../../../data/glossary.json",
  { eager: true }
);

const glossaryData: Record<string, string> = Object.values(glossaryModules)[0]?.default ?? {};

interface GlossaryEntry {
  term: string;
  definition: string;
}

// Longer terms first, so "Gaussian Splatting" claims its span before a
// shorter term could also match inside the same text.
const GLOSSARY: GlossaryEntry[] = Object.entries(glossaryData)
  .map(([term, definition]) => ({ term, definition }))
  .sort((a, b) => b.term.length - a.term.length);

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

interface Span {
  start: number;
  end: number;
  term: string;
}

/**
 * Wrap the first occurrence of each glossary term found in `text` with a
 * <span class="glossary-term" data-definition="..."> so the client-side
 * popover script (see Layout.astro) can show a definition on hover, focus,
 * or tap. Word-boundary-safe (won't match "RAG" inside "storage") and
 * tolerant of surrounding punctuation, same approach as the pipeline's
 * relevance-keyword filter. Only the first match per term is annotated —
 * a sentence that repeats an acronym doesn't need it glossed twice.
 */
export function annotateGlossary(text: string): string {
  const spans: Span[] = [];
  const claimed = new Set<string>();

  for (const { term } of GLOSSARY) {
    if (claimed.has(term)) continue;
    const pattern = new RegExp(`(?<![a-zA-Z0-9])${escapeRegExp(term)}(?![a-zA-Z0-9])`, "i");
    const match = pattern.exec(text);
    if (!match) continue;
    const start = match.index;
    const end = start + match[0].length;
    if (spans.some((span) => start < span.end && end > span.start)) continue;
    spans.push({ start, end, term });
    claimed.add(term);
  }

  if (spans.length === 0) return escapeHtml(text);

  spans.sort((a, b) => a.start - b.start);
  const definitionByTerm = new Map(GLOSSARY.map((entry) => [entry.term, entry.definition]));

  let html = "";
  let cursor = 0;
  for (const span of spans) {
    html += escapeHtml(text.slice(cursor, span.start));
    const original = text.slice(span.start, span.end);
    const definition = definitionByTerm.get(span.term) ?? "";
    html += `<span class="glossary-term" tabindex="0" data-definition="${escapeHtml(definition)}">${escapeHtml(original)}</span>`;
    cursor = span.end;
  }
  html += escapeHtml(text.slice(cursor));
  return html;
}
