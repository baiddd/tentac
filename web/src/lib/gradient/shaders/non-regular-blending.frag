// Two independent noise fields at different frequencies, combined
// nonlinearly (product + threshold) so color regions bleed into each
// other with irregular, asymmetric boundaries instead of smooth bands.
// Only the upper range of the combined field is lit — most of the
// frame stays near-black space between the color patches.
void main() {
  vec2 p = vUv - 0.5;
  p.x *= uResolution.x / uResolution.y;

  float t = uTime * uSpeed * 0.1;
  vec2 warped = domainWarp(p * uScale, uWarp, t + uSeed);

  float a = fbm(warped, 3);
  float b = fbm(warped * 1.7 + 11.3, 3);
  float n = a * b + 0.5 * a - 0.3 * b;
  n = n * 0.5 + 0.5;

  float edge = 0.06 + uGrain * 0.2;
  vec3 spaceBlack = vec3(0.008, 0.01, 0.02);
  vec3 color = spaceBlack;
  color = mix(color, uColor0, smoothstep(0.58 - edge, 0.58 + edge, n));
  color = mix(color, uColor1, smoothstep(0.68 - edge, 0.68 + edge, n));
  color = mix(color, uColor2, smoothstep(0.78 - edge, 0.78 + edge, n));
  color = mix(color, uColor3, smoothstep(0.9 - edge, 0.9 + edge, n));

  gl_FragColor = vec4(color, 1.0);
}
