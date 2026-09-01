// Multi-step vertical linear gradient (5 soft-blended stops) standing in
// for a horizon/sky. The whole gradient slowly sways up and down
// (bounded sine, so it never scrolls off and never seams) — read at any
// fixed point on screen, that sway alone reads as a slow, imperceptible
// hue transition, like time passing from dusk to dawn.
void main() {
  float driftAmp = 0.06 + uWarp * 0.1;
  float drift = driftAmp * sin(uTime * uSpeed * 0.04 + uSeed);
  float v = clamp(vUv.y + drift, 0.0, 1.0);

  vec3 color = palette5(v, uColor0, uColor1, uColor2, uColor3, uColor4);

  // Fine dither to keep the smooth gradient from banding.
  float dither = (hash1(gl_FragCoord.xy) - 0.5) * (0.01 + uGrain * 0.02);
  color += dither;

  gl_FragColor = vec4(color, 1.0);
}
