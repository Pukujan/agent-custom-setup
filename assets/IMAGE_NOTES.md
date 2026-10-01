# Image notes

The ACS root README now carries **two narrative rasters** (Refs #19 #44):

1. **Hero** — `modules/coordination/jev-oss-compare/v0.1.0/reports/assets/jev-routing-hero.png`
   (1822x1024; exact title "Catch mistakes earlier", subtitle "Jev routing turns your
   constraints into checkpoints"; prompt record `jev-routing-hero-prompt.md` beside it).
2. **Three-module overview** — `assets/acs-three-modules.jpg` (1824x1024; text-free by
   design after attempt 1 was rejected for garbled lettering; prompt record
   `assets/acs-three-modules-prompt.md`).

Full provenance for both — role, exact text, dimensions, prompt record, SHA-256 hash,
alt text, crop behavior, rejection conditions, review decision — lives in
`.content-system/asset-manifest.json`. Image provenance is never narrated inside the
README itself.

The small non-narrative SVG mark (`assets/registry-icon.svg`) remains the registry seal
for eval variants and tooling, not the README hero.
