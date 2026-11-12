# azoic — identity assets

## Core colors

- Mineral red: `#A11B1F` (letter A)
- Sandstone: `#DDD1B1` (distribution)
- Light background: `#F8F5ED`
- Dark background: `#171E22`

## Recommended assets

- GitHub README top: `banner/azoic-readme-light.png` as the default image, with `banner/azoic-readme-dark.png` selected for dark mode. The light image also works as the PyPI fallback.
- Docs homepage: `logo/azoic-horizontal-transparent.svg` on the default light background; for fixed dark backgrounds use `logo/azoic-horizontal-dark.svg`.
- Docs navbar: `favicon/favicon.svg`, the simplified mark for small display sizes.
- Standalone symbol: `symbol/azoic-symbol-light.png` is rectangular (460 × 250); preserve its proportions rather than stretching it into a square avatar.
- Website favicon: `favicon/favicon.ico` for the native theme setting and broad browser compatibility; `favicon/favicon.svg` is also supplied.
- App icons: `favicon/favicon-180.png` and `favicon/favicon-192.png`, `favicon/favicon-512.png`.

## Construction

The red capital A and sandstone severity silhouette share a geometric top at y=28 and baseline at y=180. The distribution has a steep left ascent and a long decaying right tail, and its internal strata are clipped to the silhouette. The favicon simplifies the layers.

SVG files are the **editable masters**. All letters are true vector outlines from Inter Display Medium, not live font text. No embedded bitmaps, external fonts, gradients, filters or network resources. PNGs are exported directly from SVG using CairoSVG. The two primary colors remain exact; additional sandstone shades are used only to distinguish layers subtly.

Preserve the mark's proportions and clear space. Do not stretch, recolor, add axes, or replace the skewed distribution with a bell curve. For tiny formats use the dedicated favicon rather than shrinking the full horizontal lockup.

License note: Original Azoic vector artwork in this package is released for use with the Azoic project. Inter is distributed under the SIL Open Font License (OFL); its glyph outlines have been converted to paths.
