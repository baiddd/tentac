// Parallel vertical bands of frosted, refractive glass: each band gets
// its own color, a blurred fractal "refraction" texture, and a chromatic
// fringe at its seams. Bands shift sideways in a staggered wave
// (sequential phase offset per band index = glitch/parallax), and the
// texture's roughness increases near the pointer.
void main() {
  float bandDensity = 4.0 + uParamA * 10.0;
  float bandIndex = floor(vUv.x * bandDensity);
  float bandLocalX = fract(vUv.x * bandDensity);

  float shiftPhase = bandIndex * 0.35 + uSeed;
  float shift = sin(uTime * uSpeed * 0.6 + shiftPhase) * (0.4 + uWarp * 0.6);

  float distToMouseX = abs(vUv.x - uMouse.x);
  float hoverBoost = smoothstep(0.3, 0.0, distToMouseX) * 0.7;
  float roughness = uGrain + hoverBoost;
  float freq = 2.0 + roughness * 6.0;

  vec2 texCoord = vec2(bandIndex * 0.7 + shift, vUv.y * 3.0 * uScale + uTime * uSpeed * 0.05);
  float tex = fbm(texCoord * freq, 3) * 0.5 + 0.5;

  float split = 0.015 + uParamB * 0.05;
  float nr = fbm((texCoord + vec2(split, 0.0)) * freq, 3) * 0.5 + 0.5;
  float nb = fbm((texCoord - vec2(split, 0.0)) * freq, 3) * 0.5 + 0.5;

  float bandHueT = hash1(vec2(bandIndex, uSeed));
  vec3 bandColor = palette5(bandHueT, uColor0, uColor1, uColor2, uColor3, uColor4);
  vec3 texColor = bandColor * (0.55 + 0.45 * tex);

  float edgeFactor = 1.0 - smoothstep(0.0, 0.18, min(bandLocalX, 1.0 - bandLocalX));
  texColor += (vec3(nr, tex, nb) - vec3(tex)) * edgeFactor * (0.6 + uBlend * 0.6);

  float seam = smoothstep(0.0, 0.025, bandLocalX) * smoothstep(0.0, 0.025, 1.0 - bandLocalX);
  texColor *= mix(0.65, 1.0, seam);

  vec3 spaceBlack = vec3(0.006, 0.008, 0.016);
  float alpha = 0.5 + 0.3 * tex;
  vec3 color = mix(spaceBlack, texColor, alpha);

  gl_FragColor = vec4(color, 1.0);
}
