import copy
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE = 'gyani'
config = importlib.import_module(PACKAGE + '.config')
SessionManager = importlib.import_module(PACKAGE + '.session').SessionManager


class ConfigTests(unittest.TestCase):
    def tearDown(self):
        importlib.reload(config)

    def test_new_install_uses_gyani_directory(self):
        with tempfile.TemporaryDirectory() as root, patch.object(Path, 'home', return_value=Path(root)), patch.dict(os.environ, {}, clear=True):
            importlib.reload(config)
            config.save_config(config.load_config())
            self.assertTrue((Path(root) / '.gyani/config.json').is_file())

    def test_existing_settings_and_workspace_are_preserved(self):
        with tempfile.TemporaryDirectory() as root, patch.object(Path, 'home', return_value=Path(root)), patch.dict(os.environ, {}, clear=True):
            old = Path(root) / '.bujji'
            old.mkdir()
            (old / 'config.json').write_text('{"active_provider":"existing"}')
            importlib.reload(config)
            loaded = config.load_config()
            self.assertEqual(loaded['active_provider'], 'existing')
            self.assertEqual(config.workspace_path(loaded), old / 'workspace')

    def test_explicit_config_directory(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'GYANI_CONFIG_DIR': root}):
            importlib.reload(config)
            config.save_config(config.load_config())
            self.assertTrue((Path(root) / 'config.json').exists())


class SessionTests(unittest.TestCase):
    def test_reused_session_streams_to_current_request(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = copy.deepcopy(config.DEFAULT_CONFIG)
            cfg['agents']['defaults']['workspace'] = root
            cfg['providers'] = {'ollama': {'api_key': 'local'}}
            manager = SessionManager(cfg)
            first, second = [], []
            agent = manager.get('web:test', callbacks={'on_token': first.append, 'on_tool_start': lambda name, args: first.append(name)})
            reused = manager.get('web:test', callbacks={'on_token': second.append, 'on_tool_start': lambda name, args: second.append(name)})
            self.assertIs(agent, reused)
            reused.callbacks['on_token']('hello')
            self.assertEqual(second, ['hello'])
            self.assertEqual(first, [])
            reused.tools.call('get_time', {})
            self.assertEqual(second, ['hello', 'get_time'])
            self.assertEqual(first, [])
