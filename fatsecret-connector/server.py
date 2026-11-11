"""Compatibility entry point; install the project with pip install -e . first."""
from pathlib import Path

from fatsecret_connector.__main__ import main


if __name__ == '__main__':
    main(default_config_dir=Path(__file__).resolve().parent)
