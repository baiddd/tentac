// Dark navy sky + vertical flowing curtains of color, screen-blended
// like the northern lights.
void main() {
  vec2 p = vUv - 0.5;
  p.x *= uResolution.x / uResolution.y;

  float t = uTime * uSpeed * 0.1;

  // Stretch noise vertically so curtains read as tall flowing bands.
  vec2 cp = vec2(p.x * uScale * 1.5, p.y * uScale * 0.3 + t);
  vec2 warped = domainWarp(cp, uWarp, t + uSeed);
  float n = fbm(warped, 4) * 0.5 + 0.5;

  // Curtains fade toward the top and bottom of the frame, and only the
  // brighter noise ridges light up — kept sparse so black space still
  // dominates between curtains.
  float verticalFade = smoothstep(0.55, -0.1, abs(p.y));
  float exposure = smoothstep(0.45, 0.82, n);

  vec3 curtain = palette3(n, uColor0, uColor1, uColor2);
  vec3 base = uColor4 * 0.08;

  vec3 color = blendScreen(base, curtain * exposure * verticalFade * (0.6 + uBlend * 0.6));

  float grain = (hash1(gl_FragCoord.xy + uTime) - 0.5) * uGrain * 0.3;
  color += grain;

  gl_FragColor = vec4(color, 1.0);
}
