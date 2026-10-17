"""Regression checks without Steam, game data, or an X server.

Run with the rig's Python environment: python -m unittest discover -s tools -p 'test_anoxrig.py'
"""
import contextlib
import importlib.util
import io
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from Xlib import X

spec = importlib.util.spec_from_file_location('anoxrig', Path(__file__).with_name('anoxrig.py'))
rig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rig)


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.logdir = Path(self.temp.name)
        self.log = self.logdir / 'remix-dxvk.log'
        self.log.write_text('old run: Camera cut detected\n')
        self.d = Mock()
        self.window = Mock()
        self.image = Image.new('RGB', (64, 40), (15, 25, 25))
        self.image.putpixel((32, 20), (160, 160, 160))
        self.clock = 0
        self.patches = [
            patch.object(rig, 'LOGS', str(self.logdir)),
            patch.object(rig.display, 'Display', return_value=self.d),
            patch.object(rig, 'game_window', return_value=self.window),
            patch.object(rig, 'grab', return_value=self.image),
            patch.object(rig.subprocess, 'Popen'),
            patch.object(rig.time, 'sleep', side_effect=self.advance),
            patch.object(rig.time, 'monotonic', side_effect=lambda: self.clock),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def advance(self, seconds):
        self.clock += seconds

    def start(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rig.cmd_start('3')
        return out.getvalue()

    def test_plus_visible_window_without_camera_message(self):
        output = self.start()
        self.assertIn('visible content', output)
        self.assertIn('camera unconfirmed', output)
        self.assertEqual(self.log.read_text(), 'old run: Camera cut detected\n')

    def test_old_camera_log_without_window_is_not_ready(self):
        with patch.object(rig, 'game_window', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'no game window'):
                self.start()

    def test_black_or_white_frame_is_not_ready(self):
        for color in ('black', 'white'):
            self.clock = 0
            with self.subTest(color=color), patch.object(rig, 'grab', return_value=Image.new('RGB', (64, 40), color)):
                with self.assertRaisesRegex(RuntimeError, 'visible content'):
                    self.start()

    def test_window_must_stay_visible(self):
        with patch.object(rig, 'game_window', side_effect=[self.window, self.window, None, None, None, None, None, None]):
            with self.assertRaises(RuntimeError):
                self.start()

    def test_new_camera_message_is_reported(self):
        def advance(seconds):
            self.advance(seconds)
            with self.log.open('a') as f:
                f.write('new run: Camera cut detected\n')
        with patch.object(rig.time, 'sleep', side_effect=advance):
            self.assertIn('remix camera found', self.start())

    def test_invalid_timeout_does_not_launch(self):
        for timeout in ('0', '-1', 'nan', 'inf'):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                rig.cmd_start(timeout)
        rig.subprocess.Popen.assert_not_called()


class InputTests(unittest.TestCase):
    def setUp(self):
        self.d = Mock()
        self.d.keysym_to_keycode.side_effect = lambda sym: {119: 25, 97: 38}.get(sym, 0)
        self.window = Mock()
        self.patches = [
            patch.object(rig.display, 'Display', return_value=self.d),
            patch.object(rig, 'game_window', return_value=self.window),
            patch.object(rig.xtest, 'fake_input'),
            patch.object(rig.time, 'sleep'),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_hold_focuses_then_holds_and_releases(self):
        def event(display, kind, code):
            self.window.set_input_focus.assert_called_once_with(X.RevertToParent, X.CurrentTime)
        rig.xtest.fake_input.side_effect = event
        rig.cmd_hold('2', 'w', 'a')
        self.assertEqual([call.args[1:] for call in rig.xtest.fake_input.call_args_list],
                         [(X.KeyPress, 25), (X.KeyPress, 38), (X.KeyRelease, 38), (X.KeyRelease, 25)])
        rig.time.sleep.assert_any_call(2.0)

    def test_interrupt_releases_all_pressed_keys(self):
        rig.time.sleep.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            rig.cmd_hold('2', 'w', 'a')
        calls = [call.args[1:] for call in rig.xtest.fake_input.call_args_list]
        pressed = [code for event, code in calls if event == X.KeyPress]
        released = [code for event, code in calls if event == X.KeyRelease]
        self.assertTrue(pressed)
        self.assertEqual(released, list(reversed(pressed)))

    def test_invalid_key_prevents_partial_chord(self):
        with self.assertRaises(ValueError):
            rig.cmd_hold('1', 'w', 'not_a_keysym')
        rig.xtest.fake_input.assert_not_called()

    def test_no_game_prevents_input_to_other_apps(self):
        with patch.object(rig, 'game_window', return_value=None), self.assertRaises(RuntimeError):
            rig.cmd_hold('1', 'w')
        rig.xtest.fake_input.assert_not_called()

    def test_key_taps_also_focus_game(self):
        rig.cmd_key('w')
        self.window.set_input_focus.assert_called_once_with(X.RevertToParent, X.CurrentTime)
        self.assertEqual([call.args[1:] for call in rig.xtest.fake_input.call_args_list],
                         [(X.KeyPress, 25), (X.KeyRelease, 25)])

    def test_invalid_duration_prevents_input(self):
        for duration in ('0', '-1', 'nan', 'inf', '61'):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                rig.cmd_hold(duration, 'w')
        rig.xtest.fake_input.assert_not_called()

    def test_cli_signals_release_held_keys(self):
        # Exercise __main__'s signal handling in a child, without touching X/Steam.
        stub = '''
import runpy, sys
from unittest.mock import Mock, patch
from Xlib import X
window = Mock()
window.get_wm_name.return_value = 'Anachronox'
window.get_attributes.return_value.map_state = X.IsViewable
display = Mock()
display.screen.return_value.root.query_tree.return_value.children = [window]
display.keysym_to_keycode.return_value = 25
pending = []
def event(d, kind, code):
    pending.append(kind)
    if kind == X.KeyRelease:
        print('released', flush=True)
def sync():
    if pending and pending[-1] == X.KeyPress:
        print('held', flush=True)
display.sync.side_effect = sync
script = sys.argv[1]
sys.argv = [script, 'hold', '60', 'w']
with patch('Xlib.display.Display', return_value=display), patch('Xlib.ext.xtest.fake_input', side_effect=event):
    runpy.run_path(script, run_name='__main__')
'''
        for sig, expected in ((signal.SIGINT, 130), (signal.SIGTERM, 143)):
            with self.subTest(signal=sig):
                process = subprocess.Popen([sys.executable, '-c', stub, rig.__file__],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'child never held key')
                    self.assertEqual(process.stdout.readline().strip(), 'held')
                    process.send_signal(sig)
                    out, err = process.communicate(timeout=5)
                    self.assertIn('released', out)
                    self.assertEqual(process.returncode, expected, err)
                    self.assertEqual(err, '')
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()


if __name__ == '__main__':
    unittest.main()
