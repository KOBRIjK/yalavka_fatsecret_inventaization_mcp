"""Compatibility entry point for local account authorization."""
from pathlib import Path

from fatsecret_connector.authorize import cli


if __name__ == '__main__':
    cli(default_config_dir=Path(__file__).resolve().parent)
