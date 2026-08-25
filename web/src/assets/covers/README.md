# Weekly cover images

Drop an image here named after the week it's for, e.g.:

```
web/src/assets/covers/2026-W35.jpg
```

Supported extensions: `.jpg`, `.jpeg`, `.png`, `.webp`.

If a week has a matching cover image, it's shown as a banner at the top of
that week's page (homepage when it's the latest week, and its permalink
page under `/w/<week>`). If no image exists for a week, the page renders
exactly as it does today — no cover, no layout change.

## Optional accent color per week

To also override the site's accent color for a specific week, add an entry
to `web/src/data/week-themes.json`:

```json
{
  "2026-W35": { "accent": "#ff8a5c" }
}
```

Any week without an entry uses the site's default accent color
(`--accent` in `web/src/styles/global.css`). The `accent` value can be any
valid CSS color.
