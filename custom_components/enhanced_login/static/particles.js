/* Enhanced Login: particle background for the pages of hass-oidc-auth.
   The stock sign-in page (/auth/authorize) draws its own particles, so this script only runs
   on the other pages, to give the whole sign-in flow the same background. It mirrors the
   look of the stock "links" preset (about 50 slowly moving dots with thin connecting lines)
   and uses the accent color of the theme. Opacity comes from login.css (canvas#particles).
   Without this script everything stays usable; the pages just have a plain background. */
(function () {
  "use strict";
  if (location.pathname === "/auth/authorize") return;
  if (document.getElementById("particles")) return;

  var canvas = document.createElement("canvas");
  canvas.id = "particles";
  canvas.setAttribute("aria-hidden", "true");
  canvas.style.cssText =
    "position:fixed;top:0;left:0;width:100%;height:100%;z-index:-1;pointer-events:none;";
  (document.body || document.documentElement).appendChild(canvas);

  var ctx = canvas.getContext("2d");
  if (!ctx) return;

  var LINK_DISTANCE = 100;
  var LINK_OPACITY = 0.7;
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var speedFactor = reduce ? 0.25 : 1;
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var width = 0;
  var height = 0;
  var dots = [];
  var color = [76, 141, 246];
  var running = false;

  function readColor() {
    // Accept #rgb / #rrggbb from the theme; anything else keeps the default blue.
    var raw = getComputedStyle(document.documentElement).getPropertyValue("--el-accent").trim();
    var m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(raw);
    if (!m) return;
    var hex = m[1].length === 3 ? m[1].replace(/./g, "$&$&") : m[1];
    color = [0, 2, 4].map(function (i) {
      return parseInt(hex.substr(i, 2), 16);
    });
  }

  function rand(min, max) {
    return min + Math.random() * (max - min);
  }

  function makeDot() {
    var angle = Math.random() * Math.PI * 2;
    var speed = 0.5 * speedFactor * 0.6;
    return {
      x: Math.random() * width,
      y: Math.random() * height,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      size: rand(1, 3),
      sizeDir: Math.random() < 0.5 ? -1 : 1,
      alpha: rand(0.3, 0.5),
      alphaDir: Math.random() < 0.5 ? -1 : 1,
    };
  }

  function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var count = width < 700 ? 28 : 50;
    while (dots.length < count) dots.push(makeDot());
    dots.length = count;
  }

  function rgba(alpha) {
    return "rgba(" + color[0] + "," + color[1] + "," + color[2] + "," + alpha + ")";
  }

  function frame() {
    if (!running) return;
    ctx.clearRect(0, 0, width, height);
    var i, j, a, b, dx, dy, dist;
    for (i = 0; i < dots.length; i++) {
      a = dots[i];
      a.x += a.vx;
      a.y += a.vy;
      // wrap around the edges like the stock preset ("out" mode)
      if (a.x < -5) a.x = width + 5;
      else if (a.x > width + 5) a.x = -5;
      if (a.y < -5) a.y = height + 5;
      else if (a.y > height + 5) a.y = -5;
      a.size += a.sizeDir * 0.012 * speedFactor;
      if (a.size > 3) { a.size = 3; a.sizeDir = -1; }
      else if (a.size < 1) { a.size = 1; a.sizeDir = 1; }
      a.alpha += a.alphaDir * 0.003 * speedFactor;
      if (a.alpha > 0.5) { a.alpha = 0.5; a.alphaDir = -1; }
      else if (a.alpha < 0.3) { a.alpha = 0.3; a.alphaDir = 1; }
    }
    ctx.lineWidth = 1;
    for (i = 0; i < dots.length; i++) {
      a = dots[i];
      for (j = i + 1; j < dots.length; j++) {
        b = dots[j];
        dx = a.x - b.x;
        dy = a.y - b.y;
        dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > LINK_DISTANCE) continue;
        ctx.strokeStyle = rgba(LINK_OPACITY * (1 - dist / LINK_DISTANCE));
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }
    for (i = 0; i < dots.length; i++) {
      a = dots[i];
      ctx.fillStyle = rgba(a.alpha);
      ctx.beginPath();
      ctx.arc(a.x, a.y, a.size, 0, Math.PI * 2);
      ctx.fill();
    }
    requestAnimationFrame(frame);
  }

  function start() {
    if (running) return;
    running = true;
    requestAnimationFrame(frame);
  }

  readColor();
  resize();
  window.addEventListener("resize", resize);
  // pause while the tab is hidden (like the stock "pauseOnBlur")
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) running = false;
    else start();
  });
  start();
})();
