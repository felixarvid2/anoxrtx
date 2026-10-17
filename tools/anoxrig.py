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
  anoxrig.py wait-bright [SECS]    wait until the window is not black (menu/level visible)
  anoxrig.py log                   show the interesting Remix / QindieGL log lines
"""
import math, os, re, signal, subprocess, sys, time

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
