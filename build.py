#!/usr/bin/env python3
"""Build the public CBv2 site: substitute the operator placeholders, emit a static `dist/`.

The page used to be rendered per request by the licensing service (`cblicense/app.py`), which
meant a Python process sat on the public edge to serve one HTML file. Here the same
substitution happens **once, at build time**, and the output is plain files any static host
will serve — nginx, Caddy, S3, Pages.

The trade that buys: `--vendor-name` / `--contact` are baked in at build time, so changing
either is a rebuild rather than a restart. For a marketing page that is the right way round —
the values change roughly never, and nothing dynamic belongs on this box.

    python build.py                        # -> dist/, values from the environment
    python build.py --contact sales@acme.example --out /srv/www

Placeholders in `src/index.html`, all four required:

    {{VENDOR_NAME}}   product/vendor name shown in the masthead and footer
    {{CONTACT_HREF}}  href for the "Request access" call to action
    {{CONTACT_LABEL}} its visible text
    {{YEAR}}          copyright year
"""

from __future__ import annotations

import argparse
import datetime
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
DEFAULT_OUT = ROOT / "dist"

# Every placeholder the template may contain. The build fails if one is missing from this map
# (an unsubstituted `{{...}}` would otherwise ship to production as literal text).
PLACEHOLDERS = ("VENDOR_NAME", "CONTACT_HREF", "CONTACT_LABEL", "YEAR")


def resolve_contact(contact: str) -> tuple[str, str]:
    """Turn the configured contact into an (href, label) pair.

    Ported verbatim from the licensing service's `_render_landing`, because the behaviour it
    encodes is the load-bearing part: **an unset contact must never produce a broken
    `mailto:`**. A bare email becomes a mailto link, a URL is linked as-is, anything else is
    shown as inert text, and empty falls back to a neutral prompt.
    """
    contact = contact.strip()
    if not contact:
        return "#", "Contact your account team for access."
    if "://" in contact:
        return contact, contact
    if "@" in contact:
        return "mailto:" + contact, contact
    return "#", contact


def render(template: str, *, vendor_name: str, contact: str, year: int | None = None) -> str:
    """Substitute every placeholder and prove none survived."""
    contact_href, contact_label = resolve_contact(contact)
    values = {
        "VENDOR_NAME": vendor_name,
        "CONTACT_HREF": contact_href,
        "CONTACT_LABEL": contact_label,
        "YEAR": str(year if year is not None else datetime.datetime.now(datetime.timezone.utc).year),
    }
    assert set(values) == set(PLACEHOLDERS)
    html = template
    for name, value in values.items():
        html = html.replace("{{" + name + "}}", value)
    if "{{" in html or "}}" in html:
        raise SystemExit(
            "build: template still contains an unsubstituted placeholder after rendering.\n"
            "       Add it to PLACEHOLDERS in build.py, or remove it from src/index.html."
        )
    return html


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
    if entries and not entries <= {"index.html", "vendor"}:
        raise SystemExit(
            f"build: refusing to clear {out} — it holds files this build did not create "
            f"({', '.join(sorted(entries - {'index.html', 'vendor'}))}). "
            "Point --out at an empty or previously-built directory."
        )
    for p in out.iterdir():
        shutil.rmtree(p) if p.is_dir() else p.unlink()


def build(out: Path, *, vendor_name: str, contact: str, src: Path = SRC_DIR) -> Path:
    """Render the page into `out` alongside the vendored front-end libraries."""
    template = (src / "index.html").read_text(encoding="utf-8")
    html = render(template, vendor_name=vendor_name, contact=contact)
    _prepare_out(out)
    (out / "index.html").write_text(html, encoding="utf-8")
    # The vendored tree ships with its licence and notice files; copy it whole so attribution
    # travels with the code we redistribute rather than being trimmed to "just the .js".
    shutil.copytree(src / "vendor", out / "vendor")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the static CBv2 site into dist/.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: ./dist)")
    ap.add_argument("--vendor-name", default=os.environ.get("CBSITE_VENDOR_NAME", "CBv2"),
                    help="product/vendor name (env: CBSITE_VENDOR_NAME)")
    ap.add_argument("--contact", default=os.environ.get("CBSITE_CONTACT", ""),
                    help="'Request access' target: email, URL, or free text (env: CBSITE_CONTACT)")
    args = ap.parse_args(argv)

    out = build(args.out.resolve(), vendor_name=args.vendor_name, contact=args.contact)
    href, label = resolve_contact(args.contact)
    print(f"built  {out}")
    print(f"  vendor name : {args.vendor_name}")
    print(f"  contact     : {label}  ->  {href}")
    if not args.contact.strip():
        print("  note: no contact configured — the call to action is an inert prompt.\n"
              "        Set CBSITE_CONTACT (or --contact) before deploying.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
