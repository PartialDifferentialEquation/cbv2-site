#!/usr/bin/env python3
"""Build the public CBv2 site: substitute the operator placeholders, emit a static `dist/`.

The page used to be rendered per request by the licensing service (`cblicense/app.py`), which
meant a Python process sat on the public edge to serve one HTML file. Here the same
substitution happens **once, at build time**, and the output is plain files any static host
will serve — nginx, Caddy, S3, Pages.

The trade that buys: every operator value is baked in at build time, so changing one is a
rebuild rather than a restart. For a marketing site that is the right way round — the values
change roughly never, and nothing dynamic belongs on this box.

    python build.py                        # -> dist/, values from the environment
    python build.py --contact sales@acme.example --out /srv/www

Each page is `src/pages/<slug>.html` (the body) poured into `src/layout.html` (head, nav,
footer, the tte.js bootstrap) at `{{CONTENT}}`, so the chrome exists once.

Values that are unset render as a conspicuous "not configured" marker rather than plausible
filler. A marketing site inventing a registered address or a support mailbox is worse than one
admitting the field is empty — and on the legal page it would be a fabricated record.
"""

from __future__ import annotations

import argparse
import datetime
import html
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
DEFAULT_OUT = ROOT / "dist"

# Everything a build writes into the output directory. `_prepare_out` clears only these, so a
# `--out` pointed at anything else is an error rather than a silent wipe.
PAGES = {
    # slug: (title, meta description)
    "index": (
        "{vendor} — control your software after you ship it",
        "Package, license, meter and revoke proprietary software and AI models running on "
        "infrastructure you don't own. Per-customer attribution, per-run authorization, instant "
        "revocation, and a crown jewel that never leaves your server.",
    ),
    "about": (
        "About — {vendor}",
        "What {vendor} enforces, where the ceiling is, how it is deployed, and why licence "
        "enforcement is deliberately fail-soft.",
    ),
    "contact": (
        "Contact — {vendor}",
        "How to reach {vendor} for sales, security reports, privacy requests and support, how "
        "pricing is structured, and the registered entity details.",
    ),
    "legal": (
        "Terms & privacy — {vendor}",
        "Draft terms of service and privacy statement for {vendor}: what a licence grants, the "
        "honest limits of client-side protection, and what the licensing service collects.",
    ),
    "coming-soon": (
        "Coming soon — {vendor}",
        "Contact routes, entity details and terms for {vendor} are not published yet.",
    ),
}

# Pages that are built but deliberately NOT linked from the site's navigation. They are
# finished enough to review and to deploy the moment the operator values behind them are
# real, but until then every field on them renders as NOT CONFIGURED, and pointing a
# visitor at that is worse than telling them plainly it is not ready. `coming-soon` stands
# in for them in the nav. Unlinking is not hiding: these still build and are still reachable
# by direct URL, which is what makes them previewable.
UNLINKED = ("contact", "legal")

# The page the navigation and the "Request access" buttons fall back to while the routes
# they would otherwise point at are unconfigured.
PLACEHOLDER = "coming-soon"

OUTPUTS = frozenset({"vendor", ".nojekyll"} | {f"{slug}.html" for slug in PAGES})

# Operator-supplied values. name -> (env var, CLI flag, what it is, whether it may be omitted
# without the page reading as broken).
FIELDS = {
    "VENDOR_NAME":       ("CBSITE_VENDOR_NAME", "vendor name", "CBv2"),
    "CONTACT":           ("CBSITE_CONTACT", "'Request access' target", ""),
    "EMAIL_SALES":       ("CBSITE_EMAIL_SALES", "sales address", ""),
    "EMAIL_SECURITY":    ("CBSITE_EMAIL_SECURITY", "security address", ""),
    "EMAIL_PRIVACY":     ("CBSITE_EMAIL_PRIVACY", "privacy address", ""),
    "EMAIL_SUPPORT":     ("CBSITE_EMAIL_SUPPORT", "support address", ""),
    "LEGAL_ENTITY":      ("CBSITE_LEGAL_ENTITY", "registered company name", ""),
    "LEGAL_ADDRESS":     ("CBSITE_LEGAL_ADDRESS", "registered address", ""),
    "LEGAL_REG":         ("CBSITE_LEGAL_REG", "company / VAT registration", ""),
    "LEGAL_JURISDICTION": ("CBSITE_LEGAL_JURISDICTION", "governing law", ""),
}

# Placeholders the layout and pages may contain, beyond the FIELDS above.
DERIVED = ("CONTACT_HREF", "CONTACT_LABEL", "YEAR", "PAGE_TITLE", "PAGE_DESC", "CONTENT")


def unset(what: str) -> str:
    """Render a missing operator value as an obvious gap, never as plausible filler."""
    return f'<span class="unset">{html.escape(what)} not configured</span>'


def resolve_contact(contact: str) -> tuple[str, str]:
    """Turn the configured contact into an (href, label) pair.

    Ported from the licensing service's `_render_landing`, because the behaviour it encodes is
    the load-bearing part: **an unset contact must never produce a broken `mailto:`**. A bare
    email becomes a mailto link, a URL is linked as-is, anything else is shown as inert text.

    With nothing configured the "Request access" buttons point at the `coming-soon` placeholder
    rather than at `#`. `#` is not a destination — it scrolls to the top of the current page and
    leaves the visitor where they were, so the button reads as broken. Sending them to a page
    that says the route is not published yet is at least an answer.

    The inert branch (something configured that is neither a URL nor an address — a phone
    number, "ask your account manager") deliberately keeps `#`: the contact detail *is*
    published, it is rendered as text right there, and routing to "coming soon" would contradict
    the label sitting next to it.
    """
    contact = contact.strip()
    if not contact:
        return f"./{PLACEHOLDER}.html", "Contact your account team for access."
    if "://" in contact:
        return contact, contact
    if "@" in contact:
        return "mailto:" + contact, contact
    return "#", contact


def email_link(address: str, what: str) -> str:
    """An address becomes a mailto link; anything else is shown as-is; empty is marked unset."""
    address = address.strip()
    if not address:
        return unset(what)
    if "@" in address and "://" not in address and " " not in address:
        return f'<a href="mailto:{html.escape(address)}">{html.escape(address)}</a>'
    return html.escape(address)


def build_values(cfg: dict[str, str], *, year: int | None = None) -> dict[str, str]:
    """Turn raw operator config into the exact strings substituted into the templates."""
    contact_href, contact_label = resolve_contact(cfg.get("CONTACT", ""))
    now_year = year if year is not None else datetime.datetime.now(datetime.timezone.utc).year
    values = {
        "VENDOR_NAME": html.escape(cfg.get("VENDOR_NAME") or "CBv2"),
        "CONTACT_HREF": contact_href,
        "CONTACT_LABEL": contact_label,
        "YEAR": str(now_year),
        "LEGAL_UPDATED": datetime.datetime.now(datetime.timezone.utc).strftime("%d %B %Y"),
    }
    for key in ("EMAIL_SALES", "EMAIL_SECURITY", "EMAIL_PRIVACY", "EMAIL_SUPPORT"):
        values[key] = email_link(cfg.get(key, ""), FIELDS[key][1])
    for key in ("LEGAL_ENTITY", "LEGAL_ADDRESS", "LEGAL_REG", "LEGAL_JURISDICTION"):
        raw = cfg.get(key, "").strip()
        # Addresses are commonly multi-line; keep the line breaks the operator typed.
        values[key] = html.escape(raw).replace("\n", "<br>") if raw else unset(FIELDS[key][1])
    return values


def render(layout: str, body: str, values: dict[str, str], *, slug: str) -> str:
    """Pour a page body into the layout, substitute everything, and prove nothing survived."""
    page = layout.replace("{{CONTENT}}", body)
    for name, value in values.items():
        page = page.replace("{{" + name + "}}", value)
    leftover = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", page)))
    if leftover or "{{" in page or "}}" in page:
        raise SystemExit(
            f"build: {slug}.html still contains unsubstituted placeholder(s): "
            f"{', '.join(leftover) or '{{...}}'}\n"
            "       Add the field to FIELDS/build_values in build.py, or remove it from the "
            "template."
        )
    return page


def _prepare_out(out: Path) -> None:
    """Empty the output directory, refusing anything that is not a previous build.

    `--out` is operator input and this function deletes recursively, so it will only clear a
    directory that is empty or that already looks like one of our builds. Pointing it at a
    populated directory is an error, not a silent wipe.
    """
    if not out.exists():
        out.mkdir(parents=True)
        return
    if not out.is_dir():
        raise SystemExit(f"build: --out exists and is not a directory: {out}")
    entries = {p.name for p in out.iterdir()}
    if entries and not entries <= OUTPUTS:
        raise SystemExit(
            f"build: refusing to clear {out} — it holds files this build did not create "
            f"({', '.join(sorted(entries - OUTPUTS))}). "
            "Point --out at an empty or previously-built directory."
        )
    for p in out.iterdir():
        shutil.rmtree(p) if p.is_dir() else p.unlink()


def build(out: Path, cfg: dict[str, str], *, src: Path = SRC_DIR) -> Path:
    """Render every page into `out` alongside the vendored front-end libraries."""
    layout = (src / "layout.html").read_text(encoding="utf-8")
    values = build_values(cfg)
    vendor = values["VENDOR_NAME"]

    pages = {}
    for slug, (title, desc) in PAGES.items():
        body = (src / "pages" / f"{slug}.html").read_text(encoding="utf-8")
        per_page = dict(values,
                        PAGE_TITLE=html.escape(title.format(vendor=vendor)),
                        PAGE_DESC=html.escape(desc.format(vendor=vendor)))
        pages[slug] = render(layout, body, per_page, slug=slug)

    # Render everything before writing anything: a template error must not leave a half-built
    # directory behind, since `dist/` may be what a web server is currently serving.
    _prepare_out(out)
    for slug, page in pages.items():
        (out / f"{slug}.html").write_text(page, encoding="utf-8")
    # The vendored tree ships with its licence and notice files; copy it whole so attribution
    # travels with the code we redistribute rather than being trimmed to "just the .js".
    shutil.copytree(src / "vendor", out / "vendor")
    # Belt and braces for GitHub Pages. The Actions-based deployment never runs Jekyll, so this
    # changes nothing today — it matters only if the Pages source is ever switched to
    # "deploy from a branch", where Jekyll would silently drop any path starting with `_`.
    (out / ".nojekyll").touch()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the static CBv2 site into dist/.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: ./dist)")
    for key, (env, what, default) in FIELDS.items():
        ap.add_argument(f"--{key.lower().replace('_', '-')}",
                        default=os.environ.get(env, default),
                        help=f"{what} (env: {env})")
    args = ap.parse_args(argv)

    cfg = {key: getattr(args, key.lower()) or "" for key in FIELDS}
    out = build(args.out.resolve(), cfg)

    href, label = resolve_contact(cfg["CONTACT"])
    print(f"built  {out}  ({len(PAGES)} pages)")
    print(f"  vendor name : {cfg['VENDOR_NAME'] or 'CBv2'}")
    print(f"  contact     : {label}  ->  {href}")
    missing = [f"{FIELDS[k][0]} ({FIELDS[k][1]})" for k in FIELDS if not cfg[k].strip()]
    if missing:
        print("  unset — these render as a visible 'not configured' marker, not as filler:",
              file=sys.stderr)
        for m in missing:
            print(f"    {m}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
