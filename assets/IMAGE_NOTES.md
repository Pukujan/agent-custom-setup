# Image notes

The ACS root README carries one narrative raster, regenerated with the updated
image model (role `image` → `xai-oauth/grok-imagine-image`, Refs #19 #44):

1. **Hero** — `assets/acs-readme-hero.png` (2816x1584; exact title "One pack.
   Any repo.", subtitle "The multi-agent hotloader installs decision gates into
   your coding agents" rendered legibly in a quiet right-side panel; prompt
   record `assets/acs-readme-hero-prompt.md`).

Full provenance — role, exact text, dimensions, prompt record, SHA-256 hash,
alt text, crop behavior, rejection conditions, review decision — lives in
`.content-system/asset-manifest.json`. Image provenance is never narrated inside the
README itself.

The small non-narrative SVG mark (`assets/registry-icon.svg`) remains the registry
seal for tooling, not the README hero.
