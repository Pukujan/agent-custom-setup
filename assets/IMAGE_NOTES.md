# Image notes

The ACS root README carries **two narrative rasters**, both regenerated with the
updated image model (role `image` → `xai-oauth/grok-imagine-image`, Refs #19 #44):

1. **Hero** — `assets/acs-readme-hero.png` (2816x1584; exact title "Catch mistakes
   earlier", subtitle "Jev routing turns your constraints into checkpoints" rendered
   legibly in a quiet right-side panel; prompt record
   `assets/acs-readme-hero-prompt.md`).
2. **Hotloader-centered module map** — `assets/acs-three-modules.png` (2816x1584;
   hub-and-spoke: the multi-agent hotloader card is dominant and central, `jev-omp`
   and `jev-benchmark` are smaller satellites; text-free by design after an earlier
   attempt garbled in-image lettering; prompt record `assets/acs-three-modules-prompt.md`).

Full provenance for both — role, exact text, dimensions, prompt record, SHA-256 hash,
alt text, crop behavior, rejection conditions, review decision — lives in
`.content-system/asset-manifest.json`. Image provenance is never narrated inside the
README itself.

The earlier product-page hero
(`modules/coordination/jev-oss-compare/v0.1.0/reports/assets/jev-routing-hero.png`)
stays in place for `reports/jev-routing-product.html`. The small non-narrative SVG
mark (`assets/registry-icon.svg`) remains the registry seal for eval variants and
tooling, not the README hero.
