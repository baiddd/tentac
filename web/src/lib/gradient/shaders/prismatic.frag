// A single ray fanning out from an origin point like a spotlight beam,
// sweeping back and forth angularly, with a grainy noise flicker running
// along its length for a "live" refraction feel.
#define PI 3.14159265
#define TWO_PI 6.2831853

void main() {
  vec2 p = vUv - 0.5;
  p.x *= uResolution.x / uResolution.y;

  vec2 origin = vec2(mix(-0.55, 0.55, uParamA), 0.5);
  vec2 toFrag = p - origin;
  float dist = length(toFrag);
  float angle = atan(toFrag.y, toFrag.x);

  float baseAngle = -1.5708 + (hash1(vec2(uSeed, 1.0)) - 0.5) * 0.6; // roughly downward
  float sweepRange = 0.35 + uWarp * 0.35;
  float sweepCenter = baseAngle + sweepRange * sin(uTime * uSpeed * 0.35 + uSeed);

  float angDiff = mod(angle - sweepCenter + PI, TWO_PI) - PI;
  float fanHalfAngle = 0.12 + uParamB * 0.3;
  float inBeam = smoothstep(fanHalfAngle, fanHalfAngle * 0.25, abs(angDiff));

  float distFalloff = smoothstep(1.5, 0.04, dist);

  float flicker = fbm(vec2(angle * 8.0, dist * 6.0 - uTime * uSpeed * 2.2), 3) * 0.5 + 0.5;
  float grainAmt = 0.4 + uGrain * 0.6;
  float beamBrightness = inBeam * distFalloff * mix(1.0, flicker, grainAmt);

  vec3 beamColor = palette5(clamp(dist / 1.2, 0.0, 1.0), uColor0, uColor1, uColor2, uColor3, uColor4);

  float originGlow = smoothstep(0.12, 0.0, dist);

  vec3 spaceBlack = vec3(0.006, 0.008, 0.016);
  vec3 glow = beamColor * beamBrightness * (0.7 + uBlend * 0.6) + beamColor * originGlow * 0.6;
  vec3 color = blendScreen(spaceBlack, glow);

  gl_FragColor = vec4(color, 1.0);
}
