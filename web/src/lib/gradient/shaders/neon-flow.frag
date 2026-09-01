// Curved, three-dimensional-reading light beams radiating from a random
// vanishing point (not the screen center — see uParamA/uParamB in
// styles.ts), each bending outward from that origin (curvature grows
// with distance) with a soft gaussian core standing in for motion blur.
// Perspective: each beam is razor-thin right at the origin and widens
// the farther it travels from it, like lines converging on a vanishing
// point. Traveling brightness pulses run outward along each beam, and
// their speed ramps up briefly after the style activates, for a "jump
// to light speed" feel.
#define PI 3.14159265
#define TWO_PI 6.2831853
#define BEAM_COUNT 10

void main() {
  vec2 p = vUv - 0.5;
  float aspect = uResolution.x / uResolution.y;
  p.x *= aspect;

  // Random vanishing point, not the screen center.
  vec2 origin = vec2(mix(-0.7, 0.7, uParamA), mix(-0.4, 0.4, uParamB));
  vec2 toFrag = p - origin;
  float radius = length(toFrag);
  float angle = atan(toFrag.y, toFrag.x);

  float accel = 1.0 + min(uStyleTime * 0.4, 1.8);
  float speedEff = uSpeed * accel;

  vec3 spaceBlack = vec3(0.006, 0.008, 0.016);
  vec3 glowSum = vec3(0.0);

  // Beams are grouped into a random number of clusters (varies with
  // uSeed) instead of an even fan: each beam picks one of the clusters,
  // so some clusters end up with several beams bunched close together
  // and others with just one beam alone, and which beams land where
  // reshuffles on every randomize.
  float clusterCount = 3.0 + floor(hash1(vec2(uSeed, 41.7)) * 4.0); // 3..6

  // uWarp and uGrain use a quadratic response: near the low end of the
  // slider the effect is much weaker than a linear mapping would give
  // (fixes "too strong even near zero"), while the top of the range
  // reaches further than before (more usable amplitude overall).
  float warpT = clamp(uWarp / 3.0, 0.0, 1.0);
  float bendStrength = warpT * warpT * 5.0;
  float grainT = clamp(uGrain, 0.0, 1.0);
  float baseWidth = 0.0008 + grainT * grainT * 0.03;

  for (int i = 0; i < BEAM_COUNT; i++) {
    float fi = float(i);
    float clusterId = floor(hash1(vec2(fi, uSeed * 1.7)) * clusterCount);
    float clusterAngle = hash1(vec2(clusterId, uSeed * 2.3)) * TWO_PI;
    float withinClusterJitter = (hash1(vec2(fi, uSeed * 3.1) + 7.0) - 0.5) * 0.35;
    float baseAngle = clusterAngle + withinClusterJitter;
    float curveAngle = baseAngle + bendStrength * radius * (0.6 + 0.4 * sin(fi * 1.7 + uSeed));

    float angDiff = mod(angle - curveAngle + PI, TWO_PI) - PI;
    float arcDist = abs(angDiff) * radius;

    // Perspective: razor-thin at the origin, widening with distance.
    // uParamC is a dedicated strength slider, mapped exponentially so the
    // top of the range goes dramatically further than the middle: at 0.5
    // the far screen edge reads about 10x the width at the vanishing
    // point (growth~7.5 over a ~1.2-unit reference radius to that edge);
    // at 1.0 it's roughly 240x — well over 10x stronger than that.
    float growth = 0.3 * (exp(6.5 * uParamC) - 1.0);
    float lineWidth = baseWidth * (1.0 + radius * growth);
    float core = exp(-(arcDist * arcDist) / (lineWidth * lineWidth));

    float pulse = 0.35 + 0.65 * (0.5 + 0.5 * sin(radius * 10.0 - uTime * speedEff * 6.0 + fi * 2.1));

    vec3 beamColor = palette5(fract(fi / float(BEAM_COUNT) + uSeed * 0.0007), uColor0, uColor1, uColor2, uColor3, uColor4);
    glowSum += beamColor * core * pulse * (0.5 + radius);
  }

  // Pulsing convergence point at the vanishing point.
  float centerGlow = smoothstep(0.4, 0.0, radius) * (0.6 + 0.4 * sin(uTime * 2.0 * uSpeed));
  glowSum += uColor4 * centerGlow;

  vec3 color = blendScreen(spaceBlack, glowSum * (0.5 + uBlend * 0.6));
  gl_FragColor = vec4(color, 1.0);
}
