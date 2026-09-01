// Synthwave silhouette: posterized warm bands rising out of near-black,
// like a distant sun over a dark horizon, plus horizontal scanline grain.
void main() {
  vec2 p = vUv - 0.5;
  p.x *= uResolution.x / uResolution.y;

  float t = uTime * uSpeed * 0.06;
  vec2 warped = domainWarp(p * uScale * 0.6, uWarp * 0.5, t + uSeed);
  float n = fbm(warped, 3) * 0.5 + 0.5;

  float levels = max(3.0, uParamA);
  n = floor(n * levels) / levels;

  vec3 spaceBlack = vec3(0.008, 0.01, 0.02);
  vec3 nebula = palette5(n, uColor0, uColor1, uColor2, uColor3, uColor4);
  float exposure = smoothstep(0.42, 0.8, n);
  vec3 color = mix(spaceBlack, nebula, exposure);
  color = posterize(color, 6.0);

  float scanline = sin(gl_FragCoord.y * 1.5) * 0.5 + 0.5;
  color -= scanline * uGrain * 0.15 * exposure;

  gl_FragColor = vec4(color, 1.0);
}
