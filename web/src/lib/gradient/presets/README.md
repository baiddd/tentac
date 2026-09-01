# Gradient presets

Drop a `<style-id>.json` here (e.g. `mesh.json`, `glass-structure.json`) —
the exact shape the gradient lab's **Save** button downloads — to bake in
a chosen set of parameters as that style's default for everyone, not just
the browser that saved it.

Resolution order when the lab loads a style (see `engine.ts`):

1. This browser's own saved tweak (`localStorage`, set by Save)
2. A committed preset from this folder
3. A fresh `randomize()`

**Reset to default** (the lab's Reset button) clears step 1 and falls
back to step 2, then step 3.

Style ids match `GRADIENT_STYLES` in `../styles.ts`: `mesh`, `landscape`,
`non-regular-blending`, `retro`, `trippy`, `neon-flow`, `aurora`,
`crystal-light`, `galaxy`, `glass-fractal`, `bubble`, `prismatic`,
`glass-structure`.
