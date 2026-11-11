"""Explicit configuration loading; importing this module does not read secrets."""
from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class Settings:
    consumer_key: str = field(repr=False)
    consumer_secret: str = field(repr=False)
    token_file: Path


def load_settings(config_dir: str | Path | None = None) -> Settings:
    directory = Path(config_dir or os.getenv('FATSECRET_CONFIG_DIR') or Path.cwd())
    directory = directory.expanduser().resolve()
    if os.environ.get('EDA_DATABASE_URL'):
        from eda_state import load_state
        credentials = load_state('fatsecret_credentials') or {}
        values = {'FATSECRET_CONSUMER_KEY': credentials.get('consumer_key', ''),
                  'FATSECRET_CONSUMER_SECRET': credentials.get('consumer_secret', '')}
    else:
        values = dotenv_values(directory / '.env')
    return Settings(
        consumer_key=os.getenv('FATSECRET_CONSUMER_KEY',
                               values.get('FATSECRET_CONSUMER_KEY') or ''),
        consumer_secret=os.getenv('FATSECRET_CONSUMER_SECRET',
                                  values.get('FATSECRET_CONSUMER_SECRET') or ''),
        token_file=directory / '.tokens.json',
    )
