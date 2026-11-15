#!/usr/bin/env python3
"""Import a Yandex session into the Lavka MCP config (one-time setup).

Usage:
    # from a private JSON file mapping cookie names to values:
    python scripts/import_cookies.py --json cookies.json

Optionally pin a delivery location:
    ... --lat 55.751244 --lon 37.618423 --label "Home"

Compose stores the result in PostgreSQL. Outside the stack the connector's
file configuration is used. Cookie values and delivery details are not printed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Allow running from a source checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from yandex_lavka_mcp.config import Location, load_config, save_config  # noqa: E402


def parse_cookie_header(header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in header.split(";"):
        part = part.strip()
        if not part:
            continue
        name, sep, value = part.partition("=")
        if not sep:
            raise ValueError
        cookies[name.strip()] = value.strip()
    return cookies


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--header", help="Raw Cookie header string (prefer --json to keep secrets out of shell history)")
    src.add_argument("--json", help="Path to a JSON file mapping cookie name->value")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--address-id")
    parser.add_argument("--label")
    args = parser.parse_args()

    if (args.lat is None) != (args.lon is None):
        parser.error("--lat and --lon must be supplied together")
    if args.lat is not None and not (-90 <= args.lat <= 90 and -180 <= args.lon <= 180):
        parser.error("Coordinates are out of range")
    if args.label and args.lat is None and not args.address_id:
        parser.error("--label requires coordinates or --address-id")

    try:
        if args.header is not None:
            cookies = parse_cookie_header(args.header)
        else:
            with open(args.json, encoding="utf-8-sig") as fh:
                cookies = json.load(fh)
        if not isinstance(cookies, dict) or not cookies or not all(
            isinstance(name, str) and re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name)
            and isinstance(value, str) and all(32 <= ord(ch) < 127 and ch != ";" for ch in value)
            for name, value in cookies.items()
        ):
            raise ValueError
    except (ValueError, OSError):
        print("Invalid cookie input: expected a readable name/value mapping or Cookie header.", file=sys.stderr)
        return 1

    try:
        config = load_config()
        config.cookies.update(cookies)
        if args.lat is not None or args.address_id:
            config.location = Location(
                lat=args.lat, lon=args.lon, address_id=args.address_id, label=args.label
            )
        save_config(config)
    except Exception:
        print("Could not read or save the Lavka configuration.", file=sys.stderr)
        return 1
    print(f"Saved {len(cookies)} cookies. Session cookie present: {config.is_authenticated()}")
    print(f"Location set: {config.location.is_set()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
