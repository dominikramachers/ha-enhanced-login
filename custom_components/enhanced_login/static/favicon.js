/* Enhanced Login: sets the favicon (sign-in pages and the whole UI).
   The icon is rendered in the browser from the logo; no extra files are needed.
   The two placeholders below are filled in by the integration (FaviconView). */
(function () {
  "use strict";
  var LOGO = "__LOGO__";
  var BACKGROUND = "__BACKGROUND__";
  var made = null;

  function render(size) {
    var canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    var ctx = canvas.getContext("2d");
    var r = size * 0.22;
    ctx.beginPath();
    ctx.moveTo(r, 0);
    ctx.lineTo(size - r, 0);
    ctx.quadraticCurveTo(size, 0, size, r);
    ctx.lineTo(size, size - r);
    ctx.quadraticCurveTo(size, size, size - r, size);
    ctx.lineTo(r, size);
    ctx.quadraticCurveTo(0, size, 0, size - r);
    ctx.lineTo(0, r);
    ctx.quadraticCurveTo(0, 0, r, 0);
    ctx.closePath();
    ctx.fillStyle = BACKGROUND;
    ctx.fill();
    var w = size * 0.82;
    var h = (w * img.naturalHeight) / img.naturalWidth;
    ctx.drawImage(img, (size - w) / 2, (size - h) / 2, w, h);
    return canvas.toDataURL("image/png");
  }

  function apply() {
    var head = document.head;
    if (!head || !made) return;
    var old = head.querySelectorAll('link[rel~="icon"], link[rel="apple-touch-icon"], link[rel="mask-icon"]');
    for (var i = 0; i < old.length; i++) {
      if (!old[i].hasAttribute("data-el")) old[i].remove();
    }
    if (head.querySelector("link[data-el]")) return;
    [["icon", 64], ["apple-touch-icon", 192]].forEach(function (item) {
      var link = document.createElement("link");
      link.rel = item[0];
      link.type = "image/png";
      link.sizes = item[1] + "x" + item[1];
      link.href = made[item[1]];
      link.setAttribute("data-el", "");
      head.appendChild(link);
    });
  }

  var img = new Image();
  img.onload = function () {
    try {
      made = { 64: render(64), 192: render(192) };
    } catch (e) {
      return;
    }
    apply();
    new MutationObserver(apply).observe(document.head || document.documentElement, { childList: true });
  };
  img.src = LOGO;
})();
