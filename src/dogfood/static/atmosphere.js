(function () {
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var root = document.documentElement;

  function themeVar(name, fallback) {
    var v = getComputedStyle(root).getPropertyValue(name).trim();
    return v || fallback;
  }

  function themeRgb(name, fallbackTriple) {
    var v = themeVar(name, fallbackTriple);
    return v.split(",").map(function (n) { return parseInt(n.trim(), 10); });
  }

  var gridInk = themeRgb("--fx-grid-rgb", "37, 34, 34");
  var gridLine = themeRgb("--fx-grid-line-rgb", "216, 214, 204");
  var waveBase = themeVar("--fx-wave-base", "#1c1b19");
  var waveInk = themeVar("--fx-wave-ink", "#8a8680");

  function whenReady(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  function size2d(canvas) {
    var parent = canvas.parentElement;
    if (!parent) return { w: 1, h: 1 };
    var w = Math.max(1, parent.clientWidth);
    var h = Math.max(1, parent.clientHeight);
    var dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.width = Math.max(1, Math.floor(w * dpr));
    canvas.height = Math.max(1, Math.floor(h * dpr));
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    var ctx = canvas.getContext("2d");
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { w: w, h: h, ctx: ctx };
  }

  function paintGrid(ctx, w, h, t) {
    ctx.clearRect(0, 0, w, h);
    var chars = "0123456789ABCDEF";
    var cellSize = 32;
    var cols = Math.ceil(w / cellSize);
    var rows = Math.ceil(h / cellSize);
    var fontSize = 13;
    ctx.font = "bold " + fontSize + "px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        var x = c * cellSize + cellSize / 2;
        var y = r * cellSize + cellSize / 2;
        var phase = Math.floor(t * 1.4 + r * 0.5 + c * 0.3);
        var charIdx = ((phase + r * 7 + c * 13) % chars.length + chars.length) % chars.length;
        var wave = Math.sin(t * 1.2 + r * 0.4 + c * 0.3) * 0.5 + 0.5;
        ctx.fillStyle = "rgba(" + gridInk.join(",") + "," + (0.05 + wave * 0.12) + ")";
        ctx.fillText(chars.charAt(charIdx), x, y);
      }
    }

    ctx.strokeStyle = "rgba(" + gridLine.join(",") + ",0.35)";
    ctx.lineWidth = 1;
    for (var gr = 0; gr <= rows; gr++) {
      ctx.beginPath();
      ctx.moveTo(0, gr * cellSize);
      ctx.lineTo(w, gr * cellSize);
      ctx.stroke();
    }
    for (var gc = 0; gc <= cols; gc++) {
      ctx.beginPath();
      ctx.moveTo(gc * cellSize, 0);
      ctx.lineTo(gc * cellSize, h);
      ctx.stroke();
    }
  }

  function initGrid(canvas) {
    var t = 0;
    var rafId = 0;
    var visible = true;
    var sized = size2d(canvas);
    if (!sized.ctx) return;

    function frame() {
      sized = size2d(canvas);
      if (sized.ctx) paintGrid(sized.ctx, sized.w, sized.h, t);
      if (!reduceMotion) t += 0.016;
      if (!reduceMotion && visible) rafId = window.requestAnimationFrame(frame);
    }

    if (reduceMotion) {
      paintGrid(sized.ctx, sized.w, sized.h, 0);
    } else {
      frame();
    }

    window.addEventListener("resize", function () {
      if (reduceMotion) {
        sized = size2d(canvas);
        if (sized.ctx) paintGrid(sized.ctx, sized.w, sized.h, 0);
      }
    });

    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        visible = entries.some(function (e) { return e.isIntersecting; });
        if (visible && !reduceMotion && !rafId) frame();
        if (!visible && rafId) {
          window.cancelAnimationFrame(rafId);
          rafId = 0;
        }
      }).observe(canvas.parentElement || canvas);
    }
  }

  /** ditherwave IO treats 0×0 canvases as off-screen and never draws. Size first. */
  function primeWaveCanvas(canvas, attempt, done) {
    var stage = canvas.parentElement;
    if (!stage) return;
    var rect = stage.getBoundingClientRect();
    if ((rect.width < 4 || rect.height < 4) && attempt < 30) {
      window.requestAnimationFrame(function () {
        primeWaveCanvas(canvas, attempt + 1, done);
      });
      return;
    }
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = Math.max(1, Math.floor(rect.width));
    var h = Math.max(1, Math.floor(rect.height));
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    canvas.width = Math.max(1, Math.floor(w * dpr));
    canvas.height = Math.max(1, Math.floor(h * dpr));
    done();
  }

  function initWaves(canvas) {
    if (!window.Dither || typeof window.Dither.createDitheredWaves !== "function") {
      return;
    }
    primeWaveCanvas(canvas, 0, function () {
      try {
        window.Dither.createDitheredWaves(canvas, {
          waveColor: waveInk,
          baseColor: waveBase,
          pixelSize: 4,
          colorNum: 5,
          waveSpeed: reduceMotion ? 0.029 : 0.0504,
          waveFrequency: 2.8,
          waveAmplitude: 0.28,
          enableMouseInteraction: !reduceMotion,
          disableAnimation: false,
        });
      } catch (err) {
        if (canvas.parentElement) canvas.parentElement.hidden = true;
      }
    });
  }

  function boot() {
    if (!window.Dither) {
      window.requestAnimationFrame(boot);
      return;
    }
    document.querySelectorAll('canvas[data-fx="grid"]').forEach(initGrid);
    document.querySelectorAll('canvas[data-fx="waves"]').forEach(initWaves);
  }

  whenReady(function () {
    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(boot);
    });
  });
})();
