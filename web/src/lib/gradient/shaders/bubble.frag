// Spherical shapes with an ultra-thin luminous rim and a subtle internal
// gradient on near-black space. Each bubble drifts organically and its
// radius wobbles slightly over time (soft-body morphing); the rim's
// brightness varies by angle around the bubble against a fixed "light"
// direction, so refraction reads as coming from one side rather than a
// uniform glow ring.
#define BUBBLE_COUNT 6

void main() {
  // Deliberately NOT scaled by uScale: bubble centers/radii live in a
  // fixed -0.7..0.7 space sized to fit the view — see the note that used
  // to live here about the 1/d^2 metaball blowup this avoids.
  vec2 p = vUv - 0.5;
  p.x *= uResolution.x / uResolution.y;

  float t = uTime * uSpeed * 0.2;
  vec2 lightDir = normalize(vec2(-0.5, 0.7));

  float bestAbsD = 1e6;
  float bestD = 1e6;
  float bestRadius = 0.1;
  vec2 bestCenter = vec2(0.0);
  float bestHue = 0.0;

  for (int i = 0; i < BUBBLE_COUNT; i++) {
    float fi = float(i);
    vec2 seed = vec2(fi * 12.9 + uSeed, fi * 78.2 - uSeed);
    vec2 center = (hash2(seed) - 0.5) * 1.3;
    center += 0.15 * vec2(
      sin(t * (0.4 + fi * 0.08) + fi),
      cos(t * (0.3 + fi * 0.06) + fi * 1.7)
    );

    float wobble = 1.0 + 0.08 * sin(uTime * uSpeed * (0.6 + fi * 0.1) + fi * 3.0);
    float radius = (0.09 + hash1(seed + 3.1) * 0.1 * (0.5 + uWarp * 0.5)) * wobble;

    float d = length(p - center) - radius;
    if (abs(d) < bestAbsD) {
      bestAbsD = abs(d);
      bestD = d;
      bestRadius = radius;
      bestCenter = center;
      bestHue = hash1(seed + 9.4);
    }
  }

  vec3 bubbleColor = palette5(bestHue, uColor0, uColor1, uColor2, uColor3, uColor4);

  float insideMask = 1.0 - smoothstep(-0.006, 0.006, bestD);
  float innerT = clamp(-bestD / max(bestRadius, 0.001), 0.0, 1.0);
  vec3 fill = mix(bubbleColor * 0.35, bubbleColor * 0.65, innerT);

  float rimWidth = 0.006 + uGrain * 0.01;
  float rim = exp(-(bestD * bestD) / (rimWidth * rimWidth));
  vec2 dir = bestAbsD < 1e5 ? normalize(p - bestCenter) : vec2(0.0);
  float angleFactor = clamp(dot(dir, lightDir) * 0.5 + 0.5, 0.0, 1.0);
  float rimBrightness = rim * mix(0.2, 1.3, pow(angleFactor, 1.4)) * (0.6 + uBlend * 0.6);

  vec3 spaceBlack = vec3(0.006, 0.008, 0.016);
  vec3 color = mix(spaceBlack, fill, insideMask * 0.5);
  color += bubbleColor * rimBrightness;

  gl_FragColor = vec4(color, 1.0);
}
