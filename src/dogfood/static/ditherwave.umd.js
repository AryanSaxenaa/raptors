"use strict";var Dither=(()=>{var H=Object.defineProperty;var ce=Object.getOwnPropertyDescriptor;var ue=Object.getOwnPropertyNames;var fe=Object.prototype.hasOwnProperty;var me=(t,r)=>{for(var n in r)H(t,n,{get:r[n],enumerable:!0})},pe=(t,r,n,o)=>{if(r&&typeof r=="object"||typeof r=="function")for(let e of ue(r))!fe.call(t,e)&&e!==n&&H(t,e,{get:()=>r[e],enumerable:!(o=ce(r,e))||o.enumerable});return t};var de=t=>pe(H({},"__esModule",{value:!0}),t);var be={};me(be,{createDither:()=>q,createDitheredWaves:()=>ie,dither:()=>Ee});var y=`#version 300 es
precision highp float;
layout(location=0) in vec2 a_pos;
out vec2 v_uv;
void main(){
  v_uv = a_pos * 0.5 + 0.5;
  gl_Position = vec4(a_pos, 0.0, 1.0);
}`;var x=`#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 o_frag;
uniform sampler2D u_src;
uniform sampler2D u_pal;
uniform vec2 u_res;         // logical dither grid (cells across)
uniform float u_time;
uniform float u_intensity;
uniform float u_paletteCount;
uniform float u_contrast;   // 0.5..3, default 1
uniform float u_brightness; // 0.5..2, default 1

float luma(vec3 c){ return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

// Snap v_uv to the dither grid before sampling so the source is quantised to
// the same cells the threshold pattern uses. Without this, a sharp source
// image will still show its full detail underneath the dot pattern.
vec2 pixelUV(vec2 uv){
  return (floor(uv * u_res) + 0.5) / u_res;
}

// Webcam content sits in a narrow mid-tone band, so without contrast
// expansion the dither pattern becomes uniform speckle. Apply the standard
// 8-bit contrast curve and a brightness multiplier before the luminance
// lookup. Both default to 1 (no-op) for image inputs.
vec3 adjustExposure(vec3 c){
  c = (c - 0.5) * u_contrast + 0.5;
  c *= u_brightness;
  return clamp(c, 0.0, 1.0);
}

vec3 paletteLookup(float t){
  t = clamp(t, 0.0, 1.0);
  float n = max(u_paletteCount - 1.0, 1.0);
  float idx = floor(t * n + 0.5);
  vec2 uv = vec2((idx + 0.5) / u_paletteCount, 0.5);
  return texture(u_pal, uv).rgb;
}

// Per-channel palette quantisation: dither each RGB channel independently
// through the Bayer matrix. For multi-colour palettes this preserves hue far
// better than quantising luminance alone.
vec3 ditherRGB(vec3 color, float threshold){
  float step = 1.0 / max(u_paletteCount - 1.0, 1.0);
  color += vec3(threshold) * step;
  color = clamp(color, 0.0, 1.0);
  return floor(color * (u_paletteCount - 1.0) + 0.5) / (u_paletteCount - 1.0);
}
`;var C=`
const float BAYER[64] = float[64](
   0.0/64.0, 48.0/64.0, 12.0/64.0, 60.0/64.0,  3.0/64.0, 51.0/64.0, 15.0/64.0, 63.0/64.0,
  32.0/64.0, 16.0/64.0, 44.0/64.0, 28.0/64.0, 35.0/64.0, 19.0/64.0, 47.0/64.0, 31.0/64.0,
   8.0/64.0, 56.0/64.0,  4.0/64.0, 52.0/64.0, 11.0/64.0, 59.0/64.0,  7.0/64.0, 55.0/64.0,
  40.0/64.0, 24.0/64.0, 36.0/64.0, 20.0/64.0, 43.0/64.0, 27.0/64.0, 39.0/64.0, 23.0/64.0,
   2.0/64.0, 50.0/64.0, 14.0/64.0, 62.0/64.0,  1.0/64.0, 49.0/64.0, 13.0/64.0, 61.0/64.0,
  34.0/64.0, 18.0/64.0, 46.0/64.0, 30.0/64.0, 33.0/64.0, 17.0/64.0, 45.0/64.0, 29.0/64.0,
  10.0/64.0, 58.0/64.0,  6.0/64.0, 54.0/64.0,  9.0/64.0, 57.0/64.0,  5.0/64.0, 53.0/64.0,
  42.0/64.0, 26.0/64.0, 38.0/64.0, 22.0/64.0, 41.0/64.0, 25.0/64.0, 37.0/64.0, 21.0/64.0
);
float bayer8(vec2 p){
  int x = int(mod(p.x, 8.0));
  int y = int(mod(p.y, 8.0));
  return BAYER[y * 8 + x] - 0.5;
}
float bayer2(vec2 p){
  int x = int(mod(p.x, 2.0));
  int y = int(mod(p.y, 2.0));
  float m[4] = float[4](0.0/4.0, 2.0/4.0, 3.0/4.0, 1.0/4.0);
  return m[y * 2 + x] - 0.5;
}
float bayer4(vec2 p){
  int x = int(mod(p.x, 4.0));
  int y = int(mod(p.y, 4.0));
  float m[16] = float[16](
     0.0/16.0,  8.0/16.0,  2.0/16.0, 10.0/16.0,
    12.0/16.0,  4.0/16.0, 14.0/16.0,  6.0/16.0,
     3.0/16.0, 11.0/16.0,  1.0/16.0,  9.0/16.0,
    15.0/16.0,  7.0/16.0, 13.0/16.0,  5.0/16.0
  );
  return m[y * 4 + x] - 0.5;
}
float bayerN(vec2 p, float n){
  if (n < 3.0) return bayer2(p);
  if (n < 5.0) return bayer4(p);
  return bayer8(p);
}
`;var ee=x+C+`
uniform float u_matrixSize;

void main(){
  vec3 src = texture(u_src, pixelUV(v_uv)).rgb;
  src = adjustExposure(src);
  vec2 cell = floor(v_uv * u_res + u_time * 4.0);

  float threshold = bayerN(cell, u_matrixSize);

  float l = luma(src);
  float dithered = clamp(l + threshold * u_intensity, 0.0, 1.0);

  float levels = max(u_paletteCount - 1.0, 1.0);
  float quantised = floor(dithered * levels + 0.5) / levels;

  o_frag = vec4(paletteLookup(quantised), 1.0);
}`;var te=x+C+`
float hash(vec2 p){
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

void main(){
  vec3 src = texture(u_src, pixelUV(v_uv)).rgb;
  src = adjustExposure(src);
  vec2 cell = floor(v_uv * u_res);

  float n = hash(cell + u_time * 13.0) - 0.5;
  float b = bayer8(cell) * 0.4;
  float threshold = (n * 0.6 + b) * u_intensity;

  float l = luma(src);
  float dithered = clamp(l + threshold, 0.0, 1.0);

  float levels = max(u_paletteCount - 1.0, 1.0);
  float quantised = floor(dithered * levels + 0.5) / levels;

  o_frag = vec4(paletteLookup(quantised), 1.0);
}`;var oe=x+`
void main(){
  float ang = radians(15.0);
  float cs = cos(ang), sn = sin(ang);
  mat2 rot = mat2(cs, -sn, sn, cs);

  // Rotate the sampling grid into a tilted coordinate frame; one cell per
  // u_res unit across the screen.
  vec2 p = rot * ((v_uv - 0.5) * u_res);
  vec2 f = fract(p) - 0.5;

  vec3 src = texture(u_src, pixelUV(v_uv)).rgb;
  src = adjustExposure(src);
  float l = luma(src);
  float dark = 1.0 - l;

  // sqrt keeps mid-tones readable; ink coverage goes ~0 .. ~0.58
  float r = sqrt(dark) * 0.58 * mix(0.6, 1.0, u_intensity);
  float d = length(f);

  // Crisp edge, anti-aliased over one cell.
  float edge = fwidth(d) + 0.01;
  float mask = smoothstep(r + edge, r - edge, d);

  vec3 ink = paletteLookup(0.0);
  vec3 paper = paletteLookup(1.0);

  o_frag = vec4(mix(paper, ink, mask), 1.0);
}`;var re=x+`
uniform sampler2D u_atlas;
uniform float u_charCount;
uniform vec2 u_cell;

void main(){
  // Quantise UV to cell grid for both source sampling and glyph lookup.
  vec2 cell = floor(v_uv * u_cell);
  vec2 cellCenter = (cell + 0.5) / u_cell;
  vec3 src = texture(u_src, cellCenter).rgb;
  src = adjustExposure(src);
  float l = luma(src);

  float idx = floor(l * (u_charCount - 1.0) + 0.5);

  vec2 local = fract(v_uv * u_cell);
  // Flip Y to match canvas2D atlas orientation.
  local.y = 1.0 - local.y;
  vec2 atlasUV = vec2((idx + local.x) / u_charCount, local.y);
  float glyph = texture(u_atlas, atlasUV).r;

  vec3 ink = paletteLookup(0.0);
  vec3 paper = paletteLookup(1.0);

  o_frag = vec4(mix(paper, ink, glyph), 1.0);
}`;function ne(t,r,n){let o=t.createShader(r);if(!o)throw new Error("shader alloc failed");if(t.shaderSource(o,n),t.compileShader(o),!t.getShaderParameter(o,t.COMPILE_STATUS)){let e=t.getShaderInfoLog(o)||"unknown";throw t.deleteShader(o),new Error("shader compile: "+e)}return o}function T(t,r,n){let o=ne(t,t.VERTEX_SHADER,r),e=ne(t,t.FRAGMENT_SHADER,n),f=t.createProgram();if(!f)throw new Error("program alloc failed");if(t.attachShader(f,o),t.attachShader(f,e),t.linkProgram(f),t.deleteShader(o),t.deleteShader(e),!t.getProgramParameter(f,t.LINK_STATUS)){let _=t.getProgramInfoLog(f)||"unknown";throw t.deleteProgram(f),new Error("program link: "+_)}return f}function W(t){let r=t.createVertexArray();t.bindVertexArray(r);let n=t.createBuffer();return t.bindBuffer(t.ARRAY_BUFFER,n),t.bufferData(t.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),t.STATIC_DRAW),t.enableVertexAttribArray(0),t.vertexAttribPointer(0,2,t.FLOAT,!1,0,0),t.bindVertexArray(null),r}function L(t,r){let n=t.createTexture();t.bindTexture(t.TEXTURE_2D,n);let o=r?.filter??t.LINEAR,e=r?.wrap??t.CLAMP_TO_EDGE;return t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MIN_FILTER,o),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_MAG_FILTER,o),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_WRAP_S,e),t.texParameteri(t.TEXTURE_2D,t.TEXTURE_WRAP_T,e),n}function G(t){let r=t.trim().replace("#","");if(r.length===3&&(r=r.split("").map(o=>o+o).join("")),r.length!==6)return[0,0,0];let n=parseInt(r,16);return[(n>>16&255)/255,(n>>8&255)/255,(n&255)/255]}function F(t,r=16){let n=document.createElement("canvas");n.width=r*t.length,n.height=r;let o=n.getContext("2d");o.fillStyle="#000",o.fillRect(0,0,n.width,n.height),o.fillStyle="#fff",o.textBaseline="middle",o.textAlign="center",o.font=`${Math.floor(r*.9)}px ui-monospace, "JetBrains Mono", "Fira Code", "Menlo", monospace`;for(let e=0;e<t.length;e++)o.fillText(t[e],e*r+r/2,r/2+1);return n}var ve={mode:"bayer",resolution:256,palette:["#0f0f10","#f5f3ef"],intensity:1,animate:!1,matrixSize:8,charset:" .:-=+*#%@",contrast:1,brightness:1,pauseOffscreen:!0,pixelRatio:typeof window<"u"?Math.min(window.devicePixelRatio||1,2):1};function ae(t){return t.tagName==="IMG"}function k(t){return t.tagName==="VIDEO"}function he(t){return t.tagName==="CANVAS"}function q(t,r,n={}){let o={...ve,...n},e=t.getContext("webgl2",{antialias:!1,premultipliedAlpha:!1});if(!e)throw new Error("WebGL2 not supported");let f={bayer:T(e,y,ee),floyd:T(e,y,te),dots:T(e,y,oe),ascii:T(e,y,re)},_=W(e),g=L(e,{filter:e.LINEAR}),w=L(e,{filter:e.NEAREST}),s=L(e,{filter:e.LINEAR});e.bindTexture(e.TEXTURE_2D,g),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,1,1,0,e.RGBA,e.UNSIGNED_BYTE,new Uint8Array([0,0,0,0]));let U=null,S=o.charset.length;function D(i){let a=Math.max(2,Math.min(8,i.length)),m=new Uint8Array(a*4);for(let u=0;u<a;u++){let[d,v,b]=G(i[u]||"#000");m[u*4+0]=Math.round(d*255),m[u*4+1]=Math.round(v*255),m[u*4+2]=Math.round(b*255),m[u*4+3]=255}return e.bindTexture(e.TEXTURE_2D,w),e.pixelStorei(e.UNPACK_ALIGNMENT,1),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,a,1,0,e.RGBA,e.UNSIGNED_BYTE,m),a}function M(i){U=F(i),S=i.length,e.bindTexture(e.TEXTURE_2D,s),e.pixelStorei(e.UNPACK_ALIGNMENT,1),e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,U)}let A=D(o.palette);M(o.charset);function B(){let i=0,a=0;return ae(r)?(i=r.naturalWidth,a=r.naturalHeight):k(r)?(i=r.videoWidth,a=r.videoHeight):(i=r.width,a=r.height),(!i||!a)&&(i=640,a=360),{w:i,h:a}}function z(){let{w:i,h:a}=B(),m=o.pixelRatio,u=t.parentElement,d=t.clientWidth,v=t.clientHeight;(!d||!v)&&u&&(d=u.clientWidth,v=u.clientHeight),(!d||!v)&&(d=i,v=a);let b=Math.max(1,Math.floor(d*m)),O=Math.max(1,Math.floor(v*m));t.width!==b&&(t.width=b),t.height!==O&&(t.height=O)}function h(){e.bindTexture(e.TEXTURE_2D,g),e.pixelStorei(e.UNPACK_ALIGNMENT,1),e.pixelStorei(e.UNPACK_FLIP_Y_WEBGL,!0);try{e.texImage2D(e.TEXTURE_2D,0,e.RGBA,e.RGBA,e.UNSIGNED_BYTE,r)}catch{}e.pixelStorei(e.UNPACK_FLIP_Y_WEBGL,!1)}let R=!1;ae(r)?r.complete&&r.naturalWidth>0?(R=!0,h()):r.addEventListener("load",()=>{R=!0,h()},{once:!0}):R=!0;let N=!0,l=null;o.pauseOffscreen&&typeof IntersectionObserver<"u"&&(l=new IntersectionObserver(i=>{for(let a of i)N=a.isIntersecting},{threshold:0}),l.observe(t));let c=performance.now(),p=0,E=0;function I(){if(!e)return;z(),(k(r)&&r.readyState>=2||he(r))&&h();let i=o.mode,a=f[i];e.useProgram(a),e.bindVertexArray(_),e.activeTexture(e.TEXTURE0),e.bindTexture(e.TEXTURE_2D,g);let m=e.getUniformLocation(a,"u_src");m&&e.uniform1i(m,0),e.activeTexture(e.TEXTURE1),e.bindTexture(e.TEXTURE_2D,w);let u=e.getUniformLocation(a,"u_pal");u&&e.uniform1i(u,1);let d=e.getUniformLocation(a,"u_res");d&&e.uniform2f(d,o.resolution,o.resolution);let v=e.getUniformLocation(a,"u_time");v&&e.uniform1f(v,o.animate?(performance.now()-c)/1e3:0);let b=e.getUniformLocation(a,"u_intensity");b&&e.uniform1f(b,o.intensity);let O=e.getUniformLocation(a,"u_contrast");O&&e.uniform1f(O,o.contrast);let K=e.getUniformLocation(a,"u_brightness");K&&e.uniform1f(K,o.brightness);let $=e.getUniformLocation(a,"u_paletteCount");if($&&e.uniform1f($,A),i==="bayer"){let V=e.getUniformLocation(a,"u_matrixSize");V&&e.uniform1f(V,o.matrixSize)}if(i==="ascii"){e.activeTexture(e.TEXTURE2),e.bindTexture(e.TEXTURE_2D,s);let V=e.getUniformLocation(a,"u_atlas");V&&e.uniform1i(V,2);let J=e.getUniformLocation(a,"u_charCount");J&&e.uniform1f(J,S);let Q=e.getUniformLocation(a,"u_cell");if(Q){let le=t.width/t.height,Z=Math.max(4,Math.floor(o.resolution/4)),se=Math.max(4,Math.floor(Z/le));e.uniform2f(Q,Z,se)}}e.viewport(0,0,t.width,t.height),e.drawArrays(e.TRIANGLES,0,3),e.bindVertexArray(null)}function P(){p=requestAnimationFrame(P),N&&R&&I()}p=requestAnimationFrame(P);function X(){k(r)&&"requestVideoFrameCallback"in r&&(E=r.requestVideoFrameCallback(()=>{h(),X()}))}X();let Y=i=>{i.preventDefault(),cancelAnimationFrame(p)},j=()=>{};return t.addEventListener("webglcontextlost",Y),t.addEventListener("webglcontextrestored",j),{destroy(){cancelAnimationFrame(p),l&&l.disconnect(),t.removeEventListener("webglcontextlost",Y),t.removeEventListener("webglcontextrestored",j),k(r)&&"cancelVideoFrameCallback"in r&&E&&r.cancelVideoFrameCallback(E),e.deleteTexture(g),e.deleteTexture(w),e.deleteTexture(s),Object.values(f).forEach(i=>e.deleteProgram(i))},setOptions(i){let a=o.palette,m=o.charset;o={...o,...i},i.palette&&i.palette!==a&&(A=D(o.palette)),i.charset&&i.charset!==m&&M(o.charset)},render(){I()}}}var xe=`#version 300 es
precision highp float;
in vec2 v_uv;
out vec4 o_frag;

uniform vec2  u_res;
uniform float u_time;
uniform float u_waveSpeed;
uniform float u_waveFrequency;
uniform float u_waveAmplitude;
uniform vec3  u_waveColor;
uniform vec3  u_baseColor;
uniform float u_pixelSize;
uniform float u_colorNum;
uniform vec2  u_mouse;
uniform float u_mouseEnabled;
uniform float u_mouseRadius;
uniform int   u_mode;        // 0 bayer \xB7 1 floyd \xB7 2 dots \xB7 3 ascii
uniform float u_matrixSize;  // 2 | 4 | 8
uniform sampler2D u_atlas;
uniform float u_charCount;

vec4 mod289(vec4 x){ return x - floor(x * (1.0/289.0)) * 289.0; }
vec4 permute(vec4 x){ return mod289(((x * 34.0) + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r){ return 1.79284291400159 - 0.85373472095314 * r; }
vec2 fade(vec2 t){ return t*t*t*(t*(t*6.0-15.0)+10.0); }

float cnoise(vec2 P){
  vec4 Pi = floor(P.xyxy) + vec4(0.0, 0.0, 1.0, 1.0);
  vec4 Pf = fract(P.xyxy) - vec4(0.0, 0.0, 1.0, 1.0);
  Pi = mod289(Pi);
  vec4 ix = Pi.xzxz;
  vec4 iy = Pi.yyww;
  vec4 fx = Pf.xzxz;
  vec4 fy = Pf.yyww;
  vec4 i = permute(permute(ix) + iy);
  vec4 gx = fract(i * (1.0/41.0)) * 2.0 - 1.0;
  vec4 gy = abs(gx) - 0.5;
  vec4 tx = floor(gx + 0.5);
  gx = gx - tx;
  vec2 g00 = vec2(gx.x, gy.x);
  vec2 g10 = vec2(gx.y, gy.y);
  vec2 g01 = vec2(gx.z, gy.z);
  vec2 g11 = vec2(gx.w, gy.w);
  vec4 norm = taylorInvSqrt(vec4(dot(g00,g00), dot(g01,g01), dot(g10,g10), dot(g11,g11)));
  g00 *= norm.x; g01 *= norm.y; g10 *= norm.z; g11 *= norm.w;
  float n00 = dot(g00, vec2(fx.x, fy.x));
  float n10 = dot(g10, vec2(fx.y, fy.y));
  float n01 = dot(g01, vec2(fx.z, fy.z));
  float n11 = dot(g11, vec2(fx.w, fy.w));
  vec2 fade_xy = fade(Pf.xy);
  vec2 n_x = mix(vec2(n00, n01), vec2(n10, n11), fade_xy.x);
  return 2.3 * mix(n_x.x, n_x.y, fade_xy.y);
}

float fbm(vec2 p){
  float v = 0.0;
  float amp = 1.0;
  for (int i = 0; i < 4; i++) {
    v += amp * abs(cnoise(p));
    p *= u_waveFrequency;
    amp *= u_waveAmplitude;
  }
  return v;
}
float pattern(vec2 p){
  vec2 q = p - u_time * u_waveSpeed;
  return fbm(p + fbm(q));
}

float hash(vec2 p){
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

${C}

// Sample the wave at cell-centre coords so each dither cell draws one value.
float sampleWave(vec2 snappedUV){
  vec2 p = snappedUV - 0.5;
  p.x *= u_res.x / u_res.y;
  float f = pattern(p);
  if (u_mouseEnabled > 0.5) {
    vec2 mN = (u_mouse / u_res - 0.5);
    mN.y = -mN.y;
    mN.x *= u_res.x / u_res.y;
    float d = length(p - mN);
    float e = 1.0 - smoothstep(0.0, u_mouseRadius, d);
    f -= 0.5 * e;
  }
  return clamp(f, 0.0, 1.0);
}

void main(){
  vec2 px = u_pixelSize / u_res;
  vec2 snappedUV = px * floor(v_uv / px);
  vec2 cell = floor(v_uv * u_res / u_pixelSize);

  float f = sampleWave(snappedUV);
  vec3 col = mix(u_baseColor, u_waveColor, f);

  // ----- bayer (default) -----
  if (u_mode == 0) {
    float threshold = bayerN(cell, u_matrixSize) * 0.5;
    float step = 1.0 / max(u_colorNum - 1.0, 1.0);
    vec3 c = col + vec3(threshold) * step;
    c = clamp(c - 0.15, 0.0, 1.0);
    c = floor(c * (u_colorNum - 1.0) + 0.5) / (u_colorNum - 1.0);
    o_frag = vec4(c, 1.0);
    return;
  }

  // ----- floyd / riemersma approximation -----
  if (u_mode == 1) {
    float n = hash(cell + u_time * 13.0) - 0.5;
    float b = bayerN(cell, u_matrixSize) * 0.4;
    float threshold = (n * 0.65 + b) * 0.9;
    float step = 1.0 / max(u_colorNum - 1.0, 1.0);
    vec3 c = col + vec3(threshold) * step;
    c = clamp(c, 0.0, 1.0);
    c = floor(c * (u_colorNum - 1.0) + 0.5) / (u_colorNum - 1.0);
    o_frag = vec4(c, 1.0);
    return;
  }

  // ----- dots / halftone -----
  if (u_mode == 2) {
    float ang = radians(15.0);
    float cs = cos(ang), sn = sin(ang);
    mat2 rot = mat2(cs, -sn, sn, cs);
    // Centre + correct aspect FIRST so dots stay circular in screen space,
    // THEN rotate, THEN scale uniformly. (Scaling non-uniformly before
    // rotating skews the grid into a parallelogram on portrait viewports \u2014
    // visible as the whole image looking tilted on phones.)
    vec2 uvCentered = v_uv - 0.5;
    uvCentered.x *= u_res.x / u_res.y;
    float dotsAcross = u_res.y / (u_pixelSize * 2.0);
    vec2 p = rot * uvCentered * dotsAcross;
    vec2 fc = fract(p) - 0.5;
    float dark = 1.0 - f;
    float r = sqrt(dark) * 0.58;
    float d = length(fc);
    float edge = fwidth(d) + 0.01;
    float mask = smoothstep(r + edge, r - edge, d);
    o_frag = vec4(mix(u_baseColor, u_waveColor, mask), 1.0);
    return;
  }

  // ----- ascii -----
  // True square cells: derive cell size from a fixed pixel dimension so
  // glyphs are never stretched on portrait viewports.
  float cellPx = u_pixelSize * 8.0;
  vec2  cellSizeUV = vec2(cellPx) / u_res;
  vec2  gCell    = floor(v_uv / cellSizeUV);
  vec2  gCenter  = (gCell + 0.5) * cellSizeUV;
  float fg = sampleWave(gCenter);

  float idx   = floor(fg * (u_charCount - 1.0) + 0.5);
  vec2  local = fract(v_uv / cellSizeUV);
  local.y = 1.0 - local.y;
  vec2  atlasUV = vec2((idx + local.x) / u_charCount, local.y);
  float glyph = texture(u_atlas, atlasUV).r;
  o_frag = vec4(mix(u_baseColor, u_waveColor, glyph), 1.0);
}
`,_e={bayer:0,floyd:1,dots:2,ascii:3},ge={mode:"bayer",matrixSize:8,waveSpeed:.05,waveFrequency:3,waveAmplitude:.3,waveColor:"#7e7e7e",baseColor:"#000000",colorNum:4,pixelSize:2,charset:" .:-=+*#%@",disableAnimation:!1,enableMouseInteraction:!0,mouseRadius:1,pixelRatio:typeof window<"u"?Math.min(window.devicePixelRatio||1,2):1};function ie(t,r={}){let n={...ge,...r},o=t.getContext("webgl2",{antialias:!1,premultipliedAlpha:!1});if(!o)throw new Error("WebGL2 not supported");let e=T(o,y,xe),f=W(o),_=L(o,{filter:o.LINEAR}),g=n.charset.length;function w(l){let c=F(l);g=l.length,o.bindTexture(o.TEXTURE_2D,_),o.pixelStorei(o.UNPACK_ALIGNMENT,1),o.texImage2D(o.TEXTURE_2D,0,o.RGBA,o.RGBA,o.UNSIGNED_BYTE,c)}w(n.charset);let s={res:o.getUniformLocation(e,"u_res"),time:o.getUniformLocation(e,"u_time"),waveSpeed:o.getUniformLocation(e,"u_waveSpeed"),waveFrequency:o.getUniformLocation(e,"u_waveFrequency"),waveAmplitude:o.getUniformLocation(e,"u_waveAmplitude"),waveColor:o.getUniformLocation(e,"u_waveColor"),baseColor:o.getUniformLocation(e,"u_baseColor"),pixelSize:o.getUniformLocation(e,"u_pixelSize"),colorNum:o.getUniformLocation(e,"u_colorNum"),mouse:o.getUniformLocation(e,"u_mouse"),mouseEnabled:o.getUniformLocation(e,"u_mouseEnabled"),mouseRadius:o.getUniformLocation(e,"u_mouseRadius"),mode:o.getUniformLocation(e,"u_mode"),matrixSize:o.getUniformLocation(e,"u_matrixSize"),atlas:o.getUniformLocation(e,"u_atlas"),charCount:o.getUniformLocation(e,"u_charCount")},U=0,S=0,D=l=>{let c=t.getBoundingClientRect(),p=n.pixelRatio;U=(l.clientX-c.left)*p,S=(l.clientY-c.top)*p};t.addEventListener("pointermove",D);let M=!0,A=null;typeof IntersectionObserver<"u"&&(A=new IntersectionObserver(l=>{for(let c of l)M=c.isIntersecting}),A.observe(t));function B(){let l=n.pixelRatio,c=t.parentElement,p=t.clientWidth||c?.clientWidth||0,E=t.clientHeight||c?.clientHeight||0;(!p||!E)&&(p=640,E=360);let I=Math.max(1,Math.floor(p*l)),P=Math.max(1,Math.floor(E*l));t.width!==I&&(t.width=I),t.height!==P&&(t.height=P)}let z=performance.now(),h=0;function R(){B(),o.useProgram(e),o.bindVertexArray(f),o.activeTexture(o.TEXTURE0),o.bindTexture(o.TEXTURE_2D,_),o.uniform1i(s.atlas,0),o.uniform1f(s.charCount,g),o.uniform2f(s.res,t.width,t.height),o.uniform1f(s.time,n.disableAnimation?0:(performance.now()-z)/1e3),o.uniform1f(s.waveSpeed,n.waveSpeed),o.uniform1f(s.waveFrequency,n.waveFrequency),o.uniform1f(s.waveAmplitude,n.waveAmplitude);let l=G(n.waveColor),c=G(n.baseColor);o.uniform3f(s.waveColor,l[0],l[1],l[2]),o.uniform3f(s.baseColor,c[0],c[1],c[2]),o.uniform1f(s.pixelSize,Math.max(1,n.pixelSize)),o.uniform1f(s.colorNum,Math.max(2,Math.min(8,n.colorNum))),o.uniform2f(s.mouse,U,S),o.uniform1f(s.mouseEnabled,n.enableMouseInteraction?1:0),o.uniform1f(s.mouseRadius,n.mouseRadius),o.uniform1i(s.mode,_e[n.mode]??0),o.uniform1f(s.matrixSize,n.matrixSize),o.viewport(0,0,t.width,t.height),o.drawArrays(o.TRIANGLES,0,3)}function N(){h=requestAnimationFrame(N),M&&R()}return h=requestAnimationFrame(N),{destroy(){cancelAnimationFrame(h),t.removeEventListener("pointermove",D),A?.disconnect(),o.deleteTexture(_),o.deleteProgram(e)},setOptions(l){let c=n.charset;n={...n,...l},l.charset&&l.charset!==c&&w(n.charset)}}}function Ee(t,r,n){return q(r,t,n)}return de(be);})();
globalThis.Dither = Dither;
//# sourceMappingURL=vanilla.umd.global.js.map