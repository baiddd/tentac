// Superimposed circular/elliptical "orbit" rings, each independently
// rotated and squashed (simulating a different tilt around its own Z
// axis) with a soft radial glow and a peripheral halo, plus a pulsing
// core at the center — read as overlapping orbiting rings rather than
// a nebula cloud.
#define TWO_PI 6.2831853
#define RING_COUNT 5

void main() {
  vec2 p = vUv - 0.5;
  p.x *= uResolution.x / uResolution.y;

  vec3 spaceBlack = vec3(0.006, 0.008, 0.016);
  vec3 glowSum = vec3(0.0);

  for (int i = 0; i < RING_COUNT; i++) {
    float fi = float(i);
    float seedI = fi + uSeed;

    float squash = mix(0.22, 1.0, hash1(vec2(seedI, 1.0)));
    float rotSpeed = (hash1(vec2(seedI, 2.0)) - 0.5) * 0.5;
    float rotAngle = hash1(vec2(seedI, 3.0)) * TWO_PI + uTime * uSpeed * rotSpeed;
    float ringRadius = mix(0.12, 0.85, fi / float(RING_COUNT - 1)) * uScale;

    vec2 rp = rot2(rotAngle) * p;
    rp.y /= squash;
    float d = length(rp) - ringRadius;

    float ringWidth = 0.03 + uWarp * 0.04;
    float core = exp(-(d * d) / (ringWidth * ringWidth));
    float halo = exp(-(d * d) / pow(ringWidth * 3.5, 2.0)) * 0.25;

    float shimmer = 0.6 + 0.4 * sin(uTime * 0.3 * uSpeed + fi * 1.9);
    vec3 ringColor = palette5(fi / float(RING_COUNT - 1), uColor0, uColor1, uColor2, uColor3, uColor4);
    glowSum += ringColor * (core + halo) * shimmer;
  }

  // Pulsing core / inner halo breathing at the center.
  float pulse = 0.5 + 0.5 * sin(uTime * uSpeed * 0.8);
  float coreGlow = smoothstep(0.4, 0.0, length(p)) * (0.35 + 0.5 * pulse) * (0.3 + uParamA);
  glowSum += palette5(0.5, uColor0, uColor1, uColor2, uColor3, uColor4) * coreGlow;

  vec3 color = blendScreen(spaceBlack, glowSum * (0.45 + uBlend * 0.45));
  gl_FragColor = vec4(color, 1.0);
}
