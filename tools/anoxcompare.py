#!/usr/bin/env python3
"""Offline, manifest-checked screenshot regression. See docs/screenshot-regression.md."""
import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image


class Invalid(ValueError):
    pass


class Incompatible(ValueError):
    pass


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def sha256(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in '0123456789abcdef' for c in value))


def load_capture(manifest):
    manifest = Path(manifest).resolve(strict=True)
    data = json.loads(manifest.read_text())
    if (not isinstance(data, dict) or type(data.get('schema_version')) is not int
            or data['schema_version'] != 1):
        raise Invalid('schema_version must be 1')
    save = data.get('save', {})
    if not isinstance(save, dict) or any(not isinstance(save.get(k), str) or not save[k]
                                         for k in ('selector', 'map', 'sha256')):
        raise Invalid('save requires selector, map, sha256 strings')
    digest = save['sha256']
    if not sha256(digest):
        raise Invalid('save.sha256 must be lowercase SHA-256 hex')
    pose = data.get('pose', {})
    if (not isinstance(pose, dict) or not isinstance(pose.get('xyz'), list)
            or len(pose['xyz']) != 3 or not all(number(v) for v in pose['xyz'])
            or not number(pose.get('yaw'))):
        raise Invalid('pose requires finite xyz[3] and yaw')
    fingerprints = data.get('fingerprints', {})
    if not isinstance(fingerprints, dict) or any(not sha256(fingerprints.get(k))
                                               for k in ('runtime', 'dll')):
        raise Invalid('fingerprints.runtime and dll must be lowercase SHA-256 hex')
    for key in ('config', 'layers'):
        inventory = fingerprints.get(key)
        if (not isinstance(inventory, dict) or not inventory
                or any(not isinstance(k, str) or not k or not sha256(v)
                       for k, v in inventory.items())):
            raise Invalid(f'fingerprints.{key} must be a nonempty path-to-SHA256 object')
    geometry = data.get('geometry', {})
    if not isinstance(geometry, dict) or any(type(geometry.get(k)) is not int or geometry[k] <= 0
                                           for k in ('width', 'height')):
        raise Invalid('geometry requires positive integer width and height')
    if not number(data.get('settle_seconds')) or data['settle_seconds'] < 0:
        raise Invalid('settle_seconds must be finite and nonnegative')
    if not number(data.get('interval_seconds')) or data['interval_seconds'] <= 0:
        raise Invalid('interval_seconds must be finite and positive')
    images = data.get('images')
    if not isinstance(images, list) or len(images) < 3:
        raise Invalid('images must contain at least three distinct RGB frames')
    frames, paths = [], set()
    for name in images:
        if not isinstance(name, str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
            raise Invalid('image paths must be bounded relative paths without ..')
        path = (manifest.parent / name).resolve(strict=True)
        if not path.is_relative_to(manifest.parent) or path == manifest or path in paths:
            raise Invalid('image paths escape capture directory or repeat a frame')
        paths.add(path)
        with Image.open(path) as frame:
            if frame.mode != 'RGB' or frame.size != (geometry['width'], geometry['height']):
                raise Invalid('every image must be RGB and match manifest geometry')
            frames.append(np.array(frame, dtype=np.float32))
    return data, np.median(np.stack(frames), axis=0), paths, manifest


def compatible(base, candidate, allow_config_change=False, allow_dll_change=False, position_tolerance=2.0, yaw_tolerance=1.0):
    for key in ('save', 'geometry', 'settle_seconds', 'interval_seconds'):
        if base[key] != candidate[key]:
            raise Incompatible(f'{key} differs; comparison refused')
    a, b = dict(base['fingerprints']), dict(candidate['fingerprints'])
    config_changed = a.get('config') != b.get('config')
    dll_changed = a.get('dll') != b.get('dll')
    if allow_dll_change:
        a.pop('dll', None)
        b.pop('dll', None)
    if allow_config_change:
        a.pop('config', None)
        b.pop('config', None)
    if a != b:
        raise Incompatible('fingerprints differ; comparison refused')
    distance = math.dist(base['pose']['xyz'], candidate['pose']['xyz'])
    yaw = abs((base['pose']['yaw'] - candidate['pose']['yaw'] + 180) % 360 - 180)
    if distance > position_tolerance or yaw > yaw_tolerance:
        raise Incompatible(f'pose differs: distance={distance:.4f}, yaw={yaw:.4f}')
    return {'position_distance': distance, 'yaw_distance': yaw,
            'config_mismatch_waived': bool(allow_config_change and config_changed),
            'dll_mismatch_waived': bool(allow_dll_change and dll_changed)}


def box(text):
    try:
        values = tuple(float(v) for v in text.split(','))
        if (len(values) != 4 or not all(math.isfinite(v) and 0 <= v <= 1 for v in values)
                or values[0] >= values[2] or values[1] >= values[3]):
            raise ValueError()
        return values
    except ValueError:
        raise argparse.ArgumentTypeError('box must be normalized x0,y0,x1,y1 with positive area')


def region(shape, roi=None, exclusions=()):
    height, width = shape[:2]
    mask = np.zeros((height, width), dtype=bool)

    def apply(bounds, value):
        x0, y0, x1, y1 = bounds
        mask[math.floor(y0 * height):math.ceil(y1 * height),
             math.floor(x0 * width):math.ceil(x1 * width)] = value

    apply(roi or (0, 0, 1, 1), True)
    for exclusion in exclusions:
        apply(exclusion, False)
    if not mask.any():
        raise Invalid('ROI/exclusions select no pixels')
    return mask


def compare(base_path, candidate_path, out, pixel_threshold=12.0, max_changed_fraction=.02,
            max_mean_error=2.0, metric='max', roi=None, exclusions=(), allow_config_change=False, allow_dll_change=False):
    for value in (pixel_threshold, max_changed_fraction, max_mean_error):
        if not number(value) or value < 0:
            raise Invalid('thresholds must be finite and nonnegative')
    if pixel_threshold >= 255 or max_changed_fraction >= 1 or max_mean_error > 255:
        raise Invalid('thresholds must retain changed-pixel evidence (pixel <255, fraction <1)')
    if metric not in ('max', 'mean'):
        raise Invalid('metric must be max or mean')
    base, a, a_paths, a_manifest = load_capture(base_path)
    candidate, b, b_paths, b_manifest = load_capture(candidate_path)
    pose = compatible(base, candidate, allow_config_change, allow_dll_change)
    out = Path(out).absolute()
    resolved_out = out.resolve()
    # Keep reports outside both immutable input capture trees, including symlinks.
    for manifest in (a_manifest, b_manifest):
        if resolved_out.is_relative_to(manifest.parent) or manifest.is_relative_to(resolved_out):
            raise Invalid('output must be separate from capture directories')
    if out.exists():
        raise Invalid('output directory already exists; refusing overwrite')
    mask = region(a.shape, roi, exclusions)
    delta = np.abs(a - b)
    pixels = delta.max(axis=2) if metric == 'max' else delta.mean(axis=2)
    changed = float(np.mean(pixels[mask] > pixel_threshold))
    mean = float(delta[mask].mean())
    passed = changed <= max_changed_fraction and mean <= max_mean_error
    report = {
        'schema_version': 1, 'result': 'pass' if passed else 'fail',
        'baseline_manifest': str(a_manifest), 'candidate_manifest': str(b_manifest),
        'pose_delta': pose, 'frames': {'baseline': len(a_paths), 'candidate': len(b_paths)},
        'metric': metric, 'changed_fraction': changed, 'mean_absolute_error': mean,
        'selected_pixels': int(mask.sum()), 'roi': roi, 'exclusions': list(exclusions),
        'thresholds': {'pixel': pixel_threshold, 'max_changed_fraction': max_changed_fraction,
                       'max_mean_error': max_mean_error},
        'artifacts': {'comparison': 'side-by-side.png', 'difference': 'diff.png'},
    }
    out.mkdir(parents=True, exist_ok=False)
    Image.fromarray(np.concatenate((a, b), axis=1).astype(np.uint8)).save(out / 'side-by-side.png')
    diff = np.clip(delta * 4, 0, 255).astype(np.uint8)
    diff[~mask] = 0
    Image.fromarray(diff).save(out / 'diff.png')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    command = sub.add_parser('compare')
    command.add_argument('baseline')
    command.add_argument('candidate')
    command.add_argument('--out', required=True)
    command.add_argument('--pixel-threshold', type=float, default=12)
    command.add_argument('--max-changed-fraction', type=float, default=.02)
    command.add_argument('--max-mean-error', type=float, default=2)
    command.add_argument('--metric', choices=('max', 'mean'), default='max')
    command.add_argument('--allow-dll-change', action='store_true',
                         help='diagnostic A/B only: waive DLL fingerprint mismatch')
    command.add_argument('--allow-config-change', action='store_true',
                         help='diagnostic control only: waive config fingerprint mismatch')
    command.add_argument('--roi', type=box)
    command.add_argument('--exclude', type=box, action='append', default=[])
    args = parser.parse_args(argv)
    try:
        report = compare(args.baseline, args.candidate, args.out, args.pixel_threshold,
                         args.max_changed_fraction, args.max_mean_error, args.metric,
                         args.roi, args.exclude, args.allow_config_change, args.allow_dll_change)
    except Incompatible as error:
        print(f'incompatible: {error}', file=sys.stderr)
        return 3
    except (Invalid, OSError, ValueError, TypeError, KeyError) as error:
        print(f'invalid: {error}', file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0 if report['result'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
