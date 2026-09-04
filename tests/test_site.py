"""The public CBv2 site: the build pipeline and the page it produces.

Ported from the licensing service's `tests/test_landing.py` when the page moved out of that
repo. What changed is *when* substitution happens — build time, not per request — so the
route-level tests became build-level ones. What did not change is the set of things that break
silently, which is what all of this exists to pin:

  - every operator placeholder is substituted, and a missing contact never yields a broken
    `mailto:`;
  - the honesty rules (no overselling; the client-side ceiling is stated on the page);
  - tte.js is vendored **with its MIT licence and both upstream notices**, and they survive the
    copy into `dist/` — attribution is an obligation, not a nicety;
  - every effect name used actually exists in the vendored catalogue (a wrong name throws
    inside the library and costs that headline its animation, with nothing in the console for
    a casual look);
  - `.js` is served as JavaScript, because an ES module served as `text/plain` is rejected and
    the page then degrades to static type — which looks like success;
  - and the page still reads as plain text with no JS and under reduced motion.
"""

import pathlib
import re

import pytest

import build as build_mod
import serve

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENDOR = ROOT / "src" / "vendor" / "tte"


@pytest.fixture
def site(tmp_path):
    """Build into a temp dir and hand back (dist_path, html)."""
    def _build(vendor_name="CBv2", contact="sales@acme.example"):
        out = build_mod.build(tmp_path / "dist", vendor_name=vendor_name, contact=contact)
        return out, (out / "index.html").read_text(encoding="utf-8")
    return _build


# ── substitution ────────────────────────────────────────────────────────────────────
def test_build_emits_a_complete_page(site):
    out, html = site()
    assert (out / "index.html").is_file()
    assert "<!doctype html>" in html.lower()
    assert "Protection tiers" in html
    assert "{{" not in html and "}}" not in html      # every placeholder substituted


def test_build_renders_vendor_and_contact(site):
    _, html = site(vendor_name="AcmeGuard", contact="sales@acme.example")
    assert "AcmeGuard" in html
    assert "mailto:sales@acme.example" in html


def test_contact_url_and_default(site):
    _, html = site(contact="https://acme.example/access")
    assert 'href="https://acme.example/access"' in html
    # no contact configured → neutral prompt, never a broken mailto
    _, html2 = site(contact="")
    assert "Contact your account team" in html2 and "mailto:" not in html2


@pytest.mark.parametrize("contact,expected", [
    ("", ("#", "Contact your account team for access.")),
    ("  ", ("#", "Contact your account team for access.")),
    ("sales@acme.example", ("mailto:sales@acme.example", "sales@acme.example")),
    ("https://acme.example/x", ("https://acme.example/x", "https://acme.example/x")),
    ("call your rep", ("#", "call your rep")),
])
def test_resolve_contact(contact, expected):
    assert build_mod.resolve_contact(contact) == expected


def test_unknown_placeholder_fails_the_build():
    """An unsubstituted `{{...}}` must stop the build, not ship as literal text on the page."""
    with pytest.raises(SystemExit):
        build_mod.render("<p>{{NOT_A_REAL_PLACEHOLDER}}</p>", vendor_name="CBv2", contact="")


def test_build_is_repeatable_and_clears_stale_output(site, tmp_path):
    out, _ = site()
    stale = out / "vendor" / "stale.js"
    stale.write_text("// left over from an older build", encoding="utf-8")
    site()
    assert not stale.exists(), "a second build left a file from the first one in dist/"


def test_build_refuses_to_clear_a_foreign_directory(tmp_path):
    """`--out` is operator input and the build deletes recursively. Pointing it at a populated
    directory must be an error rather than a silent wipe."""
    victim = tmp_path / "not-a-build"
    victim.mkdir()
    (victim / "important.txt").write_text("do not delete me", encoding="utf-8")
    with pytest.raises(SystemExit):
        build_mod.build(victim, vendor_name="CBv2", contact="")
    assert (victim / "important.txt").is_file()


# ── the page's content rules ────────────────────────────────────────────────────────
def test_page_is_honest(site):
    _, html = site()
    body = html.lower()
    for oversell in ("unbreakable", "100% secure", "uncrackable", "impossible to"):
        assert oversell not in body
    assert "secrecy" in body and ("reverse-engineer" in body or "reverse engineer" in body)


def test_fonts_loaded_with_fallbacks(site):
    _, html = site()
    assert "fonts.googleapis.com/css2" in html and "display=swap" in html
    for fam in ("IBM+Plex+Mono", "IBM+Plex+Sans"):
        assert fam in html
    assert "monospace" in html and "sans-serif" in html    # generic fallbacks
    assert "fonts.gstatic.com" in html                     # preconnect


# ── tte.js: vendored, attributed, and actually wired ────────────────────────────────
def test_tte_is_vendored_with_licences():
    """tte.js is MIT and carries upstream notices from TerminalTextEffects and ttfx. Vendoring
    it means we redistribute it, so the licence files must travel with the source."""
    assert (VENDOR / "src" / "index.js").is_file()
    assert (VENDOR / "LICENSE").is_file()
    assert (VENDOR / "THIRD_PARTY_NOTICES.md").is_file()
    upstream = sorted(p.name for p in (VENDOR / "LICENSES").glob("*.txt"))
    assert upstream, "upstream licence texts missing"
    assert any("terminaltexteffects" in n for n in upstream)
    assert any("ttfx" in n for n in upstream)
    assert "MIT" in (VENDOR / "LICENSE").read_text(encoding="utf-8")


def test_licences_survive_the_build(site):
    """Shipping `dist/` is the act of redistribution, so the notices have to be *in* `dist/` —
    it is not enough for them to sit in the source tree."""
    out, _ = site()
    v = out / "vendor" / "tte"
    assert (v / "src" / "index.js").is_file()
    for required in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        assert (v / required).is_file(), f"{required} was dropped from the build output"
    assert len(list((v / "LICENSES").glob("*.txt"))) >= 2


def test_effect_names_are_real(site):
    """A misspelt effect name throws inside tte.js and costs the headline its animation.
    Validate every name used against the catalogue in the vendored source."""
    _, html = site()
    used = set(re.findall(r'data-effect="([a-z]+)"', html))
    assert used, "no tte.js effects wired into the page"
    registered = set(re.findall(
        r"effect\('([a-z]+)'", (VENDOR / "src" / "builtin-effects.js").read_text(encoding="utf-8")))
    assert len(registered) >= 30, "effect catalogue did not parse"
    assert used <= registered, f"unknown effect(s): {used - registered}"
    # the runtime guard is present too, so an unknown name degrades instead of throwing
    assert "effectNames" in html and "falling back" in html


def test_micro_effect_names_are_real(site):
    """The headline effects live in `data-effect` attributes; the button/nav/chip effects are
    string literals in the module script. Same failure mode either way -- an unknown name
    throws inside the library -- so validate both against the vendored catalogue."""
    _, html = site()
    registered = set(re.findall(
        r"effect\('([a-z]+)'", (VENDOR / "src" / "builtin-effects.js").read_text(encoding="utf-8")))
    # the [selector, effect, duration, accent] tuples that drive the micro layer
    used = set(re.findall(r"\['[^']+',\s*'([a-z]+)',\s*\d+", html))
    assert len(used) >= 4, f"expected the micro-effect table to parse, got {used}"
    assert used <= registered, f"unknown micro effect(s): {used - registered}"


def test_effects_never_target_padded_elements(site):
    """The renderer spreads its character grid across the target's whole border box and sizes
    the font from the box height (CanvasRenderer.resize). Aiming it at a padded element draws
    a stretched, oversized label -- so `.btn` (padding 16/28) and the chips (padding 9/15) are
    animated through an inner, unpadded `.fx` span, never directly."""
    _, html = site()
    selectors = set(re.findall(r"\['([^']+)',\s*'[a-z]+',\s*\d+", html))
    assert selectors, "no micro-effect selectors found"
    for sel in selectors:
        assert sel not in (".btn", ".langs > span", ".langs span"), (
            f"{sel!r} is a padded element; target its inner .fx span instead")
    # and the elements that carry padding really do have an inner target
    for m in re.finditer(r'<a class="btn[^"]*"[^>]*>(.*?)</a>', html, re.S):
        assert 'class="fx"' in m.group(1), "a button label is not wrapped in an .fx span"
    chips = re.search(r'<div class="langs">(.*?)</div>', html, re.S)
    assert chips and chips.group(1).count('class="fx"') >= 5, "language chips lack inner targets"


def test_effects_disable_library_autoplay(site):
    """Every createTextEffect call must pass `autoplay: false`.

    The library defaults to `autoplay: true` and queues its own play() from the constructor.
    An explicit restart() then starts a run, and that queued play() immediately calls stop()
    on it -- which resolves the promise restart() returned as `{cancelled: true}`. Any code
    that treats "promise settled" as "animation finished" therefore tears the effect down a
    microtask after starting it, and the element never animates: no error, no warning, just
    static text. Found in a browser, invisible everywhere else.
    """
    _, html = site()
    calls = re.findall(r"createTextEffect\(\s*el\s*,\s*\{(.*?)\}\s*\)", html, re.S)
    assert len(calls) >= 2, f"expected the headline and micro constructors, found {len(calls)}"
    for opts in calls:
        assert re.search(r"autoplay:\s*false", opts), \
            f"createTextEffect without autoplay:false -- {' '.join(opts.split())[:80]}"


def test_micro_effects_are_torn_down_not_stopped(site):
    """A button whose effect is halted rather than destroyed keeps `color: transparent` and
    loses its label permanently. Pin the teardown path for the interactive elements."""
    _, html = site()
    assert "pointerleave" in html and "stopMicro" in html
    assert re.search(r"stopMicro\s*=\s*\(el\)\s*=>\s*\{[^}]*destroy\(\)", html), \
        "pointerleave must destroy(), not stop()"


def test_module_imports_are_relative_and_resolve(site):
    """The import specifier and the output layout have to agree; a mismatch is a blank page.

    They must also be **relative**. GitHub Pages serves a project site under `/<repo>/`, so a
    root-absolute `/vendor/...` resolves to the domain root and 404s — and the failure is
    invisible in review, because the page still renders as static type with no effects. Relative
    specifiers resolve against the document, so one build works at a subpath, at a custom
    domain's root, and under `serve.py` alike.
    """
    out, html = site()
    specifiers = re.findall(r"""\bfrom ['"]([^'"]+)['"]""", html)
    assert specifiers, "no module import found in the page"
    for spec in specifiers:
        assert not spec.startswith("/"), (
            f"module import {spec!r} is root-absolute and will 404 on a Pages project site; "
            "use './vendor/...' instead")
        assert spec.startswith("."), f"unexpected bare module specifier {spec!r} (no bundler here)"
        assert (out / spec.lstrip("./")).is_file(), f"page imports {spec}, which the build does not emit"


def test_no_root_absolute_asset_paths(site):
    """Same trap, wider net: any `src=\"/...\"` or `href=\"/...\"` breaks a subpath deployment."""
    _, html = site()
    absolute = re.findall(r'(?:src|href)="(/[^/"][^"]*)"', html)
    assert not absolute, f"root-absolute asset path(s) break a Pages project site: {absolute}"


def test_build_emits_nojekyll(site):
    """Only load-bearing if the Pages source is ever switched to 'deploy from a branch', where
    Jekyll drops paths starting with `_`. Cheap to keep, expensive to debug when missing."""
    out, _ = site()
    assert (out / ".nojekyll").is_file()


# ── serving ─────────────────────────────────────────────────────────────────────────
def test_javascript_is_served_as_javascript():
    """ES modules are rejected unless the MIME type is a JavaScript one. Python inherits this
    from the system MIME database, and on Windows a registry entry can override `.js` — so the
    preview server pins it, and this test pins the pin."""
    for ext in (".js", ".mjs"):
        assert serve.Handler.extensions_map[ext] == "text/javascript"


# ── degradation ─────────────────────────────────────────────────────────────────────
def test_page_degrades_without_js(site):
    """tte.js draws over text that stays in the document. Every headline must therefore be real
    DOM text, not injected by script, so a no-JS visitor reads the whole page."""
    _, html = site()
    assert 'type="module"' in html
    headlines = re.findall(r'<pre class="line[^"]*"[^>]*>(.*?)</pre>', html, re.S)
    assert len(headlines) >= 8, "expected a statement per screen"
    for h in headlines:
        assert h.strip(), "a headline is empty in the built HTML"
    # the load-bearing sentences are present as text, not built by JS
    for phrase in ("YOUR CODE RUNS", "NO SECURITY", "REQUEST ACCESS"):
        assert phrase in html


def test_reduced_motion_respected(site):
    _, html = site()
    assert "prefers-reduced-motion" in html
    # the effect bootstrap is skipped entirely when reduced motion is requested
    assert re.search(r"if \(!reduce[^)]*\)", html), "effects are not gated on reduced motion"
