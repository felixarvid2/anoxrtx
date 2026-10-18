#!/usr/bin/env python3
"""Load a verified Anachronox save and capture a local regression manifest.

Requires an already running game on the rig's nested display. Does not launch
Steam, change configs, accept baselines, or manage the surrounding test session.
"""
import argparse
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import signal
import time

import anoxrig as rig


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fingerprints():
    game = Path(rig.GAME)
    runtime_files = ['d3d9.dll', '.trex/d3d9.dll', '.trex/NvRemixBridge.exe']
    runtime = {name: digest(game / name) for name in runtime_files}
    configs = ['rtx.conf', 'QindieGL.ini', 'anox_customise.ini', '.trex/bridge.conf']
    # Include per-map source/overrides and all generated mod assets, so changed
    # textures cannot silently compare as the same material environment.
    config_paths = [game / name for name in configs]
    config_paths += sorted((game / 'rtx-remix/maplights').glob('*.lights'))
    config_paths += sorted((game / 'rtx-remix/maplights').glob('*.override'))
    layers = sorted(p for p in (game / 'rtx-remix/mods').rglob('*') if p.is_file())
    if not layers:
        raise ValueError('installed mod inventory is empty; capture refused before save loading')
    return {
        'runtime': hashlib.sha256(json.dumps(runtime, sort_keys=True).encode()).hexdigest(),
        'dll': digest(game / 'opengl32.dll'),
        'config': {str(p.relative_to(game)): digest(p) for p in config_paths},
        'layers': {str(p.relative_to(game)): digest(p) for p in layers},
    }, runtime


def parse_receipt(text):
    matches = re.findall(
        r'^loaded (\S+) map=(\S+) viewpos=\((-?\d+) (-?\d+) (-?\d+)\) '
        r'yaw=(-?\d+) sha256=([a-f0-9]{64})$', text, re.M)
    if len(matches) != 1:
        raise ValueError('capture requires one successful verified load receipt')
    selector, mapname, x, y, z, yaw, sha256 = matches[0]
    return {'selector': selector, 'map': mapname, 'sha256': sha256}, {
        'xyz': [int(x), int(y), int(z)], 'yaw': int(yaw)}


def check_pose(pose, expected):
    if len(expected) != 4 or not all(math.isfinite(v) for v in expected):
        raise ValueError('expected pose must contain four finite values')
    distance = math.dist(pose['xyz'], expected[:3])
    yaw = abs((pose['yaw'] - expected[3] + 180) % 360 - 180)
    if distance > 2 or yaw > 1:
        raise ValueError(f'loaded pose does not match expected view: {pose}')


def validate_capture(settle, interval, frames):
    if not math.isfinite(settle) or settle < 0 or not math.isfinite(interval) or interval <= 0:
        raise ValueError('settle must be nonnegative; interval must be positive and finite')
    if not 3 <= frames <= 30:
        raise ValueError('capture requires 3 to 30 frames')


def capture_frames(out, receipt, expected, settle=8, interval=2, frames=3,
                   pose_source='verified save-load transcript'):
    """Capture a settled sequence after a verified load or controlled reload.

    Controllers using a previous load receipt must independently verify that
    the camera did not move, and record their evidence in pose_source.
    """
    validate_capture(settle, interval, frames)
    save, pose = parse_receipt(receipt)
    check_pose(pose, expected)
    if rig.save_info(save['selector'])['sha256'] != save['sha256']:
        raise ValueError('save fingerprint changed after load')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'load.txt').write_text(receipt)
    before, runtime = fingerprints()
    time.sleep(settle)
    d = rig.display.Display()
    images = []
    geometry = None
    try:
        for index in range(frames):
            if index:
                time.sleep(interval)
            im = rig.grab(d)
            if not rig.visible_content(im) or rig.is_console(im) or rig.is_menu(im):
                raise RuntimeError('capture rejected: scene missing, console or menu visible')
            current = {'width': im.width, 'height': im.height}
            if geometry is not None and current != geometry:
                raise RuntimeError('capture geometry changed during sequence')
            geometry = current
            name = f'frame-{index:02}.png'
            im.save(out / name)
            images.append(name)
    finally:
        d.close()
    after, _ = fingerprints()
    if after != before or rig.save_info(save['selector'])['sha256'] != save['sha256']:
        raise RuntimeError('capture rejected: settings/assets/save changed during sequence')
    for source in [Path(rig.GAME) / 'QindieGL.log',
                   Path(rig.LOGS) / 'remix-dxvk.log', Path(rig.LOGS) / 'bridge32.log']:
        if source.is_file():
            shutil.copy2(source, out / source.name)
    manifest = {'schema_version': 1, 'save': save, 'pose': pose,
                'pose_source': pose_source, 'fingerprints': before,
                'runtime_files': runtime, 'geometry': geometry,
                'settle_seconds': settle, 'interval_seconds': interval,
                'images': images, 'captured_at_unix': time.time()}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', required=True, help='existing PROFILE/SLOT selector')
    parser.add_argument('--expected-pose', nargs=4, type=float, required=True,
                        metavar=('X', 'Y', 'Z', 'YAW'))
    parser.add_argument('--out', required=True, type=Path, help='new local output directory')
    parser.add_argument('--settle', type=float, default=8)
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--frames', type=int, default=3)
    parser.add_argument('--timeout', default='120', help='rig save-load waiting budget')
    args = parser.parse_args()
    try:
        if args.out.exists():
            raise ValueError('output already exists; captures are never overwritten')
        if not all(math.isfinite(v) for v in args.expected_pose):
            raise ValueError('expected pose must be finite')
        validate_capture(args.settle, args.interval, args.frames)
        rig.seconds(args.timeout)
        before_load, _ = fingerprints()
        text = io.StringIO()
        try:
            with contextlib.redirect_stdout(text):
                rig.cmd_load_save(args.save, args.timeout)
        except BaseException:
            print(text.getvalue(), end='')
            raise
        receipt = text.getvalue()
        print(receipt, end='', flush=True)
        if fingerprints()[0] != before_load:
            raise RuntimeError('installed environment changed while loading; capture refused')
        manifest = capture_frames(args.out, receipt, args.expected_pose,
                                  args.settle, args.interval, args.frames)
        print(args.out / 'manifest.json', manifest['geometry'])
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    main()
