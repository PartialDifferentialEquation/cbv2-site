#!/usr/bin/env python3
"""Local preview server for the built site. Development only — never the production edge.

Two things make this worth having rather than just opening `dist/index.html` in a browser:

1. **`file://` cannot load ES modules.** tte.js ships as ES modules and the page imports it
   with `<script type="module">`, which browsers refuse to load over `file://`. Without a real
   HTTP origin the page renders as static type and every effect is silently absent — which
   looks like working output, so it is a genuinely misleading way to review the page.
2. **The JavaScript MIME type has to be right.** A module served as `text/plain` is rejected
   outright. Python reads the system MIME database, and on Windows a registry entry can map
   `.js` to something else entirely, so the mapping is pinned below rather than inherited.

    python serve.py                 # build, then serve on http://127.0.0.1:8000
    python serve.py --port 9000 --no-build

Production hosting is a static file server (nginx, Caddy, S3, Pages) pointed at `dist/`.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import socketserver
from pathlib import Path

import build as build_mod


class Handler(http.server.SimpleHTTPRequestHandler):
    # Pinned rather than inherited from the system MIME database — see the module docstring.
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".html": "text/html",
        ".css": "text/css",
        ".svg": "image/svg+xml",
        ".json": "application/json",
        ".md": "text/plain; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }

    def end_headers(self) -> None:
        # A preview server that serves stale bytes wastes more time than it saves.
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:  # quieter than the stdlib default
        if not str(args[1] if len(args) > 1 else "").startswith("2"):
            super().log_message(fmt, *args)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Preview the built site over HTTP (development only).")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1", help="default: loopback only")
    ap.add_argument("--dist", type=Path, default=build_mod.DEFAULT_OUT)
    ap.add_argument("--no-build", action="store_true", help="serve dist/ as-is instead of rebuilding")
    # Every operator field, read from the same environment variables build.py uses, so a
    # preview shows exactly what a deploy would. Kept in lockstep by iterating build.FIELDS
    # rather than restating the list — a new field added there must not silently vanish here.
    for key, (env, _what, default) in build_mod.FIELDS.items():
        ap.add_argument(f"--{key.lower().replace('_', '-')}",
                        default=os.environ.get(env, default))
    args = ap.parse_args(argv)

    dist = args.dist.resolve()
    if not args.no_build:
        build_mod.build(dist, {k: getattr(args, k.lower()) or "" for k in build_mod.FIELDS})
        print(f"built  {dist}")
    elif not (dist / "index.html").is_file():
        raise SystemExit(f"serve: nothing built at {dist} — run without --no-build first.")

    handler = functools.partial(Handler, directory=str(dist))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print(f"serving {dist} at http://{args.host}:{args.port}/  (ctrl-c to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
