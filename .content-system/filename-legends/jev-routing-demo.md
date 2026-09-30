# Jev routing demo and hero filenames

Companion to `jev-routing-demo.json`. Speakable identity is `Jev routing`; the
basenames use the machine-safe twin so relative web links never need percent
encoding.

| Token | Meaning |
| --- | --- |
| `jev-routing` | Demo identity: the product+technical page pair under `reports/`. |
| `product` | The marketing/presentation page. |
| `technical` | The compact technical breakdown (flow diagram + short benchmark). |
| `hero` | The wide narrative hero illustration embedded by the product page. |
| `prompt` | The regeneration record kept beside its image. |
| `-` | Safe-twin separator (no spaces in web paths). |

Rules: identity first, then the role word; defaults omitted; the SHA-256 lives
in `.content-system/asset-manifest.json` as a separate field, never in a
basename.

## Files

- `modules/coordination/jev-oss-compare/v0.1.0/reports/jev-routing-product.html`
- `modules/coordination/jev-oss-compare/v0.1.0/reports/jev-routing-technical.html`
- `modules/coordination/jev-oss-compare/v0.1.0/reports/assets/jev-routing-hero.png`
- `modules/coordination/jev-oss-compare/v0.1.0/reports/assets/jev-routing-hero-prompt.md`
