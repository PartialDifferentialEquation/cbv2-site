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
# external assets the page fetches at runtime (expect: Google Fonts only)
grep -oE 'https://[^"]+' src/index.html | sort -u
# libraries we vendor, and therefore redistribute (expect: tte)
ls src/vendor/
```

Anything either prints that is not described above is a gap. The second matters most: **a new
directory under `src/vendor/` is a new redistribution obligation**, and it must arrive with its
licence and notice files.
