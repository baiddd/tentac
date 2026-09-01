// Raw WebGL1 engine: compiles one program per style (common.glsl text
// prepended to the style's fragment source, since GLSL ES 1.00 has no
// #include), runs a continuous render loop, and eases current params
// toward a randomized target whenever randomize() is called.

import commonGlsl from "./shaders/common.glsl?raw";
import vertSource from "./shaders/fullscreen.vert?raw";
import { GRADIENT_STYLES, PRESETS, withParamDefaults, type GradientParams, type GradientStyle } from "./styles";

const TRANSITION_MS = 1500;
const STORAGE_PREFIX = "gradient-lab:";

export type NumericParamKey = "warp" | "scale" | "speed" | "grain" | "blend" | "paramA" | "paramB" | "paramC";
const EMPTY_LOCK_SET: ReadonlySet<NumericParamKey> = new Set();

function loadSavedParams(styleId: string): GradientParams | null {
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + styleId);
    if (!raw) return null;
    return withParamDefaults(JSON.parse(raw) as Partial<GradientParams>);
  } catch {
    return null;
  }
}

function persistParams(styleId: string, params: GradientParams): void {
  try {
    localStorage.setItem(STORAGE_PREFIX + styleId, JSON.stringify(params));
  } catch {
    // Storage unavailable (private mode, quota) — saving to disk via the
    // download still works, only the "remember across reloads" part is lost.
  }
}

function clearSavedParams(styleId: string): void {
  try {
    localStorage.removeItem(STORAGE_PREFIX + styleId);
  } catch {
    // ignore
  }
}

/** Resolution order for a style's starting params: this browser's saved
 * tweak (localStorage) > a committed preset (presets/<id>.json) > a
 * fresh randomize(). */
function resolveParams(style: GradientStyle): GradientParams {
  return loadSavedParams(style.id) ?? PRESETS[style.id] ?? style.randomize();
}

// Global, style-independent knobs (feedback round 1): every effect's flow
// reads 4x slower, and every effect is "zoomed in" 5x (features 5x bigger)
// — applied once here rather than per-style so it's guaranteed uniform
// across all 13 recipes instead of relying on each one's own ranges.
const TIME_SLOWDOWN = 0.25; // uTime *= this -> 4x slower flow
const ZOOM_FACTOR = 0.2; // uScale *= this -> 5x bigger features

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function lerpParams(a: GradientParams, b: GradientParams, t: number): GradientParams {
  return {
    colors: a.colors.map((c, i) => [
      lerp(c[0], b.colors[i][0], t),
      lerp(c[1], b.colors[i][1], t),
      lerp(c[2], b.colors[i][2], t),
    ]) as GradientParams["colors"],
    warp: lerp(a.warp, b.warp, t),
    scale: lerp(a.scale, b.scale, t),
    speed: lerp(a.speed, b.speed, t),
    grain: lerp(a.grain, b.grain, t),
    blend: lerp(a.blend, b.blend, t),
    paramA: lerp(a.paramA, b.paramA, t),
    paramB: lerp(a.paramB, b.paramB, t),
    paramC: lerp(a.paramC, b.paramC, t),
    seed: t < 1 ? a.seed : b.seed, // seed snaps at the end — mid-lerp values are meaningless
  };
}

function compileShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("createShader failed");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const info = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(`Shader compile error: ${info}`);
  }
  return shader;
}

function linkProgram(gl: WebGLRenderingContext, vertShader: WebGLShader, fragShader: WebGLShader): WebGLProgram {
  const program = gl.createProgram();
  if (!program) throw new Error("createProgram failed");
  gl.attachShader(program, vertShader);
  gl.attachShader(program, fragShader);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const info = gl.getProgramInfoLog(program);
    gl.deleteProgram(program);
    throw new Error(`Program link error: ${info}`);
  }
  return program;
}

interface CompiledStyle {
  program: WebGLProgram;
  uniforms: Record<string, WebGLUniformLocation | null>;
  aPosition: number;
}

const UNIFORM_NAMES = [
  "uTime", "uResolution", "uSeed",
  "uColor0", "uColor1", "uColor2", "uColor3", "uColor4",
  "uWarp", "uScale", "uSpeed", "uGrain", "uBlend", "uParamA", "uParamB", "uParamC",
  "uMouse", "uStyleTime",
];

export class GradientEngine {
  private gl: WebGLRenderingContext;
  private quad: WebGLBuffer;
  private compiled = new Map<string, CompiledStyle>();
  private currentStyle: GradientStyle;
  private currentParams: GradientParams;
  private targetParams: GradientParams;
  private transitionStart = 0;
  private startTime = performance.now();
  private styleActivatedAt = performance.now();
  private mouseX = 0.5;
  private mouseY = 0.5;
  private rafId = 0;

  constructor(private canvas: HTMLCanvasElement) {
    const gl = canvas.getContext("webgl") as WebGLRenderingContext | null;
    if (!gl) throw new Error("WebGL is not available in this browser");
    this.gl = gl;

    canvas.addEventListener("pointermove", (e) => {
      const rect = canvas.getBoundingClientRect();
      this.mouseX = (e.clientX - rect.left) / rect.width;
      this.mouseY = 1 - (e.clientY - rect.top) / rect.height; // flip to match vUv's bottom-up convention
    });

    const quad = gl.createBuffer();
    if (!quad) throw new Error("createBuffer failed");
    this.quad = quad;
    gl.bindBuffer(gl.ARRAY_BUFFER, quad);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
      gl.STATIC_DRAW
    );

    this.currentStyle = GRADIENT_STYLES[0];
    this.currentParams = resolveParams(this.currentStyle);
    this.targetParams = this.currentParams;

    this.resize();
    this.loop = this.loop.bind(this);
  }

  private getCompiled(style: GradientStyle): CompiledStyle {
    const existing = this.compiled.get(style.id);
    if (existing) return existing;

    const gl = this.gl;
    const vertShader = compileShader(gl, gl.VERTEX_SHADER, vertSource);
    const fragShader = compileShader(gl, gl.FRAGMENT_SHADER, commonGlsl + "\n" + style.fragSource);
    const program = linkProgram(gl, vertShader, fragShader);

    const uniforms: Record<string, WebGLUniformLocation | null> = {};
    for (const name of UNIFORM_NAMES) {
      uniforms[name] = gl.getUniformLocation(program, name);
    }
    const aPosition = gl.getAttribLocation(program, "aPosition");

    const compiled: CompiledStyle = { program, uniforms, aPosition };
    this.compiled.set(style.id, compiled);
    return compiled;
  }

  /** Switch styles immediately (no cross-style lerp). Uses that style's
   * last-saved params if the user has saved any for it in this browser,
   * else a committed preset, else a fresh randomize(). */
  setStyle(id: string): void {
    const style = GRADIENT_STYLES.find((s) => s.id === id);
    if (!style) return;
    this.currentStyle = style;
    this.getCompiled(style); // ensure compiled before first frame
    this.currentParams = resolveParams(style);
    this.targetParams = this.currentParams;
    this.transitionStart = 0;
    this.styleActivatedAt = performance.now();
  }

  /** Render an exact, caller-supplied style+params combo, bypassing the
   * localStorage/preset resolution chain entirely. Used for a specific
   * issue's frozen cover, where the params come from that issue's own
   * saved/generated file, not from this browser's lab state. */
  setExact(id: string, params: GradientParams): void {
    const style = GRADIENT_STYLES.find((s) => s.id === id);
    if (!style) return;
    this.currentStyle = style;
    this.getCompiled(style);
    this.currentParams = withParamDefaults(params);
    this.targetParams = this.currentParams;
    this.transitionStart = 0;
    this.styleActivatedAt = performance.now();
  }

  /** Reset the current style to its default: clears this browser's saved
   * tweak for it and falls back to the committed preset (if any) or a
   * fresh randomize() — i.e. what you'd see without ever hitting Save. */
  resetToDefault(): void {
    clearSavedParams(this.currentStyle.id);
    this.currentParams = PRESETS[this.currentStyle.id] ?? this.currentStyle.randomize();
    this.targetParams = this.currentParams;
    this.transitionStart = 0;
  }

  /** Re-roll params within the current style and ease toward them. Any
   * key in `lockedKeys` keeps its current (manually set) value instead
   * of being overwritten by the new random draw — colors always
   * re-roll, locking only applies to the numeric sliders. Also restarts
   * uStyleTime, so a style with a one-shot reveal animation (staggered
   * slide, door opening) plays it again as a nice payoff. */
  randomize(lockedKeys: ReadonlySet<NumericParamKey> = EMPTY_LOCK_SET): void {
    const display = this.sampleCurrentParams();
    this.currentParams = display;
    const fresh = this.currentStyle.randomize();
    for (const key of lockedKeys) fresh[key] = display[key];
    this.targetParams = fresh;
    this.transitionStart = performance.now();
    this.styleActivatedAt = performance.now();
  }

  private sampleCurrentParams(): GradientParams {
    if (this.transitionStart === 0) return this.currentParams;
    const elapsed = performance.now() - this.transitionStart;
    const t = easeInOutCubic(Math.min(1, elapsed / TRANSITION_MS));
    return lerpParams(this.currentParams, this.targetParams, t);
  }

  /** Current style id, for building preset filenames etc. */
  getStyleId(): string {
    return this.currentStyle.id;
  }

  /** Params as currently displayed (mid-transition values included) —
   * what the sliders should show right after a style switch or load. */
  getDisplayParams(): GradientParams {
    return this.sampleCurrentParams();
  }

  /** Where a randomize() transition is headed — what the sliders should
   * jump to right after clicking Randomize, without waiting out the ease. */
  getTargetParams(): GradientParams {
    return this.targetParams;
  }

  /** Direct, un-eased control for a single numeric param (sliders). */
  setParam(key: NumericParamKey, value: number): void {
    // Must merge into what's currently DISPLAYED (sampleCurrentParams),
    // not the raw this.currentParams — that field is a snapshot frozen
    // at the start of the last transition and is never written back
    // once the transition finishes, so merging into it directly would
    // silently revert every other param to its pre-transition value the
    // moment a slider is touched after a randomize().
    const display = this.sampleCurrentParams();
    this.currentParams = { ...display, [key]: value };
    this.targetParams = this.currentParams;
    this.transitionStart = 0;
  }

  /** Freeze whatever is currently displayed as the new current/target
   * (so a save mid-transition doesn't get overwritten by the transition
   * finishing), persist it as this style's default for this browser, and
   * return it for the caller to also offer as a file download. */
  saveCurrentParams(): GradientParams {
    const params = this.sampleCurrentParams();
    this.currentParams = params;
    this.targetParams = params;
    this.transitionStart = 0;
    persistParams(this.currentStyle.id, params);
    return params;
  }

  resize(): void {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.round(this.canvas.clientWidth * dpr);
    const height = Math.round(this.canvas.clientHeight * dpr);
    if (this.canvas.width !== width || this.canvas.height !== height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
    this.gl.viewport(0, 0, width, height);
  }

  start(): void {
    this.loop();
  }

  stop(): void {
    cancelAnimationFrame(this.rafId);
  }

  private loop(): void {
    this.render();
    this.rafId = requestAnimationFrame(this.loop);
  }

  private render(): void {
    const gl = this.gl;
    const compiled = this.getCompiled(this.currentStyle);

    let elapsed = TRANSITION_MS;
    if (this.transitionStart !== 0) {
      elapsed = performance.now() - this.transitionStart;
    }
    const t = easeInOutCubic(Math.min(1, elapsed / TRANSITION_MS));
    const params = lerpParams(this.currentParams, this.targetParams, t);

    gl.useProgram(compiled.program);

    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    gl.enableVertexAttribArray(compiled.aPosition);
    gl.vertexAttribPointer(compiled.aPosition, 2, gl.FLOAT, false, 0, 0);

    const u = compiled.uniforms;
    gl.uniform1f(u.uTime, ((performance.now() - this.startTime) / 1000) * TIME_SLOWDOWN);
    gl.uniform2f(u.uResolution, this.canvas.width, this.canvas.height);
    gl.uniform1f(u.uSeed, params.seed);
    gl.uniform3f(u.uColor0, ...params.colors[0]);
    gl.uniform3f(u.uColor1, ...params.colors[1]);
    gl.uniform3f(u.uColor2, ...params.colors[2]);
    gl.uniform3f(u.uColor3, ...params.colors[3]);
    gl.uniform3f(u.uColor4, ...params.colors[4]);
    gl.uniform1f(u.uWarp, params.warp);
    gl.uniform1f(u.uScale, params.scale * ZOOM_FACTOR);
    gl.uniform1f(u.uSpeed, params.speed);
    gl.uniform1f(u.uGrain, params.grain);
    gl.uniform1f(u.uBlend, params.blend);
    gl.uniform1f(u.uParamA, params.paramA);
    gl.uniform1f(u.uParamB, params.paramB);
    gl.uniform1f(u.uParamC, params.paramC);
    gl.uniform2f(u.uMouse, this.mouseX, this.mouseY);
    gl.uniform1f(u.uStyleTime, ((performance.now() - this.styleActivatedAt) / 1000) * TIME_SLOWDOWN);

    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }
}

export { GRADIENT_STYLES };
