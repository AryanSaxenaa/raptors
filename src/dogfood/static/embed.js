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
    "width:100%;max-width:960px;height:" + height + "px;border:1px solid #3a4a32;border-radius:2px;background:#10160e";
  script.parentNode.insertBefore(iframe, script.nextSibling);
})();
