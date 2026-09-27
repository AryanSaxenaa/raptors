# Field station design system

Dogfood Portal is a self-hosted hackathon gallery, ballot, and organizer console. The visual system treats that console as an expedition field station: bone-paper specimen cards on a canopy ground, amber catalogue marks, and an original raptor plate. It is not a film tie-in. No Jurassic Park / Jurassic World names, logos, stills, or trademarks are used.

The stylesheet and fonts are local. The portal still renders with the network off.

## Palette

All text pairings below were checked at 4.5:1 or better.

| Token | Hex | Use |
| --- | --- | --- |
| Canopy | `#10160e` | Page background |
| Canopy raised | `#1a2416` | Code chips on the dark ground, scrollbar track |
| Moss line | `#3a4a32` | Header rule, dark dividers |
| Bone | `#f4efe4` | Specimen cards, panels, form sheets |
| Bone deep | `#efe6d4` | Badge fill, pressed paper |
| Ink | `#1c1914` | Text on bone |
| Ink dim | `#3e382f` | Secondary text on bone |
| Ink faint | `#5c564b` | Labels and meta on bone (6.3:1 on bone) |
| Bone text | `#f3ecdf` | Headings on canopy (15.6:1) |
| Bone dim | `#d7ccb6` | Ledes on canopy (11.6:1) |
| Amber | `#f0b429` | Links and kickers on canopy (9.9:1), focus ring |
| Amber button | `#e0a23a` | Primary buttons; label `#1a1206` is 8.3:1 |
| Amber deep | `#7a3e06` | Links and catalogue numbers on bone (7.3:1) |
| Fern | `#0f5c38` | Positive deltas, success badges (7.0:1 on bone) |
| Warn | `#7a4a00` | Warnings on bone (6.5:1) |
| Danger | `#8e1e1e` | Errors and downward rank moves (7.8:1 on bone) |

Focus is a double ring: a near-black outline plus an amber halo, so it stays visible on both bone and canopy. Selection is amber `#e0a23a` with ink `#1a1206`.

## Type

Self-hosted latin WOFF2, `font-display: swap`. See [ASSETS.md](ASSETS.md).

| Role | Family | Weights |
| --- | --- | --- |
| Display | Fraunces | 600, 700 |
| Body | Atkinson Hyperlegible | 400, 700 |
| Catalogue / UI labels | IBM Plex Mono | 400, 500 |

Body size is 16px, line-height 1.6. Headings use Fraunces with tight leading. Catalogue numbers, kickers, and table headers use Plex Mono in small caps tracking. Glyphs outside the latin subset (the gallery’s non-ASCII fixture titles) fall through to the system sans.

## Spacing and shape

- Page column: 1120px, 20px side padding.
- Base unit: 4px. Card padding 14–20px. Section gaps 16px. Stack rhythm 18px between sheets.
- Corners are nearly square (2px). Specimen cards use corner ticks instead of large radii.
- Elevation is one soft shadow (`0 10px 28px rgba(0,0,0,.22)`), enough to lift paper off the canopy.

## Components

- **Station header.** Sticky canopy bar, a simplified raptor mark (tail, snout, eye, sickle claw), wordmark DOGFOOD, “Field station” subtitle. Primary links underline in amber when current. Below 860px the links collapse into a Menu disclosure.
- **Hero.** Display title plus an engraved lateral plate of a dromaeosaur: stiff tail, lean skull, feathered arm, and an amber sickle claw. A specimen line and a one-metre scale sit under the plate. The title wipes in like a claw scratch. The plate’s eye blinks on a slow cycle. Both motions are disabled under `prefers-reduced-motion`.
- **Kickers.** Mono labels (Catalogue, Specimen, Ballot, Chain of custody) sit above each page title.
- **Specimen cards.** Bone sheet, corner ticks, “Specimen / id” line, Fraunces title, tag chips.
- **Panels and stats.** Same bone sheet. Stats get a catalogue corner and a Fraunces numeral.
- **Tables.** Hairline rows, mono numerics, amber row hover. Wide tables scroll inside the sheet.
- **Buttons.** Amber fill with ink text. Ghost buttons invert: bone border on canopy, ink border on paper.
- **Notices.** Bone slip with a 4px fern, amber, or danger rail. Body text stays ink for contrast.
- **Rubric scale.** Paper cells; the chosen score fills amber.
- **Forms.** Warm field `#fffaf1`, amber-deep focus, uppercase mono labels. Checkboxes stay inline and are not forced to uppercase.
- **Loader.** The community ballot shows an amber ring until the first response, then stops even if the list is empty.
- **404.** Same problem document as before, with the raptor plate and a “Trail ends” kicker.
- **Embed.** The iframe gallery uses the same sheets, without foliage or scroll footprints.
- **Chrome.** Topographic contour tile on the canopy, foliage silhouettes in the wide margins (they drift slightly with scroll), a claw-mark rule under section titles and above the footer, and a short footprint gait in the left gutter while scrolling. A small survey cursor is used on the page ground; links, buttons, and fields keep the system pointer and text cursor.

## Motion and accessibility

- `prefers-reduced-motion: reduce` removes the scratch-in, the blink, the spinner rotation, card lift, foliage drift, and the footprint trail.
- Keyboard focus is visible on every control.
- Decorative art is `aria-hidden` or has an empty alt. Specimen ids in the card header are hidden from assistive tech because the same id is in the card meta.
- A skip link jumps to `#content`.
- Colour is never the only status signal: badges keep their words (ok, warn, thin, flat).

## What this system does not restyle

`/docs` is FastAPI’s built-in API explorer. It does not load this stylesheet. Pointing it at the field-station CSS would mean changing server code, so it is unchanged.
