"""Command-line entry point for HTTP and stdio."""
import argparse
import os
from pathlib import Path

from .config import load_settings
from .server import create_server


def main(argv=None, *, default_config_dir: Path | None = None):
    parser = argparse.ArgumentParser(description='Personal FatSecret MCP server')
    parser.add_argument('--http', action='store_true',
                        help='Serve Streamable HTTP on loopback; otherwise use stdio.')
    parser.add_argument('--port', type=int, default=8000, help='HTTP port (default: 8000).')
    parser.add_argument('--config-dir', type=Path,
                        default=os.getenv('FATSECRET_CONFIG_DIR') or default_config_dir,
                        help='Directory containing .env and .tokens.json; defaults to cwd.')
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    server = create_server(settings=load_settings(args.config_dir), port=args.port)
    server.run(transport='streamable-http' if args.http else 'stdio')


if __name__ == '__main__':
    main()
