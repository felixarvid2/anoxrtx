import importlib.util, os, struct, tempfile, unittest

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('pbr_classify', os.path.join(here, 'pbr_classify.py'))
pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
RULES = pc.load_rules()


def bsp(texinfo, faces, brushes=()):
    """minimal IBSP: texinfo [(name, flags, next)], faces [texinfo index], brushes [(contents, [texinfo])]"""
    lumps = [b''] * 19
    lumps[5] = b''.join(struct.pack('<8fii32si', *([0.0] * 8), f, 0, n.encode(), nx) for n, f, nx in texinfo)
    lumps[6] = b''.join(struct.pack('<HHiHHBBBBi', 0, 0, 0, 3, t, 0, 255, 255, 255, 0) for t in faces)
    sides, br = [], []
    for cont, tis in brushes:
        br.append(struct.pack('<iii', len(sides), len(tis), cont)); sides += tis
    lumps[14] = b''.join(br)
    lumps[15] = b''.join(struct.pack('<Hh', 0, t) for t in sides)
    off = 8 + 19 * 8; head = b'IBSP' + struct.pack('<i', 38); body = b''
    for l in lumps:
        head += struct.pack('<ii', off + len(body), len(l)); body += l
    return head + body


def use(faces=10, flags=0, light=0, trans=0, contents=0, maps=1):
    return {'faces': faces, 'maps': maps, 'flags': flags, 'light': light, 'trans': trans, 'contents': contents,
            'frame_of': ''}


class MatchTest(unittest.TestCase):
    def test_confidence_by_position(self):
        self.assertEqual(pc.match('pipewall', 'pipe'), 'high')
        self.assertEqual(pc.match('tpipewall', 'pipe'), 'medium')
        self.assertEqual(pc.match('wall_pipe', 'pipe'), 'high')
        self.assertEqual(pc.match('swindoor', 'win'), 'low')
        self.assertEqual(pc.match('mwin', 'win'), 'medium')
        self.assertIsNone(pc.match('wall01', 'pipe'))

    def test_weak_match_only_counts_in_legacy_rules(self):
        # "lit" (light rule, not legacy) buried in "military" is ignored; "bar" (legacy wood rule) still applies
        r = pc.classify('baltown/military-01', use(), RULES)
        self.assertEqual(r['class'], 'default')
        self.assertTrue(any(n.startswith('weak match "lit"') for n in r['notes']))
        self.assertEqual(pc.classify('limbus/fbarrel1', use(), RULES)['class'], 'wood')

    def test_legacy_values_kept(self):
        for name, rough, metal in (('a/metlwall', 0.45, 0.6), ('a/glass1', 0.25, 0.0), ('a/door2', 0.5, 0.3),
                                   ('a/redcarpet', 0.95, 0.0), ('a/rockwall', 0.85, 0.0), ('a/monitor', 0.2, 0.0),
                                   ('a/marble', 0.3, 0.0), ('a/crate', 0.6, 0.0), ('a/xyz01', 0.7, 0.0)):
            r = pc.classify(name, use(), RULES)
            self.assertEqual((r['roughness'], r['metallic']), (rough, metal), name)


class PriorityTest(unittest.TestCase):
    def setUp(self):
        self.rules = dict(RULES, exceptions={'a/pipeglass': {'class': 'glass', 'why': 'test'}})

    def test_exception_beats_everything(self):
        r = pc.classify('a/pipeglass', use(), self.rules, jev={'a/pipeglass': {'material': 'metal', 'roughness': 0.5,
                                                                                'metal': 0.9, 'material_conf': 1}})
        self.assertEqual((r['class'], r['source']), ('glass', 'exception'))

    def test_sky_and_liquid_skipped(self):
        self.assertEqual(pc.classify('a/metal', use(flags=pc.SURF['SKY']), RULES)['class'], 'skip')
        self.assertEqual(pc.classify('a/water', use(flags=pc.SURF['WARP']), RULES)['class'], 'skip')
        self.assertEqual(pc.classify('sunder/sun_glass3', use(flags=pc.SURF['TRANS33']), RULES)['source'], 'haze_glass')

    def test_translucent_glass_needs_flag_and_word(self):
        self.assertTrue(pc.classify('a/glass1', use(flags=pc.SURF['TRANS33'], trans=10), RULES)['translucent'])
        self.assertFalse(pc.classify('a/glass1', use(), RULES)['translucent'])
        r = pc.classify('a/haze', use(flags=pc.SURF['TRANS66'], trans=10), RULES)
        self.assertFalse(r['translucent'])
        self.assertIn('translucent faces, not named glass (stays opaque)', r['notes'])

    def test_jev_values_and_conflict(self):
        jev = {'a/rockwall': {'material': 'metal', 'roughness': 0.02, 'metal': 0.7, 'material_conf': 1.0}}
        r = pc.classify('a/rockwall', use(), RULES, jev)
        self.assertEqual((r['source'], r['roughness'], r['metallic']), ('jev', 0.05, 0.7))
        self.assertTrue(r['conflict'])
        self.assertTrue(pc.uncertain(r))

    def test_rule_and_model_outvote_jev(self):
        jev = {'a/rockwall': {'material': 'metal', 'roughness': 0.5, 'metal': 0.1, 'material_conf': 1.0}}
        ai = {'a/rockwall': {'class': 'stone', 'confidence': 'high'}}
        r = pc.classify('a/rockwall', use(), RULES, jev, ai)
        self.assertEqual((r['class'], r['source'], r['roughness']), ('stone', 'rule+model', 0.85))

    def test_light_flags_then_model_then_default(self):
        r = pc.classify('a/xyz', use(faces=10, flags=pc.SURF['LIGHT'], light=8), RULES)
        self.assertEqual((r['class'], r['source']), ('light', 'flags'))
        ai = {'a/xyz': {'class': 'metal', 'confidence': 'high'}}
        r = pc.classify('a/xyz', use(), RULES, ai=ai)
        self.assertEqual((r['class'], r['source'], r['confidence']), ('metal', 'deepseek', 'medium'))
        r = pc.classify('a/xyz', use(), RULES, ai={'a/xyz': {'class': 'plastic', 'confidence': 'high'}})
        self.assertEqual(r['class'], 'default')
        r = pc.classify('a/rockwall', use(), RULES, ai={'a/rockwall': {'class': 'default', 'confidence': 'low'}})
        self.assertEqual((r['class'], r['confidence']), ('stone', 'high'))
        self.assertIn('model: no evidence', r['notes'])

    def test_validate_keeps_allowed_classes(self):
        got = {'a/x': {'class': 'Metal', 'confidence': 'HIGH', 'why': 'w'}, 'a/y': {'class': 'plastic'},
               'a/z': 'stone', 'b/unasked': {'class': 'wood'}}
        self.assertEqual(pc.validate(got, ['a/x', 'a/y', 'a/z'], RULES['classes']),
                         {'a/x': {'class': 'metal', 'confidence': 'high', 'why': 'w'}})


class UsageTest(unittest.TestCase):
    def test_faces_flags_frames_and_contents(self):
        data = bsp([('a/+0blink', 0x1, 1), ('a/+1blink', 0x1, 0), ('a/wall', 0, -1), ('a/pool', 0, -1)],
                   [0, 0, 2, 2, 2], [(0x20, [3]), (0x1, [2])])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'm1.bsp')
            with open(p, 'wb') as f:
                f.write(data)
            u = pc.usage([p, p])
        self.assertEqual((u['a/wall']['faces'], u['a/wall']['maps']), (6, 1))
        self.assertEqual((u['a/+0blink']['faces'], u['a/+0blink']['light']), (4, 4))
        self.assertEqual(u['a/+1blink']['frame_of'], 'a/+0blink')
        self.assertEqual(u['a/+0blink']['frame_of'], '')
        self.assertEqual(u['a/pool']['contents'], 0x20)
        self.assertIn('on liquid brushes without SURF_WARP', pc.classify('a/pool', u['a/pool'], RULES)['notes'])

    def test_report_lists_uncertain(self):
        res = {n: pc.classify(n, use(), RULES) for n in ('a/xyz', 'a/metlwall')}
        text = pc.report(res)
        self.assertIn('## Unclassified (1)', text)
        self.assertIn('| a/xyz | default |', text)


if __name__ == '__main__':
    unittest.main()
