"""Synthetic image checks: python -m unittest discover -s tools -p test_anoxcompare.py."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

import anoxcompare as comparator


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {
            'schema_version': 1,
            'save': {'selector': 'steamuser/1', 'map': 'rowdys', 'sha256': 'a' * 64},
            'pose': {'xyz': [1, 2, 3], 'yaw': 359.5},
            'fingerprints': {'runtime': 'b' * 64, 'dll': 'c' * 64,
                             'config': {'rtx.conf': 'd' * 64}, 'layers': {'mod.usda': 'e' * 64}},
            'geometry': {'width': 20, 'height': 10}, 'settle_seconds': 10, 'interval_seconds': 2,
            'images': ['0.png', '1.png', '2.png'],
        }
        self.frame = np.full((10, 20, 3), 100, dtype=np.uint8)

    def capture(self, name, frames=None, mutate=None):
        directory = self.root / name
        directory.mkdir()
        manifest = copy.deepcopy(self.manifest)
        if mutate:
            mutate(manifest)
        for i, frame in enumerate(frames if frames is not None else [self.frame] * 3):
            Image.fromarray(frame).save(directory / f'{i}.png')
        path = directory / 'capture.json'
        path.write_text(json.dumps(manifest))
        return path

    def compare(self, base, candidate, **kwargs):
        return comparator.compare(base, candidate, self.root / 'output', **kwargs)

    def test_temporal_median_and_small_noise_pass(self):
        base = self.capture('base', [self.frame - 3, self.frame, self.frame + 3])
        candidate = self.capture('candidate', [self.frame + 1, self.frame - 1, self.frame + 100])
        report = self.compare(base, candidate)
        self.assertEqual(report['result'], 'pass')
        self.assertEqual(report['mean_absolute_error'], 1)
        self.assertTrue((self.root / 'output' / 'diff.png').exists())

    def test_dark_lighting_loss_fails_and_preserves_baseline(self):
        base = self.capture('base')
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in base.parent.iterdir()}
        candidate = self.capture('candidate', [self.frame // 4] * 3)
        report = self.compare(base, candidate)
        self.assertEqual(report['result'], 'fail')
        self.assertEqual(report['changed_fraction'], 1)
        self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in base.parent.iterdir()})
        with self.assertRaises(comparator.Invalid):
            self.compare(base, candidate)

    def test_mean_error_alone_cannot_hide_local_loss(self):
        changed = self.frame.copy()
        changed[:, :1] = 70  # 5% pixels; mean error 1.5 passes, changed fraction must fail.
        report = self.compare(self.capture('base'), self.capture('candidate', [changed] * 3))
        self.assertEqual(report['result'], 'fail')
        self.assertLess(report['mean_absolute_error'], 2)

    def test_pose_and_environment_incompatible(self):
        base = self.capture('base')
        for i, mutate in enumerate((
            lambda m: m['pose'].update(xyz=[4, 2, 3]),
            lambda m: m['pose'].update(yaw=2),
            lambda m: m['fingerprints'].update(dll='f' * 64),
            lambda m: m['save'].update(map='other'),
            lambda m: m.update(settle_seconds=11),
            lambda m: m.update(interval_seconds=3),
        )):
            candidate = self.capture(f'candidate{i}', mutate=mutate)
            with self.assertRaises(comparator.Incompatible):
                self.compare(base, candidate)
        self.assertFalse((self.root / 'output').exists())

    def test_circular_yaw_passes(self):
        report = self.compare(self.capture('base'), self.capture('candidate', mutate=
                              lambda m: m['pose'].update(yaw=.5)))
        self.assertEqual(report['pose_delta']['yaw_distance'], 1)

    def test_geometry_checks_actual_pixels_and_manifest(self):
        base = self.capture('base')
        candidate = self.capture('candidate', mutate=lambda m: m['geometry'].update(width=19))
        with self.assertRaises(comparator.Invalid):
            self.compare(base, candidate)
        data = json.loads(candidate.read_text())
        data['geometry'] = {'width': 10, 'height': 10}
        candidate.write_text(json.dumps(data))
        for path in candidate.parent.glob('*.png'):
            Image.new('RGB', (10, 10)).save(path)
        with self.assertRaises(comparator.Incompatible):
            self.compare(base, candidate)

    def test_unsafe_references_and_duplicate_frames(self):
        base = self.capture('base')
        for i, names in enumerate((['../outside.png', '1.png', '2.png'],
                                   ['/tmp/outside.png', '1.png', '2.png'],
                                   ['0.png', '0.png', '2.png'], ['0.png', '1.png'])):
            candidate = self.capture(f'candidate{i}', mutate=lambda m: m.update(images=names))
            with self.assertRaises(comparator.Invalid):
                self.compare(base, candidate)
        candidate = self.capture('symlink')
        (candidate.parent / '0.png').unlink()
        (candidate.parent / '0.png').symlink_to(base.parent / '0.png')
        with self.assertRaises(comparator.Invalid):
            self.compare(base, candidate)

    def test_roi_and_exclusion(self):
        changed = self.frame.copy()
        changed[:, 10:] = 0
        base, candidate = self.capture('base'), self.capture('candidate', [changed] * 3)
        report = self.compare(base, candidate, roi=(0, 0, .5, 1))
        self.assertEqual(report['result'], 'pass')
        report = comparator.compare(base, candidate, self.root / 'output2',
                                    exclusions=[(.5, 0, 1, 1)])
        self.assertEqual(report['result'], 'pass')
        with self.assertRaises(comparator.Invalid):
            comparator.compare(base, candidate, self.root / 'output3', exclusions=[(0, 0, 1, 1)])

    def test_config_waiver_is_explicit_and_reported(self):
        base = self.capture('base')
        candidate = self.capture('candidate', mutate=lambda m: m['fingerprints'].update(config={'x': 'f' * 64}))
        with self.assertRaises(comparator.Incompatible):
            self.compare(base, candidate)
        report = self.compare(base, candidate, allow_config_change=True)
        self.assertTrue(report['pose_delta']['config_mismatch_waived'])

    def test_dll_waiver_preserves_other_environment_checks(self):
        base = self.capture('base')
        candidate = self.capture('candidate', mutate=lambda m: m['fingerprints'].update(dll='f' * 64))
        report = self.compare(base, candidate, allow_dll_change=True)
        self.assertTrue(report['pose_delta']['dll_mismatch_waived'])
        data = json.loads(candidate.read_text())
        data['fingerprints']['runtime'] = 'f' * 64
        candidate.write_text(json.dumps(data))
        with self.assertRaises(comparator.Incompatible):
            comparator.compare(base, candidate, self.root / 'output2', allow_dll_change=True)

    def test_interval_must_be_present_positive_finite_number(self):
        base = self.capture('base')
        for i, value in enumerate((None, 0, -1, float('nan'), float('inf'), True, '2')):
            candidate = self.capture(f'candidate{i}', mutate=lambda m: m.update(interval_seconds=value))
            with self.subTest(value=value), self.assertRaises(comparator.Invalid):
                self.compare(base, candidate)
        candidate = self.capture('missing', mutate=lambda m: m.pop('interval_seconds'))
        with self.assertRaises(comparator.Invalid):
            self.compare(base, candidate)

    def test_fingerprint_schema_rejects_untyped_or_invalid_digests(self):
        base = self.capture('base')
        invalid = [('runtime', True), ('dll', ['a' * 64]), ('runtime', 'not-a-hash'),
                   ('config', ['a' * 64]), ('config', {}), ('config', {'x': True}),
                   ('layers', {'': 'a' * 64}), ('layers', {'mod.usda': 'A' * 64})]
        for i, (key, value) in enumerate(invalid):
            with self.subTest(key=key, value=value):
                candidate = self.capture(f'candidate{i}', mutate=
                                         lambda m: m['fingerprints'].update({key: value}))
                with self.assertRaises(comparator.Invalid):
                    self.compare(base, candidate)

    def test_refuses_output_in_capture_and_disabled_fraction_check(self):
        base, candidate = self.capture('base'), self.capture('candidate')
        with self.assertRaises(comparator.Invalid):
            comparator.compare(base, candidate, base.parent / 'output')
        with self.assertRaises(comparator.Invalid):
            self.compare(base, candidate, max_changed_fraction=1)

    def test_cli_exit_codes(self):
        base = self.capture('base')
        candidate = self.capture('candidate', [self.frame // 4] * 3)
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(comparator.main(['compare', str(base), str(candidate),
                                             '--out', str(self.root / 'output')]), 1)
            self.assertEqual(comparator.main(['compare', str(base), str(candidate),
                                             '--out', str(self.root / 'output')]), 2)


if __name__ == '__main__':
    unittest.main()
