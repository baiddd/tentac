// Classic mesh gradient, reworked as a nebula: warped noise field, but
// only the upper range of the field is lit — most of the frame stays
// near-black space, with soft mesh-colored clouds blooming through.
//
// Colors: c0-c3 are one majority hue family; c4 is its complementary
// accent (see styles.ts). The accent is driven by its OWN independent
// noise field, thresholded into visible patches — mixing it in via the
// main field's rare extreme tail (n approaching 1.0) made it show up
// as an almost-invisible sliver on most draws, not the "touches of
// orange" the majority color is supposed to have running through it.
void main() {
  vec2 p = vUv - 0.5;
  p.x *= uResolution.x / uResolution.y;
  p *= uScale;

  float t = uTime * uSpeed * 0.1;
  vec2 warped = domainWarp(p, uWarp, t + uSeed);
  float n = fbm(warped, 4);
  n = n * 0.5 + 0.5;

  // Majority color: capped below palette5's c3->c4 segment so it stays
  // within the c0-c3 family on its own, never drifting into the accent.
  vec3 majority = palette5(min(n, 0.74), uColor0, uColor1, uColor2, uColor3, uColor4);

  // Complementary accent: independent noise field, thresholded into
  // patches rather than left to the main field's rare tail. uBlend
  // controls how much of it shows (more blend -> lower threshold ->
  // bigger touches of the complementary color).
  vec2 warped2 = domainWarp(p * 1.3 + 31.4, uWarp * 0.8, t * 0.7 + uSeed * 1.7);
  float accentField = fbm(warped2, 3) * 0.5 + 0.5;
  float accentThreshold = mix(0.82, 0.58, clamp(uBlend / 1.4, 0.0, 1.0));
  float accentMask = smoothstep(accentThreshold, accentThreshold + 0.12, accentField);
  vec3 nebula = mix(majority, uColor4, accentMask * 0.85);

  vec3 spaceBlack = vec3(0.008, 0.01, 0.02);
  float exposure = smoothstep(0.52, 0.92, n);
  vec3 color = mix(spaceBlack, nebula, exposure);

  float grain = (hash1(gl_FragCoord.xy + uTime) - 0.5) * uGrain;
  color += grain * exposure;

  gl_FragColor = vec4(color, 1.0);
}
