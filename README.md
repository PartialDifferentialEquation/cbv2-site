# cbv2-site — the public CBv2 marketing site

The front page for CBv2, split out of
[`cbv2-licensing`](https://github.com/PartialDifferentialEquation/cbv2-licensing), where it used
to be rendered per request by the licensing API. It is now a **static build**: no server-side
code on the public edge, no dependency on the licensing service being up, and nothing on this box
that holds a key or touches a customer.

```bash
python build.py --vendor-name CBv2 --contact sales@yourco.example   # -> dist/
python serve.py                                                      # preview on :8000
```

`dist/` is plain files — point nginx, Caddy, S3 or Pages at it. No runtime, no build toolchain,
no npm.

## What the page is

A **minimal, typographic** design: one enormous statement per full-height screen, with the motion
supplied by **[tte.js](https://flaviocopes.com/software/tte-js/)** — 37 Canvas "terminal text
effects" ported from ChrisBuilds' Python *TerminalTextEffects*. Each screen's effect is chosen for
meaning rather than novelty; the hero of an encryption product runs `decrypt`.

Positioning is deliberate and unchanged from the version that shipped in the licensing repo: the
hero sells, and the honest limits of client-side protection stay **mid-page on their own screen**
— present, not buried, and not in the first viewport.

## Configuration

Four placeholders in `src/index.html` are substituted at build time:

| Placeholder | Source | Default |
|---|---|---|
| `{{VENDOR_NAME}}` | `--vendor-name`, `CBSITE_VENDOR_NAME` | `CBv2` |
| `{{CONTACT_HREF}}` / `{{CONTACT_LABEL}}` | `--contact`, `CBSITE_CONTACT` | *(neutral prompt)* |
| `{{YEAR}}` | current UTC year | — |

`--contact` takes an **email** (becomes a `mailto:`), a **URL** (linked as-is), or free text
(shown, not linked). Left empty it renders "Contact your account team for access." as inert text
— deliberately, because a broken `mailto:` on the only call to action is worse than no link.

Substitution is build-time, so changing either value is a rebuild rather than a restart. That is
the trade taken when the page left the licensing service; for values that change roughly never it
buys a public edge with no Python on it. A leftover `{{...}}` **fails the build** rather than
shipping as literal text.

## Why `serve.py` exists

Opening `dist/index.html` directly does not work, and fails in a way that looks like success:
browsers refuse ES modules over `file://`, so tte.js never loads and the page renders as plain
static type with no error a casual look would catch. `serve.py` builds, then serves over real
HTTP with the JavaScript MIME type pinned (Python inherits `.js` from the system MIME database,
and a Windows registry entry can override it). Development only — production is a static file
server.

## Dependencies

**One external asset:** Google Fonts (IBM Plex Mono + Sans), with generic `monospace` /
`sans-serif` fallbacks if it never arrives.

**One vendored library:** tte.js, at `src/vendor/tte/`. It is not on npm or any CDN, so it is
committed here — which makes this repo a redistributor, and means it also carries the library's
MIT licence and both upstream notices. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
The honest cost of vendoring: no upstream security updates arrive on their own.

`build.py` and `serve.py` are pure standard library. `pytest` and `pyflakes` are needed only to
run the checks.

## Accessibility and degradation

tte.js paints an `aria-hidden` Canvas *over* text that stays in the document, so every headline is
real DOM text:

- **No JavaScript** → the whole page reads as static type. Nothing is injected by script.
- **`prefers-reduced-motion`** → effects are skipped entirely (verified in a browser: zero
  canvases created).
- **Fonts blocked** → generic fallbacks, layout intact.

Effects do not replay when a screen is scrolled back into view; the headline settles as static
readable text. Known and acceptable.

## Test

```bash
python -m pyflakes build.py serve.py tests
python -m pytest tests/ -q
```

The suite pins the things that fail silently rather than loudly: placeholder substitution, the
contact-link rules, the honesty guard (no "unbreakable" / "100% secure" / "uncrackable"; the
ceiling must be stated), that the vendored licences survive into `dist/`, that every effect name
used exists in the vendored catalogue, that the page's module import path matches what the build
emits, that `.js` is served as JavaScript, and that the page still reads with no JS and under
reduced motion.

CI runs it on ubuntu + windows and uploads `dist/` as an artifact.

## Related repositories

| Repo | What it is |
|---|---|
| [`Cbv2`](https://github.com/PartialDifferentialEquation/Cbv2) | The engine — packaging, licensing, execution control |
| [`cbv2-licensing`](https://github.com/PartialDifferentialEquation/cbv2-licensing) | Vendor-side licensing & billing API |
| [`cbv2-docs`](https://github.com/PartialDifferentialEquation/cbv2-docs) | Documentation (MkDocs) |
