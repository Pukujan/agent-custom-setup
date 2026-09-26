# Image notes

Narrative hero/problem README images are **not generated on this machine yet**. This
repository ships a text-first README and one small non-narrative SVG icon
(`assets/registry-icon.svg`) so the CGM adapter has a real asset on day one without
claiming visuals that do not exist.

When a built-in image generator is available, add wide hero and problem rasters under
`assets/`, record full provenance for each in `.content-system/asset-manifest.json`
(role, exact title/subtitle, dimensions, prompt record, SHA-256 hash, alt text, review
decision), then link them from `README.md`. Until then the visual contract declares
`generation_workflow: "built-in image_gen"` while the manifest intentionally lists **zero**
narrative rasters — the honest "text-first, images pending" boundary described in the
README's "Image generation and use" section.
