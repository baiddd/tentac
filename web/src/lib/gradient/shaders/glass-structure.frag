// Swiss-grid composition (Josef Müller-Brockmann style): oblique
// overlapping rectangles, each with a semi-transparent gradient fill,
// painted in sequence over a faint grid. On style activation each
// rectangle slides in along the same diagonal, staggered by index
// (uStyleTime gates each one's local reveal progress); hovering a
// rectangle boosts its opacity.
#define RECT_COUNT 7

void main() {
  vec2 p = vUv - 0.5;
  float aspect = uResolution.x / uResolution.y;
  p.x *= aspect;

  vec2 mouseP = uMouse - 0.5;
  mouseP.x *= aspect;

  vec3 spaceBlack = vec3(0.006, 0.008, 0.016);

  // Faint grid guides, Swiss-poster style.
  float gridDensity = 6.0 + uParamB * 8.0;
  vec2 gridUv = fract(vUv * gridDensity);
  float gridLine = min(gridUv.x, gridUv.y);
  float grid = (1.0 - smoothstep(0.0, 0.02, gridLine)) * (0.03 + uGrain * 0.05);
  vec3 color = spaceBlack + grid;

  vec2 slideDir = normalize(vec2(-1.0, -1.0));
  float revealSpeed = 0.5 + uParamA * 1.2;
  float staggerGap = 0.18;

  for (int i = 0; i < RECT_COUNT; i++) {
    float fi = float(i);
    vec2 seed = vec2(fi * 17.3 + uSeed, fi * 91.7 - uSeed);

    float angle = (hash1(seed) - 0.5) * (0.3 + uWarp * 0.3);
    float width = mix(0.28, 0.6, hash1(seed + 1.1)) * uScale * 4.0;
    float height = mix(0.07, 0.2, hash1(seed + 2.2));

    float gridT = fi / float(RECT_COUNT - 1);
    vec2 jitter = (hash2(seed + 4.4) - 0.5) * 0.25;
    vec2 targetPos = mix(vec2(-0.35, -0.22), vec2(0.35, 0.22), gridT) + jitter;
    vec2 startPos = targetPos + slideDir * 1.3;

    float delay = fi * staggerGap;
    float localProgress = clamp((uStyleTime - delay) * revealSpeed, 0.0, 1.0);
    float eased = smoothstep(0.0, 1.0, localProgress);
    vec2 currentPos = mix(startPos, targetPos, eased);

    vec2 lp = rot2(-angle) * (p - currentPos);
    float hw = width * 0.5;
    float hh = height * 0.5;
    float sdf = sdBox(lp, vec2(hw, hh));
    float shapeMask = 1.0 - smoothstep(0.0, 0.015, sdf);

    float localT = clamp(lp.x / max(hw, 0.001) * 0.5 + 0.5, 0.0, 1.0);
    vec3 rectColor = palette5(mix(gridT, localT, 0.4), uColor0, uColor1, uColor2, uColor3, uColor4);

    float baseAlpha = 0.3 + uBlend * 0.3;
    float hoverBoost = smoothstep(0.5, 0.0, length(mouseP - currentPos)) * 0.5;
    float alpha = clamp(baseAlpha + hoverBoost, 0.0, 1.0);

    color = mix(color, rectColor, shapeMask * alpha * eased);
  }

  gl_FragColor = vec4(color, 1.0);
}
