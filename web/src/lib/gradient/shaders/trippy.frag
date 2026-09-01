// Fast, strong warp with a rotating sample coordinate and a saturated
// galaxy palette — psychedelic swirl blooming out of near-black space
// rather than filling the whole frame.
void main() {
  vec2 p = vUv - 0.5;
  p.x *= uResolution.x / uResolution.y;

  float t = uTime * uSpeed * 0.25;

  float angle = t * 0.3 + length(p) * 2.0;
  float ca = cos(angle);
  float sa = sin(angle);
  vec2 rp = mat2(ca, -sa, sa, ca) * p * uScale;

  vec2 warped = domainWarp(rp, uWarp * 1.6, t + uSeed);
  float n = fbm(warped * 1.5, 4) * 0.5 + 0.5;

  vec3 spaceBlack = vec3(0.008, 0.01, 0.02);
  vec3 swirl = palette5(fract(n + t * 0.05), uColor0, uColor1, uColor2, uColor3, uColor4);
  float exposure = smoothstep(0.5, 0.88, n);
  vec3 color = mix(spaceBlack, swirl, exposure);

  float grain = (hash1(gl_FragCoord.xy + uTime) - 0.5) * uGrain;
  color += grain * exposure;

  gl_FragColor = vec4(color, 1.0);
}
