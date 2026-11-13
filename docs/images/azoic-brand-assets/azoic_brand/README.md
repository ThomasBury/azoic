# azoic — identity assets

## Core colors

- Mineral red: `#A11B1F` (letter A)
- Sandstone: `#DDD1B1` (distribution)
- Light background: `#F8F5ED`
- Dark background: `#171E22`

## Recommended assets

- GitHub README top: `banner/azoic-readme-light.png` as the default image, with `banner/azoic-readme-dark.png` selected for dark mode. The light image also works as the PyPI fallback.
- Docs homepage: `logo/azoic-horizontal-transparent.svg#only-light` on the ivory background and `logo/azoic-horizontal-dark.svg#only-dark` on the matching charcoal background. Zensical selects the image for the active site mode. Display at 448 × 120 px, shrinking proportionally on phones; reserve the tagline banner for the README.
- Docs navbar: `favicon/favicon.svg`, the simplified mark for small display sizes.
- Standalone symbol: `symbol/azoic-symbol-light.png` is rectangular (460 × 250); preserve its proportions rather than stretching it into a square avatar.
- Website favicon: `favicon/favicon.ico` for the native theme setting and broad browser compatibility; `favicon/favicon.svg` is also supplied.
- App icons: `favicon/favicon-180.png` and `favicon/favicon-192.png`, `favicon/favicon-512.png`.

## Documentation colours

The documentation retains Zensical's default theme and components. Its only custom
stylesheet, `docs/stylesheets/brand.css`, sets colour variables: ivory surfaces,
charcoal text and mineral-red links/buttons in light mode; charcoal surfaces,
ivory text and sandstone links/buttons in dark mode. Button text uses the opposite
surface colour. Red on ivory has 7.16:1 contrast; sandstone on charcoal has 11.11:1.
The original mineral red is retained in dark artwork, but its 2.16:1 contrast on
charcoal is insufficient for link text. Secondary text uses `#41494B` in light
mode and `#C2BFB5` in dark mode so the native button fade on hover still clears
4.5:1 contrast. Syntax highlighting and semantic warning colours retain their
theme defaults. Initial mode follows system preference; the native toggle saves
an explicit choice.

## Construction

The red capital A and sandstone severity silhouette share a geometric top at y=28 and baseline at y=180. The distribution has a steep left ascent and a long decaying right tail, and its internal strata are clipped to the silhouette. The favicon simplifies the layers.

SVG files are the **editable masters**. All letters are true vector outlines from Inter Display Medium, not live font text. No embedded bitmaps, external fonts, gradients, filters or network resources. PNGs are exported directly from SVG using CairoSVG. The two primary colors remain exact; additional sandstone shades are used only to distinguish layers subtly.

Preserve the mark's proportions and clear space. Do not stretch, recolor, add axes, or replace the skewed distribution with a bell curve. For tiny formats use the dedicated favicon rather than shrinking the full horizontal lockup.

License note: Original Azoic vector artwork in this package is released for use with the Azoic project. Inter is distributed under the SIL Open Font License (OFL); its glyph outlines have been converted to paths.
