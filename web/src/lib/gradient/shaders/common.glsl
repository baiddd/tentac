// Shared GLSL helpers, textually prepended to every style's .frag source
// (WebGL1 / GLSL ES 1.00 has no #include, so engine.ts concatenates this
// file's text in front of each style before compiling). Keep this file
// free of a main() — it only declares uniforms + reusable functions so
// individual style shaders can pick whichever subset they need.

precision highp float;

varying vec2 vUv;

uniform float uTime;
uniform vec2 uResolution;
uniform float uSeed;

// Up to 5 palette stops — not every style uses all 5.
uniform vec3 uColor0;
uniform vec3 uColor1;
uniform vec3 uColor2;
uniform vec3 uColor3;
uniform vec3 uColor4;

uniform float uWarp;   // domain-warp intensity
uniform float uScale;  // base noise frequency
uniform float uSpeed;  // flow speed multiplier
uniform float uGrain;  // fine-noise / texture amount
uniform float uBlend;  // per-style blend-mode intensity
uniform float uParamA; // free per-style knob (e.g. posterize levels, cell density)
uniform float uParamB; // free per-style knob (e.g. chromatic split, bubble radius)
uniform float uParamC; // free per-style knob (e.g. perspective strength)

// Pointer position in the same 0..1 space as vUv (y already flipped to
// match — see engine.ts's pointermove handler), and seconds since the
// current style was activated (reset on style switch and on Randomize) —
// used by styles with a hover reaction or a one-shot reveal animation.
uniform vec2 uMouse;
uniform float uStyleTime;

// ---------------------------------------------------------------- hashing

float hash1(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

vec2 hash2(vec2 p) {
  return vec2(
    hash1(p),
    hash1(p + vec2(19.19, 7.77))
  );
}

// ------------------------------------------------------------- 2D simplex

vec3 permute3(vec3 x) { return mod((x * 34.0 + 1.0) * x, 289.0); }

float snoise(vec2 v) {
  const vec4 C = vec4(0.211324865405187, 0.366025403784439,
                       -0.577350269189626, 0.024390243902439);
  vec2 i  = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod(i, 289.0);
  vec3 p = permute3(permute3(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
  vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x12.xy, x12.xy), dot(x12.zw, x12.zw)), 0.0);
  m = m * m;
  m = m * m;
  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 ox = floor(x + 0.5);
  vec3 a0 = x - ox;
  m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
  vec3 g;
  g.x = a0.x * x0.x + h.x * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;
  return 130.0 * dot(m, g);
}

// fractal Brownian motion — layered noise, more octaves = more detail
float fbm(vec2 p, int octaves) {
  float value = 0.0;
  float amplitude = 0.5;
  for (int i = 0; i < 8; i++) {
    if (i >= octaves) break;
    value += amplitude * snoise(p);
    p *= 2.02;
    amplitude *= 0.5;
  }
  return value;
}

// Displaces `p` by a second noise field before sampling a first — the
// technique behind every "organic flow" look on this page.
vec2 domainWarp(vec2 p, float amount, float t) {
  vec2 q = vec2(
    fbm(p + vec2(0.0, 0.0) + t, 3),
    fbm(p + vec2(5.2, 1.3) - t, 3)
  );
  return p + amount * q;
}

// -------------------------------------------------------------- worley

// Cellular noise: distance from `p` to the nearest of its jittered grid
// neighbors. Used by the faceted / glass-structure look.
float worley(vec2 p) {
  vec2 cell = floor(p);
  float minDist = 8.0;
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      vec2 neighbor = vec2(float(x), float(y));
      vec2 point = hash2(cell + neighbor);
      vec2 diff = neighbor + point - fract(p);
      minDist = min(minDist, length(diff));
    }
  }
  return minDist;
}

// ------------------------------------------------------------- palette

vec3 palette5(float t, vec3 c0, vec3 c1, vec3 c2, vec3 c3, vec3 c4) {
  t = clamp(t, 0.0, 1.0) * 4.0;
  if (t < 1.0) return mix(c0, c1, t);
  if (t < 2.0) return mix(c1, c2, t - 1.0);
  if (t < 3.0) return mix(c2, c3, t - 2.0);
  return mix(c3, c4, t - 3.0);
}

vec3 palette3(float t, vec3 c0, vec3 c1, vec3 c2) {
  t = clamp(t, 0.0, 1.0) * 2.0;
  if (t < 1.0) return mix(c0, c1, t);
  return mix(c1, c2, t - 1.0);
}

// ---------------------------------------------------------- blend modes

vec3 blendScreen(vec3 base, vec3 blend) {
  return 1.0 - (1.0 - base) * (1.0 - blend);
}

vec3 blendOverlay(vec3 base, vec3 blend) {
  return mix(
    2.0 * base * blend,
    1.0 - 2.0 * (1.0 - base) * (1.0 - blend),
    step(0.5, base)
  );
}

vec3 blendSoftLight(vec3 base, vec3 blend) {
  return mix(
    2.0 * base * blend + base * base * (1.0 - 2.0 * blend),
    sqrt(base) * (2.0 * blend - 1.0) + 2.0 * base * (1.0 - blend),
    step(0.5, blend)
  );
}

vec3 posterize(vec3 color, float levels) {
  return floor(color * levels) / levels;
}

// ------------------------------------------------------------ geometry

mat2 rot2(float a) {
  float c = cos(a);
  float s = sin(a);
  return mat2(c, -s, s, c);
}

// Signed distance to an axis-aligned box centered at origin, half-size b
// (rotate/translate `p` first for an oriented box elsewhere).
float sdBox(vec2 p, vec2 b) {
  vec2 d = abs(p) - b;
  return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}
