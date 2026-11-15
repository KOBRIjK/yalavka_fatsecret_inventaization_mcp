#!/usr/bin/env python3
"""Get Yandex's captcha pass (`spravka` cookie) for a server whose IP is blocked.

When Lavka answers a server with a captcha (the MCP says "Yandex anti-bot
returned a captcha"), it is the server's IP that is flagged, not the session.
Solve the captcha once *through that IP* and give the server the resulting
`spravka` cookie — requests from there pass again (the cookie lives ~30 days).

Usage:
    python scripts/solve_captcha.py --help

A Chrome window opens on the captcha (a throwaway profile, not your browser);
solve it there. The script waits until Lavka really answers with data, then
writes the result to a new file in a private directory specified by --output.
The cookie is never printed.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

LAVKA = "https://lavka.yandex.ru"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def save_result(path: Path, value: str) -> None:
    # Exclusive creation also prevents following an existing file or symlink.
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w", encoding="utf-8") as fh:
        fh.write(value)


def search(ctx) -> dict:
    """One real Lavka API call with the browser's cookies (doesn't touch the page)."""
    html = ctx.request.get(LAVKA + "/").text()
    m = re.search(r'"csrfToken":"([^"]+)"', html)
    r = ctx.request.post(
        LAVKA + "/api/v1/providers/search/v3/lavka",
        data={"text": "молоко"},
        headers={
            "x-csrf-token": m.group(1) if m else "",
            "x-requested-with": "XMLHttpRequest",
            "x-captcha-service": "lavka",
        },
    )
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("Unexpected service response")
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy", required=True, help="proxy through the blocked IP, e.g. socks5://127.0.0.1:1080")
    ap.add_argument("--timeout", type=int, default=900, help="seconds to wait for the solve (default 900)")
    ap.add_argument("--output", required=True, type=Path, help="new file in a private directory; never overwritten")
    args = ap.parse_args()
    if args.timeout <= 0:
        ap.error("--timeout must be positive")
    try:
        from playwright.sync_api import Error as PlaywrightError, sync_playwright
    except ImportError:
        log("Interactive mode requires Playwright and desktop Chrome; they are not part of the MCP image.")
        return 1

    profile = tempfile.mkdtemp(prefix="lavka-captcha-")
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                profile, channel="chrome", headless=False, proxy={"server": args.proxy}
            )
            first = search(ctx)
            if first.get("type") != "captcha":
                log("No captcha from this IP — nothing to solve.")
                return 1
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(first["captcha"]["captcha-page"], wait_until="domcontentloaded")
            log("Solve the captcha in the Chrome window (don't close it)...")
            deadline = time.time() + args.timeout
            while time.time() < deadline:
                time.sleep(3)
                if search(ctx).get("type") != "captcha":
                    break
            else:
                log("Timed out: captcha not solved.")
                return 1
            spravka = next((c["value"] for c in ctx.cookies() if c["name"] == "spravka"), None)
            ctx.close()
        if not spravka:
            log("Lavka passes, but no `spravka` cookie was set.")
            return 1
        save_result(args.output, spravka)
        log("Result saved.")
        return 0
    except FileExistsError:
        log("Output file already exists; nothing was overwritten.")
        return 1
    except OSError:
        log("File operation failed. Check the private output directory and its permissions.")
        return 1
    except (PlaywrightError, ValueError, KeyError):
        log("Browser request failed. Check desktop Chrome, the connection and the service response.")
        return 1
    finally:
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
