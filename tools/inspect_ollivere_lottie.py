"""Inspect Ollivere t-rex Lottie text layers."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

URL = "https://cdn.prod.website-files.com/5ef89928a1cfcec5918d8d5d/5f0ab45b992a5eb630a33b01_t-rex-05.json"
OUT = Path(__file__).resolve().parents[1] / "src/dogfood/static/raptor-hero.lottie.json"

raw = urllib.request.urlopen(URL, timeout=60).read()
data = json.loads(raw)
print("w/h", data.get("w"), data.get("h"), "nm", data.get("nm"))
print("fonts", data.get("fonts"))
print("--- layers ---")
for L in data["layers"]:
    extra = ""
    if L.get("ty") == 5:
        k = L.get("t", {}).get("d", {}).get("k", [])
        s = k[0].get("s", {}) if k else {}
        extra = f" text={s.get('t')!r} size={s.get('s')} f={s.get('f')} fc={s.get('fc')} j={s.get('j')} tr={s.get('tr')}"
    print(f"ind={L.get('ind')} ty={L.get('ty')} parent={L.get('parent')} nm={L.get('nm')!r}{extra}")

# Keep a local copy of original for patching
Path(r"C:\Users\aryan\AppData\Local\Temp\t-rex-05.json").write_bytes(raw)
print("saved original")
