/* Field-station motion. No dependencies. Stays quiet when the visitor asks
   for reduced motion, and never blocks clicks. */
(function () {
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.querySelectorAll("header nav a").forEach(function (link) {
    var href = link.getAttribute("href") || "";
    if (href.charAt(0) !== "/") return;
    var path = window.location.pathname;
    var on = false;
    if (href === "/projects") {
      on = path === "/projects" || (path.indexOf("/projects/") === 0 && path.indexOf("/projects/new") !== 0);
    } else if (href === "/projects/new") {
      on = path.indexOf("/projects/new") === 0;
    } else if (href === "/organizer") {
      on = path === "/organizer";
    } else if (href === "/") {
      on = path === "/";
    } else {
      on = path === href || path.indexOf(href + "/") === 0;
    }
    if (on) {
      link.classList.add("on");
      link.setAttribute("aria-current", "page");
    }
  });

  if (reduce || document.body.classList.contains("embed")) return;

  var flora = document.querySelectorAll(".flora");
  if (flora.length && window.innerWidth >= 1500) {
    var paintFlora = function () {
      var shift = Math.round(window.scrollY * 0.08);
      flora[0].style.transform = "translate3d(0," + (-shift) + "px,0)";
      if (flora[1]) {
        flora[1].style.transform = "scaleX(-1) translate3d(0," + (shift * 0.45) + "px,0)";
      }
    };
    paintFlora();
    window.addEventListener("scroll", paintFlora, { passive: true });
  }

  if (window.innerWidth < 1500) return;

  var layer = document.createElement("div");
  layer.className = "track";
  layer.setAttribute("aria-hidden", "true");
  document.body.appendChild(layer);

  var step = 0;
  var lastY = window.scrollY;

  function drop(x, y, flip) {
    var mark = document.createElement("i");
    if (flip) mark.className = "flip";
    mark.style.left = x + "px";
    mark.style.top = y + "px";
    layer.appendChild(mark);
    window.setTimeout(function () {
      if (mark.parentNode) mark.parentNode.removeChild(mark);
    }, 2800);
  }

  function gait(fromScroll) {
    step += 1;
    var leftFoot = step % 2 === 0;
    var x = leftFoot ? 22 : 46;
    var span = Math.max(window.innerHeight - 160, 200);
    var y = 96 + ((step * 86) % span);
    if (fromScroll) y = Math.min(window.innerHeight - 72, Math.max(88, y));
    drop(x, y, !leftFoot);
  }

  window.setTimeout(function () { gait(false); }, 400);
  window.setTimeout(function () { gait(false); }, 700);

  window.addEventListener("scroll", function () {
    if (Math.abs(window.scrollY - lastY) < 180) return;
    lastY = window.scrollY;
    gait(true);
  }, { passive: true });
})();
