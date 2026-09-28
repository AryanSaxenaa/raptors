(function () {
  function hashId(id) {
    var h = 0;
    for (var i = 0; i < id.length; i++) h = (Math.imul(31, h) + id.charCodeAt(i)) | 0;
    return Math.abs(h);
  }

  document.querySelectorAll(".specimen-thumb[data-project-id]").forEach(function (el) {
    var id = el.getAttribute("data-project-id") || "";
    var h = hashId(id) % 360;
    el.style.setProperty("--spec-h", String(h));
    el.style.setProperty("--spec-x", String((hashId(id + "x") % 80) + 10) + "%");
    el.style.setProperty("--spec-y", String((hashId(id + "y") % 70) + 15) + "%");
  });

  document.querySelectorAll(".vote-stepper").forEach(function (wrap) {
    var input = wrap.querySelector(".ballot-credits");
    if (!input) return;
    wrap.querySelectorAll("[data-step]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var max = parseInt(input.getAttribute("max"), 10) || 99;
        var min = parseInt(input.getAttribute("min"), 10) || 1;
        var v = parseInt(input.value, 10) || min;
        v += parseInt(btn.getAttribute("data-step"), 10);
        input.value = String(Math.max(min, Math.min(max, v)));
      });
    });
  });
})();
