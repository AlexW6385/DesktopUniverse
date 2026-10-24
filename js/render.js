// Painting with WebGL: trails (two framebuffers, the last frame faded toward the
// background), pixels and soft dots, kaleidoscope copies, lines, the slime's scent map.
(function () {
"use strict";
const DU = window.DU;
const TAU = Math.PI * 2;

const PRECISION = "#ifdef GL_FRAGMENT_PRECISION_HIGH\nprecision highp float;\n#else\nprecision mediump float;\n#endif\n";

const VS_QUAD = `attribute vec2 a_pos; varying vec2 v_uv;
void main() { v_uv = a_pos * 0.5 + 0.5; gl_Position = vec4(a_pos, 0.0, 1.0); }`;

// the last frame, a veil of the background over it, and a nudge of one step so that every
// pixel really reaches the background (from above at night, from below on paper)
const FS_FADE = PRECISION + `uniform sampler2D u_prev; uniform vec3 u_bg; uniform float u_a; uniform float u_nudge;
varying vec2 v_uv;
void main() {
  vec3 c = texture2D(u_prev, v_uv).rgb;
  c = c + (u_bg - c) * u_a;
  if (u_nudge < -0.5) c = max(c - 1.0 / 255.0, u_bg);
  else if (u_nudge > 0.5) c = min(c + 1.0 / 255.0, u_bg);
  gl_FragColor = vec4(c, 1.0);
}`;

const FS_COPY = PRECISION + `uniform sampler2D u_tex; varying vec2 v_uv;
void main() { gl_FragColor = vec4(texture2D(u_tex, v_uv).rgb, 1.0); }`;

// world coordinates in, one kaleidoscope copy (rotation about the centre, then mirror)
const VS_SHAPES = `attribute vec2 a_pos; attribute vec3 a_col;
uniform vec2 u_world; uniform vec2 u_center; uniform vec2 u_rot; uniform float u_mirror;
uniform float u_size; uniform float u_shift;
varying vec3 v_col;
void main() {
  vec2 p = a_pos - u_center;
  p = vec2(p.x * u_rot.x - p.y * u_rot.y, p.x * u_rot.y + p.y * u_rot.x);
  if (u_mirror > 0.5) p.x = -p.x;
  p += u_center + vec2(u_shift);
  gl_Position = vec4(p.x / u_world.x * 2.0 - 1.0, 1.0 - p.y / u_world.y * 2.0, 0.0, 1.0);
  gl_PointSize = u_size;
  v_col = a_col;
}`;

const FS_PIXEL = PRECISION + `uniform float u_gain; varying vec3 v_col;
void main() { gl_FragColor = vec4(v_col * u_gain, 1.0); }`;

// make_dot: a crisp disk (1 px soft edge) blended toward a gaussian glow by u_soft
const FS_DOT = PRECISION + `uniform float u_diam; uniform float u_soft; uniform float u_additive;
varying vec3 v_col;
void main() {
  float dist = length(gl_PointCoord - 0.5) * u_diam;
  float a = clamp(u_diam * 0.5 + 0.5 - dist, 0.0, 1.0);
  if (u_soft > 0.0) { float r = dist / max(u_diam * 0.5, 0.5); a = a * (1.0 - u_soft) + exp(-2.5 * r * r) * u_soft; }
  if (a <= 0.002) discard;
  if (u_additive > 0.5) gl_FragColor = vec4(v_col * a, 1.0);
  else gl_FragColor = vec4(v_col, a);
}`;

const FS_LINE = PRECISION + `varying vec3 v_col; void main() { gl_FragColor = vec4(v_col, 1.0); }`;

const VS_TEX = `attribute vec2 a_pos; uniform vec2 u_world; uniform vec2 u_size; varying vec2 v_uv;
void main() { v_uv = a_pos; vec2 p = a_pos * u_size;
  gl_Position = vec4(p.x / u_world.x * 2.0 - 1.0, 1.0 - p.y / u_world.y * 2.0, 0.0, 1.0); }`;

class Renderer {
  constructor(canvas) {
    const opts = { alpha: false, antialias: false, depth: false, stencil: false, premultipliedAlpha: false,
                   preserveDrawingBuffer: false, powerPreference: "high-performance" };
    const gl = canvas.getContext("webgl2", opts) || canvas.getContext("webgl", opts);
    if (!gl) throw new Error("this browser has no WebGL");
    this.gl = gl; this.canvas = canvas;
    this.fade = this.program(VS_QUAD, FS_FADE);
    this.copy = this.program(VS_QUAD, FS_COPY);
    this.pixel = this.program(VS_SHAPES, FS_PIXEL);
    this.dot = this.program(VS_SHAPES, FS_DOT);
    this.line = this.program(VS_SHAPES, FS_LINE);
    this.texq = this.program(VS_TEX, FS_COPY);
    this.quad = this.buffer(new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]));
    this.unit = this.buffer(new Float32Array([0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1]));
    this.posBuf = gl.createBuffer(); this.colBuf = gl.createBuffer();
    this.maxPoint = gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE)[1] || 64;
    this.tex = []; this.fbo = []; this.cur = 0;
    this.scentTex = gl.createTexture(); this.scentSize = [0, 0];
    this.scratch = { pos: new Float32Array(0), col: new Float32Array(0) };
  }

  program(vs, fs) {
    const gl = this.gl;
    const sh = (type, src) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    const p = gl.createProgram();
    gl.attachShader(p, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs));
    gl.bindAttribLocation(p, 0, "a_pos"); gl.bindAttribLocation(p, 1, "a_col");
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    const u = {};
    const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
    for (let i = 0; i < n; i++) { const info = gl.getActiveUniform(p, i); u[info.name] = gl.getUniformLocation(p, info.name); }
    return { p, u };
  }

  buffer(data) {
    const gl = this.gl, b = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    return b;
  }

  /** world: [W, H] in simulation pixels; scale: device pixels per simulation pixel */
  resize(world, scale) {
    const gl = this.gl;
    this.world = world; this.scale = scale;
    const w = Math.max(1, Math.round(world[0] * scale)), h = Math.max(1, Math.round(world[1] * scale));
    this.canvas.width = w; this.canvas.height = h;
    for (let i = 0; i < 2; i++) {
      if (this.tex[i]) { gl.deleteTexture(this.tex[i]); gl.deleteFramebuffer(this.fbo[i]); }
      const t = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      const f = gl.createFramebuffer();
      gl.bindFramebuffer(gl.FRAMEBUFFER, f);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
      this.tex[i] = t; this.fbo[i] = f;
    }
    this.size = [w, h];
    this.clear([0, 0, 0]);
  }

  clear(bg) {
    const gl = this.gl;
    for (let i = 0; i < 2; i++) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo[i]);
      gl.viewport(0, 0, this.size[0], this.size[1]);
      gl.clearColor(bg[0] / 255, bg[1] / 255, bg[2] / 255, 1); gl.clear(gl.COLOR_BUFFER_BIT);
    }
  }

  fullscreen(prog) {
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.disableVertexAttribArray(1);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
  }

  /** One frame: fade the last one into the other framebuffer, paint every layer, show it. */
  frame(uni) {
    const gl = this.gl, p = uni.p, prev = this.cur, cur = 1 - prev;
    const bg = p.background.map((v) => v / 255);
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo[cur]);
    gl.viewport(0, 0, this.size[0], this.size[1]);
    gl.disable(gl.BLEND);
    if (p.trail <= 0) {
      gl.clearColor(bg[0], bg[1], bg[2], 1); gl.clear(gl.COLOR_BUFFER_BIT);
    } else {
      const alpha = 255 * (1 - p.trail);
      const every = alpha >= 1 ? 1 : Math.max(1, Math.round(1 / alpha));
      const fading = p.trail < 1 && uni.frame % every === 0;
      gl.useProgram(this.fade.p);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.tex[prev]);
      gl.uniform1i(this.fade.u.u_prev, 0);
      gl.uniform3f(this.fade.u.u_bg, bg[0], bg[1], bg[2]);
      gl.uniform1f(this.fade.u.u_a, fading ? Math.max(1, Math.round(alpha)) / 255 : 0);
      const paper = p.background[0] + p.background[1] + p.background[2] >= 384;
      gl.uniform1f(this.fade.u.u_nudge, fading ? (paper ? 1 : -1) : 0);
      this.fullscreen(this.fade);
    }
    for (const sw of uni.swarms) this.paint(uni, sw);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, this.size[0], this.size[1]);
    gl.disable(gl.BLEND);
    gl.useProgram(this.copy.p);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.tex[cur]);
    gl.uniform1i(this.copy.u.u_tex, 0);
    this.fullscreen(this.copy);
    this.cur = cur;
  }

  copies(p) {
    const k = Math.max(1, Math.floor(p.symmetry)), out = [];
    for (let j = 0; j < k; j++) {
      const a = TAU * j / k;
      out.push([Math.cos(a), Math.sin(a), 0]);
      if (p.mirror) out.push([Math.cos(a), Math.sin(a), 1]);
    }
    return out;
  }

  setShapes(prog, uni, pos, col) {
    const gl = this.gl;
    gl.useProgram(prog.p);
    gl.uniform2f(prog.u.u_world, uni.world[0], uni.world[1]);
    gl.uniform2f(prog.u.u_center, uni.cx, uni.cy);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.posBuf); gl.bufferData(gl.ARRAY_BUFFER, pos, gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.colBuf); gl.bufferData(gl.ARRAY_BUFFER, col, gl.DYNAMIC_DRAW);
    gl.enableVertexAttribArray(1); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);
  }

  drawCopies(prog, uni, mode, count) {
    const gl = this.gl;
    for (const [c, s, mirror] of this.copies(uni.p)) {
      gl.uniform2f(prog.u.u_rot, c, s);
      gl.uniform1f(prog.u.u_mirror, mirror);
      gl.drawArrays(mode, 0, count);
    }
  }

  points(uni, pos, col, count, look) {
    const gl = this.gl, sc = this.scale;
    if (!count) return;
    if (look.kind === "dot") {
      const prog = this.dot;
      this.setShapes(prog, uni, pos, col);
      gl.uniform1f(prog.u.u_size, Math.min(this.maxPoint, look.diam * sc));
      gl.uniform1f(prog.u.u_shift, 0);
      gl.uniform1f(prog.u.u_diam, look.diam);
      gl.uniform1f(prog.u.u_soft, look.soft);
      gl.uniform1f(prog.u.u_additive, look.additive ? 1 : 0);
      gl.enable(gl.BLEND);
      if (look.additive) gl.blendFunc(gl.ONE, gl.ONE); else gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      this.drawCopies(prog, uni, gl.POINTS, count);
    } else {
      const prog = this.pixel;
      this.setShapes(prog, uni, pos, col);
      gl.uniform1f(prog.u.u_size, Math.min(this.maxPoint, look.size * sc));
      gl.uniform1f(prog.u.u_shift, look.size / 2);         // an s x s square from the body's position
      gl.uniform1f(prog.u.u_gain, look.gain);
      if (look.additive) { gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE); } else gl.disable(gl.BLEND);
      this.drawCopies(prog, uni, gl.POINTS, count);
    }
  }

  lines(uni, verts, cols) {
    const gl = this.gl, prog = this.line;
    this.setShapes(prog, uni, verts, cols);
    gl.uniform1f(prog.u.u_size, 1); gl.uniform1f(prog.u.u_shift, 0);
    gl.disable(gl.BLEND);
    this.drawCopies(prog, uni, gl.LINES, verts.length / 2);
  }

  /** The slime's scent map itself, tone mapped and scaled up smoothly, added on top. */
  scent(uni, sw, col) {
    const gl = this.gl, L = sw.layer, T = sw.scent, gw = sw.scentW, gh = sw.scentH, g = Math.max(1, Math.floor(L.slime_cell));
    const k = L.slime_show * 0.1 / Math.max(L.slime_deposit, 1e-6);
    let tr = 0, tg = 0, tb = 0;
    for (let i = 0; i < sw.n; i++) { tr += col[i * 3]; tg += col[i * 3 + 1]; tb += col[i * 3 + 2]; }
    tr = tr / sw.n * 255; tg = tg / sw.n * 255; tb = tb / sw.n * 255;
    if (!this.scentBuf || this.scentBuf.length !== gw * gh * 4) this.scentBuf = new Uint8Array(gw * gh * 4);
    const B = this.scentBuf;
    for (let j = 0; j < gw * gh; j++) {
      const v = 1 - Math.exp(-Math.max(T[j], 0) * k), v4 = v * v * v * v * 0.4;   // the busiest veins burn white
      B[j * 4] = Math.min(255, v * tr + v4 * (255 - tr));
      B[j * 4 + 1] = Math.min(255, v * tg + v4 * (255 - tg));
      B[j * 4 + 2] = Math.min(255, v * tb + v4 * (255 - tb));
      B[j * 4 + 3] = 255;
    }
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.scentTex);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    if (this.scentSize[0] !== gw || this.scentSize[1] !== gh) {
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gw, gh, 0, gl.RGBA, gl.UNSIGNED_BYTE, B);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      this.scentSize = [gw, gh];
    } else gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, gw, gh, gl.RGBA, gl.UNSIGNED_BYTE, B);
    const prog = this.texq;
    gl.useProgram(prog.p);
    gl.uniform1i(prog.u.u_tex, 0);
    gl.uniform2f(prog.u.u_world, uni.world[0], uni.world[1]);
    gl.uniform2f(prog.u.u_size, gw * g, gh * g);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.unit);
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.disableVertexAttribArray(1);
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
  }

  grow(name, n) {
    if (this.scratch[name].length < n) this.scratch[name] = new Float32Array(Math.ceil(n * 1.25));
    return this.scratch[name];
  }

  paint(uni, sw) {
    const L = sw.layer, p = uni.p, n = sw.n;
    const extras = L.links > 0 || (L.motion === "slime" && L.slime_show > 0) || (L.motion === "pendulum" && L.pend_arms > 0);
    if (!n || (L.look === "none" && !extras)) return;
    const col = new Float32Array(n * 3);
    const light = uni.paintColors(sw, col);
    const additive = p.blend === "add";
    if (L.links > 0) { const g = uni.links(sw, col); if (g) this.lines(uni, g.verts, g.cols); }
    if (L.motion === "pendulum" && L.pend_arms > 0) {
      const a = uni.arms(sw, col);
      if (a) {
        this.lines(uni, a.verts, a.cols);
        this.points(uni, a.dots, a.dcols, a.dots.length / 2, { kind: "dot", diam: 6, soft: 0, additive: false });
      }
    }
    if (L.motion === "slime" && L.slime_show > 0 && sw.scent) this.scent(uni, sw, col);
    if (L.look === "none") return;
    const pos = this.grow("pos", n * 2);
    let m = 0, c = col;
    if (L.motion === "grow" && light) {                    // skip the invisible waiting walkers
      c = this.grow("col", n * 3);
      for (let i = 0; i < n; i++) {
        if (!(light[i] > 0)) continue;
        pos[m * 2] = sw.px[i]; pos[m * 2 + 1] = sw.py[i];
        c[m * 3] = col[i * 3]; c[m * 3 + 1] = col[i * 3 + 1]; c[m * 3 + 2] = col[i * 3 + 2];
        m++;
      }
    } else {
      for (let i = 0; i < n; i++) { pos[i * 2] = sw.px[i]; pos[i * 2 + 1] = sw.py[i]; }
      m = n;
    }
    const P = pos.subarray(0, m * 2), C = c.subarray(0, m * 3);
    if (L.look === "dot") this.points(uni, P, C, m, { kind: "dot", diam: L.dot, soft: L.dot_soft, additive });
    else this.points(uni, P, C, m, { kind: "pixel", size: Math.max(1, Math.min(4, Math.floor(L.size))),
                                     gain: additive ? p.glow : 1, additive });
  }
}

DU.Renderer = Renderer;
})();
