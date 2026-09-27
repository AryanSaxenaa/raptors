# Asset credits

Every image in this interface is either drawn for this repo or a self-hosted open-licensed font. Nothing is hotlinked. Nothing is taken from Jurassic Park, Jurassic World, or fan archives of those films.

## Original artwork

Drawn for this project (no third-party licence; use within this repo).

| File | What it is |
| --- | --- |
| `src/dogfood/static/raptor.svg` | Field-plate raptor, side view, used as the source drawing |
| `src/dogfood/templates/_raptor.html` | The same plate, inlined so the eye can blink |
| `src/dogfood/static/mark.svg` | Header mark: raptor head in a specimen frame |
| `src/dogfood/static/favicon.svg` | Station favicon |
| `src/dogfood/static/footprint.svg` | Three-toed track used by the scroll gait |
| `src/dogfood/static/claw.svg` | Claw-scratch divider |
| `src/dogfood/static/topo.svg` | Repeating contour-line tile |
| `src/dogfood/static/foliage.svg` | Margin silhouette of fronds |
| `src/dogfood/static/cursor.svg` | Survey pointer for the page ground |
| `src/dogfood/static/og.png` | Social image rendered from the same plate and palette |

## Fonts

Latin-subset WOFF2 files, committed under `src/dogfood/static/fonts/`. They were downloaded from Fontsource’s CDN at build time and are served by this app, not requested from a CDN at runtime. Each family remains under the SIL Open Font License 1.1. The license text shipped with the upstream family is in the same folder. Reserved Font Names are unchanged.

| Files | Family | Copyright | Source | Licence |
| --- | --- | --- | --- | --- |
| `fraunces-latin-600.woff2`, `fraunces-latin-700.woff2` | Fraunces | Copyright 2018 The Fraunces Project Authors (https://github.com/undercasetype/Fraunces) | https://fontsource.org/fonts/fraunces · upstream https://github.com/undercasetype/Fraunces | SIL OFL 1.1 (`Fraunces-OFL.txt`) |
| `atkinson-hyperlegible-latin-400.woff2`, `atkinson-hyperlegible-latin-700.woff2` | Atkinson Hyperlegible | Copyright 2020 Braille Institute of America, Inc. | https://fontsource.org/fonts/atkinson-hyperlegible · upstream https://github.com/googlefonts/atkinson-hyperlegible | SIL OFL 1.1 (`AtkinsonHyperlegible-OFL.txt`) |
| `ibm-plex-mono-latin-400.woff2`, `ibm-plex-mono-latin-500.woff2` | IBM Plex Mono | Copyright © 2017 IBM Corp. with Reserved Font Name "Plex" | https://fontsource.org/fonts/ibm-plex-mono · upstream https://github.com/IBM/plex | SIL OFL 1.1 (`IBMPlexMono-OFL.txt`) |

Fontsource package versions used for the subset files: Fraunces 5.2.8, Atkinson Hyperlegible 5.2.8, IBM Plex Mono 5.2.7.
