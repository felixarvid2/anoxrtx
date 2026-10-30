"""Regression checks without Steam, game data, or an X server.

Run with the rig's Python environment: python -m unittest discover -s tools -p 'test_anoxrig.py'
"""
import contextlib
import gzip
import importlib.util
import io
from pathlib import Path
import select
import signal
import subprocess
import struct
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


class ConsoleInputTests(unittest.TestCase):
    def setUp(self):
        self.d = Mock()
        self.d.get_keyboard_control.return_value = Mock(
            global_auto_repeat=X.AutoRepeatModeOn, auto_repeats=bytes([255] * 32))

    def test_clear_budget_covers_long_line_at_server_rate(self):
        with patch.object(rig.subprocess, 'run', return_value=Mock(
                stdout='auto repeat delay: 600 repeat rate: 25')) as query:
            self.assertAlmostEqual(rig.console_clear_seconds(self.d, 22), 10.7)
        self.assertEqual(query.call_args.kwargs['timeout'], 5)

    def test_disabled_backspace_repeat_is_rejected(self):
        self.d.get_keyboard_control.return_value.auto_repeats = bytes(32)
        with self.assertRaisesRegex(RuntimeError, 'autorepeat is disabled'):
            rig.console_clear_seconds(self.d, 22)

    def test_unreadable_repeat_rate_is_rejected(self):
        for result in ('', 'auto repeat delay: 600 repeat rate: 0'):
            with self.subTest(result=result), patch.object(rig.subprocess, 'run',
                    return_value=Mock(stdout=result)):
                with self.assertRaisesRegex(RuntimeError, 'autorepeat rate'):
                    rig.console_clear_seconds(self.d, 22)
        with patch.object(rig.subprocess, 'run', side_effect=subprocess.TimeoutExpired('xset', 5)):
            with self.assertRaisesRegex(RuntimeError, 'autorepeat rate'):
                rig.console_clear_seconds(self.d, 22)

    def test_console_input_uses_held_clear_and_slow_keys(self):
        with patch.object(rig, 'console_keys', return_value=[[20], [21]]), \
                patch.object(rig, 'keycodes', side_effect=lambda d, names: {
                    ('End',): [10], ('BackSpace',): [11], ('Return',): [12]}[tuple(names)]), \
                patch.object(rig, 'console_clear_seconds', return_value=10.7), \
                patch.object(rig, 'press_keys') as press, patch.object(rig.time, 'sleep') as sleep:
            rig.console_line(self.d, 'ab')
        self.assertEqual(press.call_args_list, [
            unittest.mock.call(self.d, [10], 0.2),
            unittest.mock.call(self.d, [11], 10.7),
            unittest.mock.call(self.d, [20], 0.12),
            unittest.mock.call(self.d, [21], 0.12),
            unittest.mock.call(self.d, [12], 0.12)])
        self.assertEqual(sleep.call_args_list, [unittest.mock.call(0.5),
            unittest.mock.call(0.12), unittest.mock.call(0.12)])

    def test_held_backspace_released_when_sync_fails(self):
        self.d.sync.side_effect = [RuntimeError('sync failed'), None]
        with patch.object(rig.xtest, 'fake_input') as fake:
            with self.assertRaisesRegex(RuntimeError, 'sync failed'):
                rig.press_keys(self.d, [22], 10.7)
        self.assertEqual(fake.call_args_list, [unittest.mock.call(self.d, X.KeyPress, 22),
            unittest.mock.call(self.d, X.KeyRelease, 22)])


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = Path(self.temp.name)
        self.save_root = self.game / 'anoxdata/SAVE/steamuser'
        self.save_root.mkdir(parents=True)
        self.autoexec = self.game / 'anoxdata/CONFIGS/autoexec.cfg'
        self.autoexec.parent.mkdir()
        label = b"Bricks:\nRowdy's Bar\x00"
        data = struct.pack('<6I', 1004, 988, 432, 0, len(label) + 32, len(label))
        data += label + b'\x00maps/rowdys.bsp\x00'
        self.save = self.save_root / 'anoxsave1.sav'
        self.save.write_bytes(gzip.compress(data))
        p = patch.object(rig, 'GAME', str(self.game))
        p.start()
        self.addCleanup(p.stop)

    def test_save_metadata_and_fingerprint(self):
        info = rig.save_info('steamuser/1')
        self.assertEqual(info['save'], 'steamuser/1')
        self.assertEqual(info['map'], 'rowdys')
        self.assertEqual(info['description'], "Bricks: / Rowdy's Bar")
        self.assertEqual(len(info['sha256']), 64)

    def test_bad_selectors_never_touch_game(self):
        for name in ('../1', 'steamuser/../1', '/1', 'steamuser/1;quit', 'steamuser/1000', 'steamuser/-1'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                rig.save_info(name)

    def test_missing_or_corrupt_saves_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not found'):
            rig.save_info('steamuser/2')
        self.save.write_bytes(b'invalid')
        with self.assertRaisesRegex(ValueError, 'save'):
            rig.save_info('steamuser/1')

    def test_list_saves_does_not_write_files(self):
        before = self.save.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rig.cmd_list_saves()
        self.assertIn('steamuser/1', out.getvalue())
        self.assertIn('rowdys', out.getvalue())
        self.assertEqual(before, self.save.read_bytes())
        self.assertFalse(self.autoexec.exists())

    def test_invalid_save_never_stops_game_or_changes_config(self):
        with patch.object(rig, 'cmd_stop') as stop, self.assertRaises(ValueError):
            rig.cmd_load_save('steamuser/2')
        stop.assert_not_called()
        self.assertFalse(self.autoexec.exists())

    def transcript(self, slot=1):
        return (f'LoadGame2: "S:\\steamapps\\common\\Anachronox\\anoxdata/save/steamuser/anoxsave{slot}.sav"\n'
                'Parsed and distributed 313 savegame lumps.\nATIME: Timer (1) is being reset.\nLoadGame2: Aborted.')

    def test_transcript_requires_requested_file_and_complete_data_without_errors(self):
        info = rig.save_info('steamuser/1')
        rig.verify_load_transcript(self.transcript(), info)
        rig.verify_load_transcript(self.transcript().replace('/steamuser/', '/steam\nuser/'), info)
        for text in (self.transcript(2), 'old maplights loaded', self.transcript() + '\nERROR: unexpected EOF'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                rig.verify_load_transcript(text, info)

    def test_capture_accepts_only_nonce_bounded_output_and_cleans_dump(self):
        marker = 'ar_123456789abc'
        dump = self.game / 'anoxdata' / (marker + '.txt')
        def execute(d, command):
            dump.write_text('old evidence\n' + marker + '\nnew evidence\n' + marker + '_done\n')
        with patch.object(rig.uuid, 'uuid4', return_value=Mock(hex='123456789abcdef')):
            with patch.object(rig, 'console_line', side_effect=execute):
                self.assertEqual(rig.console_capture(Mock(), 'debug', rig.time.monotonic() + 1), 'new evidence')
        self.assertFalse(dump.exists())

    def test_capture_rejects_stale_transcript(self):
        marker = 'ar_123456789abc'
        dump = self.game / 'anoxdata' / (marker + '.txt')
        with patch.object(rig.uuid, 'uuid4', return_value=Mock(hex='123456789abcdef')):
            with patch.object(rig, 'console_line', side_effect=lambda *args: dump.write_text('old marker\nold data\n')):
                with patch.object(rig.time, 'monotonic', side_effect=[0, 2]), patch.object(rig.time, 'sleep'):
                    with self.assertRaisesRegex(RuntimeError, 'fresh console transcript'):
                        rig.console_capture(Mock(), 'debug', 1)
        self.assertFalse(dump.exists())

    def test_load_save_success_and_failure_restore_debug_and_preserve_save(self):
        before = self.save.read_bytes()
        for status, fails, debug in ((self.transcript(), False, 0), (self.transcript(), False, 1), (self.transcript(2), True, 0)):
            with self.subTest(fails=fails, debug=debug):
                clock = [0]
                def advance(seconds):
                    clock[0] += seconds
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(rig.display, 'Display', return_value=Mock()))
                    for name in ('focus_game', 'console_keys', 'ensure_console', 'grab'):
                        stack.enter_context(patch.object(rig, name, return_value=False))
                    line = stack.enter_context(patch.object(rig, 'console_line'))
                    stack.enter_context(patch.object(rig, 'is_console', return_value=False))
                    stack.enter_context(patch.object(rig, 'visible_content', return_value=True))
                    stack.enter_context(patch.object(rig, 'console_capture', side_effect=[f'"debug" is "{debug}"', status, '(1 2 3) : 4']))
                    stack.enter_context(patch.object(rig.time, 'monotonic', side_effect=lambda: clock[0]))
                    stack.enter_context(patch.object(rig.time, 'sleep', side_effect=advance))
                    out = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                    if fails:
                        with self.assertRaises(RuntimeError):
                            rig.cmd_load_save('steamuser/1', '10')
                        self.assertNotIn('loaded steamuser/1', out.getvalue())
                    else:
                        rig.cmd_load_save('steamuser/1', '10')
                        self.assertIn('viewpos=(1 2 3) yaw=4', out.getvalue())
                    self.assertEqual(line.call_args.args[1], f'toggleconsole;set debug {debug}')
                    self.assertEqual(before, self.save.read_bytes())

    def test_console_detection_handles_translucent_backgrounds(self):
        for background in ('black', (100, 100, 100)):
            im = Image.new('RGB', (640, 400), background)
            for y in range(0, 200, 4):
                for x in range(100):
                    im.putpixel((x, y), (255, 180, 0))
            for y in range(310, 320):
                for x in range(420, 600):
                    im.putpixel((x, y), (255, 180, 0))
            self.assertTrue(rig.is_console(im))
        self.assertFalse(rig.is_console(Image.new('RGB', (640, 400), 'black')))

    def test_console_typing_handles_shift_and_requires_valid_physical_keys(self):
        d = Mock()
        d.get_display_name.return_value = ':7'
        with patch.object(rig.subprocess, 'run', return_value=Mock(
                stdout='<AC01> = 38; <LFSH> = 50;')):
            self.assertEqual(rig.console_keys(d, 'A'), [[50, 38]])
        for mapping in ('<AC01> = 38;', '<AC01> = 0; <LFSH> = 50;'):
            with self.subTest(mapping=mapping), patch.object(rig.subprocess, 'run',
                    return_value=Mock(stdout=mapping)), self.assertRaises(ValueError):
                rig.console_keys(d, 'A')

    def test_console_typing_uses_physical_keys_despite_swedish_symbols(self):
        d = Mock()
        # These Swedish symbols are valid X bindings but wrong for the game.
        stale = {ord('_'): (61, (ord('-'), ord('_'))),
                 ord(';'): (59, (ord(','), ord(';'))),
                 ord('/'): (16, (ord('7'), ord('/'))), 65505: (50, (65505,))}
        d.keysym_to_keycode.side_effect = lambda symbol: stale[symbol][0]
        d.keycode_to_keysym.side_effect = lambda code, level: next(
            values[level] for key, values in stale.values() if key == code)
        d.display.info.min_keycode = 8
        d.display.info.max_keycode = 255
        current = [(0, 0)] * 248
        for code, values in {61: (ord('-'), ord('_')), 59: (ord(','), ord(';')),
                             16: (ord('7'), ord('/')), 50: (65505, 0)}.items():
            current[code - 8] = values
        d.get_keyboard_mapping.return_value = current
        d.get_display_name.return_value = ':7'
        with patch.object(rig.subprocess, 'run', return_value=Mock(
                stdout='<AE11> = 20; <AC10> = 47; <AB10> = 61; <LFSH> = 50;')) as query:
            self.assertEqual(rig.console_keys(d, '_;/'), [[50, 20], [47], [61]])
        self.assertEqual(query.call_args.args[0], ['xkbcomp', '-xkb', ':7', '-'])
        self.assertEqual(query.call_args.kwargs['timeout'], 5)
        d.get_keyboard_mapping.assert_not_called()
        d.keysym_to_keycode.assert_not_called()
        # Key names, not assumed evdev numbers, are the source of the codes.
        with patch.object(rig.subprocess, 'run', return_value=Mock(
                stdout='<AE11> = 120; <LFSH> = 150;')):
            self.assertEqual(rig.console_keys(d, '_'), [[150, 120]])

    def test_unreadable_physical_keymap_prevents_console_input(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired('xkbcomp', 5)):
            with self.subTest(error=error), patch.object(rig.subprocess, 'run', side_effect=error):
                with patch.object(rig, 'press_keys') as press:
                    with self.assertRaisesRegex(RuntimeError, 'physical keymap'):
                        rig.console_line(Mock(), 'echo test')
                    press.assert_not_called()

    def test_interruption_while_enabling_console_registers_rollback_first(self):
        rollback = Mock()
        with patch.object(rig, 'grab'), patch.object(rig, 'is_console', return_value=False):
            with patch.object(rig, 'cmd_key'), patch.object(rig.time, 'sleep'):
                def interrupt(*args):
                    rollback.assert_called_once()
                    raise KeyboardInterrupt
                with patch.object(rig, 'cmd_chord', side_effect=interrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        rig.ensure_console(Mock(), before_enable=rollback)

    def test_slow_console_does_not_toggle_developer_mode(self):
        with patch.object(rig, 'grab'), patch.object(rig, 'is_console', side_effect=[False] * 8 + [True]):
            with patch.object(rig, 'cmd_key') as key, patch.object(rig, 'cmd_chord') as chord, \
                    patch.object(rig.time, 'sleep'):
                self.assertFalse(rig.ensure_console(Mock()))
        key.assert_called_once()
        chord.assert_not_called()

    def test_cleanup_waits_for_game_to_close_console(self):
        clock = [0]
        with patch.object(rig, 'grab'), patch.object(rig, 'is_console', side_effect=[True, True, False]) as console:
            with patch.object(rig.time, 'monotonic', side_effect=lambda: clock[0]):
                with patch.object(rig.time, 'sleep', side_effect=lambda delay: clock.__setitem__(0, clock[0] + delay)):
                    rig.wait_console_closed(Mock())
        self.assertEqual(console.call_count, 3)


if __name__ == '__main__':
    unittest.main()
