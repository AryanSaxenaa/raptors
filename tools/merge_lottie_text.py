"""One-off: restore bite text layers from Ollivere source into local hero Lottie."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "src/dogfood/static/raptor-hero.lottie.json"
SKIP_TEXT = {"Great Design"}


def fetch_ollivere_trex_url() -> str:
    html = urllib.request.urlopen("https://ollivere.webflow.io/", timeout=60).read().decode(
        "utf-8", "replace"
    )
    urls = re.findall(r"https://[^\"'\s>]+\.json", html)
    for u in urls:
        if "t-rex" in u.lower() or "trex" in u.lower():
            return u
    for u in urls:
        if "lottie" in u.lower() or "animation" in u.lower():
            return u
    raise SystemExit(f"No trex json in page; found: {urls[:10]}")


def main() -> None:
    src_url = fetch_ollivere_trex_url()
    print("source", src_url)
    remote = json.loads(urllib.request.urlopen(src_url, timeout=60).read())
    local = json.loads(LOCAL.read_text(encoding="utf-8"))

    text_layers = [L for L in remote["layers"] if L.get("ty") == 5 and L.get("nm") not in SKIP_TEXT]
    if not text_layers:
        raise SystemExit("No text layers in remote")

    # Replace shape stack with local shapes + bite text only (no duplicate headline).
    shapes = [L for L in local["layers"] if L.get("ty") != 5]
    merged_layers = remote["layers"]
    # Use full remote layer order (jaw over text) but drop Great Design.
    merged_layers = [L for L in remote["layers"] if not (L.get("ty") == 5 and L.get("nm") in SKIP_TEXT)]

    out = {k: v for k, v in remote.items() if k != "layers"}
    out["layers"] = merged_layers
    out["nm"] = local.get("nm", out.get("nm", "raptor-hero-raptors"))

    # Patch copy to match our headline (keep animation paths).
    for layer in out["layers"]:
        if layer.get("ty") != 5:
            continue
        t = layer.get("t", {}).get("d", {}).get("k", [])
        if isinstance(t, list) and t:
            s = t[0].get("s", {})
            nm = layer.get("nm", "")
            if nm == "No":
                s["t"] = "No"
            elif "nonsense" in nm.lower() or nm == "KIlled Word":
                s["t"] = "nonsense."

    LOCAL.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {LOCAL.name}: {len(out['layers'])} layers, text:", [L["nm"] for L in text_layers])


if __name__ == "__main__":
    main()
