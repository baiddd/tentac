// Crystal light in the dark: a near-black field with soft, gently
// warped color glints — refracted light rather than a flat pastel wash.
// No sparkle points (removed, they read as scattered white noise);
// uGrain now adds a subtle texture to the glint itself instead.
void main() {
  vec2 p = vUv - 0.5;
  p.x *= uResolution.x / uResolution.y;

  float t = uTime * uSpeed * 0.06;
  vec2 warped = domainWarp(p * uScale * 0.7, uWarp * 0.4, t + uSeed);
  float n = fbm(warped, 3) * 0.5 + 0.5;

  vec3 spaceBlack = vec3(0.008, 0.01, 0.02);
  vec3 glint = palette5(n, uColor0, uColor1, uColor2, uColor3, uColor4);
  float exposure = smoothstep(0.55, 0.88, n);
  vec3 color = mix(spaceBlack, glint, exposure * 0.8);

  float texture = (hash1(gl_FragCoord.xy * 0.5) - 0.5) * uGrain * 0.06;
  color += texture * exposure;

  gl_FragColor = vec4(color, 1.0);
}
