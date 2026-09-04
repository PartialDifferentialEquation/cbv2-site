# cbv2-site — the public CBv2 marketing site

Five pages — **home, about, contact, legal, coming-soon** — split out of
[`cbv2-licensing`](https://github.com/PartialDifferentialEquation/cbv2-licensing), where it used
to be rendered per request by the licensing API. It is now a **static build**: no server-side
code on the public edge, no dependency on the licensing service being up, and nothing on this box
that holds a key or touches a customer.

```bash
python build.py --vendor-name CBv2 --contact sales@yourco.example   # -> dist/
python serve.py                                                      # preview on :8000
```

`dist/` is plain files — point nginx, Caddy, S3 or Pages at it. No runtime, no build toolchain,
no npm. **Pushes to `main` publish to GitHub Pages automatically** (see below).

## What the page is

A **minimal, typographic** design: one enormous statement per full-height screen, with the motion
supplied by **[tte.js](https://flaviocopes.com/software/tte-js/)** — 37 Canvas "terminal text
effects" ported from ChrisBuilds' Python *TerminalTextEffects*. Each screen's effect is chosen for
meaning rather than novelty; the hero of an encryption product runs `decrypt`.

The same library drives the small type, so the terminal idiom runs through the whole page rather
than stopping at the headlines:

| Element | Trigger | Effect |
|---|---|---|
| Buttons, header links | hover / tap | `decrypt`, `scattered` |
| Eyebrow captions | scroll into view | `wipe` |
| Tier names (`open`…`enclave`) | scroll into view, staggered | `decrypt` |
| Language chips | scroll into view, staggered | `binarypath` |

Three rules make that work, each learned from a failure that was invisible without a browser:

- **Never target a padded element.** The renderer spreads its character grid across the target's
  whole border box and derives font size from the box height, so aiming at `.btn`
  (`padding:16px 28px`) draws a stretched, oversized label. Every target is an inner `.fx` span
  that hugs its text.
- **`autoplay: false` on every effect.** The library's default queues a `play()` from the
  constructor, which cancels the run an explicit `restart()` just began — resolving that promise
  as `{cancelled: true}`. Completion handlers then destroy the effect a microtask after it
  starts, and the label never animates: no error, no warning.
- **Always `destroy()`, never `stop()`.** The library paints over text it has set to
  `color: transparent`. Anything short of `destroy()` strands a button with no visible label —
  so `pointerleave` mid-effect tears down rather than halting.

Positioning is deliberate and unchanged from the version that shipped in the licensing repo: the
hero sells, and the honest limits of client-side protection stay **mid-page on their own screen**
— present, not buried, and not in the first viewport.

## Deployment — GitHub Pages

`.github/workflows/build.yml` publishes `main` to Pages on every push, and only after the test
matrix is green on both OS legs — a red build never reaches the live site. `workflow_dispatch`
re-publishes the current `main` without a commit, which is how you apply a changed
`CBSITE_CONTACT`.

**Two things to set once, in the repo's settings:**

| Where | Set |
|---|---|
| Settings → Secrets and variables → Actions → **Variables** | `CBSITE_CONTACT` (e.g. `sales@yourco.example`), and optionally `CBSITE_VENDOR_NAME` |
| Settings → **Pages** | Source = **GitHub Actions**. This one is **required before the first deploy** — see below. |

They are **variables, not secrets** — both are printed on a public page, and hiding a public
address in a secret only makes it harder to audit what actually shipped. If `CBSITE_CONTACT` is
unset the build still succeeds and the call to action degrades to an inert prompt (it warns on
stderr), which is the deliberate behaviour: no link beats a broken `mailto:`.

**Two things worth knowing:**

- **Pages must be enabled by hand, once.** The workflow does not turn it on: creating a Pages
  site from Actions needs `POST /repos/{owner}/{repo}/pages`, and `GITHUB_TOKEN` was refused that
  call here (`Resource not accessible by integration`) despite holding `pages: write`. So the
  `deploy` job fails until **Settings → Pages → Source** is set to **GitHub Actions**. After
  that, every push to `main` publishes.
- **Pages on a private repo needs a paid plan** (Pro / Team / Enterprise); on Free it is
  public-repos-only. Either way the **published site is public** — restricting who can view a
  Pages site is an Enterprise Cloud feature. That is the point for a marketing page, but it means
  `dist/` is world-readable, so nothing that is not meant for the public should ever reach the
  build output. Today `dist/` is the pages, two vendored MIT trees (`vendor/tte`, the library the
  page loads, and `vendor/uiverse`, the provenance record for three adapted CSS techniques), and
  their licence files.

### Paths must stay relative

The project site is served from `https://<owner>.github.io/cbv2-site/`, a **subpath**. A
root-absolute `/vendor/...` resolves to the domain root there and 404s — and the page still
renders as static type, so the breakage looks like a design choice rather than a fault. Every
asset path is therefore relative, and two tests
(`test_module_imports_are_relative_and_resolve`, `test_no_root_absolute_paths`) fail the
build if one goes absolute again. The same build works unchanged at a subpath, at a custom
domain's root, and under `serve.py`.

For a **custom domain**, set it in Settings → Pages and commit a `CNAME` file into `src/` —
then add it to `build.py`'s copy step and to `OUTPUTS`, so it survives the build rather than
being cleared on the next deploy.

## Pages and layout

`src/layout.html` holds the head, nav, footer and the effect bootstrap; each page is just a body
in `src/pages/<slug>.html`, poured in at `{{CONTENT}}`. Add a page by dropping a file there and
adding its slug, title and description to `PAGES` in `build.py`.

| Page | What it carries |
|---|---|
| `index` | The landing page — one statement per full-height screen |
| `about` | What the platform enforces, where the ceiling is, how it deploys |
| `contact` | Routed addresses, how pricing is structured, registered entity details |
| `legal` | Draft terms of service and privacy statement |
| `coming-soon` | Placeholder standing in for the two pages below, with a way back |

**Two pages are built but deliberately unlinked** — `contact` and `legal`, listed in `UNLINKED`
in `build.py`. Every operator value on them is still unset, so following "Contact" from the nav
would land a visitor on a page of `NOT CONFIGURED` markers; the nav points at `coming-soon`
instead. Unlinking is not hiding: both still build and are still reachable by direct URL, which
is what makes them reviewable. Deleting their entries from `UNLINKED` relinks them, and nothing
else changes.

## Configuration

Values are substituted at build time from flags or environment variables:

| Field | Env | Used for |
|---|---|---|
| `--vendor-name` | `CBSITE_VENDOR_NAME` | product name throughout (default `CBv2`) |
| `--contact` | `CBSITE_CONTACT` | the "Request access" call to action |
| `--email-sales` / `-security` / `-privacy` / `-support` | `CBSITE_EMAIL_*` | the routed addresses on the contact page |
| `--legal-entity` / `-address` / `-reg` / `-jurisdiction` | `CBSITE_LEGAL_*` | registered identity and governing law |

`--contact` takes an **email** (becomes a `mailto:`), a **URL** (linked as-is), or free text
(shown, not linked). Left empty, the label reads "Contact your account team for access." and every
"Request access" button points at `coming-soon.html` — deliberately, because a broken `mailto:` on
the only call to action is worse than no link, and `#` is worse still: it is not a destination, it
just leaves the reader on the page they were already on, so the button reads as broken rather than
as unconfigured. The free-text branch keeps `#` on purpose — that detail *is* published, rendered
as text beside the button, so routing it to "coming soon" would contradict what the reader can
see.

**Anything unset renders as a visible `NOT CONFIGURED` marker, never as filler.** This is the
rule the legal and contact pages depend on: a site that invents a registered address, a company
number or a governing law is publishing a fabricated record, which is worse than one that admits
the field is empty. The build also lists every unset field on stderr, so an unfilled deploy is
obvious rather than plausible.

> **The legal page is a draft.** It carries a prominent banner saying so: not an executed
> agreement, not legal advice, not reviewed by counsel, and explicitly subordinate to any signed
> agreement. It is published for transparency — including a section stating plainly that the
> audit log's hash chain is in tension with a right to erasure and that the fix is not yet
> implemented. Have counsel review it before treating any of it as binding.

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

- **No JavaScript** → the whole page reads as static type. Nothing is injected by script,
  buttons and links included.
- **`prefers-reduced-motion`** → effects are skipped entirely, headlines and small type alike
  (verified in a browser: zero canvases created).
- **Fonts blocked** → generic fallbacks, layout intact.

Interactive elements keep working while animating: the library's canvas is `pointer-events: none`,
so a button stays clickable mid-effect, its box never shifts, and the text underneath stays
selectable and readable to a screen reader (the canvas is `aria-hidden`).

### The arrival transition

Every page opens behind a **full-screen grid of random hex**, and it runs in two phases:

1. **Decrypt.** The whole viewport is a field of scrambling characters with the page's own
   headline embedded in it, resolving through tte.js's `decrypt`.
2. **The message stays, the noise goes.** A second frame is built from the *same* placement at
   the *same* grid dimensions, with every non-headline cell blanked, and painted with
   `render(1)` — no second animation. The surviving characters therefore sit in exactly the
   cells they already occupied, so the headline reads as persisting out of the decryption while
   everything around it disappears. The overlay then dissolves into the real page.

Two properties of the library make this work, and both are load-bearing:
`parseText` marks a cell `visible: character !== ' '` and effects only ever draw visible cells,
so blanking a cell genuinely removes it; and the surviving frame must never be re-animated, or
the message would be drawn a second time instead of standing still.

A tiny synchronous script in `<head>` arms the overlay before first paint; the deferred module
runs both phases and uncovers.

It is **arrival-only, on purpose.** An earlier version also intercepted link clicks to run an
"encrypt" animation *before* navigating. That could not be made reliable — in browser testing the
click was intermittently swallowed with no navigation request issued at all, leaving the visitor
stuck on the page with no error and nothing in the console. A decorative transition is not worth
a link that sometimes does nothing, so links are ordinary anchors the browser handles itself and
no script sits between a click and the page it asks for.

Three properties keep the overlay from ever stranding anyone, each pinned by a test: it is
`display:none` until a script turns it on (so no-JS never sees it), it is `pointer-events:none`
(an `opacity:0` overlay still swallows clicks), and the head script removes it on a timer even if
the module never executes. Every phase advances on a timer rather than on an animation's promise,
so the page becomes usable on a schedule.

One more thing worth knowing if you touch this: tte.js wraps its target in a box it styles
inline as `width: fit-content`. For a full-viewport overlay that collapses the grid to the
natural size of its text — the noise filled only the top-left corner until an `!important`
override forced the wrapper to fill.

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
emits and is relative (not root-absolute, which breaks a Pages subpath), that `.js` is served as
JavaScript, and that the page still reads with no JS and under reduced motion.

CI runs it on ubuntu + windows, uploads `dist/` as an artifact, and — on `main` only, after both
legs pass — deploys to Pages.

## Related repositories

Deliberately not linked. The engine, the licensing/billing API and the documentation live in
separate **private** repositories, and this one is public so that GitHub Pages can serve it —
so listing their URLs here would publish the names and addresses of private repos to no one's
benefit. Anyone who needs them has access to them.
