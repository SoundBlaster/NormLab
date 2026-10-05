# NormLab wordmark

`normlab-logo.tex` is the canonical formula supplied by the project owner:

```latex
\mathscr{N}^{\mathrm{o}}_{\mathrm{rm}} \cdot \left\{ \mathscr{L}_{\mathrm{ab}} \right\}
```

The header uses `client/public/normlab-logo.svg` through the shared `Logo` component. MathRSFS letters, upright superscript/subscripts and scalable braces are typeset by LaTeX, then converted to vector outlines using `dvisvgm --no-fonts`. The runtime needs no TeX, MathJax or installed fonts. `alt="NormLab"` labels the image; the home link has its own accessible name.

## Regenerate

Requires LaTeX with `standalone`, `mathrsfs`, and dvisvgm (development tooling only):

```sh
logo_build=$(mktemp -d)
latex -interaction=nonstopmode -halt-on-error -output-directory="$logo_build" design/branding/normlab-logo.tex
dvisvgm --no-fonts --exact --bbox=min --output=client/public/normlab-logo.svg "$logo_build/normlab-logo.dvi"
```

Keep the SVG title/description when replacing the generated file. Do not rasterize it or replace the script letters with browser font fallbacks.
