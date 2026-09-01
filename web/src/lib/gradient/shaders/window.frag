// A dark wall with a rectangular door/window opening, spilling a
// trapezoid of light onto the floor below it — dramatic chiaroscuro.
// The trapezoid's reach grows from closed to fully open over the first
// few seconds after the style activates (uStyleTime), like a door
// slowly opening, then keeps a small continuous breathing motion so the
// scene stays alive rather than freezing once fully open.
void main() {
  vec2 p = vUv - 0.5;
  p.x *= uResolution.x / uResolution.y;

  float horizonY = 0.05; // wall/floor boundary, in the same centered space as p
  float doorHalfWidth = 0.06 + uParamA * 0.12;
  float doorCenterX = (uParamB - 0.5) * 0.7;
  float doorHeight = 0.24;

  float reveal = smoothstep(0.0, 1.0, clamp(uStyleTime * (0.12 + uSpeed * 0.3), 0.0, 1.0));
  float breathe = 0.05 * sin(uTime * uSpeed * 1.4) * reveal;
  float openAmount = clamp(reveal + breathe, 0.0, 1.0);

  vec3 wall = uColor0;
  vec3 floorColor = uColor1;
  vec3 lightColor = uColor2;
  vec3 doorColor = uColor3;
  vec3 shadow = uColor4;

  bool isWall = p.y >= horizonY;
  vec3 color = isWall ? wall : floorColor;

  // The door opening itself: a bright rectangle in the wall, just above
  // the horizon, whose brightness (not size) ramps in with openAmount.
  float doorMaskX = smoothstep(doorHalfWidth, doorHalfWidth - 0.015, abs(p.x - doorCenterX));
  float doorMaskY = smoothstep(horizonY, horizonY + 0.02, p.y) * smoothstep(horizonY + doorHeight, horizonY + doorHeight - 0.02, p.y);
  float doorMask = doorMaskX * doorMaskY * float(isWall);
  color = mix(color, doorColor, doorMask * openAmount);

  // Trapezoid of light spilling onto the floor: narrow at the horizon
  // (matching the door width), widening as it reaches toward the viewer.
  float maxReach = 0.5;
  float reach = maxReach * openAmount;
  float t = (horizonY - p.y) / max(reach, 0.001); // 0 at horizon, 1 at the light's current far edge
  float spread = 0.3 + uWarp * 0.15;
  float widthAtT = doorHalfWidth + spread * clamp(t, 0.0, 1.0);
  float inTrapezoidX = smoothstep(widthAtT, widthAtT - 0.03, abs(p.x - doorCenterX));
  float inTrapezoidY = step(0.0, t) * smoothstep(1.0, 0.85, t);
  float falloff = mix(1.0, 0.25, clamp(t, 0.0, 1.0));
  float trapezoidMask = inTrapezoidX * inTrapezoidY * float(!isWall) * step(0.001, reach);

  float grain = (hash1(gl_FragCoord.xy + uTime * 4.0) - 0.5) * uGrain * 0.15;
  color = mix(color, lightColor * (falloff + grain), trapezoidMask * (0.55 + uBlend * 0.35));

  // Vignette for extra dramatic falloff at the screen edges.
  float vignette = smoothstep(0.95, 0.15, length(p));
  color = mix(shadow * 0.6, color, vignette);

  gl_FragColor = vec4(color, 1.0);
}
