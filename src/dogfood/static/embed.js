(function () {
  var script = document.currentScript;
  if (!script) return;
  var src = new URL(script.src);
  var event = script.getAttribute("data-event") || "evt_01";
  var height = script.getAttribute("data-height") || "420";
  var iframe = document.createElement("iframe");
  iframe.src = src.origin + "/embed/gallery?event=" + encodeURIComponent(event);
  iframe.title = "Dogfood gallery";
  iframe.loading = "lazy";
  iframe.style.cssText =
    "width:100%;max-width:960px;height:" + height + "px;border:1px solid #30363d;border-radius:8px;background:#0d1117";
  script.parentNode.insertBefore(iframe, script.nextSibling);
})();
