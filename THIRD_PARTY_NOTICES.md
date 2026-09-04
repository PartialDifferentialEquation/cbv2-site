# Third-Party Notices — CBv2 site

The built site (`dist/`) redistributes third-party code. This file, and the licence texts it
points at, must ship **with** that output — copying only the `.js` and leaving the notices behind
is the failure mode this exists to prevent, and `tests/test_site.py::test_licences_survive_the_build`
fails the build if the copy drops them.

## Redistributed

### tte.js — MIT

Browser text-effect library (Canvas). Vendored at `src/vendor/tte/`, copied verbatim into
`dist/vendor/tte/`. Not published to npm or any CDN, which is why it is vendored rather than
linked.

```
Copyright (c) 2026 Flavio Copes
Copyright (c) 2026 37signals / omacom-io
Copyright (c) 2023 ChrisBuilds (TerminalTextEffects)
```

Full text: [`src/vendor/tte/LICENSE`](src/vendor/tte/LICENSE).

tte.js is itself an adaptation, and carries two upstream notices which are preserved alongside it:

| Upstream | Licence | Relationship | Text |
|---|---|---|---|
| [TerminalTextEffects](https://github.com/ChrisBuilds/terminaltexteffects) (ChrisBuilds) | MIT | The original Python engine; source of the 37 effect designs | [`LICENSES/terminaltexteffects-MIT.txt`](src/vendor/tte/LICENSES/terminaltexteffects-MIT.txt) |
| [ttfx](https://github.com/omacom/ttfx) (37signals / omacom) | MIT | Rust port used as a behavioural reference | [`LICENSES/ttfx-MIT.txt`](src/vendor/tte/LICENSES/ttfx-MIT.txt), [`ttfx-NOTICE.txt`](src/vendor/tte/LICENSES/ttfx-NOTICE.txt) |

See [`src/vendor/tte/THIRD_PARTY_NOTICES.md`](src/vendor/tte/THIRD_PARTY_NOTICES.md) for the
upstream project's own account of that lineage.

**Standing obligation, stated plainly:** a vendored library gets no upstream security updates.
tte.js is v0.1.0 with no runtime dependencies, which bounds the exposure to Canvas/DOM code we
serve ourselves, but patching it is ours to do.

### Uiverse galaxy — MIT

Three CSS techniques from the [Uiverse galaxy](https://github.com/uiverse-io/galaxy) collection,
**adapted** into `src/layout.html` rather than loaded as files. The unmodified originals and the
licence sit in `src/vendor/uiverse/` and are copied into `dist/vendor/uiverse/`; nothing there is
referenced by any page.

```
Copyright (c) 2023 Uiverse.io
```

Full text: [`src/vendor/uiverse/LICENSE`](src/vendor/uiverse/LICENSE).

| Element | Creator | Where it ended up |
|---|---|---|
| [`curly-earwig-79`](src/vendor/uiverse/adamgiebl_curvy-earwig-79.html) | [adamgiebl](https://uiverse.io/adamgiebl) | `.grid-bg` — the fixed graph-paper ground |
| [`short-warthog-33`](src/vendor/uiverse/kennyotsu_short-warthog-33.html) | [kennyotsu](https://uiverse.io/kennyotsu) | `.facts > div` — the dot field in the numbers block |
| [`bitter-impala-54`](src/vendor/uiverse/Cornerstone-04_bitter-impala-54.html) | [Cornerstone-04](https://uiverse.io/Cornerstone-04) | `.draw` — the border-draw hover on the numbers and tier rows |

**Why the originals are kept even though nothing loads them.** MIT requires the copyright notice
to travel with any substantial portion of the work, and what was taken here is CSS — recoloured
and restyled, but structurally the same declarations. Shipping the sources next to the licence
makes the claim checkable instead of asking a reader to trust a summary. Uiverse additionally
*asks* (does not require) that the individual creator be credited; the table above is that credit,
and `src/vendor/uiverse/README.md` repeats it at the source.

Every element was recoloured onto this site's tokens and had its border radii, drop shadows and
stated colours removed — the originals are light-themed or brightly coloured. What was actually
reused is the technique, which is the part worth crediting.

## Loaded at runtime, not redistributed

### IBM Plex Mono / IBM Plex Sans — SIL OFL-1.1 *(to confirm)*

Fetched by the visitor's browser from Google Fonts (`fonts.googleapis.com`). The site does not
ship the font files, so OFL notice retention does not currently apply.

**It applies the moment anyone self-hosts them.** Vendoring IBM Plex for an air-gapped or
CDN-free deployment is redistribution: put the OFL text next to the font files and observe the
reserved-name rules. The page falls back to generic `monospace` / `sans-serif` if the fonts never
arrive, so dropping them entirely is also a valid choice.

## No other third-party code

`build.py` and `serve.py` use only the Python standard library. There are no runtime
dependencies, no bundler, and nothing else in `dist/`.

## Keeping this honest

```bash
# external assets the page fetches at runtime
# (expect: fonts.googleapis.com, fonts.gstatic.com, and the uiverse URL in a CSS comment)
grep -rhoE 'https://[^"]+' src/layout.html src/pages/ | sort -u
# libraries and sources we vendor, and therefore redistribute (expect: tte, uiverse)
ls src/vendor/
```

Anything either prints that is not described above is a gap. The second matters most: **a new
directory under `src/vendor/` is a new redistribution obligation**, and it must arrive with its
licence and notice files.

The first command used to read `src/index.html`, a path that stopped existing when the site became
multi-page. `grep` on a missing file prints nothing and returns non-zero, so the check reported a
clean result for weeks by not looking at anything — which is the exact failure mode this section
exists to catch. If either command ever prints nothing at all, that is the bug, not a pass.
