#!/usr/bin/env python3
"""Test rig for Anachronox + RTX Remix on Linux (Steam/Proton).

Runs against an X display (default :7, a nested `Xwayland :7 -geometry 1920x1200 -decorate`; put
`DISPLAY=:7` in the game's Steam launch options). Needs python-xlib and Pillow.

  anoxrig.py start [SECS]          launch via Steam, wait for visible content (default 180 s)
  anoxrig.py stop                  kill the game (and the Remix bridge server)
  anoxrig.py shot NAME             save the game window to shots/NAME.png, print brightness
  anoxrig.py click FX FY           left click at a fraction of the game window (0..1)
  anoxrig.py move DX DY [STEPS]    relative mouse motion (menu cursor moves by deltas)
  anoxrig.py press                 left button press/release at the current position
  anoxrig.py to-rowdys             fresh start -> New Universe -> skip cutscenes (about 4 min)
  anoxrig.py timeline PFX T...     fresh start -> New Universe, shots at T seconds (deterministic scenes)
  anoxrig.py chord K1 K2 ...        hold keys together (e.g. Control_L Shift_L q = Remix capture)
  anoxrig.py key NAME [NAME...]    press keys (X keysym names: Return, Escape, F1, a, ...)
  anoxrig.py hold SECS KEY...      focus game and hold keys for movement (e.g. hold 2 w)
  anoxrig.py list-saves            list local PROFILE/SLOT selectors and saved maps
  anoxrig.py load-save SAVE [SECS] restore PROFILE/SLOT through the game console
  anoxrig.py wait-bright [SECS]    wait until the window is not black (menu/level visible)
  anoxrig.py log                   show the interesting Remix / QindieGL log lines
"""
import gzip, hashlib, math, os, re, signal, struct, subprocess, sys, time, uuid, zlib
from pathlib import Path

GAME = os.path.expanduser('~/.steam/debian-installation/steamapps/common/Anachronox')
LOGS = os.path.join(GAME, 'rtx-remix', 'logs')
SHOTS = os.environ.get('ANOX_SHOTS', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shots'))
os.environ['DISPLAY'] = os.environ.get('ANOX_DISPLAY', ':7')

from Xlib import display, X, XK
from Xlib.ext import xtest


def pids(pattern):
    out = subprocess.run(['pgrep', '-f', pattern], capture_output=True, text=True).stdout.split()
    return [int(p) for p in out if int(p) != os.getpid()]


def game_window(d):
    def find(w):
        for c in w.query_tree().children:
            try:
                if c.get_wm_name() == 'Anachronox' and c.get_attributes().map_state == X.IsViewable:
                    return c
            except Exception:
                pass
            f = find(c)
            if f:
                return f
        return None
    return find(d.screen().root)


def grab(d):
    from PIL import Image
    w = game_window(d)
    if not w:
        return None
    # read what is on screen (root window, cropped to the game window): reading the game window itself can
    # return black when the Remix bridge presents through another X window
    g = w.get_geometry(); root = d.screen().root
    t = w.translate_coords(root, 0, 0)
    x, y = max(0, -t.x), max(0, -t.y)
    sw, sh = d.screen().width_in_pixels, d.screen().height_in_pixels
    ww, hh = min(g.width, sw - x), min(g.height, sh - y)
    raw = root.get_image(x, y, ww, hh, X.ZPixmap, 0xffffffff)
    return Image.frombytes('RGB', (ww, hh), raw.data, 'raw', 'BGRX')


def brightness(im):
    px = list(im.resize((64, 40)).getdata())
    return [sum(p[k] for p in px) // len(px) for k in range(3)], max(max(p) for p in px)


def is_menu(im):
    """the Fatima menu is mostly dark teal: avg around (11..14, 26..30, 26..30)"""
    if im is None:
        return False
    (r, g, b), _ = brightness(im)
    return r < 18 and 22 <= g <= 34 and 22 <= b <= 34


def seconds(value, maximum=None):
    result = float(value)
    if not math.isfinite(result) or result <= 0 or (maximum is not None and result > maximum):
        raise ValueError('duration must be positive and finite' + (f' (at most {maximum} seconds)' if maximum else ''))
    return result


def read_log(path):
    try:
        with open(path, errors='replace') as f:
            return f.read()
    except OSError:
        return ''


def visible_content(im):
    """Reject missing/black/flat white windows; this is not a gameplay/camera check."""
    if im is None:
        return False
    extrema = im.resize((64, 40)).getextrema()
    return max(high for low, high in extrema) > 60 and max(high - low for low, high in extrema) > 8


def cmd_start(timeout='180'):
    limit = seconds(timeout)
    log = os.path.join(LOGS, 'remix-dxvk.log')
    previous = read_log(log)  # preserve diagnostics; ignore messages from earlier runs
    d = display.Display()
    try:
        if game_window(d) is None:
            subprocess.Popen(['steam', 'steam://rungameid/242940'], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, cwd=os.path.expanduser('~'), start_new_session=True)
        end = time.monotonic() + limit
        visible_since = None
        camera_seen = False
        state = 'no game window on ' + os.environ['DISPLAY']
        while time.monotonic() < end:
            current = read_log(log)
            fresh = current[len(previous):] if current.startswith(previous) else current
            previous = current
            camera_seen |= 'Camera cut' in fresh
            w = game_window(d)
            if w is not None:
                w.set_input_focus(X.RevertToParent, X.CurrentTime)
                d.sync()
                if visible_content(grab(d)):
                    if visible_since is None:
                        visible_since = time.monotonic()
                    if time.monotonic() - visible_since >= 1:
                        status = 'remix camera found' if camera_seen else 'camera unconfirmed'
                        print(f'game window ready: visible content; {status}')
                        return
                else:
                    visible_since = None
                state = 'game window found, but no stable visible content (try key Escape for a black intro)'
            else:
                visible_since = None
                state = 'no game window on ' + os.environ['DISPLAY']
            time.sleep(0.5)
        raise RuntimeError(f'start timeout after {limit:g}s: {state}; inspect logs with anoxrig.py log')
    finally:
        d.close()


def cmd_stop():
    """kill the game and the Remix bridge server and wait until they are really gone"""
    for sig, wait in ((15, 30), (9, 10)):
        for p in pids(r'[S]:.steamapps.common.Anachronox'):
            try:
                os.kill(p, sig)
            except ProcessLookupError:
                pass
        end = time.time() + wait
        while time.time() < end and pids(r'[S]:.steamapps.common.Anachronox'):
            time.sleep(1)
        if not pids(r'[S]:.steamapps.common.Anachronox'):
            break
    time.sleep(3)


def cmd_shot(name):
    d = display.Display()
    im = grab(d)
    if im is None:
        print('no game window'); return
    os.makedirs(SHOTS, exist_ok=True)
    path = os.path.join(SHOTS, name + '.png')
    im.resize((960, int(960 * im.height / im.width))).save(path)
    avg, mx = brightness(im)
    print(path, 'avg', avg, 'max', mx)


def cmd_click(fx, fy):
    d = display.Display()
    w = game_window(d)
    g = w.get_geometry(); t = w.translate_coords(d.screen().root, 0, 0)
    x, y = int(-t.x + float(fx) * g.width), int(-t.y + float(fy) * g.height)
    xtest.fake_input(d, X.MotionNotify, x=x, y=y); d.sync(); time.sleep(0.25)
    xtest.fake_input(d, X.ButtonPress, 1); d.sync(); time.sleep(0.08)
    xtest.fake_input(d, X.ButtonRelease, 1); d.sync()
    print('click', x, y)


def cmd_move(dx, dy, steps='20'):
    """relative pointer motion in small steps (the game reads deltas, Quake 2 style)"""
    d = display.Display()
    d.change_pointer_control(accel=(1, 1), threshold=0)   # no acceleration: deltas must be exact
    n = int(steps); dx, dy = float(dx) / n, float(dy) / n
    ax = ay = 0.0
    for _ in range(n):
        ax += dx; ay += dy
        ix, iy = int(round(ax)), int(round(ay)); ax -= ix; ay -= iy
        xtest.fake_input(d, X.MotionNotify, detail=1, x=ix, y=iy); d.sync(); time.sleep(0.03)
    print('moved')


def cmd_press():
    d = display.Display()
    xtest.fake_input(d, X.ButtonPress, 1); d.sync(); time.sleep(0.08)
    xtest.fake_input(d, X.ButtonRelease, 1); d.sync()
    print('pressed')


def cmd_to_rowdys():
    """from a fresh start: skip the intro, New Universe, skip the opening cutscenes -> Boots in Rowdy's bar"""
    wait_menu()                                                       # intro -> main menu
    cmd_move(-3000, -3000, 60); cmd_move(268, 139, 30); cmd_press()   # New Universe (game coords 268,139)
    time.sleep(3)
    cmd_move(0, 13, 5); cmd_press()                                  # difficulty: Normal (game coords 268,152)
    time.sleep(15)
    for _ in range(25):                     # skip cinematics; Esc does nothing in gameplay
        cmd_key('Escape'); time.sleep(8)
    time.sleep(10)
    print('should be in Rowdy\'s now')


def wait_menu(limit=180):
    """press Esc every few seconds until the main (Fatima) menu is on screen; intro length varies"""
    d = display.Display()
    end = time.time() + limit
    while time.time() < end:
        cmd_key('Escape')                   # Esc toggles the menu, and it fades in over a few seconds
        for _ in range(15):
            time.sleep(1)
            if is_menu(grab(d)):
                time.sleep(2); return True
    print('main menu not found'); return False


def cmd_timeline(prefix, *times):
    """fresh start -> New Universe/Normal, no skipping; shots at fixed seconds after the difficulty click"""
    wait_menu()
    d = display.Display()
    for attempt in range(4):                # the menu may not take input yet (slow texture loading)
        time.sleep(4 + 4 * attempt)
        from PIL import ImageChops, ImageStat
        before = grab(d)
        cmd_move(-3000, -3000, 60); cmd_move(268, 139, 30); cmd_press()
        changed = False
        for _ in range(20):                 # the difficulty panel fades in; wait up to 10 s for a change
            time.sleep(0.5)
            after = grab(d)
            diff = sum(ImageStat.Stat(ImageChops.difference(before.resize((160, 100)), after.resize((160, 100)))).mean) / 3
            if diff > 2.0:
                changed = True; break
        if changed:
            time.sleep(2)
            break
        print('New Universe click not taken, retrying')
    cmd_move(0, 13, 5); cmd_press()
    t0 = time.time()
    for t in times:
        time.sleep(max(0, t0 + float(t) - time.time()))
        cmd_shot('%s-%03d' % (prefix, int(float(t))))


def focus_game(d):
    w = game_window(d)
    if w is None:
        raise RuntimeError('no game window on ' + os.environ['DISPLAY'])
    w.set_input_focus(X.RevertToParent, X.CurrentTime)
    d.sync()
    return w


def keycodes(d, names):
    if not names:
        raise ValueError('at least one key is required')
    codes = []
    for name in names:
        code = int(name[2:]) if name.startswith('kc') else d.keysym_to_keycode(XK.string_to_keysym(name))
        if not 8 <= code <= 255:
            raise ValueError('unknown or invalid key: ' + name)
        if code not in codes:
            codes.append(code)
    return codes


def press_keys(d, codes, duration):
    pressed = []
    try:
        for code in codes:
            xtest.fake_input(d, X.KeyPress, code)
            pressed.append(code)
            d.sync()
        time.sleep(duration)
    finally:
        for code in reversed(pressed):
            xtest.fake_input(d, X.KeyRelease, code)
        d.sync()


def cmd_hold(duration, *names):
    """Hold keys with game focus; always release them, including on interruption."""
    limit = seconds(duration, maximum=60)
    d = display.Display()
    try:
        codes = keycodes(d, names)  # validate the whole chord before sending anything
        focus_game(d)
        press_keys(d, codes, limit)
        print('held', '+'.join(names), 'for', f'{limit:g}s')
    finally:
        d.close()


def cmd_chord(*names):
    """Hold several keys together; ANOX_HOLD preserves the existing duration override."""
    cmd_hold(os.environ.get('ANOX_HOLD', '0.3'), *names)


def cmd_sendkey(*names):
    """like chord, but XSendEvent straight to the game window (focus-independent)"""
    from Xlib.protocol import event
    d = display.Display(); w = game_window(d); root = d.screen().root
    codes = [d.keysym_to_keycode(XK.string_to_keysym(n)) for n in names]
    state = 0
    for etype in (X.KeyPress, X.KeyRelease):
        seq = codes if etype == X.KeyPress else list(reversed(codes))
        for c in seq:
            ev = (event.KeyPress if etype == X.KeyPress else event.KeyRelease)(
                time=X.CurrentTime, root=root, window=w, same_screen=1, child=X.NONE,
                root_x=0, root_y=0, event_x=0, event_y=0, state=state, detail=c)
            w.send_event(ev, propagate=True); d.sync(); time.sleep(0.2)
    print('sendkey', '+'.join(names))


def cmd_key(*names):
    d = display.Display()
    try:
        codes = [keycodes(d, (name,))[0] for name in names]
        if not codes:
            raise ValueError('at least one key is required')
        focus_game(d)
        for code in codes:
            press_keys(d, [code], 0.08)
            time.sleep(0.3)
        print('keys', ' '.join(names))
    finally:
        d.close()


def save_info(selector):
    match = re.fullmatch(r'([A-Za-z0-9_-]+)/([0-9]{1,9})', selector)
    if not match:
        raise ValueError('save must be PROFILE/SLOT (for example steamuser/1)')
    profile, slot = match.groups()
    slot = int(slot)
    root = Path(GAME) / 'anoxdata/SAVE'
    path = root / profile / f'anoxsave{slot}.sav'
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('save must stay inside anoxdata/SAVE')
    if not path.is_file():
        raise ValueError(f'save not found: {profile}/{slot}; use list-saves')
    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError('save is too large to inspect safely')
        packed = path.read_bytes()
        with gzip.open(path, 'rb') as f:
            header = f.read(65536)  # enough for the description and current-map field, not all game state
        if len(header) < 24 or struct.unpack_from('<I', header)[0] != 1004:
            raise ValueError('unsupported save header')
        length = struct.unpack_from('<I', header, 20)[0]
        if not 1 <= length <= 4096 or 24 + length > len(header):
            raise ValueError('invalid save description')
        description = header[24:24 + length].rstrip(b'\0').decode('cp1252', errors='replace')
        map_match = re.search(rb'maps/([A-Za-z0-9_-]+)\.bsp\x00', header, re.I)
        if not map_match:
            raise ValueError('current map not found in save header')
    except (OSError, EOFError, struct.error, zlib.error) as error:
        raise ValueError(f'cannot inspect save {profile}/{slot}: {error}') from error
    return {'save': f'{profile}/{slot}', 'map': map_match[1].decode('ascii').lower(),
            'description': ' / '.join(description.splitlines()), 'sha256': hashlib.sha256(packed).hexdigest()}


def cmd_list_saves():
    root = Path(GAME) / 'anoxdata/SAVE'
    found = False
    for path in sorted(root.glob('*/anoxsave*.sav')):
        match = re.fullmatch(r'anoxsave([0-9]+)\.sav', path.name)
        if not match:
            continue
        try:
            info = save_info(f'{path.parent.name}/{match[1]}')
        except ValueError as error:
            print(error, file=sys.stderr)
            continue
        print(f"{info['save']}\t{info['map']}\t{info['description']}\tsha256={info['sha256']}")
        found = True
    if not found:
        raise RuntimeError('no readable saves found in ' + str(root))


def is_console(im):
    """Recognize gold console text and its build/version footer, including translucent panels."""
    if im is None:
        return False
    sample = im.resize((640, 400))
    def gold_fraction(box):
        region = sample.crop(box)
        pixels = list(region.get_flattened_data() if hasattr(region, 'get_flattened_data') else region.getdata())
        return sum(r > 60 and g > 25 and r > g * 1.1 and b < g * 0.4 for r, g, b in pixels) / len(pixels)
    return gold_fraction((0, 0, 640, 200)) > 0.01 and gold_fraction((400, 308, 640, 324)) > 0.015


def ensure_console(d, before_enable=None):
    """Return whether we enabled developer mode, so the caller can turn it back off."""
    if is_console(grab(d)):
        return False
    toggle = os.environ.get('ANOX_CONSOLE_KEY', 'kc49')
    cmd_key(toggle)
    time.sleep(0.5)
    if is_console(grab(d)):
        return False
    if before_enable is not None:
        before_enable()  # register rollback before the first key can change developer mode
    cmd_chord('Alt_L', 'Shift_L', 'F10')  # game's built-in developer-mode toggle
    cmd_key(toggle)
    time.sleep(0.5)
    if is_console(grab(d)):
        return True
    cmd_chord('Alt_L', 'Shift_L', 'F10')
    raise RuntimeError('developer console not recognized; no load command sent (check ANOX_CONSOLE_KEY)')


def console_keys(d, text):
    """Validate text and keyboard levels before editing the current console line."""
    result = []
    for char in text:
        symbol = ord(char)
        code = d.keysym_to_keycode(symbol)
        if not 32 <= symbol <= 126 or not 8 <= code <= 255:
            raise ValueError('cannot type save selector with the current keyboard layout')
        if d.keycode_to_keysym(code, 0) == symbol:
            result.append([code])
        elif d.keycode_to_keysym(code, 1) == symbol:
            result.append(keycodes(d, ('Shift_L',)) + [code])
        else:
            raise ValueError('save selector needs an unsupported keyboard group')
    return result


def console_line(d, text):
    typed = console_keys(d, text)
    if len(text) > 240:
        raise ValueError('console command is too long')
    press_keys(d, keycodes(d, ('End',)), 0)
    backspace = keycodes(d, ('BackSpace',))
    for _ in range(1024):
        press_keys(d, backspace, 0)
    for codes in typed:
        press_keys(d, codes, 0.03)
        time.sleep(0.02)
    press_keys(d, keycodes(d, ('Return',)), 0.08)


def console_capture(d, commands, deadline):
    """Read a nonce-bounded transcript, never a previous run's output."""
    marker = 'ar_' + uuid.uuid4().hex[:12]
    path = Path(GAME) / 'anoxdata' / (marker + '.txt')
    if path.exists():
        raise RuntimeError('console transcript path already exists')
    try:
        console_line(d, f'echo {marker};{commands};echo {marker}_done;condump {marker}.txt')
        while time.monotonic() < deadline:
            if path.is_file() and path.stat().st_size <= 2 * 1024 * 1024:
                lines = path.read_text(errors='replace').splitlines()
                lines = [line.strip() for line in lines]
                if marker in lines and marker + '_done' in lines:
                    start, end = lines.index(marker), lines.index(marker + '_done')
                    if start < end:
                        return '\n'.join(lines[start + 1:end])
            time.sleep(0.1)
        raise RuntimeError('timed out waiting for a fresh console transcript; no save load confirmed')
    finally:
        path.unlink(missing_ok=True)


def verify_load_transcript(text, info):
    # Console rows can wrap the absolute path. Normalize separators and join rows.
    flat = re.sub(r'/+', '/', ''.join(text.splitlines()).replace('\\', '/')).lower()
    profile, slot = info['save'].split('/')
    expected = f'/save/{profile}/anoxsave{slot}.sav"'.lower()
    if re.search(r'error:|loadgame error|gzopen failed|invalid header|unexpected.*eof|checksum failed', text, re.I):
        raise RuntimeError('game reported a load/read error; save not confirmed')
    if expected not in flat or not re.search(r'Parsed and distributed [1-9][0-9]* savegame lumps', text):
        raise RuntimeError('console did not confirm the requested save and restored game data')
    # This build's LoadGame2 success flag is never assigned: it prints "Aborted"
    # even after the restore path. Do not confuse that broken status with read errors.


def wait_console_closed(d):
    # XSync only flushes the input; the game still needs a frame to execute it.
    end = time.monotonic() + 5
    time.sleep(0.1)
    while time.monotonic() < end:
        if not is_console(grab(d)):
            return
        time.sleep(0.1)
    raise RuntimeError('console did not close; developer-mode restoration needs inspection')


def cmd_load_save(selector, timeout='120'):
    info = save_info(selector)
    limit = seconds(timeout)
    deadline = time.monotonic() + limit
    d = display.Display()
    original_debug = None
    enabled = False
    def remember_disabled():
        nonlocal original_debug
        original_debug = 0
    try:
        focus_game(d)
        console_keys(d, 'loadgame ' + info['save'])  # validate the layout before changing UI state
        enabled = ensure_console(d, before_enable=remember_disabled)
        if enabled:
            original_debug = 0
        query = console_capture(d, 'debug', deadline)
        debug = re.search(r'"debug" is "([01])"', query)
        if not debug:
            raise RuntimeError('cannot determine developer-mode state; no load command sent')
        if not enabled:
            original_debug = int(debug[1])
        transcript = console_capture(d, 'set debug 1;loadgame ' + info['save'], deadline)
        verify_load_transcript(transcript, info)
        # Same-map loads leave the console open; the saved camera settles only
        # after the scene draws again. Close it before waiting or recording viewpos.
        if is_console(grab(d)):
            cmd_key(os.environ.get('ANOX_CONSOLE_KEY', 'kc49'))
        visible_since = None
        while time.monotonic() < deadline:
            im = grab(d)
            if visible_content(im) and not is_console(im):
                if visible_since is None:
                    visible_since = time.monotonic()
                if time.monotonic() - visible_since >= 2:
                    break
            else:
                visible_since = None
            time.sleep(0.5)
        else:
            raise RuntimeError('save restore reported, but no stable visible scene appeared')
        ensure_console(d)
        view = console_capture(d, 'viewpos', deadline)
        pose = re.search(r'\((-?[0-9]+) (-?[0-9]+) (-?[0-9]+)\)\s*:\s*(-?[0-9]+)', view)
        if not pose:
            raise RuntimeError('restored scene has no confirmed camera position')
        if save_info(selector)['sha256'] != info['sha256']:
            raise RuntimeError('save changed during loading; capture is not reproducible')
    finally:
        try:
            if original_debug is not None:
                ensure_console(d)
                console_line(d, f'toggleconsole;set debug {original_debug}')
                wait_console_closed(d)
            elif enabled:
                if is_console(grab(d)):
                    cmd_key(os.environ.get('ANOX_CONSOLE_KEY', 'kc49'))
                cmd_chord('Alt_L', 'Shift_L', 'F10')
        finally:
            d.close()
    print(f"loaded {info['save']} map={info['map']} viewpos=({' '.join(pose.groups()[:3])}) yaw={pose[4]} sha256={info['sha256']}")


def cmd_wait_bright(secs='90'):
    d = display.Display()
    end = time.time() + float(secs)
    while time.time() < end:
        im = grab(d)
        if im is not None and brightness(im)[1] > 60:
            print('bright after', int(float(secs) - (end - time.time())), 's'); return
        time.sleep(2)
    print('still dark')


def cmd_log():
    pat = re.compile(r'err:|Camera cut|rejected|Window|BorderlessFullscreen|Hookinit: failed|Failed', re.I)
    for f in [os.path.join(LOGS, 'remix-dxvk.log'), os.path.join(LOGS, 'bridge32.log'), os.path.join(GAME, 'QindieGL.log')]:
        if not os.path.exists(f):
            continue
        lines = [l.rstrip() for l in open(f, errors='replace') if pat.search(l) and 'DLSS Message' not in l]
        print('==', os.path.basename(f))
        for l in lines[-12:]:
            print('  ', l[:160])


if __name__ == '__main__':
    # Let finally blocks release synthetic keys when a test controller stops us.
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    fn = globals().get('cmd_' + sys.argv[1].replace('-', '_'))
    if not fn:
        print(__doc__); sys.exit(1)
    try:
        fn(*sys.argv[2:])
    except KeyboardInterrupt:
        sys.exit(130)
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
