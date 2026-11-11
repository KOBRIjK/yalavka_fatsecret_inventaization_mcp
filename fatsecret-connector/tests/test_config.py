import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fatsecret_connector.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_explicit_directory_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / '.env').write_text(
                'FATSECRET_CONSUMER_KEY=file-key\nFATSECRET_CONSUMER_SECRET=file-secret\n',
                encoding='utf-8')
            with patch.dict(os.environ, {'FATSECRET_CONSUMER_KEY': 'env-key'}, clear=True):
                settings = load_settings(root)
                self.assertEqual(settings.consumer_key, 'env-key')
                self.assertEqual(settings.consumer_secret, 'file-secret')
                self.assertNotIn('FATSECRET_CONSUMER_SECRET', os.environ)
            self.assertEqual(settings.token_file, root / '.tokens.json')
            self.assertNotIn('env-key', repr(settings))
            self.assertNotIn('file-secret', repr(settings))

    def test_config_directory_environment_variable(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'FATSECRET_CONFIG_DIR': directory}, clear=True):
                settings = load_settings()
            self.assertEqual(settings.token_file, Path(directory).resolve() / '.tokens.json')
            self.assertEqual(settings.consumer_key, '')
