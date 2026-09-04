"""The public CBv2 site: the build pipeline and the pages it produces.

Ported from the licensing service's `tests/test_landing.py` when the page moved out of that
repo, then widened when the site grew from one page to four. What changed is *when*
substitution happens -- build time, not per request -- so the route-level tests became
build-level ones. What did not change is the set of things that break silently, which is what
all of this exists to pin:

  - every operator placeholder is substituted on every page, and a missing contact never
    yields a broken `mailto:`;
  - an operator value nobody configured renders as a visible gap, never as plausible filler --
    on the legal page, invented entity details would be a fabricated record;
  - the honesty rules (no overselling; the client-side ceiling is stated) hold on *all* pages,
    not just the one that happened to carry the disclaimer;
  - tte.js is vendored **with its MIT licence and both upstream notices**, and they survive the
    copy into `dist/` -- attribution is an obligation, not a nicety;
  - every effect name used exists in the vendored catalogue, and no effect targets a padded
    element or forgets `autoplay: false` (both fail silently -- see the tests);
  - links and module imports stay relative, because Pages serves this under `/<repo>/`;
  - `.js` is served as JavaScript, since an ES module served as `text/plain` is rejected and
    the page then degrades to static type, which looks like success;
  - and the pages still read with no JS and under reduced motion.
"""

import pathlib
import re

import pytest

import build as build_mod
import serve

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENDOR = ROOT / "src" / "vendor" / "tte"
SLUGS = ("index", "about", "contact", "legal", "coming-soon")
# Built, but deliberately absent from the nav until the values behind them are real.
UNLINKED = ("contact", "legal")
LINKED = tuple(s for s in SLUGS if s not in UNLINKED)

FULL_CFG = {
    "VENDOR_NAME": "AcmeGuard",
    "CONTACT": "sales@acme.example",
    "EMAIL_SALES": "sales@acme.example",
    "EMAIL_SECURITY": "security@acme.example",
    "EMAIL_PRIVACY": "privacy@acme.example",
    "EMAIL_SUPPORT": "support@acme.example",
    "LEGAL_ENTITY": "Acme Guard Ltd",
    "LEGAL_ADDRESS": "1 Example Street\nLondon",
    "LEGAL_REG": "12345678",
    "LEGAL_JURISDICTION": "England and Wales",
}


@pytest.fixture
def site(tmp_path):
    """Build into a temp dir and hand back (dist_path, {slug: html})."""
    def _build(**overrides):
        cfg = dict(FULL_CFG, **overrides)
        out = build_mod.build(tmp_path / "dist", cfg)
        return out, {s: (out / f"{s}.html").read_text(encoding="utf-8") for s in SLUGS}
    return _build


# ── the build ───────────────────────────────────────────────────────────────────────
def test_every_page_builds_complete(site):
    out, pages = site()
    assert set(pages) == set(SLUGS)
    for slug, html in pages.items():
        assert (out / f"{slug}.html").is_file()
        assert "<!doctype html>" in html.lower(), slug
        assert "{{" not in html and "}}" not in html, f"{slug} has an unsubstituted placeholder"
        assert "AcmeGuard" in html, slug
    assert "Protection tiers" in pages["index"]


def test_unknown_placeholder_fails_the_build():
    """An unsubstituted `{{...}}` must stop the build, not ship as literal text on the page."""
    with pytest.raises(SystemExit) as e:
        build_mod.render("<p>{{NOT_A_REAL_PLACEHOLDER}}</p>", "", {"YEAR": "2026"}, slug="x")
    assert "NOT_A_REAL_PLACEHOLDER" in str(e.value)


def test_contact_url_and_default(site):
    _, pages = site(CONTACT="https://acme.example/access")
    assert 'href="https://acme.example/access"' in pages["index"]
    # no contact configured -> neutral prompt, never a broken mailto
    _, pages2 = site(CONTACT="", EMAIL_SALES="", EMAIL_SECURITY="", EMAIL_PRIVACY="",
                     EMAIL_SUPPORT="")
    assert "Contact your account team" in pages2["index"]
    # `href="mailto:` specifically, not the bare substring — the transition script mentions
    # mailto: in a comment explaining which links it leaves alone, and that is not a link.
    assert 'href="mailto:' not in pages2["index"]


@pytest.mark.parametrize("contact,expected", [
    ("", ("#", "Contact your account team for access.")),
    ("  ", ("#", "Contact your account team for access.")),
    ("sales@acme.example", ("mailto:sales@acme.example", "sales@acme.example")),
    ("https://acme.example/x", ("https://acme.example/x", "https://acme.example/x")),
    ("call your rep", ("#", "call your rep")),
])
def test_resolve_contact(contact, expected):
    assert build_mod.resolve_contact(contact) == expected


def test_build_is_repeatable_and_clears_stale_output(site):
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
        build_mod.build(victim, FULL_CFG)
    assert (victim / "important.txt").is_file()


def test_build_emits_nojekyll(site):
    """Only load-bearing if the Pages source is ever switched to 'deploy from a branch', where
    Jekyll drops paths starting with `_`. Cheap to keep, expensive to debug when missing."""
    out, _ = site()
    assert (out / ".nojekyll").is_file()


# ── operator values: gaps must look like gaps ───────────────────────────────────────
def test_unconfigured_values_render_as_a_visible_gap_not_filler(site):
    """The most important rule on these pages. A site that invents a registered address, a
    governing law or a support mailbox is publishing a fabricated record -- worse than one that
    admits the field is empty. Every unset value must be conspicuous."""
    blanks = {k: "" for k in ("EMAIL_SALES", "EMAIL_SECURITY", "EMAIL_PRIVACY", "EMAIL_SUPPORT",
                              "LEGAL_ENTITY", "LEGAL_ADDRESS", "LEGAL_REG", "LEGAL_JURISDICTION")}
    _, pages = site(**blanks)
    for slug in ("contact", "legal"):
        assert 'class="unset"' in pages[slug], f"{slug} hides its unconfigured fields"
        assert "not configured" in pages[slug], slug
    assert pages["contact"].count('class="unset"') >= 8, "some empty field rendered as filler"


def test_emails_become_mailto_links_when_configured(site):
    _, pages = site()
    both = pages["contact"] + pages["legal"]
    for addr in ("sales@acme.example", "security@acme.example",
                 "privacy@acme.example", "support@acme.example"):
        assert f'href="mailto:{addr}"' in both, addr
    assert 'class="unset"' not in pages["contact"], "a configured field still rendered as unset"


def test_operator_values_are_escaped(site):
    """Operator config reaches the page as HTML. It is trusted input, but an unescaped `&` in a
    company name still produces invalid markup."""
    _, pages = site(LEGAL_ENTITY="Smith & Sons <Ltd>")
    assert "Smith &amp; Sons &lt;Ltd&gt;" in pages["legal"]
    assert "<Ltd>" not in pages["legal"]


def test_multiline_address_keeps_its_line_breaks(site):
    _, pages = site(LEGAL_ADDRESS="1 Example Street\nLondon\nEC1A 1AA")
    assert "1 Example Street<br>London<br>EC1A 1AA" in pages["contact"]


# ── content rules ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("slug", SLUGS)
def test_every_page_is_honest(site, slug):
    _, pages = site()
    body = pages[slug].lower()
    for oversell in ("unbreakable", "100% secure", "uncrackable", "impossible to"):
        assert oversell not in body, f"{slug} oversells: {oversell}"


def test_the_ceiling_is_stated_where_it_matters(site):
    """The limits of client-side protection belong on the pages a buyer reads before signing,
    not only on the landing page."""
    _, pages = site()
    for slug in ("index", "about", "legal"):
        body = pages[slug].lower()
        assert "secrecy" in body, slug
        assert ("reverse-engineer" in body or "reverse engineer" in body
                or "recover" in body), slug


def test_legal_page_is_marked_as_a_draft(site):
    """Publishing terms that read as executed when they have not been reviewed is the failure
    mode here. The disclaimer is load-bearing, so pin it."""
    _, pages = site()
    legal = pages["legal"]
    assert "Draft" in legal and "not yet in force" in legal
    assert "not legal advice" in legal
    assert "has not been reviewed by counsel" in legal
    assert "that agreement governs" in legal   # must not override a real signed agreement


def test_legal_page_discloses_the_erasure_limitation(site):
    """The audit log is a hash chain, which is in real tension with a right to erasure. The
    product does not resolve it yet; the page must say so rather than imply compliance."""
    _, pages = site()
    assert "hash chain" in pages["legal"]
    assert "not yet implemented" in pages["legal"]


def test_contact_page_states_the_billing_model_without_inventing_prices(site):
    _, pages = site()
    contact = pages["contact"]
    for claim in ("Peak, not cumulative", "out of band", "No payment processor", "PCI scope"):
        assert claim in contact, claim
    # a currency amount anywhere on this page would be a number nobody supplied
    assert not re.search(r"[$£€]\s?\d", contact), "the contact page quotes a price it cannot know"


def test_fonts_loaded_with_fallbacks(site):
    _, pages = site()
    html = pages["index"]
    assert "fonts.googleapis.com/css2" in html and "display=swap" in html
    for fam in ("IBM+Plex+Mono", "IBM+Plex+Sans"):
        assert fam in html
    assert "monospace" in html and "sans-serif" in html    # generic fallbacks
    assert "fonts.gstatic.com" in html                     # preconnect


# ── navigation ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("slug", SLUGS)
def test_every_page_links_to_the_linked_ones(site, slug):
    _, pages = site()
    for target in LINKED:
        assert f'href="./{target}.html"' in pages[slug], f"{slug} does not link to {target}"


@pytest.mark.parametrize("slug", SLUGS)
def test_unlinked_pages_are_not_in_the_navigation(site, slug):
    """`contact` and `legal` are finished enough to review but every operator field on them
    is still NOT CONFIGURED. Sending a visitor there is worse than the placeholder saying
    plainly that it is not ready, so nothing links to them until the values are real."""
    _, pages = site()
    chrome = pages[slug].split("<main")[0] + pages[slug].split("</main>")[-1]
    for target in UNLINKED:
        assert f'href="./{target}.html"' not in chrome, \
            f"{slug} links to {target}, which is not meant to be wired up yet"


def test_unlinked_pages_are_still_built(site):
    """Unwired is not deleted: they must keep building so they can be previewed and shipped
    the moment the details exist."""
    out, pages = site()
    for slug in UNLINKED:
        assert (out / f"{slug}.html").is_file()
        assert len(pages[slug]) > 2000, f"{slug} built empty"


def test_placeholder_offers_a_way_back(site):
    """A dead end with no way out is the failure mode for a placeholder page."""
    _, pages = site()
    page = pages["coming-soon"]
    assert 'href="./index.html"' in page.split("<main")[1].split("</main>")[0], \
        "the placeholder has no back link in its body"
    assert "Coming soon" in page


def test_placeholder_does_not_invent_details(site):
    """The whole reason it exists: no address, no governing law, no mailbox that isn't real."""
    _, pages = site()
    body = pages["coming-soon"].split("<main")[1].split("</main>")[0]
    assert 'class="unset"' not in body, "the placeholder should have no fields to leave unset"
    assert not re.search(r"[$£€]\s?\d", body)


@pytest.mark.parametrize("slug", SLUGS)
def test_no_root_absolute_paths(site, slug):
    """A Pages project site is served from `/<repo>/`. A root-absolute `/about.html` or
    `/vendor/...` leaves the site entirely -- and for the module import the page still renders
    as static type, so the breakage reads as a design choice rather than a fault."""
    _, pages = site()
    absolute = re.findall(r'(?:src|href)="(/[^/"][^"]*)"', pages[slug])
    assert not absolute, f"{slug} has root-absolute path(s): {absolute}"


def test_module_imports_are_relative_and_resolve(site):
    out, pages = site()
    specifiers = re.findall(r"""\bfrom ['"]([^'"]+)['"]""", pages["index"])
    assert specifiers, "no module import found in the page"
    for spec in specifiers:
        assert not spec.startswith("/"), (
            f"module import {spec!r} is root-absolute and will 404 on a Pages project site")
        assert spec.startswith("."), f"unexpected bare module specifier {spec!r} (no bundler here)"
        assert (out / spec.lstrip("./")).is_file(), f"page imports {spec}, which the build omits"


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
    """Shipping `dist/` is the act of redistribution, so the notices have to be *in* `dist/` --
    it is not enough for them to sit in the source tree."""
    out, _ = site()
    v = out / "vendor" / "tte"
    assert (v / "src" / "index.js").is_file()
    for required in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        assert (v / required).is_file(), f"{required} was dropped from the build output"
    assert len(list((v / "LICENSES").glob("*.txt"))) >= 2


def _registered_effects():
    return set(re.findall(
        r"effect\('([a-z]+)'", (VENDOR / "src" / "builtin-effects.js").read_text(encoding="utf-8")))


def test_effect_names_are_real(site):
    """A misspelt effect name throws inside tte.js and costs the headline its animation."""
    _, pages = site()
    used = set(re.findall(r'data-effect="([a-z]+)"', pages["index"]))
    assert used, "no tte.js effects wired into the page"
    registered = _registered_effects()
    assert len(registered) >= 30, "effect catalogue did not parse"
    assert used <= registered, f"unknown effect(s): {used - registered}"
    assert "effectNames" in pages["index"] and "falling back" in pages["index"]


def test_micro_effect_names_are_real(site):
    """The headline effects live in `data-effect` attributes; the button/nav/chip effects are
    string literals in the module script. Same failure mode either way."""
    _, pages = site()
    used = set(re.findall(r"\['[^']+',\s*'([a-z]+)',\s*\d+", pages["index"]))
    registered = _registered_effects()
    assert len(used) >= 4, f"expected the micro-effect table to parse, got {used}"
    assert used <= registered, f"unknown micro effect(s): {used - registered}"


def test_effects_never_target_padded_elements(site):
    """The renderer spreads its character grid across the target's whole border box and sizes
    the font from the box height (CanvasRenderer.resize). Aiming it at a padded element draws
    a stretched, oversized label -- so `.btn` (padding 16/28) and the chips (padding 9/15) are
    animated through an inner, unpadded `.fx` span, never directly."""
    _, pages = site()
    selectors = set(re.findall(r"\['([^']+)',\s*'[a-z]+',\s*\d+", pages["index"]))
    assert selectors, "no micro-effect selectors found"
    for sel in selectors:
        assert sel not in (".btn", ".langs > span", ".langs span"), (
            f"{sel!r} is a padded element; target its inner .fx span instead")
    for slug in SLUGS:
        for m in re.finditer(r'<a class="btn[^"]*"[^>]*>(.*?)</a>', pages[slug], re.S):
            assert 'class="fx"' in m.group(1), f"a button label on {slug} lacks its .fx span"


def test_effects_disable_library_autoplay(site):
    """Every createTextEffect call must pass `autoplay: false`.

    The library defaults to `autoplay: true` and queues its own play() from the constructor.
    An explicit restart() then starts a run, and that queued play() immediately calls stop()
    on it -- which resolves the promise restart() returned as `{cancelled: true}`. Any code
    that treats "promise settled" as "animation finished" therefore tears the effect down a
    microtask after starting it, and the element never animates: no error, no warning, just
    static text. Found in a browser, invisible everywhere else.
    """
    _, pages = site()
    calls = re.findall(r"createTextEffect\(\s*el\s*,\s*\{(.*?)\}\s*\)", pages["index"], re.S)
    assert len(calls) >= 2, f"expected the headline and micro constructors, found {len(calls)}"
    for opts in calls:
        assert re.search(r"autoplay:\s*false", opts), \
            f"createTextEffect without autoplay:false -- {' '.join(opts.split())[:80]}"


def test_micro_effects_are_torn_down_not_stopped(site):
    """A button whose effect is halted rather than destroyed keeps `color: transparent` and
    loses its label permanently."""
    _, pages = site()
    html = pages["index"]
    assert "pointerleave" in html and "stopMicro" in html
    assert re.search(r"stopMicro\s*=\s*\(el\)\s*=>\s*\{[^}]*destroy\(\)", html), \
        "pointerleave must destroy(), not stop()"


def test_effect_bootstrap_is_not_gated_on_headlines(site):
    """The micro layer used to sit behind `lines.length`, which is zero on pages with no giant
    headline -- silently disabling every button and nav effect on about/contact/legal."""
    _, pages = site()
    assert "if (!reduce && 'IntersectionObserver' in window)" in pages["index"], \
        "the effect bootstrap is gated on headlines existing"


# ── the arrival transition ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("slug", SLUGS)
def test_transition_overlay_is_present_and_inert_without_js(site, slug):
    """The overlay covers the whole viewport, so it must be `display:none` until a script
    turns it on. With JavaScript off the inline head script never runs and the visitor must
    never meet a blank screen."""
    _, pages = site()
    html = pages[slug]
    assert 'id="xfer"' in html and 'aria-hidden="true"' in html
    assert re.search(r"#xfer \{[^}]*display:none", html), "overlay is not hidden by default"
    assert re.search(r"#xfer \{[^}]*pointer-events:none", html), (
        "overlay must not swallow clicks -- it lingers at opacity 0 while fading out")


def test_transition_has_a_failsafe_uncover(site):
    """The overlay is shown by a synchronous head script and removed by the deferred module.
    If the module never runs -- network error, syntax error, blocked import -- the page would
    stay covered forever. The head script therefore uncovers on a timer of its own."""
    _, pages = site()
    head = pages["index"].split("<style>")[0]
    assert "xfer-cover" in head, "the overlay is not armed before first paint"
    assert re.search(r"setTimeout\(function \(\) \{ d\.classList\.remove\('xfer-cover'\) \}", head), \
        "no failsafe to uncover the page if the module never runs"
    assert "prefers-reduced-motion" in head, "the transition is not gated on reduced motion"


def test_transition_keeps_the_headline_and_clears_the_rest(site):
    """Two frames built from ONE placement: a full-screen noise field with the page's headline
    embedded, and the same grid with every non-headline cell blanked. Identical dimensions mean
    the surviving characters stay in the cells they already occupy, so the message reads as
    persisting out of the decryption rather than being redrawn."""
    _, pages = site()
    html = pages["index"]
    assert "buildFrames" in html
    assert "noise:" in html and "kept:" in html, "the two frames are not both produced"
    # phase two paints the finished state directly -- animating it again would re-draw the
    # message instead of leaving it standing
    assert re.search(r"mount\(frames\.kept, 'decrypt', 1\)\.render\(1, 0\)", html), \
        "phase two must render(1) the final frame, not replay an animation"
    # the message comes from the page's own headline
    assert "querySelector('.line[data-effect]') || document.querySelector('h1')" in html


def test_transition_handles_a_page_with_no_headline(site):
    """A grid of nothing but spaces has no visible cells and the library throws on it. A page
    without a heading must fall back to noise-only rather than a broken transition."""
    _, pages = site()
    assert "hasMessage" in pages["index"]
    assert re.search(r"kept: hasMessage \?", pages["index"])


def test_transition_overlay_fills_the_viewport(site):
    """tte.js wraps its target in a box it styles inline as `width: fit-content`, which
    collapsed the overlay to the natural size of its text -- the noise filled only the
    top-left corner. The override needs !important to beat an inline style."""
    _, pages = site()
    assert re.search(r"#xfer \[data-text-effect\] \{[^}]*width:100% !important", pages["index"]), \
        "the overlay wrapper is not forced to fill the viewport"


def test_transition_does_not_intercept_navigation(site):
    """Deliberately arrival-only. An earlier version hijacked link clicks to animate before
    navigating, and browser testing showed the click being swallowed with no navigation request
    issued at all -- a link that silently does nothing. Links must stay ordinary anchors."""
    _, pages = site()
    html = pages["index"]
    assert "preventDefault" not in html, "something is intercepting clicks again"
    assert "window.location.href =" not in html, "script-driven navigation is back"


# ── serving ─────────────────────────────────────────────────────────────────────────
def test_javascript_is_served_as_javascript():
    """ES modules are rejected unless the MIME type is a JavaScript one. Python inherits this
    from the system MIME database, and on Windows a registry entry can override `.js`."""
    for ext in (".js", ".mjs"):
        assert serve.Handler.extensions_map[ext] == "text/javascript"


# ── degradation ─────────────────────────────────────────────────────────────────────
def test_landing_degrades_without_js(site):
    """tte.js draws over text that stays in the document. Every headline must therefore be real
    DOM text, not injected by script, so a no-JS visitor reads the whole page."""
    _, pages = site()
    html = pages["index"]
    assert 'type="module"' in html
    headlines = re.findall(r'<pre class="line[^"]*"[^>]*>(.*?)</pre>', html, re.S)
    assert len(headlines) >= 8, "expected a statement per screen"
    for h in headlines:
        assert h.strip(), "a headline is empty in the built HTML"
    for phrase in ("YOUR CODE RUNS", "NO SECURITY", "REQUEST ACCESS"):
        assert phrase in html


@pytest.mark.parametrize("slug", ("about", "contact", "legal"))
def test_secondary_pages_are_real_text(site, slug):
    """These pages carry the substantive claims. None of it may depend on JavaScript."""
    html = site()[1][slug]
    body = html.split("<main")[1].split("</main>")[0]
    assert len(re.sub(r"<[^>]+>", " ", body).split()) > 250, f"{slug} has little real text"


@pytest.mark.parametrize("slug", SLUGS)
def test_reduced_motion_respected(site, slug):
    _, pages = site()
    assert "prefers-reduced-motion" in pages[slug]
    assert re.search(r"if \(!reduce[^)]*\)", pages[slug]), \
        f"{slug} does not gate effects on reduced motion"
