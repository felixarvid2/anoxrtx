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

    def test_exception_settles_conflicts_and_keeps_jev_values(self):
        rules = dict(RULES, exceptions={'a/pipe_glass': {'class': 'metal', 'why': 'test'},
                                        'a/rockwall': {'class': 'wood', 'why': 'test'}})
        jev = {n: {'material': 'metal', 'roughness': 0.02, 'metal': 0.8, 'material_conf': 1} for n in
               ('a/pipe_glass', 'a/rockwall')}
        self.assertTrue(pc.classify('a/pipe_glass', use(), RULES)['conflict'])          # metal vs glass rule
        r = pc.classify('a/pipe_glass', use(), rules, jev)                              # confirms Jev: Jev's values
        self.assertEqual((r['class'], r['roughness'], r['metallic'], r['conflict']), ('metal', 0.05, 0.8, False))
        r = pc.classify('a/rockwall', use(), rules, jev)                               # overrides Jev: class values
        self.assertEqual((r['class'], r['roughness'], r['metallic'], r['conflict']), ('wood', 0.6, 0.0, False))

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


class VisionTest(unittest.TestCase):
    def test_numbered_answers_map_to_names(self):
        got = {'1': {'class': 'stone', 'confidence': 'high', 'why': 'rock'}, '2': {'class': 'plastic'},
               '3': {'class': 'Glass', 'confidence': 'sure'}, '9': {'class': 'wood'}}
        self.assertEqual(pc.vision_validate(got, ['a/x', 'a/y', 'a/z'], RULES['classes']),
                         {'a/x': {'class': 'stone', 'confidence': 'high', 'why': 'rock'},
                          'a/z': {'class': 'glass', 'confidence': 'low', 'why': ''}})

    def test_prompt_lists_numbers_and_classes(self):
        p = pc.dsv_prompt(RULES, ['a/x | 5 | 1 | 0 | 0 | -', 'a/y | 2 | 1 | 0 | 0 | -'])
        self.assertIn('\n1: a/x | 5', p)
        self.assertIn('\n2: a/y | 2', p)
        self.assertIn('- polished: ', p)

    def test_image_is_a_data_url_and_key_only_a_header(self):
        import io, json
        sent = {}
        def fake(req, timeout=0):
            sent['body'] = json.loads(req.data); sent['headers'] = dict(req.header_items()); sent['url'] = req.full_url
            return io.BytesIO(json.dumps({'usage': {'prompt_tokens': 3}, 'choices': [
                {'message': {'content': '{"1": {"class": "metal"}}'}}]}).encode())
        orig = pc.urllib.request.urlopen
        pc.urllib.request.urlopen = fake
        try:
            got, u = pc.ds_ask('SECRET', 'prompt', lambda u: None, b'\x89PNG')
        finally:
            pc.urllib.request.urlopen = orig
        self.assertEqual(got, {'1': {'class': 'metal'}})
        msg = sent['body']['messages'][0]['content']
        self.assertEqual(sent['body']['model'], 'deepseek-flash')
        self.assertEqual(msg[0]['image_url']['url'], 'data:image/png;base64,iVBORw==')
        self.assertEqual(msg[1], {'type': 'text', 'text': 'prompt'})
        self.assertNotIn('SECRET', json.dumps(sent['body']) + sent['url'])
        self.assertEqual(sent['headers']['Authorization'], 'Bearer SECRET')

    def test_pick_sets(self):
        jev = lambda m: {'material': m, 'roughness': 0.5, 'metal': 0.0, 'material_conf': 1.0}
        u = {'a/rockwall': use(5), 'a/pipewall': use(50), 'a/xyz': use(7), 'a/abc': use(70), 'a/sky': use(9, pc.SURF['SKY']),
             'a/noimage': use(99)}
        j = {'a/rockwall': jev('stone'), 'a/pipewall': jev('wood'), 'a/xyz': jev('metal')}
        res = {n: pc.classify(n, v, RULES, j) for n, v in u.items()}
        files = {n: n for n in u if n != 'a/noimage'}
        pick = lambda p: pc.vision_pick(res, u, RULES, files, p)
        self.assertEqual(pick('calib'), ['a/rockwall'])
        self.assertEqual(pick('conflicts'), ['a/pipewall'])
        self.assertEqual(pick('unclassified'), ['a/abc', 'a/xyz'])
        self.assertEqual(pick('unclassified:1,top:2'), ['a/abc', 'a/pipewall', 'a/xyz'])   # N new ones per set
        self.assertEqual(sorted(pick('jev')), ['a/pipewall', 'a/rockwall', 'a/xyz'])

    def test_rule_and_image_outvote_jev(self):
        jev = {'a/rockwall': {'material': 'metal', 'roughness': 0.5, 'metal': 0.7, 'material_conf': 1.0}}
        vis = lambda c, conf: {'a/rockwall': {'class': c, 'confidence': conf}}
        r = pc.classify('a/rockwall', use(), RULES, jev, vision=vis('stone', 'high'))
        self.assertEqual((r['class'], r['source'], r['metallic'], r['conflict']), ('stone', 'rule+vision', 0.0, False))
        for v in (vis('stone', 'medium'), vis('metal', 'high'), vis('light', 'high'), vis('default', 'high')):
            r = pc.classify('a/rockwall', use(), RULES, jev, vision=v)
            self.assertEqual((r['class'], r['source'], r['conflict']), ('metal', 'jev', True), v)
        # a weak (non-high) rule never outvotes Jev
        jev = {'a/tpipewall': {'material': 'wood', 'roughness': 0.5, 'metal': 0.0, 'material_conf': 1.0}}
        r = pc.classify('a/tpipewall', use(), RULES, jev, vision={'a/tpipewall': {'class': 'metal', 'confidence': 'high'}})
        self.assertEqual(r['source'], 'jev')

    def test_image_before_text_model_for_unnamed(self):
        r = pc.classify('a/xyz', use(), RULES, ai={'a/xyz': {'class': 'wood', 'confidence': 'high'}},
                        vision={'a/xyz': {'class': 'stone', 'confidence': 'high'}})
        self.assertEqual((r['class'], r['source'], r['confidence']), ('stone', 'vision', 'medium'))
        self.assertTrue(pc.uncertain(r))

    def test_vision_answer_recorded(self):
        r = pc.classify('a/xyz', use(), RULES, vision={'a/xyz': {'class': 'metal', 'confidence': 'high', 'why': 'w'}})
        self.assertEqual(r['vision'], {'class': 'metal', 'confidence': 'high', 'why': 'w'})
        self.assertNotIn('vision', pc.classify('a/xyz', use(), RULES, vision={'a/xyz': {'class': 'plastic'}}))


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
