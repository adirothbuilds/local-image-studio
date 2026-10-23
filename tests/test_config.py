import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from studio import config

class ConfigTests(unittest.TestCase):
    def test_data_only_parser_rejects_shell_and_unknown_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'.env'
            path.write_text('# comment\nSTUDIO_PASSWORD="literal$(echo secret)"\nSTUDIO_PORT=8000\n')
            self.assertEqual(config.read_env(path)['STUDIO_PASSWORD'],'literal$(echo secret)')
            path.write_text('export STUDIO_PORT=8000')
            with self.assertRaises(ValueError): config.read_env(path)

    def test_initialize_preserves_credentials_and_environment_overrides(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(config,'ROOT',Path(temp)):
            initial=config.initialize()
            self.assertGreaterEqual(len(initial['STUDIO_PASSWORD']),16)
            self.assertEqual(config.initialize(),initial)
            self.assertEqual((Path(temp)/'.env').stat().st_mode & 0o777,0o600)
            with patch.dict('os.environ',{'STUDIO_PORT':'8001'}):
                self.assertEqual(config.settings()['STUDIO_PORT'],'8001')
            self.assertEqual(config.read_env(Path(temp)/'.env')['STUDIO_PORT'],'7860')

    def test_migrates_legacy_password_without_changing_it(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(config,'ROOT',Path(temp)):
            runtime=Path(temp)/'.runtime'
            runtime.mkdir()
            (runtime/'lan-password').write_text('existing-house-password-123\n')
            self.assertEqual(config.initialize()['STUDIO_PASSWORD'],'existing-house-password-123')
