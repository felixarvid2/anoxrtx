"""Offline capture orchestration tests; no X display, Steam, or game is used."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from PIL import Image

import anoxcapture as capture
import anoxcompare

REAL_FINGERPRINTS = capture.fingerprints


class CaptureTests(unittest.TestCase):
    receipt = 'loaded steamuser/1 map=rowdys viewpos=(1 2 3) yaw=359 sha256=' + 'a' * 64 + '\n'
    expected = [1, 2, 3, 359]

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'capture'
        self.fingerprints = {
            'runtime': 'b' * 64, 'dll': 'c' * 64,
            'config': {'rtx.conf': 'd' * 64}, 'layers': {'mod.usda': 'e' * 64},
        }
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        patch = lambda name, **kw: self.patches.enter_context(mock.patch(name, **kw))
        self.save = patch('anoxcapture.rig.save_info', return_value={'sha256': 'a' * 64})
        self.inventory = patch('anoxcapture.fingerprints',
                               side_effect=lambda: (copy.deepcopy(self.fingerprints), {'d3d9.dll': 'b' * 64}))
        self.sleep = patch('anoxcapture.time.sleep')
        self.display = patch('anoxcapture.rig.display.Display')
        self.grab = patch('anoxcapture.rig.grab', return_value=Image.new('RGB', (20, 10), (100, 100, 100)))
        self.visible = patch('anoxcapture.rig.visible_content', side_effect=lambda image: image is not None)
        self.console = patch('anoxcapture.rig.is_console', return_value=False)
        self.menu = patch('anoxcapture.rig.is_menu', return_value=False)
        patch('anoxcapture.rig.GAME', new=str(self.root / 'game'))
        patch('anoxcapture.rig.LOGS', new=str(self.root / 'logs'))
        self.load = patch('anoxcapture.rig.cmd_load_save', side_effect=lambda *args: print(self.receipt, end=''))

    def run_capture(self, **kwargs):
        return capture.capture_frames(self.out, self.receipt, self.expected, **kwargs)

    def main(self, extra=()):
        args = ['anoxcapture.py', '--save', 'steamuser/1', '--expected-pose', '1', '2', '3', '359',
                '--out', str(self.out), *extra]
        with mock.patch('sys.argv', args), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return capture.main()

    def test_invalid_arguments_rejected_before_loading(self):
        for args in (['--settle', '-1'], ['--settle', 'nan'], ['--interval', '0'],
                     ['--interval', 'inf'], ['--frames', '2'], ['--frames', '31'],
                     ['--expected-pose', 'nan', '2', '3', '4'], ['--timeout', '0']):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                self.main(args)
            self.load.assert_not_called()
            self.display.assert_not_called()
            self.assertFalse(self.out.exists())

    def test_real_inventory_rejects_missing_or_empty_mods_before_load(self):
        game = self.root / 'game'
        for name in ('d3d9.dll', '.trex/d3d9.dll', '.trex/NvRemixBridge.exe',
                     'opengl32.dll', 'rtx.conf', 'QindieGL.ini', 'anox_customise.ini',
                     '.trex/bridge.conf'):
            path = game / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'synthetic installed file')
        self.inventory.side_effect = REAL_FINGERPRINTS
        mods = game / 'rtx-remix/mods'
        for state in ('missing', 'empty'):
            if state == 'empty':
                mods.mkdir(parents=True)
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, 'installed mod inventory is empty'):
                    REAL_FINGERPRINTS()
                with self.assertRaises(SystemExit):
                    self.main()
                self.load.assert_not_called()
                self.display.assert_not_called()
                self.assertFalse(self.out.exists())
        # A real nonempty inventory succeeds, proving rejection was about mods.
        (mods / 'mod.usda').write_text('#usda 1.0')
        fingerprints, _ = REAL_FINGERPRINTS()
        self.assertEqual(list(fingerprints['layers']), ['rtx-remix/mods/mod.usda'])

    def test_missing_environment_preflight_rejected_before_load(self):
        self.inventory.side_effect = FileNotFoundError('missing d3d9.dll')
        with self.assertRaises(SystemExit):
            self.main()
        self.load.assert_not_called()
        self.display.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_environment_changed_during_load_rejected_before_capture(self):
        changed = copy.deepcopy(self.fingerprints)
        changed['config']['rtx.conf'] = 'f' * 64
        self.inventory.side_effect = [(self.fingerprints, {}), (changed, {})]
        with self.assertRaises(SystemExit):
            self.main()
        self.load.assert_called_once()
        self.display.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_existing_output_rejected_without_load_or_overwrite(self):
        self.out.mkdir()
        sentinel = self.out / 'manifest.json'
        sentinel.write_text('preserved')
        with self.assertRaises(SystemExit):
            self.main()
        self.load.assert_not_called()
        self.assertEqual(sentinel.read_text(), 'preserved')

    def test_wrong_pose_rejected_before_screenshots_or_output(self):
        for expected in ([4, 2, 3, 359], [1, 2, 3, 2], [float('nan'), 2, 3, 359], [1, 2, 3]):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                capture.capture_frames(self.out, self.receipt, expected)
        self.display.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_changed_save_before_sequence_rejected(self):
        self.save.return_value = {'sha256': 'f' * 64}
        with self.assertRaisesRegex(ValueError, 'fingerprint changed'):
            self.run_capture()
        self.assertFalse(self.out.exists())
        self.display.assert_not_called()

    def test_changed_save_during_sequence_has_no_completed_manifest(self):
        self.save.side_effect = [{'sha256': 'a' * 64}, {'sha256': 'f' * 64}]
        with self.assertRaisesRegex(RuntimeError, 'changed during sequence'):
            self.run_capture()
        self.assertFalse((self.out / 'manifest.json').exists())
        self.display.return_value.close.assert_called_once()

    def test_config_change_during_sequence_has_no_completed_manifest(self):
        changed = copy.deepcopy(self.fingerprints)
        changed['config']['rtx.conf'] = 'f' * 64
        self.inventory.side_effect = [(self.fingerprints, {}), (changed, {})]
        with self.assertRaisesRegex(RuntimeError, 'changed during sequence'):
            self.run_capture()
        self.assertEqual(len(list(self.out.glob('frame*.png'))), 3)
        self.assertFalse((self.out / 'manifest.json').exists())

    def test_reject_missing_menu_console_without_completed_manifest(self):
        for name in ('missing', 'menu', 'console'):
            with self.subTest(name=name):
                self.out = self.root / name
                self.grab.return_value = None if name == 'missing' else Image.new('RGB', (20, 10))
                self.menu.return_value = name == 'menu'
                self.console.return_value = name == 'console'
                with self.assertRaisesRegex(RuntimeError, 'scene missing, console or menu'):
                    self.run_capture()
                self.assertFalse((self.out / 'manifest.json').exists())
        self.assertEqual(self.display.return_value.close.call_count, 3)

    def test_geometry_change_rejected_and_display_closed(self):
        self.grab.side_effect = [Image.new('RGB', (20, 10)), Image.new('RGB', (21, 10))]
        with self.assertRaisesRegex(RuntimeError, 'geometry changed'):
            self.run_capture()
        self.assertFalse((self.out / 'manifest.json').exists())
        self.display.return_value.close.assert_called_once()

    def test_success_schema_is_accepted_by_comparator(self):
        self.main(['--settle', '0', '--interval', '.1'])
        manifest = json.loads((self.out / 'manifest.json').read_text())
        self.assertEqual(manifest['save']['selector'], 'steamuser/1')
        self.assertEqual(manifest['pose'], {'xyz': [1, 2, 3], 'yaw': 359})
        self.assertEqual(manifest['geometry'], {'width': 20, 'height': 10})
        self.assertEqual(manifest['fingerprints'], self.fingerprints)
        _, median, paths, _ = anoxcompare.load_capture(self.out / 'manifest.json')
        self.assertEqual(median.shape, (10, 20, 3))
        self.assertEqual(len(paths), 3)
        self.load.assert_called_once_with('steamuser/1', '120')
        self.display.return_value.close.assert_called_once()

    def test_load_failure_does_not_create_completed_capture(self):
        self.load.side_effect = RuntimeError('load failed')
        with self.assertRaises(SystemExit):
            self.main()
        self.assertFalse(self.out.exists())
        self.display.assert_not_called()

    def test_unverified_or_ambiguous_receipt_rejected(self):
        for text in ('', 'load failed', self.receipt + self.receipt):
            with self.subTest(text=text), self.assertRaises(ValueError):
                capture.capture_frames(self.out, text, self.expected)
        self.display.assert_not_called()
        self.assertFalse(self.out.exists())


if __name__ == '__main__':
    unittest.main()
